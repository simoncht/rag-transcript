#!/usr/bin/env python3
"""
Quick test script to verify RAG pipeline components.
"""
import sys
sys.path.insert(0, '/app')

import numpy as np
from app.services.embeddings import embedding_service
from app.services.vector_store import vector_store_service

# Test query
query = "What is this song about?"

print(f"Testing RAG pipeline with query: '{query}'")
print("-" * 60)

# Step 1: Embed the query
print("\n1. Embedding query...")
query_embedding = embedding_service.embed_text(query)
# Convert to numpy array if it's a tuple (from cache)
if isinstance(query_embedding, tuple):
    query_embedding = np.array(query_embedding, dtype=np.float32)
print(f"   ✓ Query embedded: {len(query_embedding)} dimensions")
print(f"   Sample values: {query_embedding[:5]}")

# Step 2: Search vector store
print("\n2. Searching vector store...")
results = vector_store_service.search_chunks(
    query_embedding=query_embedding,
    top_k=3
)
print(f"   ✓ Found {len(results)} results")

# Step 3: Display results
print("\n3. Top results:")
for i, result in enumerate(results, 1):
    print(f"\n   Result {i} (score: {result.score:.4f}):")
    print(f"   Video ID: {result.video_id}")
    print(f"   Chunk ID: {result.chunk_id}")
    print(f"   Timestamp: {result.start_timestamp:.1f}s - {result.end_timestamp:.1f}s")
    print(f"   Title: {result.title}")
    print(f"   Text preview: {result.text[:150]}...")
    print(f"   Keywords: {result.keywords}")

print("\n" + "=" * 60)
print("✓ RAG pipeline test completed successfully!")
