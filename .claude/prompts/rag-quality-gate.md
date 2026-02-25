# RAG Quality Gate

Analyze the shell script output to evaluate RAG retrieval quality.

## What to check

### Intent Classification
- Look at PASS/FAIL counts for the intent classification benchmark
- Any FAIL means a broad query is being misrouted to PRECISION, causing poor coverage
- For failures: check `backend/app/services/intent_classifier.py` COVERAGE_PATTERNS
- Common fix: add a new regex pattern or lower the cross-source keyword threshold

### Summary Coverage
- Check percentage of completed videos with summaries
- Below 50%: the COVERAGE retrieval path falls back to chunk retrieval (degraded)
- Fix: trigger backfill via `POST /api/v1/admin/videos/backfill-summaries`
- The daily beat task at 4 AM also gradually backfills (20 per run)

### Chunk Limit Adequacy
- For collections with many videos, verify the coverage chunk limit is adequate
- Coverage limit = min(num_videos, 50)
- If a collection has >50 videos, only 50 will be represented per query

### Memory Health
- Check if long conversations (>30 messages) have facts extracted
- Early-turn facts (source_turn <= 5) should exist for conversations with 30+ messages
- If no early facts: memory dead zone likely (MEM-001) — facts not extracted before old messages leave history window
- Fix: lower fact extraction threshold or extract incrementally
- See `.claude/references/behavioral-contracts.md` for full MEM-* contract definitions

### Citation Tracking
- Check if any `MessageChunkReference` has `was_used_in_response=False`
- If ALL references are True: tracking is broken (CIT-001)
- The field defaults to True and is never updated after LLM generation
- Fix: parse `[N]` markers from LLM output and set `was_used_in_response=False` for unreferenced chunks
- See `.claude/references/behavioral-contracts.md` for full CIT-* contract definitions

### BM25 Activation
- Verify `enable_bm25_search` is True in config
- BM25 hybrid search provides 5-15% improvement for entity/keyword queries
- If disabled: exact name/term matches will be missed by dense-only retrieval

## What to report

1. Overall PASS/FAIL status
2. Any intent classification regressions (queries that changed from PASS to FAIL)
3. Summary coverage trend (is it improving?)
4. Memory health status (early facts preserved? dead zone detected?)
5. Citation tracking status (is was_used_in_response actually tracking?)
6. BM25 activation status
7. Recommendations for any failures found
