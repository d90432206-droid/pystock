# ===========================
# Stage 1: Build Frontend
# ===========================
FROM node:18-alpine AS frontend-build

WORKDIR /app/frontend

# Copy frontend package files first (better caching)
COPY frontend/package*.json ./

# Install dependencies with verbose logging
RUN echo "📦 Installing frontend dependencies..." && \
    npm install --prefer-offline --no-audit

# Copy frontend source code
COPY frontend/ ./

# Build the React app with error handling
RUN echo "🔨 Building React frontend..." && \
    npm run build && \
    echo "✅ Frontend build completed" && \
    ls -la dist/

# Verify build output exists
RUN test -f dist/index.html || (echo "❌ ERROR: index.html not found in dist/" && exit 1)

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
RUN echo "🐍 Installing Python dependencies..." && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY stock2.py .
COPY tickers.txt .
COPY capital_futures.py .

# Create directory for local cache
RUN mkdir -p yf_cache

# Copy compiled frontend from Stage 1
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

# Verify frontend files were copied
RUN echo "📂 Checking frontend files..." && \
    ls -la /app/frontend/dist/ && \
    test -f /app/frontend/dist/index.html || (echo "❌ ERROR: Frontend files missing!" && exit 1)

# Expose port (Render will provide PORT env var)
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/api/health')" || exit 1

# Run the application
CMD ["python", "stock2.py"]
