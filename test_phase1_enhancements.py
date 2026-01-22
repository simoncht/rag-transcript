#!/usr/bin/env python3
"""
Test script to verify Phase 1 citation enhancements.
Tests that the API returns speakers, chapter_title, and channel_name in chunk references.
"""
import requests
import json

API_BASE = "http://localhost:8000"
CONVERSATION_ID = "5186f68f-2e8a-4a48-ba02-4beb849e1220"

def test_conversation_detail():
    """Test that conversation detail endpoint returns new fields."""
    print(f"Testing conversation detail API...")
    url = f"{API_BASE}/conversations/{CONVERSATION_ID}"
    response = requests.get(url)

    if response.status_code != 200:
        print(f"❌ Failed to fetch conversation: {response.status_code}")
        return False

    data = response.json()
    messages = data.get("messages", [])

    print(f"✓ Found {len(messages)} messages")

    # Check assistant messages for chunk references
    assistant_messages = [m for m in messages if m.get("role") == "assistant"]
    print(f"✓ Found {len(assistant_messages)} assistant messages")

    total_refs = 0
    refs_with_channel = 0
    refs_with_chapter = 0
    refs_with_speakers = 0

    for msg in assistant_messages:
        chunk_refs = msg.get("chunk_references", [])
        total_refs += len(chunk_refs)

        for ref in chunk_refs:
            # Check if new fields are present
            if ref.get("channel_name"):
                refs_with_channel += 1
                print(f"  ✓ Found channel_name: {ref['channel_name']}")

            if ref.get("chapter_title"):
                refs_with_chapter += 1
                print(f"  ✓ Found chapter_title: {ref['chapter_title']}")

            if ref.get("speakers") and len(ref["speakers"]) > 0:
                refs_with_speakers += 1
                print(f"  ✓ Found speakers: {ref['speakers']}")

    print(f"\n📊 Summary:")
    print(f"  Total chunk references: {total_refs}")
    print(f"  References with channel_name: {refs_with_channel}/{total_refs}")
    print(f"  References with chapter_title: {refs_with_chapter}/{total_refs}")
    print(f"  References with speakers: {refs_with_speakers}/{total_refs}")

    # Show a sample reference
    if assistant_messages and assistant_messages[0].get("chunk_references"):
        sample_ref = assistant_messages[0]["chunk_references"][0]
        print(f"\n📋 Sample chunk reference:")
        print(json.dumps(sample_ref, indent=2))

    return True

def test_send_message():
    """Test that sending a new message returns new fields."""
    print(f"\nTesting send message API...")
    url = f"{API_BASE}/conversations/{CONVERSATION_ID}/messages"

    payload = {
        "message": "What is this video about?",
        "stream": False
    }

    response = requests.post(url, json=payload)

    if response.status_code != 200:
        print(f"❌ Failed to send message: {response.status_code}")
        print(response.text)
        return False

    data = response.json()
    chunk_refs = data.get("chunk_references", [])

    print(f"✓ Message sent successfully")
    print(f"✓ Received {len(chunk_refs)} chunk references")

    # Check for new fields
    has_channel = any(ref.get("channel_name") for ref in chunk_refs)
    has_chapter = any(ref.get("chapter_title") for ref in chunk_refs)
    has_speakers = any(ref.get("speakers") and len(ref["speakers"]) > 0 for ref in chunk_refs)

    print(f"  Channel names present: {has_channel}")
    print(f"  Chapter titles present: {has_chapter}")
    print(f"  Speakers present: {has_speakers}")

    if chunk_refs:
        print(f"\n📋 Sample chunk reference:")
        print(json.dumps(chunk_refs[0], indent=2))

    return True

if __name__ == "__main__":
    print("=" * 60)
    print("Phase 1 Citation Enhancement Test")
    print("=" * 60)
    print()

    try:
        success = test_conversation_detail()
        if success:
            print("\n" + "=" * 60)
            # Uncomment to test sending a message
            # test_send_message()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
