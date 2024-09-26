import unittest
from unittest.mock import patch, MagicMock
import argparse
from annotate_variants_ensembl import (
    is_valid_rsid, normalize_alleles, complement_allele, truncate_text,
    fetch_population_frequencies_batch, fetch_vep_batch, process_vcf, main
)
from ensembl_client import EnsemblRestClient

class TestAnnotateVariants(unittest.TestCase):

    def setUp(self):
        # Setup common mock client
        self.mock_client = MagicMock(spec=EnsemblRestClient)

    # ------------------------------
    # Helper Functions Tests
    # ------------------------------

    def test_is_valid_rsid(self):
        self.assertTrue(is_valid_rsid('rs12345'))
        self.assertFalse(is_valid_rsid('rsabc'))
        self.assertFalse(is_valid_rsid('12345'))

    def test_normalize_alleles(self):
        ref, alt = normalize_alleles('ACGT', 'ACGA')
        self.assertEqual(ref, 'T')
        self.assertEqual(alt, 'A')

        ref, alt = normalize_alleles('G', 'T')
        self.assertEqual(ref, 'G')
        self.assertEqual(alt, 'T')

    def test_complement_allele(self):
        complemented = complement_allele('ACGT')
        self.assertEqual(complemented, 'TGCA')

    def test_truncate_text(self):
        truncated = truncate_text('This is a test string', 10)
        self.assertEqual(truncated, 'This is a ... [truncated]')

        not_truncated = truncate_text('Short string', 20)
        self.assertEqual(not_truncated, 'Short string')

    # ------------------------------
    # API Interaction Tests
    # ------------------------------

    def test_fetch_population_frequencies_batch(self):
        # Directly set the return value on the mock client
        self.mock_client.perform_rest_action.return_value = {
            'rs123': {
                'populations': [
                    {'population': '1000GENOMES:CEU', 'frequency': 0.1}
                ]
            }
        }

        result = fetch_population_frequencies_batch(['rs123'], '1', self.mock_client)
        self.assertEqual(result['rs123']['populations'][0]['population'], '1000GENOMES:CEU')

    def test_fetch_vep_batch(self):
        # Set up the mock return value
        self.mock_client.perform_rest_action.return_value = [{
            'input': '1 1000 . A T . . .',
            'colocated_variants': [{'id': 'rs12345'}],
            'transcript_consequences': [{'gene_symbol': 'BRCA1'}]
        }]

        result = fetch_vep_batch(['1 1000 . A T . . .'], '1', self.mock_client)
        self.assertEqual(result[0]['colocated_variants'][0]['id'], 'rs12345')
        self.assertEqual(result[0]['transcript_consequences'][0]['gene_symbol'], 'BRCA1')

    # ------------------------------
    # VCF Processing Tests
    # ------------------------------

    @patch('annotate_variants_ensembl.VCF')  # Corrected Patch Target
    @patch('annotate_variants_ensembl.fetch_vep_batch')
    @patch('annotate_variants_ensembl.fetch_population_frequencies_batch')
    def test_process_vcf(self, mock_population_frequencies, mock_vep, mock_vcf):
        # Mock the VCF records
        mock_vcf.return_value = [MagicMock(CHROM='1', POS=1000, REF='A', ALT=['T'], FORMAT={'DP': [10]})]
        
        # Mock the VEP and population responses
        mock_vep.return_value = [{'input': '1 1000 . A T . . .', 'colocated_variants': [{'id': 'rs12345'}]}]
        mock_population_frequencies.return_value = {'rs12345': {'populations': [{'population': '1000GENOMES:CEU', 'frequency': 0.1}]}}

        process_vcf('test.vcf', 'output.tsv', 25, 5, self.mock_client, ['1000GENOMES:CEU'])

        # Check if the output file is written
        with open('output.tsv', 'r') as f:
            content = f.readlines()
            self.assertTrue(any('rs12345' in line for line in content))

    # ------------------------------
    # Main Function Tests
    # ------------------------------

    @patch('annotate_variants_ensembl.parse_arguments')
    @patch('annotate_variants_ensembl.process_vcf')
    def test_main(self, mock_process_vcf, mock_parse_arguments):
        mock_parse_arguments.return_value = argparse.Namespace(
            input_vcf='test.vcf', output_tsv='output.tsv', batch_size=25, max_workers=15, reqs_per_sec=10, target_populations=['1000GENOMES:CEU'])
        
        main()
        mock_process_vcf.assert_called_once()


if __name__ == '__main__':
    unittest.main()
