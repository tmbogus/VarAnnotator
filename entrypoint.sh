#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Define paths
OUTPUT_DIR="/app/output"
STATUS_FILE="$OUTPUT_DIR/pipeline_status.json"
SNAKEMAKE_LOG="$OUTPUT_DIR/snakemake.log"

# Ensure the output and logs directories exist
mkdir -p "$OUTPUT_DIR/logs"

# Initialize the status file
echo '{"status": "running", "message": "Pipeline is running..."}' > "$STATUS_FILE"

# Function to run Snakemake and update status
run_snakemake() {
    echo "Starting Snakemake pipeline..." >> "$SNAKEMAKE_LOG"
    snakemake -s scripts/Snakefile --cores 4 >> "$SNAKEMAKE_LOG" 2>&1

    if [ $? -eq 0 ]; then
        echo '{"status": "completed", "message": "Pipeline completed successfully."}' > "$STATUS_FILE"
    else
        echo '{"status": "failed", "message": "Pipeline encountered an error."}' > "$STATUS_FILE"
    fi
}

# Start Snakemake in the background
run_snakemake &

# Capture Snakemake's PID (optional, useful for monitoring or debugging)
SNAKEMAKE_PID=$!

# Start Flask app with Gunicorn in the foreground
echo "Starting Flask app with Gunicorn..."
exec gunicorn -w 4 -b 0.0.0.0:5000 app:app
