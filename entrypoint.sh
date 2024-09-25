#!/bin/bash

set -e  # Exit immediately if a command exits with a non-zero status

# Path to the shared status file
STATUS_FILE="/shared/pipeline_status.json"

# Ensure the shared directory exists
mkdir -p /shared

# Update status to running
echo '{"status": "running", "message": "Pipeline is starting..."}' > $STATUS_FILE

# Run Snakemake
snakemake -s scripts/Snakefile --cores 4

# Update status to completed
echo '{"status": "completed", "message": "Pipeline completed successfully."}' > $STATUS_FILE

# Start the Flask app
exec "$@"
