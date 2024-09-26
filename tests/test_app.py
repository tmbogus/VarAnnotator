# test_app.py

import unittest
from unittest.mock import patch
import pandas as pd
from app import app, load_variants, validate_query_param

class TestApp(unittest.TestCase):

    def setUp(self):
        # Create a test client for the Flask app
        self.client = app.test_client()

    @patch('app.pd.read_csv')
    def test_load_variants_no_file(self, mock_read_csv):
        # Simulate file not found scenario
        mock_read_csv.side_effect = FileNotFoundError
        df = load_variants('non_existent_file.tsv')
        self.assertTrue(df.empty)

    @patch('app.pd.read_csv')
    @patch('app.os.path.exists')
    def test_load_variants_valid_file(self, mock_exists, mock_read_csv):
        # Mock 'os.path.exists' to return True for 'test_file.tsv'
        mock_exists.return_value = True

        # Mock 'pd.read_csv' to return the desired DataFrame
        mock_read_csv.return_value = pd.DataFrame({
            'ID': ['rs1', 'rs2'],
            'Gene': ['GENE1', 'GENE2'],
            'Frequency': ['0.1 (Population: EUR)', '0.2 (Population: AFR)'],
            'DP': ['10', '20']
        })

        # Call the function under test
        df = load_variants('test_file.tsv')

        # Assertions to verify correct behavior
        self.assertEqual(len(df), 2)
        self.assertIn('ID', df.columns)
        self.assertIn('Gene', df.columns)
        self.assertIn('Frequency', df.columns)
        self.assertIn('DP', df.columns)
        self.assertListEqual(df['ID'].tolist(), ['rs1', 'rs2'])

    def test_validate_query_param_valid(self):
        # Test valid parameter
        param = validate_query_param('0.5', 'frequency', float, min_value=0.0, max_value=1.0)
        self.assertEqual(param, 0.5)

    def test_validate_query_param_invalid(self):
        # Test invalid parameter (out of range)
        with self.assertRaises(ValueError):
            validate_query_param('1.5', 'frequency', float, min_value=0.0, max_value=1.0)

    @patch('app.load_variants')
    def test_variants_endpoint(self, mock_load_variants):
        # Mock the DataFrame returned by load_variants
        mock_load_variants.return_value = pd.DataFrame({
            'ID': ['rs1'],
            'Gene': ['GENE1'],
            'Frequency': [0.1],
            'DP': [10]
        })

        response = self.client.get('/variants?frequency=0.1&depth=10')
        self.assertEqual(response.status_code, 200)
        response_json = response.get_json()
        self.assertIn('rs1', [variant['ID'] for variant in response_json['variants']])
        self.assertEqual(len(response_json['variants']), 1)
        self.assertEqual(response_json['variants'][0]['ID'], 'rs1')

    @patch('app.load_variants')
    def test_variants_endpoint_no_data(self, mock_load_variants):
        # Mock load_variants to return an empty DataFrame
        mock_load_variants.return_value = pd.DataFrame()

        # Mock the status file indicating completion
        with patch('app.os.path.exists') as mock_exists, \
             patch('builtins.open', unittest.mock.mock_open(read_data='{"status": "completed", "message": "Pipeline completed."}')):
            mock_exists.side_effect = lambda path: path == "output/pipeline_status.json" or path == "output/annotated_variants.tsv"

            response = self.client.get('/variants?frequency=0.1&depth=10')
            self.assertEqual(response.status_code, 503)
            response_json = response.get_json()
            self.assertIn('Pipeline has completed but no data found.', response_json['message'])

    @patch('app.load_variants')
    def test_variants_endpoint_pipeline_not_run(self, mock_load_variants):
        # Mock load_variants to return an empty DataFrame
        mock_load_variants.return_value = pd.DataFrame()

        # Mock the absence of the status file and variants file
        with patch('app.os.path.exists') as mock_exists:
            # Return False for both status and variants file
            mock_exists.side_effect = lambda path: False

            response = self.client.get('/variants?frequency=0.1&depth=10')
            self.assertEqual(response.status_code, 503)
            response_json = response.get_json()
            self.assertIn('Pipeline has not been run yet.', response_json['message'])

    @patch('app.load_variants')
    def test_variants_endpoint_invalid_sort(self, mock_load_variants):
        # Mock the DataFrame returned by load_variants
        mock_load_variants.return_value = pd.DataFrame({
            'ID': ['rs1', 'rs2'],
            'Gene': ['GENE1', 'GENE2'],
            'Frequency': [0.1, 0.2],
            'Population': ['EUR', 'AFR'],
            'DP': [10, 20]
        })

        # Attempt to sort by an invalid column
        response = self.client.get('/variants?frequency=0.1&depth=10&sort_column=INVALID&sort_order=asc')
        self.assertEqual(response.status_code, 400)
        response_json = response.get_json()
        self.assertIn('Invalid sort_column', response_json['message'])

    @patch('app.load_variants')
    def test_variants_endpoint_invalid_sort_order(self, mock_load_variants):
        # Mock the DataFrame returned by load_variants
        mock_load_variants.return_value = pd.DataFrame({
            'ID': ['rs1', 'rs2'],
            'Gene': ['GENE1', 'GENE2'],
            'Frequency': [0.1, 0.2],
            'Population': ['EUR', 'AFR'],
            'DP': [10, 20]
        })

        # Attempt to use an invalid sort order
        response = self.client.get('/variants?frequency=0.1&depth=10&sort_column=Gene&sort_order=invalid')
        self.assertEqual(response.status_code, 400)
        response_json = response.get_json()
        self.assertIn('Invalid sort_order', response_json['message'])

if __name__ == '__main__':
    unittest.main()
