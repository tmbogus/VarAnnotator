# Use an official Python base image
FROM python:3.10-slim

# Set the working directory inside the container
WORKDIR /app

# Install essential system packages and Snakemake dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
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

# Install Snakemake via pip
RUN pip install --no-cache-dir snakemake

# Install Flask and other required Python libraries
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the project source code into the container
COPY . .

# Expose the port for the Flask application
EXPOSE 5000

# Command to run the Flask app
CMD ["flask", "run", "--host=0.0.0.0"]
