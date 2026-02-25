# Content Parity Analysis

Analyze document vs video processing parity after the shell script has run. The shell script checks structural patterns; your job is to read both pipelines side-by-side and identify features present in one but missing from the other.

## Context

Read `.claude/references/behavioral-contracts.md` for contracts PAR-001 and PAR-002.

## Your Tasks

### 1. Evaluate Shell Script Output

Review the output from `content-parity.sh`. Note which contracts passed and which were flagged.

### 2. Side-by-Side Pipeline Comparison

Read both processing pipelines in full:
- `backend/app/tasks/video_tasks.py` — the video processing pipeline
- `backend/app/tasks/document_tasks.py` — the document processing pipeline

For each pipeline stage, compare:

| Stage | Video Pipeline | Document Pipeline | Parity? |
|-------|---------------|-------------------|---------|
| Download/Extract | Audio download + Whisper | Text extraction (PDF/DOCX) | N/A (different sources) |
| Chunking | `chunking.py` (semantic, timestamp-aware) | `document_chunker.py` (section/page-aware) | Check |
| Enrichment | ContextualEnricher with full transcript | ContextualEnricher with full text | Check |
| Embedding | Same service for both? | Same service for both? | Check |
| Indexing | Qdrant with video_id | Qdrant with document_id | Check |
| Summary | Video summary generation | Document summary generation | Check |

### 3. Deep Analysis of Flagged Contracts

**PAR-001 (Enrichment Parity):**
- Read the enrichment calls in both task files
- Are the parameters equivalent? (full_text, content_type, usage_collector)
- Does the document pipeline pass full_text for contextual enrichment?
- Does the document pipeline get the same cache benefits as video pipeline?

**PAR-002 (Truncation Warning):**
- Read `enrichment.py` line 94: `self.full_text = full_text[:48000]...`
- Is there a `logger.warning()` before or after truncation?
- If not: large documents are silently losing content context without any log trace

### 4. Feature Parity Checklist

Check each feature in the video pipeline and verify the document pipeline has it too:
- [ ] Status tracking (pending → processing → completed → failed)
- [ ] Cancellation support (can cancel mid-processing)
- [ ] Reprocessing support (can reprocess failed/canceled)
- [ ] Storage quota tracking (track storage usage)
- [ ] Error handling with status rollback
- [ ] Idempotency guards (skip if already completed)

### 5. Report

```
## Content Parity Report

### Pipeline Comparison
| Feature | Video | Document | Status |
|---------|-------|----------|--------|
| Contextual enrichment | Yes (full transcript) | ? | Check |
| Truncation logging | ? | ? | Check |
| Status tracking | Yes | ? | Check |
| ... | ... | ... | ... |

### Contract Status
| Contract | Status | Evidence |
|----------|--------|----------|
| PAR-001  | PASS/BROKEN | [specific finding] |
| PAR-002  | PASS/BROKEN | [specific finding] |

### Features Missing from Document Pipeline
[List any features present in video pipeline but absent from document pipeline]

### Recommended Fixes
[Prioritized list of parity gaps to close]
```
