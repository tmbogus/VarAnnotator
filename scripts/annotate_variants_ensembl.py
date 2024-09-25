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
import argparse
import random
import re

from ensembl_client import EnsemblRestClient  # Ensure this file is in the same directory or PYTHONPATH

# ================================
# Logging Configuration
# ================================

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Console handler for general logs (INFO and above)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(ch)

# File handler for detailed logs (DEBUG and above)
fh = logging.FileHandler('detailed_logs.log')
fh.setLevel(logging.DEBUG)
fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(fh)

# ================================
# Failed Batches Tracking
# ================================

# List to store failed batches with their attempt counts
failed_batches = []
failed_batches_lock = threading.Lock()

# ================================
# Helper Functions
# ================================

def log_api_time(api_type, duration, output_log="api_times_log.tsv"):
    """Log the duration of API calls."""
    try:
        with open(output_log, 'a', newline='') as log_file:
            writer = csv.writer(log_file, delimiter='\t')
            writer.writerow([api_type, f"{duration:.4f}"])
    except Exception as e:
        logger.error(f"Failed to write to API times log: {e}")

def parse_arguments():
    parser = argparse.ArgumentParser(description="Annotate VCF variants using Ensembl VEP and population frequencies.")
    parser.add_argument('input_vcf', help='Path to input VCF file')
    parser.add_argument('output_tsv', help='Path to output TSV file')
    parser.add_argument('--batch_size', type=int, default=25, help='Number of variants per API request (default: 25)')
    parser.add_argument('--max_workers', type=int, default=15, help='Number of worker threads for parallel processing (default: 15)')
    parser.add_argument('--reqs_per_sec', type=int, default=15, help='API requests per second (default: 15)')
    parser.add_argument('--target_populations', nargs='*', default=["gnomADe:NFE", "gnomADg:NFE", "1000GENOMES:phase_3:CEU"],
                        help='Target populations for frequency data')
    return parser.parse_args()

def is_valid_rsid(rsid):
    """Validate the format of an rsID."""
    return bool(re.match(r'^rs\d+$', rsid))

def normalize_alleles(ref, alt):
    """Normalize alleles by removing common prefix and suffix nucleotides."""
    ref = ref.upper()
    alt = alt.upper()

    while len(ref) > 1 and len(alt) > 1 and ref[-1] == alt[-1]:
        ref = ref[:-1]
        alt = alt[:-1]

    while len(ref) > 1 and len(alt) > 1 and ref[0] == alt[0]:
        ref = ref[1:]
        alt = alt[1:]

    logger.debug(f"Normalized alleles - REF: {ref}, ALT: {alt}")
    return ref, alt

def complement_allele(allele):
    """Return the complement of the given DNA sequence."""
    complement = str.maketrans('ACGT-', 'TGCA-')
    complemented = allele.translate(complement)
    logger.debug(f"Complemented allele: {allele} -> {complemented}")
    return complemented

def truncate_text(text, max_length=500):
    """Truncate text to a maximum length with an ellipsis if needed."""
    if len(text) <= max_length:
        return text
    else:
        return text[:max_length] + '... [truncated]'

# ================================
# Ensembl REST Client Initialization
# ================================

def initialize_client(reqs_per_sec):
    """Initialize Ensembl REST client with specified rate limit."""
    client = EnsemblRestClient(server='http://grch37.rest.ensembl.org', reqs_per_sec=reqs_per_sec)
    return client

# ================================
# Error Checking and Retry Mechanism
# ================================

def fetch_population_frequencies_batch(batch_dbsnp_ids, batch_number, client):
    """
    Fetch population frequencies for a batch of dbSNP IDs.
    Relies on built-in API limitations and retries until a successful response is received.

    Args:
        batch_dbsnp_ids (list): List of rsIDs.
        batch_number (str): Identifier for the batch (e.g., '15').
        client (EnsemblRestClient): The REST client instance.

    Returns:
        dict: Aggregated frequency data for the batch.
    """
    payload = {"ids": batch_dbsnp_ids}
    payload_str = json.dumps(payload)
    truncated_payload = truncate_text(payload_str)
    logger.debug(f"Batch {batch_number} payload for Population Frequencies: {truncated_payload}")

    while True:
        try:
            start_time = time.time()
            response = client.perform_rest_action(
                "/variation/human",
                method='POST',
                data=payload,
                params={'pops': '1'},
                hdrs={'Content-Type': 'application/json', 'Accept': 'application/json'}
            )
            duration = time.time() - start_time
            log_api_time("fetch_population_frequencies", duration)

            if response is None or response == {}:
                logger.error(f"Empty response for batch {batch_number}. Retrying...")
                continue

            logger.debug(f"Received response for batch {batch_number}: {truncate_text(json.dumps(response), 1000)}")
            return response

        except Exception as e:
            logger.error(f"Exception during API call for batch {batch_number}: {e}")
            logger.debug(traceback.format_exc())
            continue  # Retry on exception

