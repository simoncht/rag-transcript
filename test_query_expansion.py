#!/usr/bin/env python3
"""
Test Query Expansion with Live Queries

Sends test queries through the API and monitors logs for query expansion metrics.
"""
import requests
import time
import json

# Configuration
API_BASE = "http://localhost:8000/api/v1"
CONVERSATION_ID = "5186f68f-2e8a-4a48-ba02-4beb849e1220"
USER_ID = "9f3ab92f-b6ed-437f-b6a0-df84600a9947"

# Test queries designed to benefit from query expansion
TEST_QUERIES = [
    {
        "query": "What is the purpose of the Great Pyramid?",
        "description": "Factual question - should generate variants about pyramid function, significance, role"
    },
    {
        "query": "How does consciousness affect reality?",
        "description": "Abstract concept - should generate variants about awareness, perception, manifestation"
    },
    {
        "query": "Tell me about spiritual practices",
        "description": "Broad topic - should generate variants about meditation, techniques, exercises"
    }
]

def send_message(query: str) -> dict:
    """Send a message to the conversation API."""
    url = f"{API_BASE}/conversations/{CONVERSATION_ID}/messages"

    payload = {
        "message": query,
        "mode": "default"
    }

    headers = {
        "Content-Type": "application/json",
        "X-User-ID": USER_ID  # Simple auth for testing
    }

    print(f"\n{'='*80}")
    print(f"📤 Sending Query: {query}")
    print(f"{'='*80}\n")

    start_time = time.time()

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        elapsed = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Response received in {elapsed:.2f}s")
            print(f"   Response length: {len(data.get('content', ''))} chars")
            print(f"   Citations: {len(data.get('chunk_references', []))}")
            print(f"   Token count: {data.get('token_count', 0)}")
            return data
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"   {response.text}")
            return None

    except Exception as e:
        print(f"❌ Exception: {e}")
        return None

def main():
    print("🧪 Testing Query Expansion with Live Queries")
    print(f"Conversation ID: {CONVERSATION_ID}")
    print(f"API Base: {API_BASE}")
    print(f"\n📋 Will test {len(TEST_QUERIES)} queries\n")

    # Wait a moment for user to start watching logs
    print("💡 TIP: In another terminal, run:")
    print('   docker compose logs -f app | grep -E "\\[Query Expansion\\]|\\[Multi-Query\\]|\\[RAG Pipeline Complete\\]"')
    print("\nStarting tests in 3 seconds...\n")
    time.sleep(3)

    results = []

    for i, test_case in enumerate(TEST_QUERIES, 1):
        print(f"\n{'#'*80}")
        print(f"Test {i}/{len(TEST_QUERIES)}: {test_case['description']}")
        print(f"{'#'*80}")

        result = send_message(test_case['query'])

        if result:
            results.append({
                'query': test_case['query'],
                'description': test_case['description'],
                'success': True,
                'citations': len(result.get('chunk_references', [])),
                'token_count': result.get('token_count', 0)
            })
        else:
            results.append({
                'query': test_case['query'],
                'description': test_case['description'],
                'success': False
            })

        # Wait between queries
        if i < len(TEST_QUERIES):
            print("\n⏳ Waiting 2 seconds before next query...\n")
            time.sleep(2)

    # Summary
    print(f"\n{'='*80}")
    print("📊 TEST SUMMARY")
    print(f"{'='*80}\n")

    success_count = sum(1 for r in results if r['success'])
    print(f"Total Queries: {len(results)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {len(results) - success_count}")

    if success_count > 0:
        print("\n📈 Results:")
        for i, r in enumerate(results, 1):
            if r['success']:
                print(f"  {i}. {r['query'][:50]}...")
                print(f"     Citations: {r['citations']}, Tokens: {r['token_count']}")

    print(f"\n✅ Testing complete! Check the logs above for query expansion metrics.\n")

if __name__ == "__main__":
    main()
