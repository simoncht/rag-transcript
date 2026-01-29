"""
Memory Scoring Service.

Implements multi-factor fact selection based on OpenAI/Anthropic memory best practices:
- Importance scoring (LLM-rated)
- Recency decay (older facts fade unless reinforced)
- Category priority (identity > topic > preference > session)
- Query relevance (semantic similarity to current query)

This replaces the simple recency-based selection that caused 25% recall rate.
Target: 80%+ early fact recall.
"""
import logging
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy import case, func, text
from sqlalchemy.orm import Session

from app.models.conversation_fact import ConversationFact, FactCategory

logger = logging.getLogger(__name__)

# Scoring weights (OpenAI WMR recommendations + query relevance)
WEIGHT_IMPORTANCE = 0.30      # LLM-rated significance (reduced from 0.40)
WEIGHT_QUERY_RELEVANCE = 0.25 # NEW: semantic similarity to current query
WEIGHT_RECENCY = 0.15         # Time decay factor (reduced from 0.25)
WEIGHT_CATEGORY = 0.15        # Category priority (reduced from 0.20)
WEIGHT_SOURCE_TURN = 0.15     # Earlier identity facts get priority

# Recency decay factor (0.995 per hour = ~88% after 24h)
DECAY_RATE = 0.995
DECAY_HOURS_BASE = 24  # After 24h, decay starts applying more strongly

# Category priority scores (identity > topic > preference > session > ephemeral)
CATEGORY_PRIORITIES = {
    FactCategory.IDENTITY.value: 1.0,
    FactCategory.TOPIC.value: 0.75,
    FactCategory.PREFERENCE.value: 0.5,
    FactCategory.SESSION.value: 0.25,
    FactCategory.EPHEMERAL.value: 0.1,
}

# Default limit (can be overridden)
DEFAULT_FACT_LIMIT = 15

# Maximum facts to embed for query relevance (performance limit)
# Beyond this, we pre-filter by importance before embedding
MAX_FACTS_TO_EMBED = 75


def calculate_recency_score(
    created_at: datetime,
    last_accessed: Optional[datetime] = None,
    access_count: int = 0,
) -> float:
    """
    Calculate recency score with decay and reinforcement.

    Facts that are accessed frequently decay slower (reinforcement).
    Older facts that haven't been accessed decay faster.

    Args:
        created_at: When the fact was created
        last_accessed: When the fact was last used (None = never)
        access_count: How many times the fact has been accessed

    Returns:
        Recency score between 0.0 and 1.0
    """
    now = datetime.utcnow()

    # Use last_accessed if available, otherwise created_at
    reference_time = last_accessed if last_accessed else created_at
    hours_elapsed = (now - reference_time).total_seconds() / 3600

    # Base decay: exponential decay over time
    base_decay = math.pow(DECAY_RATE, hours_elapsed)

    # Reinforcement bonus: frequently accessed facts decay slower
    # Each access adds ~5% to the score (diminishing returns)
    reinforcement = min(0.3, access_count * 0.05)

    # Combine: base decay + reinforcement, clamped to [0, 1]
    score = min(1.0, base_decay + reinforcement)

    return score


def calculate_query_relevance(
    query_embedding: np.ndarray,
    fact_embedding: np.ndarray,
) -> float:
    """
    Calculate cosine similarity between query and fact.

    Since embeddings are already normalized to unit vectors,
    the dot product equals cosine similarity.

    Args:
        query_embedding: Normalized query embedding vector
        fact_embedding: Normalized fact embedding vector

    Returns:
        Relevance score between 0.0 and 1.0
    """
    similarity = np.dot(query_embedding, fact_embedding)
    # Clamp to [0, 1] - negative similarities treated as irrelevant
    return max(0.0, float(similarity))


def calculate_source_turn_priority(source_turn: int, max_turn: int) -> float:
    """
    Calculate priority based on source turn.

    Earlier turns (especially first few) often contain identity information
    that should be prioritized. This is the inverse of recency - we want
    early facts to score higher for identity preservation.

    Args:
        source_turn: Turn number where fact was extracted
        max_turn: Maximum turn number in conversation

    Returns:
        Source turn priority between 0.0 and 1.0
    """
    if max_turn <= 1:
        return 1.0

    # First few turns get highest priority (identity establishment)
    if source_turn <= 3:
        return 1.0
    elif source_turn <= 10:
        return 0.8
    elif source_turn <= 20:
        return 0.6
    else:
        # Linear decay for later turns
        return max(0.2, 1.0 - (source_turn / max_turn))


