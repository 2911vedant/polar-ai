FROM python:3.11-slim

# System dependencies for geospatial libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libgdal-dev \
    gdal-bin \
    libproj-dev \
    libgeos-dev \
    libpq-dev \
    libhdf5-dev \
    libnetcdf-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data and model directories
RUN mkdir -p /app/data/raw /app/data/processed /app/data/demo /app/models

# Run Alembic migrations then start server
RUN chmod +x /app/start.sh
CMD ["/app/start.sh"]
