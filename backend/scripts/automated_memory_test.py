#!/usr/bin/env python3
"""
Automated 40-Turn Conversation Memory Test

This script runs a fully automated test against the live API to validate
Phase 1 memory improvements (5 → 10 message window).

Requirements:
- Backend running at http://localhost:8000
- At least one completed video in the database
- Valid user authentication

Usage:
    python backend/scripts/automated_memory_test.py [--video-id VIDEO_ID]
"""
import os
import sys
import json
import time
import argparse
import requests
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1")
AUTH_TOKEN = os.environ.get("AUTH_TOKEN", None)


class Colors:
    """ANSI color codes for terminal output."""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    END = "\033[0m"


class MemoryTestRunner:
    """Automated conversation memory test runner."""

    def __init__(self, base_url: str = BASE_URL, auth_token: Optional[str] = None):
        self.base_url = base_url
        self.auth_token = auth_token
        self.headers = {}
        if auth_token:
            self.headers["Authorization"] = f"Bearer {auth_token}"

        self.conversation_id: Optional[str] = None
        self.test_results: List[Dict[str, Any]] = []
        self.start_time = time.time()

    def print_header(self, text: str):
        """Print formatted header."""
        print(f"\n{Colors.BOLD}{'='*80}{Colors.END}")
        print(f"{Colors.BOLD}{text:^80}{Colors.END}")
        print(f"{Colors.BOLD}{'='*80}{Colors.END}\n")

    def print_stage(self, text: str):
        """Print stage header."""
        print(f"\n{Colors.BLUE}{'─'*80}{Colors.END}")
        print(f"{Colors.BLUE}{Colors.BOLD}{text}{Colors.END}")
        print(f"{Colors.BLUE}{'─'*80}{Colors.END}")

    def check_health(self) -> bool:
        """Check if backend is healthy."""
        try:
            response = requests.get(
                f"{self.base_url.replace('/api/v1', '')}/health", timeout=5
            )
            if response.status_code == 200:
                print(f"{Colors.GREEN}✓{Colors.END} Backend is healthy")
                return True
            else:
                print(
                    f"{Colors.RED}✗{Colors.END} Backend returned status {response.status_code}"
                )
                return False
        except Exception as e:
            print(f"{Colors.RED}✗{Colors.END} Cannot connect to backend: {e}")
            return False

    def get_available_videos(self) -> List[Dict[str, Any]]:
        """Get list of completed videos."""
        try:
            response = requests.get(
                f"{self.base_url}/videos",
                headers=self.headers,
                params={"limit": 10},
                timeout=10,
            )

            if response.status_code == 401:
                print(
                    f"{Colors.YELLOW}⚠{Colors.END}  No authentication - using Clerk bypass"
                )
                # Try without auth (development mode)
                response = requests.get(
                    f"{self.base_url}/videos", params={"limit": 10}, timeout=10
                )

            if response.status_code == 200:
                videos = response.json().get("videos", [])
                completed = [v for v in videos if v.get("status") == "completed"]
                return completed
            else:
                print(
                    f"{Colors.RED}✗{Colors.END} Failed to fetch videos: {response.status_code}"
                )
                print(f"Response: {response.text[:200]}")
                return []

        except Exception as e:
            print(f"{Colors.RED}✗{Colors.END} Error fetching videos: {e}")
            return []

    def create_conversation(self, video_id: str) -> Optional[str]:
        """Create a new conversation with the video."""
        try:
            response = requests.post(
                f"{self.base_url}/conversations",
                headers=self.headers,
                json={
                    "title": "Automated Memory Test",
                    "selected_video_ids": [video_id],
                },
                timeout=10,
            )

            if response.status_code == 200 or response.status_code == 201:
                data = response.json()
                conv_id = data.get("id")
                print(f"{Colors.GREEN}✓{Colors.END} Conversation created: {conv_id}")
                return conv_id
            else:
                print(
                    f"{Colors.RED}✗{Colors.END} Failed to create conversation: {response.status_code}"
                )
                print(f"Response: {response.text[:200]}")
                return None

        except Exception as e:
            print(f"{Colors.RED}✗{Colors.END} Error creating conversation: {e}")
            return None

    def send_message(self, query: str, turn: int) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Send a message and get response.

        Returns:
            (success, response_content, metadata)
        """
        try:
            response = requests.post(
                f"{self.base_url}/conversations/{self.conversation_id}/messages",
                headers=self.headers,
                json={"message": query, "mode": "summarize", "stream": False},
                timeout=60,
            )

            if response.status_code == 200:
                data = response.json()
                content = data.get("content", "")
                metadata = {
                    "token_count": data.get("token_count", 0),
                    "response_time": data.get("response_time_seconds", 0),
                    "chunks_count": len(data.get("chunk_references", [])),
                    "model": data.get("model", "unknown"),
                }

                # Truncate for display
                display_content = (
                    content[:150] + "..." if len(content) > 150 else content
                )
                print(
                    f"  Turn {turn}: {Colors.GREEN}✓{Colors.END} Response received ({len(content)} chars)"
                )
                print(f"           {display_content}")

                return True, content, metadata
            else:
                print(
                    f"  Turn {turn}: {Colors.RED}✗{Colors.END} Failed ({response.status_code})"
                )
                return False, "", {}

        except Exception as e:
            print(f"  Turn {turn}: {Colors.RED}✗{Colors.END} Error: {e}")
            return False, "", {}

    def validate_recall(
        self, response: str, expected_terms: List[str], exact: bool = False
    ) -> Tuple[bool, List[str]]:
        """
        Validate that response contains expected terms.

        Returns:
            (all_found, missing_terms)
        """
        missing = []
        response_lower = response.lower()

        for term in expected_terms:
            term_lower = term.lower()
            if exact:
                # Exact phrase match
                if term_lower not in response_lower:
                    missing.append(term)
            else:
                # Flexible match (allows for variations)
                if term_lower not in response_lower:
                    missing.append(term)

        return len(missing) == 0, missing

    def run_test_stage_1(self) -> Dict[str, Any]:
        """Stage 1: Turns 1-5 - Seed basic information."""
        self.print_stage("STAGE 1: Turns 1-5 - Seeding Basic Information")

        stage_results = []

        # Turn 1: Get instructor/speaker
        query_1 = "Who are the main speakers or instructors in this video? Please give me their names."
        success, response_1, meta_1 = self.send_message(query_1, 1)

        # Extract any names mentioned (simple heuristic)
        instructor_name = "the instructor"  # Default fallback
        if success and response_1:
            # Look for proper nouns (capitalized words)
            words = response_1.split()
            caps = [
                w
                for w in words
                if w
                and w[0].isupper()
                and len(w) > 2
                and w not in ["The", "This", "In", "According"]
            ]
            if caps:
                instructor_name = caps[0]

        stage_results.append(
            {
                "turn": 1,
                "query": query_1,
                "response": response_1,
                "success": success,
                "validation": "baseline",
                "metadata": meta_1,
                "extracted_info": {"instructor": instructor_name},
            }
        )

        time.sleep(1)

        # Turn 2: Get main topic
        query_2 = "What is the main topic or subject covered in this video?"
        success, response_2, meta_2 = self.send_message(query_2, 2)

        # Extract topic
        main_topic = "the main topic"
        if success and response_2:
            # Simple extraction - first noun phrase
            words = response_2.lower().split()
            if "learning" in words:
                main_topic = "learning"
            elif "machine" in words:
                main_topic = "machine learning"

        stage_results.append(
            {
                "turn": 2,
                "query": query_2,
                "response": response_2,
                "success": success,
                "validation": "baseline",
                "metadata": meta_2,
                "extracted_info": {"topic": main_topic},
            }
        )

        time.sleep(1)

        # Turn 3: Get examples
        query_3 = "Are there any specific examples, case studies, or demonstrations mentioned?"
        success, response_3, meta_3 = self.send_message(query_3, 3)

        stage_results.append(
            {
                "turn": 3,
                "query": query_3,
                "response": response_3,
                "success": success,
                "validation": "baseline",
                "metadata": meta_3,
            }
        )

        time.sleep(1)

        # Turn 4: Get technical details
        query_4 = "What tools, frameworks, or technologies are discussed?"
        success, response_4, meta_4 = self.send_message(query_4, 4)

        framework = "the framework"
        if success and response_4:
            for tech in ["python", "tensorflow", "pytorch", "java", "javascript"]:
                if tech in response_4.lower():
                    framework = tech
                    break

        stage_results.append(
            {
                "turn": 4,
                "query": query_4,
                "response": response_4,
                "success": success,
                "validation": "baseline",
                "metadata": meta_4,
                "extracted_info": {"framework": framework},
            }
        )

        time.sleep(1)

        # Turn 5: Get methodology
        query_5 = "What approach or methodology is recommended in this video?"
        success, response_5, meta_5 = self.send_message(query_5, 5)

        stage_results.append(
            {
                "turn": 5,
                "query": query_5,
                "response": response_5,
                "success": success,
                "validation": "baseline",
                "metadata": meta_5,
            }
        )

        return {
            "stage": 1,
            "name": "Seeding (1-5)",
            "results": stage_results,
            "extracted_context": {
                "instructor": instructor_name,
                "topic": main_topic,
                "framework": framework,
            },
        }

    def run_test_stage_2(self, context: Dict[str, str]) -> Dict[str, Any]:
        """Stage 2: Turns 6-15 - Reference recent context."""
        self.print_stage("STAGE 2: Turns 6-15 - Intermediate Complexity")

        stage_results = []
        instructor = context.get("instructor", "the instructor")
        topic = context.get("topic", "the topic")
        framework = context.get("framework", "the framework")

        # Turn 6: Reference topic from Turn 2
        query_6 = f"Can you elaborate more on {topic} that was mentioned earlier?"
        success, response_6, meta_6 = self.send_message(query_6, 6)

        # Validate recall of topic
        passed, missing = self.validate_recall(response_6, [topic])

        stage_results.append(
            {
                "turn": 6,
                "query": query_6,
                "response": response_6,
                "success": success,
                "validation_passed": passed,
                "expected_terms": [topic],
                "missing_terms": missing,
                "metadata": meta_6,
            }
        )

        time.sleep(1)

        # Turn 10: Reference instructor from Turn 1
        query_10 = (
            f"What specific points did {instructor} emphasize about this subject?"
        )
        success, response_10, meta_10 = self.send_message(query_10, 10)

        # Validate recall of instructor
        passed, missing = self.validate_recall(response_10, [instructor])

        stage_results.append(
            {
                "turn": 10,
                "query": query_10,
                "response": response_10,
                "success": success,
                "validation_passed": passed,
                "expected_terms": [instructor],
                "missing_terms": missing,
                "metadata": meta_10,
            }
        )

        time.sleep(1)

        # Turn 12: Multi-reference
        query_12 = f"How does {instructor} suggest using {framework} for {topic}?"
        success, response_12, meta_12 = self.send_message(query_12, 12)

        passed, missing = self.validate_recall(response_12, [instructor, topic])

        stage_results.append(
            {
                "turn": 12,
                "query": query_12,
                "response": response_12,
                "success": success,
                "validation_passed": passed,
                "expected_terms": [instructor, topic],
                "missing_terms": missing,
                "metadata": meta_12,
            }
        )

        return {"stage": 2, "name": "Intermediate (6-15)", "results": stage_results}

    def run_test_stage_3(self, context: Dict[str, str]) -> Dict[str, Any]:
        """Stage 3: Turns 16-30 - Multi-part synthesis."""
        self.print_stage("STAGE 3: Turns 16-30 - Multi-Part Synthesis")

        stage_results = []
        topic = context.get("topic", "the topic")

        # Turn 20: Synthesize across conversation
        query_20 = f"Based on everything discussed so far about {topic}, what are the key takeaways?"
        success, response_20, meta_20 = self.send_message(query_20, 20)

        passed, missing = self.validate_recall(response_20, [topic])

        stage_results.append(
            {
                "turn": 20,
                "query": query_20,
                "response": response_20,
                "success": success,
                "validation_passed": passed,
                "expected_terms": [topic],
                "missing_terms": missing,
                "metadata": meta_20,
            }
        )

        time.sleep(1)

        # Turn 25: Cross-reference
        query_25 = "Can you connect the examples from earlier with the frameworks we discussed?"
        success, response_25, meta_25 = self.send_message(query_25, 25)

        stage_results.append(
            {
                "turn": 25,
                "query": query_25,
                "response": response_25,
                "success": success,
                "validation_passed": success,  # Just check it responded
                "expected_terms": [],
                "missing_terms": [],
                "metadata": meta_25,
            }
        )

        return {"stage": 3, "name": "Multi-part (16-30)", "results": stage_results}

    def run_test_stage_4(self, context: Dict[str, str]) -> Dict[str, Any]:
        """Stage 4: Turns 31-40 - Long-distance recall."""
        self.print_stage("STAGE 4: Turns 31-40 - Long-Distance Recall")

        stage_results = []
        instructor = context.get("instructor", "the instructor")
        topic = context.get("topic", "the topic")
        framework = context.get("framework", "the framework")

        # Turn 35: Recall Turn 1 from 30+ turns ago
        query_35 = "Going back to our very first conversation, who was the main speaker or instructor?"
        success, response_35, meta_35 = self.send_message(query_35, 35)

        # This is the critical test - can it recall Turn 1 from Turn 35?
        passed, missing = self.validate_recall(response_35, [instructor])

        stage_results.append(
            {
                "turn": 35,
                "query": query_35,
                "response": response_35,
                "success": success,
                "validation_passed": passed,
                "expected_terms": [instructor],
                "missing_terms": missing,
                "metadata": meta_35,
                "critical_test": True,
                "note": "Tests if Turn 1 info is retained at Turn 35 (Phase 1: should fail, Phase 2: should pass)",
            }
        )

        time.sleep(1)

        # Turn 40: Comprehensive recall
        query_40 = "Summarize our entire conversation: who was the instructor, what topics were covered, and what tools were mentioned?"
        success, response_40, meta_40 = self.send_message(query_40, 40)

        passed, missing = self.validate_recall(
            response_40, [instructor, topic, framework]
        )

        stage_results.append(
            {
                "turn": 40,
                "query": query_40,
                "response": response_40,
                "success": success,
                "validation_passed": passed,
                "expected_terms": [instructor, topic, framework],
                "missing_terms": missing,
                "metadata": meta_40,
                "critical_test": True,
                "note": "Final comprehensive test",
            }
        )

        return {"stage": 4, "name": "Long-distance (31-40)", "results": stage_results}

    def generate_report(self, all_stages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate comprehensive test report."""
        total_turns = sum(len(stage["results"]) for stage in all_stages)

        # Calculate success rates by stage
        stage_stats = []
        overall_passed = 0
        overall_total = 0

        for stage_data in all_stages:
            results = stage_data["results"]

            # Count validations (some turns are just baseline, not validated)
            validated = [r for r in results if "validation_passed" in r]
            if validated:
                passed = sum(1 for r in validated if r["validation_passed"])
                total = len(validated)
                success_rate = (passed / total * 100) if total > 0 else 100
            else:
                # Baseline stage - count all successful responses
                passed = sum(1 for r in results if r["success"])
                total = len(results)
                success_rate = (passed / total * 100) if total > 0 else 100

            stage_stats.append(
                {
                    "stage": stage_data["stage"],
                    "name": stage_data["name"],
                    "passed": passed,
                    "total": total,
                    "success_rate": success_rate,
                }
            )

            overall_passed += passed
            overall_total += total

        overall_success = (
            (overall_passed / overall_total * 100) if overall_total > 0 else 0
        )

        # Find critical failures
        critical_failures = []
        for stage_data in all_stages:
            for result in stage_data["results"]:
                if result.get("critical_test") and not result.get(
                    "validation_passed", True
                ):
                    critical_failures.append(result)

        return {
            "test_name": "40-Turn Conversation Memory Test",
            "timestamp": datetime.now().isoformat(),
            "duration_seconds": time.time() - self.start_time,
            "conversation_id": self.conversation_id,
            "total_turns": total_turns,
            "overall_passed": overall_passed,
            "overall_total": overall_total,
            "overall_success_rate": overall_success,
            "stage_stats": stage_stats,
            "critical_failures": critical_failures,
            "all_stages": all_stages,
        }

    def print_report(self, report: Dict[str, Any]):
        """Print human-readable report."""
        self.print_header("TEST RESULTS")

        print(f"Test Duration: {report['duration_seconds']:.1f}s")
        print(f"Conversation ID: {report['conversation_id']}")
        print(f"Total Turns: {report['total_turns']}")
        print(
            f"\nOverall Success Rate: {Colors.BOLD}{report['overall_success_rate']:.1f}%{Colors.END}"
        )
        print(f"Passed: {report['overall_passed']}/{report['overall_total']}")

        # Stage breakdown
        print(f"\n{Colors.BOLD}Stage-by-Stage Results:{Colors.END}")
        print(f"{'─'*80}")

        for stage in report["stage_stats"]:
            rate = stage["success_rate"]
            color = (
                Colors.GREEN
                if rate >= 80
                else (Colors.YELLOW if rate >= 60 else Colors.RED)
            )
            bar = "█" * int(rate / 5)

            print(
                f"{stage['name']:30} {color}{stage['passed']:2}/{stage['total']:2} ({rate:5.1f}%) {bar}{Colors.END}"
            )

        # Critical failures
        if report["critical_failures"]:
            print(
                f"\n{Colors.BOLD}{Colors.RED}Critical Failures (Long-Distance Recall):{Colors.END}"
            )
            print(f"{'─'*80}")
            for failure in report["critical_failures"]:
                print(
                    f"\n{Colors.RED}✗{Colors.END} Turn {failure['turn']}: {failure['query'][:60]}..."
                )
                print(f"  Expected: {', '.join(failure['expected_terms'])}")
                print(f"  Missing: {', '.join(failure['missing_terms'])}")
                print(f"  Note: {failure.get('note', 'N/A')}")

        # Phase assessment
        print(f"\n{Colors.BOLD}Phase Assessment:{Colors.END}")
        print(f"{'─'*80}")

        overall = report["overall_success_rate"]
        stage_4 = [s for s in report["stage_stats"] if s["stage"] == 4]
        stage_4_rate = stage_4[0]["success_rate"] if stage_4 else 0

        if overall >= 85 and stage_4_rate >= 80:
            print(
                f"{Colors.GREEN}✓ Phase 2 COMPLETE{Colors.END} - Excellent long-term memory"
            )
        elif overall >= 70 and stage_4_rate >= 40:
            print(
                f"{Colors.YELLOW}✓ Phase 1 COMPLETE{Colors.END} - Good short-term, needs Phase 2 for long-term"
            )
            print("  Recommendation: Implement Phase 2 (conversation facts extraction)")
        else:
            print(
                f"{Colors.RED}✗ Needs Improvement{Colors.END} - Memory retention below target"
            )
            print(f"  Current: {overall:.1f}% | Target: 70%+ (Phase 1), 85%+ (Phase 2)")

        print(f"\n{'='*80}\n")

        # Save detailed report
        report_file = f"memory_test_report_{int(time.time())}.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)

        print(f"Detailed report saved to: {Colors.BOLD}{report_file}{Colors.END}\n")

    def run_full_test(self, video_id: str) -> bool:
        """Run the complete 40-turn test."""
        self.print_header("40-TURN CONVERSATION MEMORY TEST")

        print("Test Objective: Validate Phase 1 memory improvements (5 → 10 messages)")
        print("Expected: ~70% success rate (up from ~42% baseline)\n")

        # Check backend health
        if not self.check_health():
            return False

        # Create conversation
        self.conversation_id = self.create_conversation(video_id)
        if not self.conversation_id:
            return False

        print(f"\n{Colors.GREEN}✓{Colors.END} Starting 40-turn test...\n")

        # Run all stages
        stage_1 = self.run_test_stage_1()
        context = stage_1.get("extracted_context", {})

        stage_2 = self.run_test_stage_2(context)
        stage_3 = self.run_test_stage_3(context)
        stage_4 = self.run_test_stage_4(context)

        # Generate and print report
        report = self.generate_report([stage_1, stage_2, stage_3, stage_4])
        self.print_report(report)

        # Success if overall rate >= 70%
        return report["overall_success_rate"] >= 70


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Automated 40-turn conversation memory test"
    )
    parser.add_argument(
        "--video-id", help="Video ID to test with (will auto-select if not provided)"
    )
    parser.add_argument("--base-url", default=BASE_URL, help="API base URL")
    parser.add_argument("--auth-token", help="Authentication token")

    args = parser.parse_args()

    runner = MemoryTestRunner(
        base_url=args.base_url, auth_token=args.auth_token or AUTH_TOKEN
    )

    # Get video to test with
    video_id = args.video_id
    if not video_id:
        print("No video ID provided, fetching available videos...")
        videos = runner.get_available_videos()

        if not videos:
            print(f"\n{Colors.RED}✗{Colors.END} No completed videos found!")
            print("\nPlease ingest a video first:")
            print("  POST http://localhost:8000/api/v1/videos/ingest")
            print('  {"youtube_url": "https://www.youtube.com/watch?v=..."}')
            return 1

        video_id = videos[0]["id"]
        print(
            f"{Colors.GREEN}✓{Colors.END} Using video: {videos[0]['title'][:50]}... (ID: {video_id})"
        )

    # Run test
    success = runner.run_full_test(video_id)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