def calculate_composite_score(
    fact: ConversationFact,
    max_turn: int,
    query_relevance: float = 0.5,
) -> float:
    """
    Calculate composite memory score using multi-factor weighting.

    Formula (OpenAI WMR-inspired + query relevance):
    score = (
        importance * 0.30 +
        query_relevance * 0.25 +
        recency_score * 0.15 +
        category_priority * 0.15 +
        source_turn_priority * 0.15
    )

    Args:
        fact: The ConversationFact to score
        max_turn: Maximum turn number in conversation
        query_relevance: Semantic similarity to user query (0.0-1.0, default 0.5)

    Returns:
        Composite score between 0.0 and 1.0
    """
    # 1. Importance score (LLM-rated, stored in DB)
    importance_score = fact.importance if fact.importance else 0.5

    # 2. Query relevance (semantic similarity to current query)
    # Uses provided value or defaults to neutral 0.5 if no query

    # 3. Recency score (with decay and reinforcement)
    recency_score = calculate_recency_score(
        fact.created_at,
        fact.last_accessed,
        fact.access_count if fact.access_count else 0,
    )

    # 4. Category priority
    category_score = CATEGORY_PRIORITIES.get(fact.category, 0.5)

    # 5. Source turn priority (earlier turns for identity facts)
    source_priority = calculate_source_turn_priority(fact.source_turn, max_turn)

    # Combine with weights
    composite = (
        importance_score * WEIGHT_IMPORTANCE +
        query_relevance * WEIGHT_QUERY_RELEVANCE +
        recency_score * WEIGHT_RECENCY +
        category_score * WEIGHT_CATEGORY +
        source_priority * WEIGHT_SOURCE_TURN
    )

    return composite


def select_facts_multifactor(
    db: Session,
    conversation_id: str,
    limit: int = DEFAULT_FACT_LIMIT,
    user_query: Optional[str] = None,
    embedding_service: Optional[Any] = None,
) -> List[Tuple[ConversationFact, float]]:
    """
    Select facts using multi-factor scoring algorithm with query-aware retrieval.

    This replaces the broken recency-only selection with industry-standard
    weighted memory retrieval (OpenAI WMR pattern) plus semantic relevance.

    Args:
        db: Database session
        conversation_id: Conversation UUID
        limit: Maximum number of facts to return
        user_query: Optional query for relevance scoring
        embedding_service: Optional embedding service for query relevance

    Returns:
        List of (fact, score) tuples, sorted by score descending
    """
    # Fetch all facts for this conversation
    facts = (
        db.query(ConversationFact)
        .filter(ConversationFact.conversation_id == conversation_id)
        .all()
    )

    if not facts:
        return []

    # Get max turn for source priority calculation
    max_turn = max(f.source_turn for f in facts)

    # Calculate query relevance scores if possible
    relevance_scores: Dict[str, float] = {}
    if user_query and embedding_service:
        try:
            import time as _time
            embed_start = _time.time()

            # Embed user query
            query_embedding = embedding_service.embed_text(user_query, use_cache=False)
            # Handle tuple return from cached embedding (convert to array)
            if isinstance(query_embedding, tuple):
                query_embedding = np.array(query_embedding)

            # Performance optimization: if too many facts, pre-filter by importance
            # to limit embedding cost while still prioritizing high-importance facts
            facts_to_embed = facts
            if len(facts) > MAX_FACTS_TO_EMBED:
                # Sort by importance and take top N
                facts_to_embed = sorted(
                    facts,
                    key=lambda f: f.importance if f.importance else 0.5,
                    reverse=True
                )[:MAX_FACTS_TO_EMBED]
                logger.info(
                    f"[Memory Scoring] Pre-filtered to {len(facts_to_embed)}/{len(facts)} facts for embedding"
                )

            # Batch embed fact texts for efficiency
            # Combine fact_key and fact_value for richer semantic matching
            fact_texts = [f"{f.fact_key}: {f.fact_value}" for f in facts_to_embed]
            fact_embeddings = embedding_service.embed_batch(fact_texts)

            # Calculate relevance for each embedded fact
            for fact, fact_emb in zip(facts_to_embed, fact_embeddings):
                # Handle tuple return from cached embedding
                if isinstance(fact_emb, tuple):
                    fact_emb = np.array(fact_emb)
                relevance_scores[str(fact.id)] = calculate_query_relevance(
                    query_embedding, fact_emb
                )

            embed_time = (_time.time() - embed_start) * 1000
            logger.info(
                f"[Memory Scoring] Calculated query relevance for {len(facts_to_embed)} facts "
                f"in {embed_time:.0f}ms"
            )
        except Exception as e:
            logger.warning(f"[Memory Scoring] Query relevance calculation failed: {e}")
            # Fall back to neutral relevance (0.5) for all facts

    # Calculate composite score for each fact
    scored_facts = []
    for fact in facts:
        relevance = relevance_scores.get(str(fact.id), 0.5)
        score = calculate_composite_score(fact, max_turn, query_relevance=relevance)
        scored_facts.append((fact, score))

    # Sort by score descending
    scored_facts.sort(key=lambda x: x[1], reverse=True)

    # Log selection details
    logger.info(
        f"[Memory Scoring] Selected {min(limit, len(scored_facts))}/{len(facts)} facts "
        f"for conversation {conversation_id}"
    )
    if scored_facts:
        top_fact, top_score = scored_facts[0]
        top_relevance = relevance_scores.get(str(top_fact.id), 0.5)
        if user_query:
            logger.info(
                f"[Memory Scoring] Top fact: {top_fact.fact_key}={top_fact.fact_value[:30]}... "
                f"(score={top_score:.3f}, relevance={top_relevance:.3f}, "
                f"importance={top_fact.importance:.2f}, category={top_fact.category})"
            )
        else:
            logger.debug(
                f"[Memory Scoring] Top fact: {top_fact.fact_key}={top_fact.fact_value[:30]}... "
                f"(score={top_score:.3f}, importance={top_fact.importance:.2f}, "
                f"category={top_fact.category}, turn={top_fact.source_turn})"
            )

    return scored_facts[:limit]


