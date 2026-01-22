"""
Performance profiling script for RAG pipeline.

Run this to measure exact timing of each stage:
    python -m pytest backend/tests/test_performance_profile.py -v -s

Or run directly:
    docker compose exec app python tests/test_performance_profile.py
"""
import sys
import time
import uuid
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings


def profile_rag_pipeline(
    query: str = "What did bashar say about self-worth and discernment?",
):
    """Profile each stage of the RAG pipeline."""

    from app.services.embeddings import embedding_service
    from app.services.vector_store import vector_store_service
    from app.services.llm_providers import llm_service, Message
    from app.services.reranker import reranker_service

    print("\n" + "=" * 80)
    print("RAG PIPELINE PERFORMANCE PROFILE")
    print("=" * 80)
    print(f"\nQuery: {query}")
    print("Configuration:")
    print(f"  - LLM Provider: {settings.llm_provider}")
    print(
        f"  - LLM Model: {settings.ollama_model if settings.llm_provider == 'ollama' else 'N/A'}"
    )
    print(f"  - Retrieval Top K: {settings.retrieval_top_k}")
    print(f"  - Reranking Enabled: {settings.enable_reranking}")
    print(f"  - Reranking Top K: {settings.reranking_top_k}")
    print(f"  - Min Relevance Score: {settings.min_relevance_score}")
    print("\n" + "-" * 80)

    timings = {}

    # Stage 1: Query Embedding
    print("\n[Stage 1] Query Embedding...")
    start = time.time()
    try:
        query_embedding = embedding_service.embed_text(query)
        timings["embedding"] = time.time() - start
        print(f"  ✓ Completed in {timings['embedding']:.3f}s")
        print(f"    Dimensions: {len(query_embedding)}")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return timings

    # Stage 2: Vector Search
    print("\n[Stage 2] Vector Search...")
    start = time.time()
    try:
        # Use a test user_id - in real scenario this comes from auth
        test_user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

        scored_chunks = vector_store_service.search_chunks(
            query_embedding=query_embedding,
            user_id=test_user_id,
            video_ids=None,  # Search all videos
            top_k=settings.retrieval_top_k,
            collection_name=embedding_service.get_collection_name(),
        )
        timings["vector_search"] = time.time() - start
        print(f"  ✓ Completed in {timings['vector_search']:.3f}s")
        print(f"    Retrieved: {len(scored_chunks)} chunks")
        if scored_chunks:
            print(
                f"    Score range: {min(c.score for c in scored_chunks):.3f} - {max(c.score for c in scored_chunks):.3f}"
            )
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return timings

    # Stage 3: Reranking (if enabled)
    if settings.enable_reranking and scored_chunks:
        print("\n[Stage 3] Reranking (cross-encoder)...")
        start = time.time()
        try:
            original_count = len(scored_chunks)
            scored_chunks = reranker_service.rerank(
                query=query,
                chunks=scored_chunks,
                top_k=settings.reranking_top_k,
            )
            timings["reranking"] = time.time() - start
            print(f"  ✓ Completed in {timings['reranking']:.3f}s")
            print(f"    Reranked {original_count} → {len(scored_chunks)} chunks")
            if scored_chunks:
                print(
                    f"    New score range: {min(c.score for c in scored_chunks):.3f} - {max(c.score for c in scored_chunks):.3f}"
                )
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            timings["reranking"] = 0
    else:
        print("\n[Stage 3] Reranking: DISABLED")
        timings["reranking"] = 0

    # Stage 4: Relevance Filtering
    print("\n[Stage 4] Relevance Filtering...")
    start = time.time()
    pre_filter_count = len(scored_chunks)
    scored_chunks = [
        c for c in scored_chunks if c.score >= settings.min_relevance_score
    ]
    timings["filtering"] = time.time() - start
    print(f"  ✓ Completed in {timings['filtering']:.3f}s")
    print(
        f"    Filtered {pre_filter_count} → {len(scored_chunks)} chunks (threshold: {settings.min_relevance_score})"
    )

    # Stage 5: Context Building
    print("\n[Stage 5] Context Building...")
    start = time.time()
    try:
        # Simplified context building (mimics what happens in conversations.py)
        context_parts = []
        for i, chunk in enumerate(scored_chunks[:5], 1):  # Top 5 for context
            context_parts.append(
                f"[Source {i}] Relevance: {(chunk.score * 100):.0f}%\n"
                f"{chunk.text[:200]}..."
            )
        context = "\n---\n".join(context_parts)
        timings["context_building"] = time.time() - start
        print(f"  ✓ Completed in {timings['context_building']:.3f}s")
        print(f"    Context size: {len(context)} chars")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return timings

    # Stage 6: LLM Generation
    print("\n[Stage 6] LLM Generation...")
    start = time.time()
    try:
        messages = [
            Message(
                role="system",
                content="You are a helpful assistant that answers questions based on provided context.",
            ),
            Message(role="user", content=f"Context:\n{context}\n\nQuestion: {query}"),
        ]

        llm_response = llm_service.complete(
            messages,
            temperature=settings.llm_temperature,
            max_tokens=min(500, settings.llm_max_tokens),  # Limit to 500 for testing
        )
        timings["llm_generation"] = time.time() - start
        print(f"  ✓ Completed in {timings['llm_generation']:.3f}s")
        print(f"    Response length: {len(llm_response.content)} chars")
        if llm_response.usage:
            total_tokens = llm_response.usage.get("total_tokens", 0)
            print(f"    Tokens: {total_tokens}")
            if timings["llm_generation"] > 0 and total_tokens > 0:
                tokens_per_sec = total_tokens / timings["llm_generation"]
                print(f"    Speed: {tokens_per_sec:.1f} tokens/second")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        print("    Note: Make sure Ollama is running and model is pulled")
        return timings

    # Summary
    print("\n" + "=" * 80)
    print("PERFORMANCE SUMMARY")
    print("=" * 80)

    total_time = sum(timings.values())

    print("\nTiming Breakdown:")
    for stage, duration in timings.items():
        percentage = (duration / total_time * 100) if total_time > 0 else 0
        bar_length = int(percentage / 2)  # Scale to 50 chars max
        bar = "█" * bar_length + "░" * (50 - bar_length)
        print(f"  {stage:20s}: {duration:6.3f}s [{bar}] {percentage:5.1f}%")

    print(f"\n{'Total Time':20s}: {total_time:6.3f}s")

    # Recommendations
    print("\n" + "-" * 80)
    print("RECOMMENDATIONS:")

    if timings.get("llm_generation", 0) > 10:
        print("  ⚠️  LLM generation is very slow (>10s)")
        print("      → Consider switching to a smaller/faster model")
        print(f"      → Current: {settings.ollama_model}")
        print("      → Try: qwen2.5-coder:7b or llama3:8b")

    if timings.get("reranking", 0) > 2:
        print("  ⚠️  Reranking is taking >2s")
        print(
            "      → Consider reducing RETRIEVAL_TOP_K (current: {settings.retrieval_top_k})"
        )
        print("      → Or disable reranking for simple queries")

    if timings.get("vector_search", 0) > 0.5:
        print("  ⚠️  Vector search is slow (>0.5s)")
        print("      → Check Qdrant performance")
        print("      → Consider reducing RETRIEVAL_TOP_K")

    if len(scored_chunks) == 0:
        print("  ⚠️  No chunks passed relevance filter")
        print(
            f"      → MIN_RELEVANCE_SCORE ({settings.min_relevance_score}) may be too high"
        )
        print("      → Try lowering to 0.15-0.30")

    print("\n" + "=" * 80 + "\n")

    return timings


if __name__ == "__main__":
    # Run profile with default query
    timings = profile_rag_pipeline()

    # Exit with error if any stage failed
    if not timings.get("llm_generation"):
        print("❌ Profile incomplete - check errors above")
        sys.exit(1)
    else:
        print("✅ Profile complete")
        sys.exit(0)
