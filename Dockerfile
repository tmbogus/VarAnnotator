# Use an official Python base image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory inside the container
WORKDIR /app

# Install essential system packages, including Bash and Snakemake dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    bash \
    build-essential \
    wget \
    curl \
    git \
    zlib1g-dev \
    libbz2-dev \
    liblzma-dev \
    libncurses5-dev \
    libncursesw5-dev \
    libcurl4-openssl-dev \
    libssl-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project source code into the container
COPY . .

# Make entrypoint script executable
RUN chmod +x entrypoint.sh

# Create output directory
RUN mkdir -p /app/output

# Expose the port for the Flask application
EXPOSE 5000

# Define volume for output data (includes annotated TSV and status JSON)
VOLUME /app/output

# Define the entrypoint with absolute path for reliability
ENTRYPOINT ["/app/entrypoint.sh"]

# Remove CMD as entrypoint.sh handles running Flask
# CMD ["python", "app.py"]  # This line is removed