# ================================
# Original Functions (Unchanged)
# ================================

def fetch_dbsnp_version():
    """Fetch dbSNP version from NCBI release notes with retry mechanism."""
    release_notes_url = "https://ftp.ncbi.nlm.nih.gov/snp/latest_release/release_notes.txt"

    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=['HEAD', 'GET', 'OPTIONS']
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    try:
        logger.info("Fetching dbSNP version from NCBI release notes...")
        response = session.get(release_notes_url, timeout=10)
        response.raise_for_status()
        for line in response.text.splitlines():
            if line.startswith("dbSNP build"):
                version = line.split()[2]  # Extract the version number (e.g., '156')
                logger.info(f"Fetched dbSNP version: {version}")
                return version
        logger.warning("dbSNP version not found in release notes.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching dbSNP version after retries: {e}")
    return "Unknown"

def fetch_vep_batch(batch_variants, batch_number, client):
    """Fetch VEP annotations for a batch of variants."""
    payload = {"variants": batch_variants}
    payload_str = json.dumps(payload)
    truncated_payload = truncate_text(payload_str)
    logger.debug(f"Batch {batch_number} payload for VEP: {truncated_payload}")
    start_time = time.time()
    try:
        vep_responses = client.perform_rest_action(
            "/vep/human/region",
            method='POST',
            data=payload,
            hdrs={'Content-Type': 'application/json', 'Accept': 'application/json'},
            retries=5
        )
        duration = time.time() - start_time
        log_api_time("fetch_vep_annotations", duration)
    except Exception as e:
        logger.error(f"Exception during VEP API call for batch {batch_number}: {e}")
        vep_responses = []
    return vep_responses

# ================================
# Main Processing Function
# ================================

