# Python 3.9 Slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (needed for matplotlib/numpy sometimes)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY stock2.py .
COPY tickers.txt .
COPY capital_futures.py .

# Create directory for local cache
RUN mkdir -p yf_cache

# Expose port (FastAPI default)
EXPOSE 8001

# Run the application
# We use python stock2.py because it now handles the dynamic PORT env var
CMD ["python", "stock2.py"]
