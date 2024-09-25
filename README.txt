VarAnnotator
============

VarAnnotator is a pipeline for annotating genetic variants from VCF files using Ensembl's REST API. It provides a Flask-based API to access the annotated variants and allows filtering based on population frequency and depth (DP).

Table of Contents
-----------------

- Features
- Installation
- Usage
  - Running the Annotation Pipeline
  - Starting the Flask API
- API Endpoints
- Testing the API
- Project Structure
- Dependencies
- License

Features
--------

- Annotate variants from VCF files using Ensembl's REST API.
- Retrieve annotated variants via a RESTful API.
- Filter variants based on population frequency and depth (DP).
- Pagination support for large datasets.

Installation
------------

1. Clone the Repository:

   git clone https://github.com/tmbogus/VarAnnotator.git
   cd VarAnnotator

2. Create a Virtual Environment:

   python3 -m venv venv
   source venv/bin/activate

3. Install Dependencies:

   pip install -r requirements.txt

Usage
-----

Running the Annotation Pipeline
-------------------------------

The pipeline uses Snakemake to process VCF files and generate annotated variant files.

1. Prepare Your VCF File:

   Place your VCF file in the 'input' directory.

2. Run the Pipeline:

   snakemake --cores 4

   This will execute the 'Snakefile', which runs the 'annotate_variants_ensembl.py' script and generates the annotated variants in 'output/annotated_variants.tsv'.

Starting the Flask API
----------------------

1. Ensure the Annotated Variants File Exists:

   Verify that 'output/annotated_variants.tsv' is present after running the pipeline.

2. Run the Flask Application:

   python app.py

   The API will be available at 'http://localhost:5000/'.

API Endpoints
-------------

For detailed information about the API endpoints, parameters, and examples, please refer to the 'API_DOCUMENTATION.txt' file.

Testing the API
---------------

You can test the API using 'curl' commands or tools like Postman.

Examples:

- Retrieve all variants:

  curl "http://localhost:5000/variants"

- Retrieve variants with frequency ≤ 0.01:

  curl "http://localhost:5000/variants?frequency=0.01"

- Retrieve variants with depth ≥ 10:

  curl "http://localhost:5000/variants?depth=10"

- Retrieve a specific variant by ID:

  curl "http://localhost:5000/variants/rs576317820"

Project Structure
-----------------

VarAnnotator/
├── app.py
├── requirements.txt
├── README.txt
├── API_DOCUMENTATION.txt
├── input/
│   └── your_input.vcf
├── output/
│   └── annotated_variants.tsv
├── scripts/
│   ├── annotate_variants_ensembl.py
│   └── ensembl_client.py
├── Snakefile
└── logs/

- 'app.py': The Flask application serving the API.
- 'scripts/': Contains the scripts for annotating variants.
- 'input/': Directory for input VCF files.
- 'output/': Directory where annotated variants are stored.
- 'Snakefile': Defines the Snakemake workflow.
- 'logs/': Directory for log files.

Dependencies
------------

Key dependencies are listed below. For a complete list, see 'requirements.txt'.

- Flask: Web framework for the API.
- pandas: Data manipulation and analysis.
- requests: HTTP library for Python.
- Snakemake: Workflow management system.

Install them using:

pip install -r requirements.txt

License
-------

This project is licensed under the Apache License Version 2.0. See the 'LICENSE' file for details.

