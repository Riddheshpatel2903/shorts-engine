# Production Dockerfile for ViralShortsEngine
FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies: ffmpeg, ffprobe, libgl for OpenCV, fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    fonts-liberation \
    fonts-dejavu-core \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy all application source code
COPY . .

# Create essential workspace directories
RUN mkdir -p workspace/downloads workspace/processing workspace/output logs assets/fonts

# Default port for Render / Cloud hosts (Render passes $PORT dynamically)
ENV PORT=8501
EXPOSE 8501

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:${PORT}/_stcore/health || exit 1

# Launch Streamlit bound to 0.0.0.0 and dynamic PORT
CMD streamlit run ui.py \
    --server.port=${PORT:-8501} \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false \
    --browser.serverAddress=0.0.0.0