def update_fact_access(db: Session, fact_ids: List[str]) -> None:
    """
    Update last_accessed and access_count for facts that were used.

    This implements the reinforcement mechanism - facts that are
    used frequently maintain higher scores over time.

    Args:
        db: Database session
        fact_ids: List of fact UUIDs that were used in this query
    """
    if not fact_ids:
        return

    now = datetime.utcnow()

    # Bulk update for efficiency
    db.query(ConversationFact).filter(
        ConversationFact.id.in_(fact_ids)
    ).update(
        {
            ConversationFact.last_accessed: now,
            ConversationFact.access_count: ConversationFact.access_count + 1,
        },
        synchronize_session=False,
    )

    logger.debug(f"[Memory Scoring] Updated access for {len(fact_ids)} facts")


def format_facts_for_prompt(
    scored_facts: List[Tuple[ConversationFact, float]],
) -> str:
    """
    Format selected facts for injection into system prompt.

    Groups facts by category for better organization.

    Args:
        scored_facts: List of (fact, score) tuples

    Returns:
        Formatted facts string for system prompt
    """
    if not scored_facts:
        return ""

    # Group by category
    categories = {}
    for fact, score in scored_facts:
        cat = fact.category or FactCategory.TOPIC.value
        if cat not in categories:
            categories[cat] = []
        categories[cat].append((fact, score))

    # Format with category headers (identity first)
    lines = []
    category_order = [
        FactCategory.IDENTITY.value,
        FactCategory.TOPIC.value,
        FactCategory.PREFERENCE.value,
        FactCategory.SESSION.value,
        FactCategory.EPHEMERAL.value,
    ]

    for cat in category_order:
        if cat in categories:
            cat_facts = categories[cat]
            # Compressed format: key=value(T1), key2=value2(T2)
            items = [
                f"{fact.fact_key}={fact.fact_value}(T{fact.source_turn})"
                for fact, _ in cat_facts
            ]
            lines.append(f"[{cat}] {', '.join(items)}")

    if lines:
        return "\n\n**Known Facts**:\n" + "\n".join(lines)
    return ""
