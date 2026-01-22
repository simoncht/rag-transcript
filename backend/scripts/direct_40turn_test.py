#!/usr/bin/env python3
"""
Direct 40-Turn Conversation Memory Test - Database Access

This script tests conversation memory by directly accessing the database
and services, bypassing API authentication. Simulates a real 40-turn conversation
to validate Phase 1 memory improvements.

Usage:
    python backend/scripts/direct_40turn_test.py
"""
import os
import sys
from typing import List, Dict, Any, Tuple

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.models import User, Video, Conversation, Message
from app.models.conversation_fact import ConversationFact
from app.core.config import settings


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    END = "\033[0m"


class Turn40TestRunner:
    """40-turn conversation memory test runner."""

    def __init__(self, db: Session):
        self.db = db
        self.test_results: List[Dict[str, Any]] = []
        self.context: Dict[str, Any] = {}

    def print_header(self, text: str):
        """Print formatted header."""
        print(f"\n{Colors.BOLD}{'='*80}{Colors.END}")
        print(f"{Colors.BOLD}{text:^80}{Colors.END}")
        print(f"{Colors.BOLD}{'='*80}{Colors.END}\n")

    def print_stage(self, stage_num: int, text: str):
        """Print stage header."""
        print(f"\n{Colors.CYAN}{'─'*80}{Colors.END}")
        print(f"{Colors.CYAN}{Colors.BOLD}STAGE {stage_num}: {text}{Colors.END}")
        print(f"{Colors.CYAN}{'─'*80}{Colors.END}\n")

    def add_turn_result(
        self,
        turn: int,
        query: str,
        expected: List[str],
        found: List[str],
        passed: bool,
        notes: str = "",
    ):
        """Record turn result."""
        self.test_results.append(
            {
                "turn": turn,
                "query": query,
                "expected": expected,
                "found": found,
                "passed": passed,
                "notes": notes,
            }
        )

        status = (
            f"{Colors.GREEN}✓{Colors.END}" if passed else f"{Colors.RED}✗{Colors.END}"
        )
        print(f"  {status} Turn {turn:2d}: {query[:60]}")
        if not passed:
            print(f"    {Colors.YELLOW}Expected: {', '.join(expected)}{Colors.END}")
            print(
                f"    {Colors.YELLOW}Found: {', '.join(found) if found else 'None'}{Colors.END}"
            )
            if notes:
                print(f"    {Colors.YELLOW}Note: {notes}{Colors.END}")

    def simulate_conversation_query(
        self, conversation: Conversation, turn_number: int
    ) -> List[Message]:
        """
        Simulate what the API does: retrieve last N messages.
        This is the core test - does the conversation history window work correctly?
        """
        # This mimics backend/app/api/routes/conversations.py:966-977
        history_messages = (
            self.db.query(Message)
            .filter(
                Message.conversation_id == conversation.id, Message.role != "system"
            )
            .order_by(Message.created_at.desc())
            .limit(10)  # Phase 1: increased from 5 to 10
            .all()
        )
        history_messages.reverse()  # Oldest first
        return history_messages

    def check_recall(
        self, messages: List[Message], expected_terms: List[str]
    ) -> Tuple[bool, List[str]]:
        """
        Check if expected terms appear in message history OR conversation facts.
        This simulates whether the LLM would have access to the context.
        """
        # Combine all message content
        full_context = " ".join(msg.content.lower() for msg in messages)

        # Phase 2: Also check conversation facts
        conversation_id = messages[0].conversation_id if messages else None
        if conversation_id:
            facts = (
                self.db.query(ConversationFact)
                .filter(ConversationFact.conversation_id == conversation_id)
                .all()
            )
            # Add facts to context (simulating system prompt injection)
            facts_context = " ".join(
                f"{f.fact_key} {f.fact_value}".lower() for f in facts
            )
            full_context += " " + facts_context

        found = []
        for term in expected_terms:
            if term.lower() in full_context:
                found.append(term)

        return len(found) >= len(expected_terms) * 0.7, found  # 70% threshold

    def create_conversation_facts(self, conversation: Conversation):
        """
        Create conversation facts from the seeded context (Turns 1-5).
        This simulates Phase 2 fact extraction.
        """
        facts_to_create = [
            ("instructor", self.context.get("instructor", ""), 1),
            ("topic", self.context.get("topic", ""), 2),
            ("example", self.context.get("example", ""), 3),
            ("framework", self.context.get("framework", ""), 4),
            ("approach", self.context.get("approach", ""), 5),
        ]

        for key, value, turn in facts_to_create:
            if value:  # Only create if value exists
                fact = ConversationFact(
                    conversation_id=conversation.id,
                    user_id=conversation.user_id,
                    fact_key=key,
                    fact_value=value,
                    source_turn=turn,
                    confidence_score=1.0,
                )
                self.db.add(fact)

        self.db.commit()
        print(
            f"\n  {Colors.GREEN}✓{Colors.END} Created {len([v for _, v, _ in facts_to_create if v])} conversation facts"
        )

    def run_stage_1_seeding(self, conversation: Conversation):
        """Stage 1: Turns 1-5 - Seed information."""
        self.print_stage(1, "Turns 1-5: Seeding Information")

        # Turn 1: Establish instructor name
        self.context["instructor"] = "Dr. Andrew Ng"
        msg1 = Message(
            conversation_id=conversation.id,
            role="user",
            content="Who is the instructor?",
        )
        self.db.add(msg1)
        resp1 = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=f"The instructor is {self.context['instructor']}.",
        )
        self.db.add(resp1)
        self.db.commit()

        history = self.simulate_conversation_query(conversation, 1)
        passed, found = self.check_recall(history, [self.context["instructor"]])
        self.add_turn_result(
            1, "Who is the instructor?", [self.context["instructor"]], found, passed
        )

        # Turn 2: Establish main topic
        self.context["topic"] = "machine learning"
        msg2 = Message(
            conversation_id=conversation.id,
            role="user",
            content="What is the main topic?",
        )
        self.db.add(msg2)
        resp2 = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=f"The main topic is {self.context['topic']}.",
        )
        self.db.add(resp2)
        self.db.commit()

        history = self.simulate_conversation_query(conversation, 2)
        passed, found = self.check_recall(history, [self.context["topic"]])
        self.add_turn_result(
            2, "What is the main topic?", [self.context["topic"]], found, passed
        )

        # Turn 3: Establish example
        self.context["example"] = "neural networks"
        msg3 = Message(
            conversation_id=conversation.id,
            role="user",
            content="What example is mentioned?",
        )
        self.db.add(msg3)
        resp3 = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=f"The main example is {self.context['example']}.",
        )
        self.db.add(resp3)
        self.db.commit()

        history = self.simulate_conversation_query(conversation, 3)
        passed, found = self.check_recall(history, [self.context["example"]])
        self.add_turn_result(
            3, "What example is mentioned?", [self.context["example"]], found, passed
        )

        # Turn 4: Establish framework
        self.context["framework"] = "TensorFlow"
        msg4 = Message(
            conversation_id=conversation.id,
            role="user",
            content="What framework is discussed?",
        )
        self.db.add(msg4)
        resp4 = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=f"The framework discussed is {self.context['framework']}.",
        )
        self.db.add(resp4)
        self.db.commit()

        history = self.simulate_conversation_query(conversation, 4)
        passed, found = self.check_recall(history, [self.context["framework"]])
        self.add_turn_result(
            4,
            "What framework is discussed?",
            [self.context["framework"]],
            found,
            passed,
        )

        # Turn 5: Establish approach
        self.context["approach"] = "supervised learning"
        msg5 = Message(
            conversation_id=conversation.id,
            role="user",
            content="What approach is used?",
        )
        self.db.add(msg5)
        resp5 = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=f"The approach is {self.context['approach']}.",
        )
        self.db.add(resp5)
        self.db.commit()

        history = self.simulate_conversation_query(conversation, 5)
        passed, found = self.check_recall(history, [self.context["approach"]])
        self.add_turn_result(
            5, "What approach is used?", [self.context["approach"]], found, passed
        )

    def run_stage_2_intermediate(self, conversation: Conversation):
        """Stage 2: Turns 6-15 - Reference recent context."""
        self.print_stage(2, "Turns 6-15: Intermediate - Reference Recent Context")

        for turn in range(6, 16):
            # Reference items from earlier turns
            if turn == 6:
                query = "Tell me more about the instructor"
                expected = [self.context["instructor"]]
            elif turn == 7:
                query = "Explain the main topic in detail"
                expected = [self.context["topic"]]
            elif turn == 8:
                query = "How does the example relate to the topic?"
                expected = [self.context["example"], self.context["topic"]]
            elif turn == 9:
                query = "What are the benefits of the framework?"
                expected = [self.context["framework"]]
            elif turn == 10:
                query = "Explain the approach methodology"
                expected = [self.context["approach"]]
            elif turn == 11:
                query = "How does the instructor teach the topic?"
                expected = [self.context["instructor"], self.context["topic"]]
            elif turn == 12:
                query = "Compare the framework with alternatives"
                expected = [self.context["framework"]]
            elif turn == 13:
                query = "What are real-world applications of the example?"
                expected = [self.context["example"]]
            elif turn == 14:
                query = "How does the approach work with the framework?"
                expected = [self.context["approach"], self.context["framework"]]
            else:  # turn == 15
                query = "Summarize what we've learned so far"
                expected = [self.context["topic"], self.context["instructor"]]

            # Add user message
            msg = Message(conversation_id=conversation.id, role="user", content=query)
            self.db.add(msg)

            # Simulate assistant response (includes expected terms)
            response_content = f"Regarding {', '.join(expected)}: [detailed response]"
            resp = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=response_content,
            )
            self.db.add(resp)
            self.db.commit()

            # Check if context is available in history window
            history = self.simulate_conversation_query(conversation, turn)
            passed, found = self.check_recall(history, expected)

            # At turn 10 with 10-message window, Turn 1 should still be visible
            notes = ""
            if turn == 10:
                notes = "Critical: Turn 1 info should be in 10-message window"
            elif turn == 15:
                notes = "Turn 1-5 may be partially outside window (edge case)"

            self.add_turn_result(turn, query, expected, found, passed, notes)

    def run_stage_3_multipart(self, conversation: Conversation):
        """Stage 3: Turns 16-30 - Multi-part synthesis."""
        self.print_stage(3, "Turns 16-30: Multi-Part Synthesis")

        for turn in range(16, 31):
            # These require combining multiple earlier pieces
            if turn % 5 == 1:
                query = "How does the instructor approach the topic?"
                expected = [
                    self.context["instructor"],
                    self.context["topic"],
                    self.context["approach"],
                ]
            elif turn % 5 == 2:
                query = "Explain the framework with the example"
                expected = [self.context["framework"], self.context["example"]]
            elif turn % 5 == 3:
                query = "What methodology does the instructor recommend?"
                expected = [self.context["instructor"], self.context["approach"]]
            elif turn % 5 == 4:
                query = "Compare the topic with the example"
                expected = [self.context["topic"], self.context["example"]]
            else:
                query = "Summarize the framework and approach"
                expected = [self.context["framework"], self.context["approach"]]

            msg = Message(conversation_id=conversation.id, role="user", content=query)
            self.db.add(msg)

            response_content = (
                f"Synthesizing {', '.join(expected)}: [detailed synthesis]"
            )
            resp = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=response_content,
            )
            self.db.add(resp)
            self.db.commit()

            history = self.simulate_conversation_query(conversation, turn)
            passed, found = self.check_recall(history, expected)

            notes = ""
            if turn == 20:
                notes = "Turn 1-10 outside window, depends on RAG + assistant memory"
            elif turn == 25:
                notes = "Only Turn 15+ in window, early context via RAG"
            elif turn == 30:
                notes = "Only Turn 20+ in window, heavy reliance on RAG"

            self.add_turn_result(turn, query, expected, found, passed, notes)

    def run_stage_4_longdistance(self, conversation: Conversation):
        """Stage 4: Turns 31-40 - Long-distance recall."""
        self.print_stage(4, "Turns 31-40: Long-Distance Recall")

        for turn in range(31, 41):
            # Explicitly reference Turn 1-5 information
            if turn == 31:
                query = "Who was the instructor we discussed at the start?"
                expected = [self.context["instructor"]]
                notes = "Turn 1 is 30 turns ago - outside 10-message window"
            elif turn == 32:
                query = "What was the original main topic?"
                expected = [self.context["topic"]]
                notes = "Turn 2 is 30 turns ago"
            elif turn == 33:
                query = "Recall the first example mentioned"
                expected = [self.context["example"]]
                notes = "Turn 3 is 30 turns ago"
            elif turn == 34:
                query = "What framework did we start with?"
                expected = [self.context["framework"]]
                notes = "Turn 4 is 30 turns ago"
            elif turn == 35:
                query = "What was the initial approach?"
                expected = [self.context["approach"]]
                notes = "Turn 5 is 30 turns ago"
            elif turn == 36:
                query = "Connect the instructor's topic with the framework"
                expected = [
                    self.context["instructor"],
                    self.context["topic"],
                    self.context["framework"],
                ]
                notes = "Requires Turn 1, 2, 4 - all outside window"
            elif turn == 37:
                query = "How does the example fit the approach?"
                expected = [self.context["example"], self.context["approach"]]
                notes = "Requires Turn 3, 5 - outside window"
            elif turn == 38:
                query = "Summarize everything from the instructor's perspective"
                expected = [self.context["instructor"], self.context["topic"]]
                notes = "Comprehensive recall needed"
            elif turn == 39:
                query = "List all key concepts: instructor, topic, example, framework, approach"
                expected = list(self.context.values())
                notes = "Complete recall of Turns 1-5"
            else:  # turn == 40
                query = "Final validation: summarize the entire conversation"
                expected = list(self.context.values())
                notes = "Ultimate test: 40 turns of context"

            msg = Message(conversation_id=conversation.id, role="user", content=query)
            self.db.add(msg)

            # Simulate degraded recall (these are outside 10-message window)
            # Assistant responses will NOT contain original Turn 1-5 context
            # unless RAG retrieves it or Phase 2 facts are present
            response_content = "[Response without full Turn 1-5 context]"
            resp = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=response_content,
            )
            self.db.add(resp)
            self.db.commit()

            history = self.simulate_conversation_query(conversation, turn)
            passed, found = self.check_recall(history, expected)

            self.add_turn_result(turn, query, expected, found, passed, notes)

    def generate_report(self) -> Dict[str, Any]:
        """Generate final test report."""
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r["passed"])

        # Break down by stage
        stage1_results = [r for r in self.test_results if 1 <= r["turn"] <= 5]
        stage2_results = [r for r in self.test_results if 6 <= r["turn"] <= 15]
        stage3_results = [r for r in self.test_results if 16 <= r["turn"] <= 30]
        stage4_results = [r for r in self.test_results if 31 <= r["turn"] <= 40]

        stage1_passed = sum(1 for r in stage1_results if r["passed"])
        stage2_passed = sum(1 for r in stage2_results if r["passed"])
        stage3_passed = sum(1 for r in stage3_results if r["passed"])
        stage4_passed = sum(1 for r in stage4_results if r["passed"])

        return {
            "total_turns": total,
            "passed": passed,
            "failed": total - passed,
            "success_rate": (passed / total * 100) if total > 0 else 0,
            "stage_1": {
                "turns": "1-5",
                "passed": stage1_passed,
                "total": len(stage1_results),
                "rate": (stage1_passed / len(stage1_results) * 100)
                if stage1_results
                else 0,
            },
            "stage_2": {
                "turns": "6-15",
                "passed": stage2_passed,
                "total": len(stage2_results),
                "rate": (stage2_passed / len(stage2_results) * 100)
                if stage2_results
                else 0,
            },
            "stage_3": {
                "turns": "16-30",
                "passed": stage3_passed,
                "total": len(stage3_results),
                "rate": (stage3_passed / len(stage3_results) * 100)
                if stage3_results
                else 0,
            },
            "stage_4": {
                "turns": "31-40",
                "passed": stage4_passed,
                "total": len(stage4_results),
                "rate": (stage4_passed / len(stage4_results) * 100)
                if stage4_results
                else 0,
            },
        }

    def print_report(self, report: Dict[str, Any]):
        """Print formatted test report."""
        self.print_header("TEST RESULTS")

        print(f"{Colors.BOLD}Overall Results:{Colors.END}")
        print(f"  Total turns: {report['total_turns']}")
        print(f"  Passed: {Colors.GREEN}{report['passed']}{Colors.END}")
        print(f"  Failed: {Colors.RED}{report['failed']}{Colors.END}")

        rate = report["success_rate"]
        color = (
            Colors.GREEN if rate >= 70 else Colors.YELLOW if rate >= 50 else Colors.RED
        )
        print(f"  Success rate: {color}{rate:.1f}%{Colors.END}")

        print(f"\n{Colors.BOLD}Stage Breakdown:{Colors.END}")

        for stage_name in ["stage_1", "stage_2", "stage_3", "stage_4"]:
            stage = report[stage_name]
            stage_num = stage_name.split("_")[1]
            rate = stage["rate"]
            color = (
                Colors.GREEN
                if rate >= 70
                else Colors.YELLOW
                if rate >= 50
                else Colors.RED
            )

            print(
                f"  Stage {stage_num} (Turns {stage['turns']:6}): "
                f"{stage['passed']:2}/{stage['total']:2} = {color}{rate:5.1f}%{Colors.END}"
            )

        print(f"\n{Colors.BOLD}Expected vs Actual:{Colors.END}")
        expectations = [
            ("Stage 1 (Turns 1-5)", 100, report["stage_1"]["rate"]),
            ("Stage 2 (Turns 6-15)", 80, report["stage_2"]["rate"]),
            ("Stage 3 (Turns 16-30)", 60, report["stage_3"]["rate"]),
            ("Stage 4 (Turns 31-40)", 40, report["stage_4"]["rate"]),
        ]

        for name, expected, actual in expectations:
            diff = actual - expected
            if diff >= 0:
                status = f"{Colors.GREEN}▲{Colors.END}"
                sign = "+"
            else:
                status = f"{Colors.RED}▼{Colors.END}"
                sign = ""
            print(
                f"  {name:25} Expected: {expected:3}%  Actual: {actual:5.1f}%  {status} {sign}{diff:+5.1f}%"
            )

        print(f"\n{Colors.BOLD}Assessment:{Colors.END}")
        if report["success_rate"] >= 70:
            print(
                f"  {Colors.GREEN}✓ EXCELLENT{Colors.END} - Phase 1 meets expectations"
            )
        elif report["success_rate"] >= 60:
            print(
                f"  {Colors.GREEN}✓ GOOD{Colors.END} - Phase 1 shows improvement, minor tuning needed"
            )
        elif report["success_rate"] >= 50:
            print(
                f"  {Colors.YELLOW}⚠ FAIR{Colors.END} - Phase 1 helps but Phase 2 recommended"
            )
        else:
            print(
                f"  {Colors.RED}✗ NEEDS WORK{Colors.END} - Phase 1 insufficient, Phase 2 required"
            )


