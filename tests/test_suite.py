import unittest
from test_app import TestApp
from test_ensembl_client import TestEnsemblRestClient
from test_annotate_variants import TestAnnotateVariants

print("Running test suite...")  # Add this line to see if the script runs

# Create a test suite combining different test cases
def suite():
    suite = unittest.TestSuite()

    # Add test cases from test_app.py
    suite.addTest(unittest.makeSuite(TestApp))
    
    # Add test cases from test_ensembl_client.py
    suite.addTest(unittest.makeSuite(TestEnsemblRestClient))

    # Add test cases from test_annotate_variants.py
    suite.addTest(unittest.makeSuite(TestAnnotateVariants))

    return suite

if __name__ == '__main__':
    print("Starting the test runner...")  # Add this line to check if the runner starts
    # Run the test suite
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite())
