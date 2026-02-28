FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    ca-certificates \
    libreoffice-core \
    && rm -rf /var/lib/apt/lists/*

# Update CA certificates
RUN update-ca-certificates

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Update certifi to use system certificates
RUN python -m pip install --upgrade certifi

# Set environment variables for SSL (corporate proxy compatibility)
ENV CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

# Pre-download ML models to avoid runtime download issues
# This ensures fast, predictable startup in production
ENV HF_HOME=/app/.cache/huggingface
ENV OPENBLAS_NUM_THREADS=1
ENV OMP_NUM_THREADS=1

# Download sentence-transformers embedding model (~90MB)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')" || \
    (echo 'Warning: Sentence-transformers model download failed, will retry at runtime' && exit 0)

# Download faster-whisper base model for transcription (~150MB CTranslate2 format)
# PRODUCTION: Change 'base' to 'small' or 'medium' for better accuracy (larger models)
RUN python -c "from faster_whisper import WhisperModel; m = WhisperModel('base', device='cpu', compute_type='int8'); print('faster-whisper model OK')"

# Copy application code
COPY . .

# Create storage directory
RUN mkdir -p /app/storage/audio /app/storage/transcripts

# Copy and make start script executable
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Expose port
EXPOSE 8000

# Default command - runs migrations then starts app
CMD ["/app/start.sh"]
