# ===========================
# Stage 1: Build Frontend
# ===========================
FROM node:18-alpine AS frontend-build

WORKDIR /app/frontend

# Copy frontend package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm install

# Copy frontend source code
COPY frontend/ ./

# Build the React app
RUN npm run build

# ===========================
# Stage 2: Python Backend + Compiled Frontend
# ===========================
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (needed for matplotlib/numpy)
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

# Copy compiled frontend from Stage 1
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

# Expose port (Render will provide PORT env var)
EXPOSE 8001

# Run the application
# Python stock2.py now serves both API and frontend
CMD ["python", "stock2.py"]

