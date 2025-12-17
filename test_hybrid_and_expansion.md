# Testing Hybrid Search & Query Expansion

## ✅ **System Status**

- App is running on http://localhost:8000
- Frontend is running on http://localhost:3000
- Both features are ENABLED in .env

---

## 🧪 **How to Test**

### Option 1: Using the Frontend (Recommended)

1. **Open your browser**: http://localhost:3000

2. **Create or open a conversation**:
   - Go to "Conversations" page
   - Click "+ New conversation"
   - Select one or more videos (you have 6 Bashar videos available)

3. **Test different query types**:

#### **Test 1: Keyword Query** (Tests Hybrid Search)
**Query**: `What specific topics are discussed?`
**Why**: Contains keywords "specific", "topics", "discussed"
**Expected**: BM25 should find exact keyword matches alongside semantic matches

**Check logs**:
```bash
docker-compose logs -f app | findstr "Hybrid search"
# Look for: "Hybrid search: combined semantic + BM25 results"
```

#### **Test 2: Vague Query** (Tests Query Expansion)
**Query**: `Tell me about the teachings`
**Why**: Vague question that can be rephrased many ways
**Expected**: Query expansion will generate variations like:
- "Tell me about the teachings"
- "What is about the teachings?"
- "What are the teachings?"

**Check logs**:
```bash
docker-compose logs -f app | findstr "Query expansion"
# Look for: "Query expansion (simple): 3 variations"
```

#### **Test 3: Specific Technical Query** (Tests Both)
**Query**: `What is the silent season?`
**Why**: Specific term that should benefit from both features
**Expected**:
- Query expansion: "What are the silent season?", "Define silent season"
- Hybrid search: Exact match on "silent season" + conceptual matches

---

### Option 2: Using cURL (Direct API Testing)

First, get a conversation ID with videos:

```bash
# List conversations
curl -s http://localhost:8000/api/v1/conversations \
  -H "Authorization: Bearer mock-token-user-123" | python -m json.tool

# Note the conversation ID from the output
```

Then send test queries:

```bash
# Set conversation ID (replace with yours)
CONV_ID="your-conversation-id-here"

# Test 1: Keyword query (Hybrid Search)
curl -s http://localhost:8000/api/v1/conversations/$CONV_ID/messages \
  -H "Authorization: Bearer mock-token-user-123" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What specific topics are discussed?",
    "stream": false
  }' | python -m json.tool

# Test 2: Vague query (Query Expansion)
curl -s http://localhost:8000/api/v1/conversations/$CONV_ID/messages \
  -H "Authorization: Bearer mock-token-user-123" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Tell me about the teachings",
    "stream": false
  }' | python -m json.tool
```

---

## 📊 **What to Look For**

### In the Response

1. **Better relevance scores**: Should be higher with hybrid search
2. **More diverse chunks**: Query expansion catches different phrasings
3. **Citations**: Check if cited chunks actually contain relevant content

### In the Logs

**Monitor logs in real-time**:
```bash
docker-compose logs -f app | findstr "Query expansion\|Hybrid search\|INFO"
```

**Expected log output**:
```
2025-12-11 18:XX:XX - app.api.routes.conversations - INFO - Query expansion (simple): 3 variations
2025-12-11 18:XX:XX - app.services.hybrid_search - INFO - Hybrid search: 10 semantic + 8 BM25 → 10 fused results
2025-12-11 18:XX:XX - app.api.routes.conversations - INFO - Hybrid search: combined semantic + BM25 results
```

---

## 🔍 **Performance Monitoring**

Monitor response times:

```bash
# Time a chat query
time curl -s http://localhost:8000/api/v1/conversations/$CONV_ID/messages \
  -H "Authorization: Bearer mock-token-user-123" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is open contact?",
    "stream": false
  }' > /dev/null
```

**Expected**: ~18-19 seconds total (vs 18 seconds without features)

---

## 🎯 **Good Test Queries for Your Content**

Based on your Bashar channeling videos:

### Keyword-Heavy (Tests Hybrid Search)
1. "What is the **silent season**?" (exact term)
2. "Tell me about **3i Atlas**" (specific name)
3. "What is **open contact**?" (specific concept)
4. "Explain the **2026** predictions" (specific year)

### Vague/Ambiguous (Tests Query Expansion)
1. "What are the teachings?" (generic)
2. "Tell me about the main ideas" (very vague)
3. "Explain the message" (ambiguous)
4. "What should I know?" (open-ended)

### Combined Benefit
1. "How do we prepare for 2026?" (specific term + vague action)
2. "What is Bashar's advice?" (name + general concept)
3. "Tell me about channeling techniques" (general + specific domain)

---

## 🐛 **Troubleshooting**

### Not seeing "Hybrid search" in logs?

Check if it's enabled:
```bash
grep ENABLE_HYBRID_SEARCH backend/.env
# Should show: ENABLE_HYBRID_SEARCH=True
```

If False, enable it:
```bash
# Edit backend/.env
ENABLE_HYBRID_SEARCH=True
# Then restart: docker-compose restart app worker
```

### Not seeing "Query expansion" in logs?

Check if it's enabled:
```bash
grep ENABLE_QUERY_EXPANSION backend/.env
# Should show: ENABLE_QUERY_EXPANSION=True
```

### Seeing errors in logs?

```bash
docker-compose logs app | tail -50
```

---

## 📈 **Comparing Results**

### Baseline (Features Disabled)

1. Temporarily disable both features:
```bash
# Edit backend/.env
ENABLE_HYBRID_SEARCH=False
ENABLE_QUERY_EXPANSION=False
```

2. Restart:
```bash
docker-compose restart app worker
```

3. Run a test query and note the results

4. Re-enable features:
```bash
# Edit backend/.env
ENABLE_HYBRID_SEARCH=True
ENABLE_QUERY_EXPANSION=True
```

5. Restart:
```bash
docker-compose restart app worker
```

6. Run the SAME query and compare:
   - Response quality
   - Chunk relevance
   - Citation accuracy

---

## ✅ **Success Criteria**

You'll know it's working when:

1. ✅ Logs show: "Query expansion (simple): 3 variations"
2. ✅ Logs show: "Hybrid search: combined semantic + BM25 results"
3. ✅ Keyword queries return chunks with exact term matches
4. ✅ Vague queries still return relevant results
5. ✅ Response time is still under 20 seconds
6. ✅ Citations are more accurate/relevant than before

---

## 🎬 **Quick Start: Test Right Now**

1. Open frontend: http://localhost:3000
2. Go to Conversations → New conversation
3. Select any Bashar video
4. Ask: **"What is the silent season?"**
5. Watch the logs: `docker-compose logs -f app | findstr "expansion\|Hybrid"`
6. Check the response quality!

---

## 📝 **Report Findings**

After testing, note:
- Which queries improved the most?
- Did you notice better chunk relevance?
- Were there any errors or issues?
- How was the response time?

This feedback will help us fine-tune the weights and parameters!
