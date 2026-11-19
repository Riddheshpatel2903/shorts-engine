# Production Dockerfile for ViralShortsEngine (HF Spaces & Render Compatible)
FROM python:3.11-slim

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

# Set up user for Hugging Face Spaces (UID 1000)
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

# Copy dependency requirements first to leverage Docker cache
COPY --chown=user:user requirements.txt .

# Install Python dependencies into user directory
RUN pip install --no-cache-dir --user --upgrade pip && \
    pip install --no-cache-dir --user -r requirements.txt

# Copy all application source code
COPY --chown=user:user . .

# Create essential workspace directories with full write permissions
RUN mkdir -p workspace/downloads workspace/processing workspace/output logs assets/fonts

# Default port: 7860 (Hugging Face default) or Render $PORT dynamically
ENV PORT=7860
EXPOSE 7860

# Launch Streamlit bound to 0.0.0.0 and dynamic PORT
CMD streamlit run ui.py \
    --server.port=${PORT:-7860} \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false
