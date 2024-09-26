
# VarAnnotator

VarAnnotator is a bioinformatics pipeline designed to efficiently annotate genetic variants from VCF (Variant Call Format) files. The system fetches gene annotations, population frequencies, and dbSNP IDs, serving results through a RESTful API and an interactive web interface.

## Features

- **VCF Processing:** Parses and processes VCF files, producing variant annotations. Currently only accepts GRCh37.
- **Population Frequency Data:** Retrieves population frequency from databases such as gnomAD and 1000 Genomes.
- **Gene Annotations:** Annotates variants with gene and transcript data using Ensembl’s API (grch37.rest).
- **Error Handling & Retries:** Gracefully handles errors (e.g., HTTP 404, 500) and retries failed API requests with exponential backoff.
- **Web Interface:** Offers a Flask-based API for querying annotated variants.
- **Dockerized:** The project is containerized for easier deployment and execution in isolated environments.

---

## Table of Contents
- [Installation](#installation)
- [Usage](#usage)
  - [Running the Variant Annotation Pipeline](#running-the-variant-annotation-pipeline)
  - [Starting the Web Interface](#starting-the-web-interface)
  - [Running with Docker](#running-with-docker)
- [API Documentation](#api-documentation)
- [Error Handling](#error-handling)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)

---

## Installation

### Prerequisites
- **Python 3.8+**
- **Docker** (for containerized execution)
- **Git**

### Steps

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/tmbogus/VarAnnotator.git
   cd VarAnnotator
   ```

2. **Install Dependencies:**

   You can install dependencies using `pip`:

   ```bash
   pip install -r requirements.txt
   ```

   Alternatively, if you prefer Docker, you can build and run the container (see Docker instructions below).

---

## Usage

### Running the Variant Annotation Pipeline

To annotate variants from a VCF file:

```bash
python scripts/annotate_variants_ensembl.py --input_vcf ./input/NIST.vcf --output_tsv ./output/NIST.annotated.tsv
```

This will generate a TSV file containing the annotations.

### Starting the Web Interface

You can use the Flask web app to interact with the annotated variants:

```bash
python app.py
```

Once the server is running, you can access the web interface at [http://localhost:5000](http://localhost:5000) to query and explore the annotated variants.

### Running with Docker

To run VarAnnotator using Docker:

1. **Build the Docker Image:**

   ```bash
   docker build -t varannotator .
   ```

2. **Run the Container:**

   Map the input and output directories and expose the API port:

   ```bash
   docker run -v $(pwd)/input:/app/input -v $(pwd)/output:/app/output -p 5000:5000 varannotator
   ```

This command will:
- Expose the Flask API at port `5000`.
- Map your `input/` and `output/` directories into the container for processing.

---

## API Documentation

VarAnnotator provides a RESTful API to interact with the annotated variants.

### `/variants`

- **Method:** `GET`
- **Description:** Retrieve a paginated list of annotated genetic variants.

**Query Parameters:**
- `frequency`: Filter variants by population frequency.
- `depth`: Filter variants by read depth.
- `sort_column`: Column to sort by (e.g., `CHROM`, `POS`, `Gene`).
- `sort_order`: Sort order (asc or desc).
- `page`: Page number for pagination (default: 1).
- `per_page`: Number of records per page (default: 20).

**Example Request:**

```bash
GET /variants?frequency=0.1&depth=10&sort_column=Gene&sort_order=asc
```

### `/variants/<variant_id>`

- **Method:** `GET`
- **Description:** Retrieve a specific variant by its ID.

For more details see API.md

---

## Error Handling

VarAnnotator includes robust error handling for API calls:

- **404 Not Found:** If the requested variant or endpoint does not exist, a 404 status with an appropriate error message is returned.
- **500 Internal Server Error:** API calls that result in server errors (HTTP 500, 502, etc.) are automatically retried with exponential backoff.
- **429 Too Many Requests:** The API respects rate limits, and retries requests after a delay based on the `Retry-After` header.

### Retry Logic

The internal `EnsemblRestClient` is responsible for handling retries and rate limits:

- **Retries:** If an API call fails with a 500-level error, the system retries up to 5 times, with exponential backoff (2^n seconds).
- **Rate Limiting:** When encountering a 429 status, the `Retry-After` header is used to determine the delay before retrying.

---

## Testing

VarAnnotator comes with a comprehensive test suite. Tests cover key components of the pipeline, including error handling, VCF processing, and API endpoints.

### Running the Test Suite:

Before running the test suite, ensure that the `PYTHONPATH` is set so the tests can locate the VarAnnotator modules. While inside the project directory, run:

```bash
# Set PYTHONPATH with absolute paths and run the test suite
PYTHONPATH=$(pwd):$(pwd)/scripts python3 tests/test_suite.py
```

### Test Coverage:

- **API Interaction Tests:** Ensure correct handling of API calls, particularly around error handling and retries.
- **Mocking:** Mocks are included for `HTTPError`, `time.sleep`, and other components to simulate error conditions and speed up testing.
- **Unit and Functional Tests:** Comprehensive tests cover VCF processing, population frequency retrieval, and Flask API endpoints.

---

## Project Structure

```
.
├── app.py                        # Flask app for the web interface
├── input                         # Directory for input VCF files
│   └── NIST.vcf                  # Example input VCF file
├── output                        # Directory for annotated output
│   ├── NIST.annotated.tsv        # Annotated output file
│   ├── pipeline_status.json      # Pipeline status file
│   ├── annotated_variants.tsv    # Main output file
│   ├── snakemake.log             # Snakemake log file
│   └── logs
│       └── annotate_variants_NIST.log  # Log file for annotation
├── static                        # Static assets for web interface
│   └── index.html
├── tests                         # Test suite
│   ├── test_annotate_variants.py
│   ├── test_app.py
│   ├── test_ensembl_client.py
│   └── test_suite.py             # Main entry point for running all tests
├── scripts
│   ├── annotate_variants_ensembl.py  # Main script for annotating VCF files
│   ├── ensembl_client.py         # Ensembl API client
│   ├── Snakefile                 # Snakemake workflow for pipeline orchestration
├── Dockerfile                    # Docker configuration file
├── entrypoint.sh                 # Entrypoint script for Docker container
├── requirements.txt              # Python dependencies
├── LICENSE                       # License information
├── README.md                     # Project documentation (this file)
├── API.md                        # API documentation
└── logs                          # Additional logs directory
    ├── detailed_logs.log
    └── api_times_log.tsv
```

---

## Contributing

We welcome contributions to VarAnnotator! If you’d like to contribute, follow these steps:

1. **Fork the repository on GitHub.**
2. **Create a feature branch for your new feature or bug fix.**
3. **Submit a pull request** with a detailed explanation of your changes.

Please ensure that your contributions adhere to the existing coding style and that all tests pass before submitting your pull request.

---

## License

This project is licensed under the Apache License Version 2.0 - see the [LICENSE](LICENSE) file for details.

---
