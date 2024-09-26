# test_ensembl_client.py

import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError
from ensembl_client import EnsemblRestClient

# Subclass HTTPError to allow setting headers without setting 'reason'
class MockHTTPError(HTTPError):
    def __init__(self, code, reason, headers=None):
        super().__init__(
            url='https://rest.ensembl.org/nonexistent-endpoint',
            code=code,
            msg=reason,     # 'reason' is derived from 'msg'
            hdrs=headers,   # Set headers appropriately
            fp=None
        )
        # Do NOT set 'self.reason' manually

class TestEnsemblRestClient(unittest.TestCase):

    def setUp(self):
        # Create an instance of the EnsemblRestClient
        self.client = EnsemblRestClient()

    @patch('ensembl_client.time.sleep', return_value=None)  # Mock sleep
    @patch('ensembl_client.urlopen')
    def test_perform_rest_action_404(self, mock_urlopen, mock_sleep):
        # Create an instance of MockHTTPError for 404
        mock_http_error = MockHTTPError(404, 'Not Found')

        # Configure the mock to raise the HTTPError when entered
        mock_urlopen.return_value.__enter__.side_effect = mock_http_error

        # Assert that HTTPError is raised with correct attributes
        with self.assertRaises(HTTPError) as context:
            self.client.perform_rest_action('/nonexistent-endpoint', method='GET')

        # Verify exception attributes
        self.assertEqual(context.exception.code, 404)
        self.assertEqual(context.exception.reason, 'Not Found')
        self.assertIsInstance(context.exception, HTTPError)

    @patch('ensembl_client.time.sleep', return_value=None)  # Mock sleep
    @patch('ensembl_client.urlopen')
    def test_perform_rest_action_500(self, mock_urlopen, mock_sleep):
        # Create an instance of MockHTTPError for 500 with headers
        mock_http_error = MockHTTPError(500, 'Internal Server Error', headers={'Retry-After': '5'})

        # Configure the mock to raise the HTTPError when entered
        mock_urlopen.return_value.__enter__.side_effect = mock_http_error

        # Assert that HTTPError is raised with correct attributes
        with self.assertRaises(HTTPError) as context:
            self.client.perform_rest_action('/server-error-endpoint', method='GET')

        # Verify exception attributes
        self.assertEqual(context.exception.code, 500)
        self.assertEqual(context.exception.reason, 'Internal Server Error')
        self.assertEqual(context.exception.headers['Retry-After'], '5')

    @patch('ensembl_client.time.sleep', return_value=None)  # Mock sleep
    @patch('ensembl_client.urlopen')
    def test_perform_rest_action_get(self, mock_urlopen, mock_sleep):
        # Mock a successful GET request
        mock_response = MagicMock()
        mock_response.read.return_value = '{"gene": "BRCA1"}'
        mock_response.getcode.return_value = 200

        # Mock the context manager's __enter__ method to return mock_response
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = self.client.perform_rest_action('/some-endpoint', method='GET')
        self.assertEqual(result['gene'], 'BRCA1')

if __name__ == '__main__':
    unittest.main()
