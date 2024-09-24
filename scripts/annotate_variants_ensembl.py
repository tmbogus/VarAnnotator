#!/usr/bin/env python3

import sys
import csv
import logging
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from cyvcf2 import VCF
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import traceback

sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts'))

from ensembl_client import EnsemblRestClient  # Import the EnsemblRestClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Helper function to log the API call type and time
def log_api_time(api_type, duration, output_log="api_times_log.tsv"):
    """Log the API call type and duration to a TSV file."""
    with threading.Lock():
        with open(output_log, 'a', newline='') as log_file:
            writer = csv.writer(log_file, delimiter='\t')
            writer.writerow([api_type, f"{duration:.4f}"])

# Initialize Ensembl REST client
client = EnsemblRestClient(server='http://grch37.rest.ensembl.org', reqs_per_sec=15)

def fetch_dbsnp_version():
    """Fetch dbSNP version from NCBI release notes with retry mechanism."""
    release_notes_url = "https://ftp.ncbi.nlm.nih.gov/snp/latest_release/release_notes.txt"

    session = requests.Session()
    retries = Retry(
        total=5,  # Total number of retries
        backoff_factor=1,  # Wait 1s * (2 ^ (retry number)) between retries
        status_forcelist=[429, 500, 502, 503, 504],  # Retry on these HTTP status codes
        allowed_methods=['HEAD', 'GET', 'OPTIONS']  # Retry on these HTTP methods
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    try:
        logging.info("Fetching dbSNP version from NCBI release notes...")
        response = session.get(release_notes_url, timeout=10)
        response.raise_for_status()  # Raise an exception for HTTP errors
        for line in response.text.splitlines():
            if line.startswith("dbSNP build"):
                version = line.split()[2]  # Extract the version number (e.g., '156')
                logging.info(f"Fetched dbSNP version: {version}")
                return version
        logging.warning("dbSNP version not found in release notes.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching dbSNP version after retries: {e}")
    return "Unknown"

def normalize_alleles(ref, alt):
    """
    Normalize alleles by removing common prefix and suffix nucleotides.
    Return minimal REF and ALT alleles.
    """
    # Convert to uppercase
    ref = ref.upper()
    alt = alt.upper()

    # Remove common suffix
    while len(ref) > 1 and len(alt) > 1 and ref[-1] == alt[-1]:
        ref = ref[:-1]
        alt = alt[:-1]

    # Remove common prefix
    while len(ref) > 1 and len(alt) > 1 and ref[0] == alt[0]:
        ref = ref[1:]
        alt = alt[1:]

    return ref, alt

def complement_allele(allele):
    """Return the complement of the given DNA sequence."""
    complement = str.maketrans('ACGT-', 'TGCA-')
    return allele.translate(complement)

def fetch_vep_batch(batch_variants):
    payload = {"variants": batch_variants}
    start_time = time.time()
    vep_responses = client.perform_rest_action(
        f"/vep/human/region",
        method='POST',
        data=payload,
        hdrs={'Content-Type': 'application/json', 'Accept': 'application/json'},
        retries=5  # Increase retries if necessary
    )
    duration = time.time() - start_time
    log_api_time("fetch_vep_annotations", duration)
    return vep_responses

def fetch_population_frequencies_batch(batch_dbsnp_ids):
    payload = {"ids": batch_dbsnp_ids}
    start_time = time.time()
    responses = client.perform_rest_action(
        f"/variation/human",
        method='POST',
        data=payload,
        params={'pops': '1'},
        hdrs={'Content-Type': 'application/json', 'Accept': 'application/json'},
        retries=5  # Increase retries if necessary
    )
    duration = time.time() - start_time
    log_api_time("fetch_population_frequencies", duration)
    return responses

def process_vcf(input_vcf, output_file):
    """Process the VCF file and annotate each variant using Ensembl VEP and population frequency data."""
    # Fetch dbSNP version
    dbsnp_version = fetch_dbsnp_version()
    logging.info(f"Using dbSNP version: {dbsnp_version} (Ensembl GRCh37)")

    # Read input VCF file using cyvcf2
    vcf_reader = VCF(input_vcf)

    # Prepare output file
    with open(output_file, 'w', newline='') as csvfile:
        # Write dbSNP version as the first line (header comment)
        csvfile.write(f"# dbSNP version: {dbsnp_version}\n")
        fieldnames = ['CHROM', 'POS', 'ID', 'REF', 'ALT', 'Gene', 'Frequency', 'DP']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter='\t')
        writer.writeheader()

        records = []
        vep_variants = []
        record_map = {}

        # Collect variants from VCF
        for idx, record in enumerate(vcf_reader):
            chrom = record.CHROM
            pos = record.POS
            ref = record.REF
            alt = record.ALT[0]

            # Construct VEP input in VCF format
            vep_input = f"{chrom} {pos} . {ref} {alt} . . ."
            vep_variants.append(vep_input)
            record_map[vep_input] = idx
            records.append(record)

        num_records = len(records)
        # Initialize lists with placeholders
        all_dbsnp_ids = ['.'] * num_records
        all_gene_annotations = ['Intergenic'] * num_records
        alt_alleles = [record.ALT[0] for record in records]

        # Process VEP variants in parallel
        batch_size = 200
        vep_batches = []
        for i in range(0, len(vep_variants), batch_size):
            batch_variants = vep_variants[i:i + batch_size]
            vep_batches.append(batch_variants)

        logging.info(f"Processing {len(vep_batches)} VEP batches in parallel")

        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_batch = {
                executor.submit(fetch_vep_batch, batch_variants): batch_variants
                for batch_variants in vep_batches
            }

            for future in as_completed(future_to_batch):
                batch_variants = future_to_batch[future]
                try:
                    vep_responses = future.result()
                    if not vep_responses:
                        logging.error("No response from VEP for a batch")
                        continue
                    # Process VEP responses
                    for response in vep_responses:
                        input_str = response.get('input')
                        idx = record_map.get(input_str)
                        if idx is None:
                            continue  # Should not happen

                        # Extract dbSNP ID
                        dbsnp_id = None
                        colocated_variants = response.get('colocated_variants', [])
                        for var in colocated_variants:
                            var_id = var.get('id')
                            if var_id and var_id.startswith('rs'):
                                dbsnp_id = var_id
                                break
                        if not dbsnp_id:
                            dbsnp_id = '.'

                        all_dbsnp_ids[idx] = dbsnp_id

                        # Extract gene annotation
                        gene_annotation = "Intergenic"
                        transcripts = response.get('transcript_consequences', [])
                        if transcripts:
                            for tx in transcripts:
                                gene_symbol = tx.get('gene_symbol')
                                if gene_symbol:
                                    gene_annotation = gene_symbol
                                    break

                        all_gene_annotations[idx] = gene_annotation

                except Exception as e:
                    logging.error(f"Error processing VEP batch: {e}")
                    logging.debug(traceback.format_exc())

        # Fetch population frequencies in batches
        frequencies = {}
        target_populations = ["gnomADe:NFE", "gnomADg:NFE", "1000GENOMES:phase_3:CEU"]
        batch_size = 200  # Maximum batch size for variation POST requests

        # Prepare list of indices for variants with dbSNP IDs
        dbsnp_indices = [idx for idx, dbsnp_id in enumerate(all_dbsnp_ids) if dbsnp_id != '.']
        variation_batches = []
        for i in range(0, len(dbsnp_indices), batch_size):
            batch_indices = dbsnp_indices[i:i + batch_size]
            batch_dbsnp_ids = [all_dbsnp_ids[idx] for idx in batch_indices]
            batch_alt_alleles = [alt_alleles[idx] for idx in batch_indices]
            batch_ref_alleles = [records[idx].REF for idx in batch_indices]
            variation_batches.append((batch_dbsnp_ids, batch_alt_alleles, batch_ref_alleles, batch_indices))

        logging.info(f"Processing {len(variation_batches)} variation batches in parallel")

        frequencies_lock = threading.Lock()

        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_batch = {
                executor.submit(fetch_population_frequencies_batch, batch_dbsnp_ids): (batch_dbsnp_ids, batch_alt_alleles, batch_ref_alleles, batch_indices)
                for batch_dbsnp_ids, batch_alt_alleles, batch_ref_alleles, batch_indices in variation_batches
            }

            for future in as_completed(future_to_batch):
                batch_info = future_to_batch[future]
                batch_dbsnp_ids, batch_alt_alleles, batch_ref_alleles, batch_indices = batch_info
                try:
                    responses = future.result()
                    if not responses:
                        logging.error("No response from variation endpoint for a batch")
                        continue
                    # Process responses
                    for idx_in_batch, dbsnp_id in enumerate(batch_dbsnp_ids):
                        idx = batch_indices[idx_in_batch]
                        alt_allele = batch_alt_alleles[idx_in_batch]
                        ref_allele = batch_ref_alleles[idx_in_batch]

                        # Normalize alleles
                        norm_ref, norm_alt = normalize_alleles(ref_allele, alt_allele)
                        if norm_alt == '':
                            norm_alt = '-'

                        # Generate possible allele representations
                        alleles_to_check = set([norm_alt, complement_allele(norm_alt)])
                        logging.debug(f"Variant {dbsnp_id}: alleles to check {alleles_to_check}")

                        variant_info = responses.get(dbsnp_id)
                        frequency = "N/A"

                        if variant_info and 'populations' in variant_info:
                            highest_maf = None
                            highest_population = None
                            for population in variant_info['populations']:
                                freq = population.get('frequency')
                                pop_name = population.get('population')
                                allele = population.get('allele')
                                allele = allele.upper()
                                allele = allele if allele != '-' else '-'

                                if freq is not None and allele in alleles_to_check:
                                    if target_populations and any(pop in pop_name for pop in target_populations):
                                        if highest_maf is None or freq > highest_maf:
                                            highest_maf = freq
                                            highest_population = pop_name
                                    elif not target_populations:
                                        if highest_maf is None or freq > highest_maf:
                                            highest_maf = freq
                                            highest_population = pop_name
                            # If no frequency found in target populations, check all populations
                            if highest_maf is None:
                                for population in variant_info['populations']:
                                    freq = population.get('frequency')
                                    pop_name = population.get('population')
                                    allele = population.get('allele')
                                    allele = allele.upper()
                                    allele = allele if allele != '-' else '-'

                                    if freq is not None and allele in alleles_to_check:
                                        if highest_maf is None or freq > highest_maf:
                                            highest_maf = freq
                                            highest_population = pop_name
                            if highest_maf is not None:
                                frequency = f"{highest_maf:.5f} (Population: {highest_population})"
                            else:
                                logging.debug(f"No frequency found for variant {dbsnp_id} with allele(s) {alleles_to_check}")
                        else:
                            logging.debug(f"No population data for variant {dbsnp_id}")

                        with frequencies_lock:
                            frequencies[dbsnp_id] = frequency

                except Exception as e:
                    logging.error(f"Error processing variation batch: {e}")
                    logging.debug(traceback.format_exc())

        # Write results to output file
        for idx, record in enumerate(records):
            dbsnp_id = all_dbsnp_ids[idx]
            gene_annotation = all_gene_annotations[idx]
            alt_allele = record.ALT[0]
            frequency = frequencies.get(dbsnp_id, "N/A") if dbsnp_id != '.' else "N/A"

            writer.writerow({
                'CHROM': record.CHROM,
                'POS': record.POS,
                'ID': dbsnp_id,
                'REF': record.REF,
                'ALT': alt_allele,
                'Gene': gene_annotation,
                'Frequency': frequency,
                'DP': record.format('DP')[0] if 'DP' in record.FORMAT else 'NA'
            })

    logging.info(f"Variant annotation completed. Output saved to: {output_file}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        logging.error("Usage: python annotate_variants.py <input_vcf> <output_tsv>")
        sys.exit(1)

    input_vcf = sys.argv[1]
    output_tsv = sys.argv[2]

    process_vcf(input_vcf, output_tsv)