def process_vcf(input_vcf, output_file, batch_size, max_workers, client, target_populations):
    """Process the VCF file and annotate each variant using Ensembl VEP and population frequency data."""
    # Fetch dbSNP version
    dbsnp_version = fetch_dbsnp_version()
    logger.info(f"Using dbSNP version: {dbsnp_version} (Ensembl GRCh37)")

    # Read input VCF file using cyvcf2
    try:
        vcf_reader = VCF(input_vcf)
    except Exception as e:
        logger.critical(f"Failed to read input VCF file '{input_vcf}': {e}")
        sys.exit(1)

    # Collect variants from VCF
    records = []
    vep_variants = []
    record_map = {}

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
    logger.info(f"Total variants to process: {num_records}")

    # Initialize lists with placeholders
    all_dbsnp_ids = ['.'] * num_records
    all_gene_annotations = ['Intergenic'] * num_records
    alt_alleles = [record.ALT[0] for record in records]

    # Process VEP variants in parallel
    vep_batches = []
    for i in range(0, len(vep_variants), batch_size):
        batch_variants = vep_variants[i:i + batch_size]
        batch_number = str((i // batch_size) + 1)
        vep_batches.append((batch_variants, batch_number))

    logger.info(f"Processing {len(vep_batches)} VEP batches in parallel with batch size {batch_size}")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_batch = {
            executor.submit(fetch_vep_batch, batch_variants, batch_number, client): (batch_variants, batch_number)
            for batch_variants, batch_number in vep_batches
        }

        for future in as_completed(future_to_batch):
            batch_variants, batch_number = future_to_batch[future]
            try:
                vep_responses = future.result()
                if not vep_responses:
                    logger.error(f"No response from VEP for batch {batch_number}. Variants: {truncate_text(json.dumps(batch_variants))}")
                    continue
                # Process VEP responses
                for response in vep_responses:
                    input_str = response.get('input')
                    idx = record_map.get(input_str)
                    if idx is None:
                        logger.warning(f"Variant input '{input_str}' not found in record_map.")
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
                logger.error(f"Error processing VEP batch {batch_number}: {e}")
                logger.debug(traceback.format_exc())

    # Fetch population frequencies in batches
    frequencies = {}
    batch_size_freq = batch_size  # Can adjust separately if needed

    # Prepare list of indices for variants with dbSNP IDs
    dbsnp_indices = [idx for idx, dbsnp_id in enumerate(all_dbsnp_ids) if dbsnp_id != '.']
    variation_batches = []
    for i in range(0, len(dbsnp_indices), batch_size_freq):
        batch_indices = dbsnp_indices[i:i + batch_size_freq]
        batch_number = str((i // batch_size_freq) + 1)
        batch_dbsnp_ids = [all_dbsnp_ids[idx] for idx in batch_indices]
        variation_batches.append((batch_dbsnp_ids, batch_number))

    logger.info(f"Processing {len(variation_batches)} variation batches in parallel with batch size {batch_size_freq}")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_batch = {
            executor.submit(fetch_population_frequencies_batch, batch_dbsnp_ids, batch_number, client): (batch_dbsnp_ids, batch_number)
            for batch_dbsnp_ids, batch_number in variation_batches
        }

        for future in as_completed(future_to_batch):
            batch_dbsnp_ids, batch_number = future_to_batch[future]
            try:
                responses = future.result()
                if not responses:
                    logger.error(f"No response from variation endpoint for batch {batch_number}. Variants: {truncate_text(json.dumps(batch_dbsnp_ids))}")
                    continue
                # Process responses
                for dbsnp_id in batch_dbsnp_ids:
                    variant_data = responses.get(dbsnp_id, {})
                    if not variant_data or variant_data == "N/A":
                        frequencies[dbsnp_id] = "N/A"
                        continue
                    populations = variant_data.get('populations', [])
                    max_freq = None
                    max_population = None
                    for pop in populations:
                        population_name = pop.get('population')
                        freq = pop.get('frequency')
                        if population_name in target_populations and freq is not None:
                            if max_freq is None or freq > max_freq:
                                max_freq = freq
                                max_population = population_name
                    if max_freq is not None:
                        frequencies[dbsnp_id] = f"{max_freq} ({max_population})"
                    else:
                        frequencies[dbsnp_id] = "N/A"

            except Exception as e:
                logger.error(f"Error processing variation batch {batch_number}: {e}")
                logger.debug(traceback.format_exc())

    # Write results to output file
    try:
        with open(output_file, 'w', newline='') as csvfile:
            # Write dbSNP version as the first line (header comment)
            csvfile.write(f"# dbSNP version: {dbsnp_version}\n")
            fieldnames = ['CHROM', 'POS', 'ID', 'REF', 'ALT', 'Gene', 'Frequency', 'DP']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter='\t')
            writer.writeheader()

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
    except Exception as e:
        logger.critical(f"Failed to write to output file '{output_file}': {e}")
        sys.exit(1)

    logger.info(f"Variant annotation completed. Output saved to: {output_file}")

    # ================================
    # Summary of Critically Failed Batches
    # ================================

    if failed_batches:
        logger.info("Summary of Critically Failed Batches:")
        for failed_batch in failed_batches:
            logger.info(f"Batch {failed_batch['batch_number']} failed after {failed_batch['attempts']} attempts.")
    else:
        logger.info("All batches processed successfully without critical failures.")

# ================================
# Main Execution
# ================================

def main():
    args = parse_arguments()
    client = initialize_client(args.reqs_per_sec)
    try:
        process_vcf(
            input_vcf=args.input_vcf,
            output_file=args.output_tsv,
            batch_size=args.batch_size,
            max_workers=args.max_workers,
            client=client,
            target_populations=args.target_populations
        )
    except Exception as e:
        logger.critical(f"An unexpected error occurred: {e}")
        logger.debug(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        logger.error("Usage: python annotate_variants_ensembl.py <input_vcf> <output_tsv> [--batch_size N] [--max_workers M] [--reqs_per_sec R]")
        sys.exit(1)
    main()
