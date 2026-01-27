FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    ca-certificates \
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
ENV WHISPER_CACHE=/root/.cache/whisper

# Download sentence-transformers embedding model (~90MB)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')" || \
    (echo 'Warning: Sentence-transformers model download failed, will retry at runtime' && exit 0)

# Download Whisper base model for transcription (~139MB)
# PRODUCTION: Change 'base' to 'small' or 'medium' for better accuracy (larger models)
RUN python -c "import whisper; whisper.load_model('base')" || \
    (echo 'Warning: Whisper model download failed, will retry at runtime' && exit 0)

# Copy application code
COPY . .

# Create storage directory
RUN mkdir -p /app/storage/audio /app/storage/transcripts

# Expose port
EXPOSE 8000

# Default command (can be overridden in docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
