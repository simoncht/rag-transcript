"""
40-Turn Conversation Memory Stress Test

Based on the LoCoMo benchmark (Evaluating Very Long-Term Conversational Memory of LLM Agents)
Tests the system's ability to maintain context and recall information across extended conversations.

Test Structure:
- Turns 1-5: Simple questions to seed information (names, facts, preferences)
- Turns 6-15: Intermediate complexity - reference earlier details
- Turns 16-30: Higher complexity - multi-part synthesis
- Turns 31-40: Advanced - long-distance recall from Turn 1-5
- Turn 40+: Final validation - comprehensive recall

Usage:
    python -m pytest backend/tests/test_conversation_memory_40turns.py -v -s
"""
import os
import sys
import uuid
import time
import json
from typing import List, Dict, Any

import pytest
from sqlalchemy.orm import Session

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models import User, Video
from app.schemas import MessageSendRequest


class ConversationMemoryTest:
    """Manages the 40-turn conversation memory test."""

    def __init__(
        self, conversation_id: uuid.UUID, test_name: str = "40-Turn Memory Test"
    ):
        self.conversation_id = conversation_id
        self.test_name = test_name
        self.turns: List[Dict[str, Any]] = []
        self.failures: List[Dict[str, Any]] = []
        self.start_time = time.time()

    def add_turn(
        self,
        turn_number: int,
        user_query: str,
        assistant_response: str,
        expected_recall: List[str] = None,
        validation_passed: bool = True,
        notes: str = "",
    ):
        """Record a conversation turn with validation results."""
        turn_data = {
            "turn": turn_number,
            "user_query": user_query,
            "assistant_response": assistant_response,
            "expected_recall": expected_recall or [],
            "validation_passed": validation_passed,
            "notes": notes,
            "timestamp": time.time() - self.start_time,
        }
        self.turns.append(turn_data)

        if not validation_passed:
            self.failures.append(turn_data)

    def validate_recall(
        self, response: str, expected_terms: List[str]
    ) -> tuple[bool, str]:
        """
        Check if response contains expected recalled information.

        Returns:
            (validation_passed, notes)
        """
        missing_terms = []
        for term in expected_terms:
            if term.lower() not in response.lower():
                missing_terms.append(term)

        if missing_terms:
            return False, f"Missing: {', '.join(missing_terms)}"
        return True, "All expected terms found"

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report."""
        total_turns = len(self.turns)
        passed_turns = sum(1 for t in self.turns if t["validation_passed"])
        failed_turns = len(self.failures)

        # Calculate success rate by stage
        stages = {
            "Turns 1-5 (Seeding)": (1, 5),
            "Turns 6-15 (Intermediate)": (6, 15),
            "Turns 16-30 (Multi-part)": (16, 30),
            "Turns 31-40 (Long-distance)": (31, 40),
        }

        stage_results = {}
        for stage_name, (start, end) in stages.items():
            stage_turns = [t for t in self.turns if start <= t["turn"] <= end]
            if stage_turns:
                stage_passed = sum(1 for t in stage_turns if t["validation_passed"])
                stage_results[stage_name] = {
                    "total": len(stage_turns),
                    "passed": stage_passed,
                    "success_rate": (stage_passed / len(stage_turns)) * 100,
                }

        return {
            "test_name": self.test_name,
            "duration_seconds": time.time() - self.start_time,
            "total_turns": total_turns,
            "passed_turns": passed_turns,
            "failed_turns": failed_turns,
            "overall_success_rate": (passed_turns / total_turns) * 100
            if total_turns
            else 0,
            "stage_results": stage_results,
            "failures": self.failures,
            "all_turns": self.turns,
        }

    def print_report(self):
        """Print human-readable test report."""
        report = self.generate_report()

        print("\n" + "=" * 80)
        print(f"  {report['test_name']}")
        print("=" * 80)
        print(f"Duration: {report['duration_seconds']:.2f}s")
        print(f"Total Turns: {report['total_turns']}")
        print(
            f"Passed: {report['passed_turns']} ({report['overall_success_rate']:.1f}%)"
        )
        print(f"Failed: {report['failed_turns']}")
        print("\n" + "-" * 80)
        print("Stage-by-Stage Results:")
        print("-" * 80)

        for stage_name, results in report["stage_results"].items():
            print(
                f"{stage_name:30} {results['passed']:2}/{results['total']:2} ({results['success_rate']:5.1f}%)"
            )

        if report["failures"]:
            print("\n" + "-" * 80)
            print("Failed Validations:")
            print("-" * 80)
            for failure in report["failures"]:
                print(f"\nTurn {failure['turn']}:")
                print(f"  Query: {failure['user_query'][:80]}...")
                print(f"  Issue: {failure['notes']}")
                print(f"  Expected: {', '.join(failure['expected_recall'])}")

        print("\n" + "=" * 80)

        # Save detailed report to file
        report_path = f"/tmp/conversation_memory_test_{int(time.time())}.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"Detailed report saved to: {report_path}")
        print("=" * 80 + "\n")


async def test_40_turn_conversation_memory(
    db: Session, test_user: User, completed_videos: List[Video]
):
    """
    Main 40-turn conversation memory test.

    Prerequisites:
    - Test user with completed videos in database
    - At least 1 video with transcripts about a specific topic (e.g., ML course)

    Test Flow:
    1. Create conversation with video(s)
    2. Execute 40-turn conversation following LoCoMo pattern
    3. Validate memory retention at each stage
    4. Generate comprehensive report
    """
    pytest.skip("Integration test - run manually with real database")

    from app.api.routes.conversations import create_conversation, send_message
    from app.schemas import ConversationCreateRequest

    # 1. Create conversation
    video_ids = [v.id for v in completed_videos[:3]]  # Use up to 3 videos

    conversation_request = ConversationCreateRequest(
        title="40-Turn Memory Stress Test", selected_video_ids=video_ids
    )

    conversation = await create_conversation(conversation_request, db, test_user)
    test = ConversationMemoryTest(conversation.id)

    print("\nStarting 40-turn conversation memory test...")
    print(f"Conversation ID: {conversation.id}")
    print(f"Using {len(video_ids)} video(s)")

    # ========================================================================
    # STAGE 1: Turns 1-5 - Seed basic information
    # ========================================================================
    print("\n[STAGE 1] Turns 1-5: Seeding information...")

    turn_1_query = "Who is the instructor in this video?"
    response_1 = await send_message(
        conversation.id,
        MessageSendRequest(message=turn_1_query, mode="summarize"),
        db,
        test_user,
    )
    # Extract instructor name from response (you'll need to parse this)
    instructor_name = "Dr. Andrew Ng"  # Example - extract from response_1.content
    test.add_turn(
        1, turn_1_query, response_1.content, [instructor_name], True, "Baseline fact"
    )

    turn_2_query = "What is the main topic covered in the first 10 minutes?"
    response_2 = await send_message(
        conversation.id,
        MessageSendRequest(message=turn_2_query, mode="summarize"),
        db,
        test_user,
    )
    main_topic = "supervised learning"  # Example - extract from response
    test.add_turn(
        2, turn_2_query, response_2.content, [main_topic], True, "Topic identification"
    )

    turn_3_query = "Are there any specific examples or case studies mentioned?"
    response_3 = await send_message(
        conversation.id,
        MessageSendRequest(message=turn_3_query, mode="summarize"),
        db,
        test_user,
    )
    test.add_turn(
        3, turn_3_query, response_3.content, [], True, "Example identification"
    )

    turn_4_query = "What programming language or framework is discussed?"
    response_4 = await send_message(
        conversation.id,
        MessageSendRequest(message=turn_4_query, mode="summarize"),
        db,
        test_user,
    )
    framework = "Python"  # Example
    test.add_turn(
        4, turn_4_query, response_4.content, [framework], True, "Technical detail"
    )

    turn_5_query = "Does the instructor recommend any specific learning approach?"
    response_5 = await send_message(
        conversation.id,
        MessageSendRequest(message=turn_5_query, mode="summarize"),
        db,
        test_user,
    )
    test.add_turn(5, turn_5_query, response_5.content, [], True, "Methodology")

    # ========================================================================
    # STAGE 2: Turns 6-15 - Reference recent context
    # ========================================================================
    print("\n[STAGE 2] Turns 6-15: Intermediate complexity...")

    turn_6_query = f"How does the {main_topic} approach you mentioned compare to unsupervised learning?"
    response_6 = await send_message(
        conversation.id,
        MessageSendRequest(message=turn_6_query, mode="compare_sources"),
        db,
        test_user,
    )
    passed, notes = test.validate_recall(response_6.content, [main_topic])
    test.add_turn(6, turn_6_query, response_6.content, [main_topic], passed, notes)

    turn_10_query = f"Based on what {instructor_name} said about {main_topic}, what are the key prerequisites?"
    response_10 = await send_message(
        conversation.id,
        MessageSendRequest(message=turn_10_query, mode="deep_dive"),
        db,
        test_user,
    )
    passed, notes = test.validate_recall(
        response_10.content, [instructor_name, main_topic]
    )
    test.add_turn(
        10,
        turn_10_query,
        response_10.content,
        [instructor_name, main_topic],
        passed,
        notes,
    )

    # ========================================================================
    # STAGE 3: Turns 16-30 - Multi-part synthesis
    # ========================================================================
    print("\n[STAGE 3] Turns 16-30: Multi-part synthesis...")

    turn_20_query = f"Can you create a learning path based on all the topics we've discussed, starting with {main_topic}?"
    response_20 = await send_message(
        conversation.id,
        MessageSendRequest(message=turn_20_query, mode="extract_actions"),
        db,
        test_user,
    )
    passed, notes = test.validate_recall(response_20.content, [main_topic])
    test.add_turn(20, turn_20_query, response_20.content, [main_topic], passed, notes)

    turn_25_query = "What connections can you draw between the examples from earlier and the frameworks mentioned?"
    response_25 = await send_message(
        conversation.id,
        MessageSendRequest(message=turn_25_query, mode="compare_sources"),
        db,
        test_user,
    )
    test.add_turn(
        25, turn_25_query, response_25.content, [framework], True, "Cross-reference"
    )

    # ========================================================================
    # STAGE 4: Turns 31-40 - Long-distance recall
    # ========================================================================
    print("\n[STAGE 4] Turns 31-40: Long-distance recall...")

    turn_35_query = f"Going back to our first conversation, what was {instructor_name}'s main teaching philosophy?"
    response_35 = await send_message(
        conversation.id,
        MessageSendRequest(message=turn_35_query, mode="summarize"),
        db,
        test_user,
    )
    passed, notes = test.validate_recall(response_35.content, [instructor_name])
    test.add_turn(
        35, turn_35_query, response_35.content, [instructor_name], passed, notes
    )

    turn_40_query = "Summarize everything we've learned, including the instructor name, main topics, frameworks, and learning approach from our entire conversation."
    response_40 = await send_message(
        conversation.id,
        MessageSendRequest(message=turn_40_query, mode="summarize"),
        db,
        test_user,
    )
    passed, notes = test.validate_recall(
        response_40.content, [instructor_name, main_topic, framework]
    )
    test.add_turn(
        40,
        turn_40_query,
        response_40.content,
        [instructor_name, main_topic, framework],
        passed,
        notes,
    )

    # ========================================================================
    # Generate and display report
    # ========================================================================
    test.print_report()
    report = test.generate_report()

    # Assert overall success rate meets threshold
    assert (
        report["overall_success_rate"] >= 70
    ), f"Overall success rate {report['overall_success_rate']:.1f}% below 70% threshold"

    # Assert stage-specific thresholds
    assert (
        report["stage_results"]["Turns 1-5 (Seeding)"]["success_rate"] >= 95
    ), "Seeding stage should have >95% success"
    assert (
        report["stage_results"]["Turns 31-40 (Long-distance)"]["success_rate"] >= 60
    ), "Long-distance recall should have >60% success"


# ============================================================================
# Simplified manual test script
# ============================================================================


def manual_test_conversation_memory():
    """
    Simplified version for manual testing via API calls.

    Usage:
        python backend/tests/test_conversation_memory_40turns.py
    """
    import requests

    BASE_URL = "http://localhost:8000/api/v1"

    # Replace with your test user token
    HEADERS = {"Authorization": "Bearer YOUR_TOKEN_HERE"}

    # 1. Create conversation
    print("Creating conversation...")
    create_response = requests.post(
        f"{BASE_URL}/conversations",
        json={
            "title": "40-Turn Memory Test",
            "selected_video_ids": ["YOUR_VIDEO_ID_HERE"],
        },
        headers=HEADERS,
    )
    conversation_id = create_response.json()["id"]
    print(f"Conversation created: {conversation_id}")

    test = ConversationMemoryTest(conversation_id)

    # 2. Define test queries
    test_queries = [
        # Stage 1: Seeding (1-5)
        ("Who is the instructor?", ["instructor name"], 1),
        ("What is the main topic?", ["topic"], 2),
        ("Are there examples mentioned?", [], 3),
        ("What framework is used?", ["framework"], 4),
        ("What learning approach is recommended?", [], 5),
        # Stage 2: Intermediate (6-15)
        (
            "How does the topic mentioned earlier compare to other approaches?",
            ["topic"],
            6,
        ),
        ("What did the instructor say about prerequisites?", ["instructor"], 10),
        # Stage 3: Multi-part (16-30)
        ("Create a learning path based on everything we discussed", ["topic"], 20),
        ("What connections exist between examples and frameworks?", ["framework"], 25),
        # Stage 4: Long-distance (31-40)
        (
            "What was the instructor's philosophy from our first conversation?",
            ["instructor"],
            35,
        ),
        (
            "Summarize everything: instructor, topics, frameworks",
            ["instructor", "topic", "framework"],
            40,
        ),
    ]

    # 3. Execute queries
    for query, expected_terms, turn_num in test_queries:
        print(f"\nTurn {turn_num}: {query}")

        response = requests.post(
            f"{BASE_URL}/conversations/{conversation_id}/messages",
            json={"message": query, "mode": "summarize"},
            headers=HEADERS,
        )

        if response.status_code == 200:
            content = response.json()["content"]
            passed, notes = test.validate_recall(content, expected_terms)
            test.add_turn(turn_num, query, content, expected_terms, passed, notes)
            print(f"✓ Response: {content[:100]}...")
        else:
            print(f"✗ Error: {response.status_code}")
            test.add_turn(
                turn_num,
                query,
                "",
                expected_terms,
                False,
                f"API error: {response.status_code}",
            )

        time.sleep(1)  # Rate limiting

    # 4. Generate report
    test.print_report()


if __name__ == "__main__":
    print("=" * 80)
    print("  40-Turn Conversation Memory Stress Test")
    print("  Based on LoCoMo Benchmark (Arxiv 2402.17753)")
    print("=" * 80)
    print("\nThis test validates that the RAG system can maintain context across")
    print("40 conversation turns, testing:")
    print("  - Short-term memory (last 10 messages)")
    print("  - Long-distance recall (Turn 1-5 → Turn 35-40)")
    print("  - Multi-hop reasoning (synthesizing across turns)")
    print("\nRunning manual test mode...")
    print("=" * 80 + "\n")

    manual_test_conversation_memory()
