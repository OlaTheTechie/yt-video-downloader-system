# Multi-stage Dockerfile for YouTube Video Downloader

# Build stage
FROM python:3.11-slim as builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt requirements-dev.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Install the package
RUN pip install --no-cache-dir -e .

# Production stage
FROM python:3.11-slim as production

# Install FFmpeg and other runtime dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash downloader

# Set working directory
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app /app

# Create downloads directory
RUN mkdir -p /downloads && chown downloader:downloader /downloads

# Switch to non-root user
USER downloader

# Set environment variables
ENV PYTHONPATH=/app
ENV DOWNLOADS_DIR=/downloads

# Expose volume for downloads
VOLUME ["/downloads"]

# Default command
ENTRYPOINT ["youtube-downloader"]
CMD ["--help"]

# Development stage
FROM builder as development

# Install development dependencies
RUN pip install --no-cache-dir -r requirements-dev.txt

# Install pre-commit hooks
RUN pre-commit install || true

# Set development environment
ENV PYTHONPATH=/app
ENV DEVELOPMENT=1

# Default command for development
CMD ["bash"]

# Testing stage
FROM development as testing

# Run tests
RUN pytest tests/ -v --cov=. --cov-report=term-missing

# Linting and code quality
RUN flake8 . --count --statistics
RUN black --check .
RUN isort --check-only .
RUN mypy . --ignore-missing-imports