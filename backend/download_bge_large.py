#!/usr/bin/env python3
"""
Download bge-large-en-v1.5 model to local cache.
This script temporarily enables network access to download the model.
"""
import os
import sys

# IMPORTANT: Apply SSL patch FIRST (corporate environment bypass)
sys.path.insert(0, '/app')
from app.core.ssl_patch import *  # Apply SSL bypass globally

# Temporarily disable offline mode for download
os.environ['HF_HUB_OFFLINE'] = '0'
os.environ['TRANSFORMERS_OFFLINE'] = '0'

print("=" * 60)
print("Downloading bge-large-en-v1.5 model")
print("=" * 60)
print("")
print("Model: BAAI/bge-large-en-v1.5")
print("Size: ~340 MB")
print("Dimensions: 1024")
print("Quality: ⭐⭐⭐⭐⭐ (State-of-the-art for RAG)")
print("")
print("SSL bypass: ENABLED (corporate environment)")
print("This may take 5-10 minutes depending on network speed...")
print("")

try:
    from sentence_transformers import SentenceTransformer

    print("Downloading model files from HuggingFace Hub...")
    model = SentenceTransformer('BAAI/bge-large-en-v1.5')

    print("")
    print("=" * 60)
    print("✅ Download Complete!")
    print("=" * 60)
    print(f"Dimensions: {model.get_sentence_embedding_dimension()}")
    print(f"Max sequence length: {model.max_seq_length}")
    print(f"Cache location: /root/.cache/huggingface/")
    print("")
    print("Testing model with sample text...")

    test_embedding = model.encode("This is a test sentence.")
    print(f"✅ Model working! Generated {len(test_embedding)}-dim embedding")
    print("")
    print("Model is ready to use!")

except Exception as e:
    print("")
    print("=" * 60)
    print("❌ Download Failed")
    print("=" * 60)
    print(f"Error: {e}")
    print("")
    import traceback
    traceback.print_exc()
    sys.exit(1)
