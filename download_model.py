"""
Download the all-MiniLM-L6-v2 model to the local cache.
"""
from sentence_transformers import SentenceTransformer
import os
import ssl

# Disable SSL verification for corporate environment
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['PYTHONHTTPSVERIFY'] = '0'

# Disable offline mode
os.environ['HF_HUB_OFFLINE'] = '0'
os.environ['TRANSFORMERS_OFFLINE'] = '0'
os.environ['HF_HUB_DISABLE_SSL_VERIFY'] = '1'

# Set cache directory
cache_dir = "./hf_cache"
os.makedirs(cache_dir, exist_ok=True)

# Download the model
print("Downloading all-MiniLM-L6-v2 model...")
print("This may take a few minutes (model size: ~90 MB)")

try:
    model = SentenceTransformer(
        "sentence-transformers/all-MiniLM-L6-v2",
        cache_folder=cache_dir,
        local_files_only=False,
        trust_remote_code=True
    )

    print(f"✓ Model downloaded successfully to: {cache_dir}")
    print(f"✓ Model dimensions: {model.get_sentence_embedding_dimension()}")
except Exception as e:
    print(f"✗ Error downloading model: {e}")
    print("\nIf you're behind a corporate proxy, the model download may be blocked.")
    print("The system was working before, so the existing cache should still work.")
    raise