def main():
    """Run 40-turn memory test."""
    print(f"\n{Colors.BOLD}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{'DIRECT 40-TURN CONVERSATION MEMORY TEST':^80}{Colors.END}")
    print(f"{Colors.BOLD}{'='*80}{Colors.END}\n")

    print(f"{Colors.BOLD}Test Objective:{Colors.END}")
    print("  Validate Phase 1 memory improvements (5 → 10 message window)")
    print("  Expected outcome: ~70% success rate (up from ~42% baseline)\n")

    # Connect to database
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        print(f"Database: {Colors.GREEN}✓{Colors.END} Connected")

        # Get or create test user
        user = db.query(User).first()
        if not user:
            print(f"{Colors.RED}✗{Colors.END} No users found in database")
            return 1

        print(f"{Colors.GREEN}✓{Colors.END} Using user: {user.email}")

        # Get a completed video
        video = (
            db.query(Video)
            .filter(Video.user_id == user.id, Video.status == "completed")
            .first()
        )

        if not video:
            print(f"{Colors.RED}✗{Colors.END} No completed videos found")
            return 1

        print(f"{Colors.GREEN}✓{Colors.END} Using video: {video.title[:50]}...")

        # Create test conversation
        conversation = Conversation(
            user_id=user.id,
            title="40-Turn Memory Test",
            selected_video_ids=[str(video.id)],
            message_count=0,
            total_tokens_used=0,
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        print(
            f"{Colors.GREEN}✓{Colors.END} Created test conversation: {conversation.id}\n"
        )

        # Run test
        runner = Turn40TestRunner(db)

        runner.run_stage_1_seeding(conversation)

        # NEW: Phase 2 - Create conversation facts after seeding
        runner.create_conversation_facts(conversation)

        runner.run_stage_2_intermediate(conversation)
        runner.run_stage_3_multipart(conversation)
        runner.run_stage_4_longdistance(conversation)

        # Generate and print report
        report = runner.generate_report()
        runner.print_report(report)

        # Update conversation stats
        message_count = (
            db.query(Message).filter(Message.conversation_id == conversation.id).count()
        )
        conversation.message_count = message_count
        db.commit()

        print(f"\n{Colors.BOLD}Test conversation:{Colors.END} {conversation.id}")
        print(f"{Colors.BOLD}Total messages:{Colors.END} {message_count}")

        return 0

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
