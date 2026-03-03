#!/usr/bin/env python3
"""
100+ Turn Conversation Memory Stress Test

Validates that conversation memory (fact extraction + loading) works correctly
at extreme distances through the STREAMING endpoint (the one the UI uses).

Seeds 15 distinct concepts in Phase 1, then tests recall at increasing distances:
5, 10, 20, 50, 100+ turns. Uses fuzzy concept matching with synonym lists.

Requirements:
- Backend running at http://localhost:8000
- Collection with completed videos (default: Alan Watts Lectures)
- NEXTAUTH_SECRET in backend/.env OR --auth-token CLI arg

Usage:
    python backend/scripts/memory_stress_test.py \\
        --collection-id c7743864-ae29-4093-a892-33e98dc72c94

    # With explicit auth token
    python backend/scripts/memory_stress_test.py \\
        --collection-id c7743864-ae29-4093-a892-33e98dc72c94 \\
        --auth-token "eyJ..."

    # Resume from a specific turn (e.g. after rate limit)
    python backend/scripts/memory_stress_test.py \\
        --collection-id c7743864-ae29-4093-a892-33e98dc72c94 \\
        --conversation-id "existing-conv-id" \\
        --resume-from 51
"""
import os
import sys
import json
import time
import uuid
import argparse
import subprocess
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta

import requests

# Add backend to path for config/jwt access
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1")
DEFAULT_COLLECTION_ID = "c7743864-ae29-4093-a892-33e98dc72c94"

# ─── Concept Registry ────────────────────────────────────────────────────────

CONCEPT_REGISTRY: Dict[int, Dict[str, Any]] = {
    1: {
        "concept": "alan_watts_identity",
        "label": "Alan Watts Identity",
        "synonyms": ["alan watts", "watts", "philosopher", "lecturer", "british philosopher"],
    },
    2: {
        "concept": "ego",
        "label": "Skin-Encapsulated Ego",
        "synonyms": ["skin-encapsulated ego", "ego", "bag of skin", "isolated self", "encapsulated"],
    },
    3: {
        "concept": "zen",
        "label": "Zen Buddhism",
        "synonyms": ["zen", "zen buddhism", "zazen", "satori", "koan"],
    },
    4: {
        "concept": "god_models",
        "label": "God Models",
        "synonyms": ["monarchical", "organic model", "dramatic model", "ceramic", "fully automatic"],
    },
    5: {
        "concept": "interconnectedness",
        "label": "Interconnectedness",
        "synonyms": ["interconnected", "inseparable", "osmotic", "universe", "one with"],
    },
    6: {
        "concept": "wu_wei",
        "label": "Wu-Wei",
        "synonyms": ["wu-wei", "wu wei", "non-action", "effortless action", "not forcing"],
    },
    7: {
        "concept": "cosmic_game",
        "label": "Cosmic Game",
        "synonyms": ["cosmic game", "hide and seek", "hide-and-seek", "play", "drama", "lila"],
    },
    8: {
        "concept": "seeking_paradox",
        "label": "Seeking Paradox",
        "synonyms": ["paradox", "cannot seek", "seeking enlightenment", "trying not to try", "catch-22"],
    },
    9: {
        "concept": "mutual_arising",
        "label": "Mutual Arising",
        "synonyms": ["mutual arising", "interdependence", "figure and ground", "polarity", "inseparable opposites"],
    },
    10: {
        "concept": "illusion_of_self",
        "label": "Illusion of Self",
        "synonyms": ["illusion", "separate self", "no-self", "boundaries", "maya"],
    },
    11: {
        "concept": "east_vs_west",
        "label": "East vs West",
        "synonyms": ["eastern", "western", "east and west", "occidental", "oriental", "contrast"],
    },
    12: {
        "concept": "meditation",
        "label": "Meditation",
        "synonyms": ["meditation", "mindfulness", "awareness", "sitting", "contemplation"],
    },
    13: {
        "concept": "death_existence",
        "label": "Death & Existence",
        "synonyms": ["death", "existence", "mortality", "impermanence", "eternity", "void"],
    },
    14: {
        "concept": "awakening",
        "label": "Awakening",
        "synonyms": ["awakening", "enlightenment", "liberation", "realization", "waking up", "satori"],
    },
    15: {
        "concept": "humor",
        "label": "Humor & Laughter",
        "synonyms": ["humor", "laughter", "joke", "playful", "comedy", "funny"],
    },
}

# ─── Question Phases ─────────────────────────────────────────────────────────

# Each entry: (turn_number, question, concepts_tested: list of concept IDs, is_recall: bool)
# concepts_tested=[] means fresh question (no recall validation needed)

PHASE_1_SEED: List[Tuple[int, str, List[int], bool]] = [
    (1, "Who is the main speaker in these lectures?", [1], False),
    (2, "What does Alan Watts mean by the 'skin-encapsulated ego'?", [2], False),
    (3, "What is Alan Watts' view on Zen Buddhism?", [3], False),
    (4, "How does Watts describe the 'monarchical' model of God?", [4], False),
    (5, "What does Watts say about the relationship between self and universe?", [5], False),
    (6, "Explain Watts' concept of wu-wei or non-action.", [6], False),
    (7, "What is the 'cosmic hide and seek' metaphor that Watts uses?", [7], False),
    (8, "How does Watts view the paradox of seeking enlightenment?", [8], False),
    (9, "What is mutual arising or interdependence in Watts' philosophy?", [9], False),
    (10, "What does Watts say about the illusion of the separate self?", [10], False),
    (11, "How does Watts compare Eastern and Western philosophy?", [11], False),
    (12, "What does Watts teach about meditation and mindfulness?", [12], False),
    (13, "What is Watts' view on death and the nature of existence?", [13], False),
    (14, "How does Watts describe awakening or enlightenment?", [14], False),
    (15, "What role does humor and laughter play in Watts' teachings?", [15], False),
]

PHASE_2_INTERMEDIATE: List[Tuple[int, str, List[int], bool]] = [
    (16, "You mentioned the speaker earlier -- what tradition is he most associated with?", [1, 3], True),
    (17, "Going back to the ego concept we discussed, how does Watts say we should relate to it?", [2], True),
    (18, "Which model does Watts prefer over the monarchical model of God?", [4], True),
    (19, "How does wu-wei connect to the cosmic game metaphor we talked about?", [6, 7], True),
    (20, "How does the seeking paradox we discussed relate to meditation?", [8, 12], True),
    (21, "What specific stories or anecdotes does Watts tell in these lectures?", [], False),
    (22, "What does Watts say about technology and modern society?", [], False),
    (23, "How does Watts view the concept of time?", [], False),
    (24, "What does Watts say about music and rhythm?", [], False),
    (25, "How does Watts describe the nature of consciousness?", [], False),
    (26, "Building on mutual arising that we discussed, how does it relate to everyday experience?", [9, 5], True),
    (27, "Earlier we talked about interconnectedness -- give me a specific example Watts uses.", [5], True),
    (28, "How does the illusion of self connect to the ego concept?", [10, 2], True),
    (29, "Summarize the key themes we've discussed so far about Watts' philosophy.", [1, 2, 5, 6, 7], True),
    (30, "What is the most important insight from Watts across all these concepts?", [1], True),
]

PHASE_3_BUILD: List[Tuple[int, str, List[int], bool]] = [
    (31, "What does Watts say about the nature of reality?", [], False),
    (32, "How does Watts view anxiety and worry?", [], False),
    (33, "Earlier when we discussed the ego, you mentioned the 'bag of skin' idea -- elaborate.", [2], True),
    (34, "Compare the cosmic game metaphor with the idea of mutual arising.", [7, 9], True),
    (35, "What does Watts say about language and its limitations?", [], False),
    (36, "How does Watts describe the relationship between order and chaos?", [], False),
    (37, "Recall wu-wei -- how would Watts apply it to modern work life?", [6], True),
    (38, "What does Watts say about art and creativity?", [], False),
    (39, "How does the East vs West comparison we discussed affect how people view nature?", [11], True),
    (40, "What is Watts' view on education and learning?", [], False),
    (41, "Connect the seeking paradox to the concept of meditation we discussed.", [8, 12], True),
    (42, "What does Watts say about love and relationships?", [], False),
    (43, "How does awakening relate to the illusion of the separate self?", [14, 10], True),
    (44, "What are Watts' views on science and religion?", [], False),
    (45, "Relate death and existence to the idea of the cosmic game.", [13, 7], True),
    (46, "What does Watts say about freedom and spontaneity?", [], False),
    (47, "How does humor in Watts' teaching connect to his views on enlightenment?", [15, 14], True),
    (48, "What is Watts' perspective on suffering?", [], False),
    (49, "How does the monarchical God model contrast with an organic worldview?", [4], True),
    (50, "Give me a comprehensive overview of Watts' core philosophy based on everything we've discussed.", [1, 2, 5, 6, 7, 10], True),
]

PHASE_4_LONG_DISTANCE: List[Tuple[int, str, List[int], bool]] = [
    (51, "Going back to the very first thing we discussed -- who is the main speaker in these lectures?", [1], True),
    (52, "What specific points about consciousness does Watts make?", [], False),
    (53, "How does Watts describe the experience of flow?", [], False),
    (54, "What does Watts say about desire and attachment?", [], False),
    (55, "Remember the skin-encapsulated ego concept from early in our discussion? Explain it again.", [2], True),
    (56, "What are Watts' views on the concept of self-improvement?", [], False),
    (57, "How does Watts view the concept of control?", [], False),
    (58, "What parallels does Watts draw between different religious traditions?", [], False),
    (59, "What does Watts say about the present moment?", [], False),
    (60, "The models of God we discussed very early on -- what were the main ones?", [4], True),
    (61, "How does Watts view the role of the teacher or guru?", [], False),
    (62, "What does Watts say about identity and roles people play?", [], False),
    (63, "How does Watts describe the experience of wonder?", [], False),
    (64, "What does Watts say about the nature of the mind?", [], False),
    (65, "Recall wu-wei from our earlier discussion. How does Watts describe effortless action?", [6], True),
    (66, "What is Watts' view on tradition and cultural norms?", [], False),
    (67, "How does Watts approach the question 'Who am I?'", [], False),
    (68, "What does Watts say about silence and stillness?", [], False),
    (69, "How does Watts use nature metaphors in his teaching?", [], False),
    (70, "What was the cosmic game metaphor about? Refresh my memory from our early discussion.", [7], True),
    (71, "What does Watts say about dreams and waking life?", [], False),
    (72, "How does Watts view the concept of purpose and meaning?", [], False),
    (73, "What does Watts say about the body-mind relationship?", [], False),
    (74, "How does Watts approach the concept of nothingness or the void?", [], False),
    (75, "Summarize the main concepts from our earliest discussion: the speaker, the ego, the God models, wu-wei, and the cosmic game.", [1, 2, 4, 6, 7], True),
]

PHASE_5_STRESS: List[Tuple[int, str, List[int], bool]] = [
    (76, "What new insights about Watts have emerged through our conversation?", [], False),
    (77, "How does the interconnectedness concept from early on manifest in Watts' later lectures?", [5], True),
    (78, "What does Watts say about forgiveness?", [], False),
    (79, "Recall the seeking paradox -- why can't you seek enlightenment according to Watts?", [8], True),
    (80, "What does Watts say about the ocean as a metaphor?", [], False),
    (81, "How does mutual arising relate to everyday decisions?", [9], True),
    (82, "What does Watts think about progress and civilization?", [], False),
    (83, "From our early discussion, what was the illusion of the separate self about?", [10], True),
    (84, "What does Watts say about food and eating?", [], False),
    (85, "How did Watts compare Eastern and Western approaches to God?", [11, 4], True),
    (86, "What does Watts say about children and childhood?", [], False),
    (87, "Recall what we said about meditation -- what is Watts' essential advice?", [12], True),
    (88, "What does Watts say about trust?", [], False),
    (89, "How did Watts view death, which we discussed earlier?", [13], True),
    (90, "What does Watts say about the sacred and the profane?", [], False),
    (91, "What was Watts' view on awakening that we discussed?", [14], True),
    (92, "What does Watts say about boredom?", [], False),
    (93, "How did humor play a role in Watts' teaching, as we noted early on?", [15], True),
    (94, "What does Watts say about transformation?", [], False),
    (95, "Connect the ego concept to the illusion of self -- both from our early turns.", [2, 10], True),
    (96, "What does Watts say about simplicity?", [], False),
    (97, "How do wu-wei and mutual arising work together in Watts' philosophy?", [6, 9], True),
    (98, "What does Watts say about power?", [], False),
    (99, "Revisit the cosmic game and the seeking paradox together.", [7, 8], True),
    (100, "What is Watts' ultimate message across all his lectures?", [1], True),
]

PHASE_6_FINAL: List[Tuple[int, str, List[int], bool]] = [
    (101, "Who is the primary speaker we've been discussing throughout this entire conversation?", [1], True),
    (102, "What is the skin-encapsulated ego concept that Watts describes?", [2], True),
    (103, "What were the two main models of God that Watts contrasts?", [4], True),
    (104, "Explain wu-wei as Watts teaches it.", [6], True),
    (105, "What is the cosmic hide and seek metaphor?", [7], True),
    (106, "Why is seeking enlightenment a paradox according to Watts?", [8], True),
    (107, "What is mutual arising in Watts' philosophy?", [9], True),
    (108, "How does Watts describe the illusion of the separate self?", [10], True),
    (109, "How does Watts compare Eastern and Western philosophy?", [11], True),
    (110, "Give a complete summary covering: the speaker, all core concepts, and key metaphors from our entire conversation.", [1, 2, 4, 6, 7, 8, 9, 10, 11], True),
]

ALL_PHASES = [
    ("Phase 1: Seed Facts (Turns 1-15)", PHASE_1_SEED),
    ("Phase 2: Intermediate Recall (Turns 16-30)", PHASE_2_INTERMEDIATE),
    ("Phase 3: Build on Context (Turns 31-50)", PHASE_3_BUILD),
    ("Phase 4: Long-Distance Recall (Turns 51-75)", PHASE_4_LONG_DISTANCE),
    ("Phase 5: Stress Mix (Turns 76-100)", PHASE_5_STRESS),
    ("Phase 6: Final Validation (Turns 101-110)", PHASE_6_FINAL),
]

# Checkpoints: turn numbers where we query the DB for fact stats
CHECKPOINT_TURNS = [15, 20, 30, 40, 50, 60, 75, 80, 90, 100, 110]

# Success criteria by distance bucket
SUCCESS_CRITERIA = {
    "<=5": 0.90,
    "<=10": 0.80,
    "<=20": 0.70,
    "<=50": 0.60,
    "<=100": 0.50,
}


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    END = "\033[0m"


class MemoryStressTestRunner:
    """110-turn conversation memory stress test via streaming endpoint."""

    def __init__(
        self,
        collection_id: str,
        auth_token: str,
        base_url: str = BASE_URL,
        conversation_id: Optional[str] = None,
        resume_from: int = 1,
        delay: float = 2.0,
    ):
        self.collection_id = collection_id
        self.base_url = base_url
        self.auth_token = auth_token
        self.headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
        }
        self.conversation_id = conversation_id
        self.resume_from = resume_from
        self.delay = delay

        # Results tracking
        self.responses: Dict[int, str] = {}  # turn -> response content
        self.recall_results: List[Dict[str, Any]] = []  # per-recall-turn results
        self.checkpoints: List[Dict[str, Any]] = []
        self.errors: List[Dict[str, Any]] = []
        self.start_time = time.time()

    # ─── Output helpers ──────────────────────────────────────────────────

    def _header(self, text: str):
        print(f"\n{Colors.BOLD}{'='*80}{Colors.END}")
        print(f"{Colors.BOLD}{text:^80}{Colors.END}")
        print(f"{Colors.BOLD}{'='*80}{Colors.END}\n")

    def _phase_header(self, text: str):
        print(f"\n{Colors.CYAN}{'━'*80}{Colors.END}")
        print(f"{Colors.CYAN}{Colors.BOLD}  {text}{Colors.END}")
        print(f"{Colors.CYAN}{'━'*80}{Colors.END}")

    def _checkpoint_header(self, turn: int):
        print(f"\n{Colors.MAGENTA}{'─'*60}{Colors.END}")
        print(f"{Colors.MAGENTA}  DB CHECKPOINT @ Turn {turn}{Colors.END}")
        print(f"{Colors.MAGENTA}{'─'*60}{Colors.END}")

    # ─── Auth ────────────────────────────────────────────────────────────

    @staticmethod
    def generate_auth_token() -> Optional[str]:
        """Generate a JWT from NEXTAUTH_SECRET in backend/.env."""
        try:
            from dotenv import load_dotenv

            env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
            load_dotenv(env_path)

            secret = os.environ.get("NEXTAUTH_SECRET")
            if not secret:
                print(f"{Colors.YELLOW}Warning: NEXTAUTH_SECRET not found in .env{Colors.END}")
                return None

            import jwt

            # Find admin email from env
            admin_emails_str = os.environ.get("ADMIN_EMAILS", "")
            admin_email = admin_emails_str.split(",")[0].strip() if admin_emails_str else "stress-test@test.local"

            now = datetime.utcnow()
            payload = {
                "sub": "stress-test-runner",
                "email": admin_email,
                "name": "Memory Stress Test",
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(hours=4)).timestamp()),
            }
            token = jwt.encode(payload, secret, algorithm="HS256")
            print(f"{Colors.GREEN}OK{Colors.END} Generated JWT for {admin_email}")
            return token
        except Exception as e:
            print(f"{Colors.RED}Error{Colors.END} generating token: {e}")
            return None

    # ─── API calls ───────────────────────────────────────────────────────

    def check_health(self) -> bool:
        """Verify backend is reachable."""
        try:
            r = requests.get(
                f"{self.base_url.replace('/api/v1', '')}/health", timeout=5
            )
            if r.status_code == 200:
                print(f"{Colors.GREEN}OK{Colors.END} Backend healthy")
                return True
            print(f"{Colors.RED}FAIL{Colors.END} Backend returned {r.status_code}")
            return False
        except Exception as e:
            print(f"{Colors.RED}FAIL{Colors.END} Cannot connect: {e}")
            return False

    def create_conversation(self) -> Optional[str]:
        """Create a new conversation linked to the collection."""
        try:
            r = requests.post(
                f"{self.base_url}/conversations",
                headers=self.headers,
                json={
                    "title": f"Memory Stress Test {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    "collection_id": self.collection_id,
                },
                timeout=15,
            )
            if r.status_code in (200, 201):
                conv_id = r.json().get("id")
                print(f"{Colors.GREEN}OK{Colors.END} Created conversation: {conv_id}")
                return conv_id
            print(f"{Colors.RED}FAIL{Colors.END} Create conversation: {r.status_code} - {r.text[:200]}")
            return None
        except Exception as e:
            print(f"{Colors.RED}FAIL{Colors.END} Create conversation error: {e}")
            return None

    def send_message_stream(self, message: str, turn: int) -> Tuple[bool, str, List[Dict]]:
        """
        Send a message via the streaming endpoint and parse SSE response.

        Returns: (success, content, sources)
        """
        url = f"{self.base_url}/conversations/{self.conversation_id}/messages/stream"
        try:
            r = requests.post(
                url,
                headers=self.headers,
                json={"message": message, "mode": "chat"},
                stream=True,
                timeout=120,
            )

            if r.status_code == 429:
                return False, "__RATE_LIMITED__", []

            if r.status_code != 200:
                return False, f"HTTP {r.status_code}: {r.text[:200]}", []

            content_parts = []
            sources = []
            message_id = None

            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]  # strip "data: "
                try:
                    event = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                if event.get("type") == "content":
                    content_parts.append(event.get("content", ""))
                elif event.get("type") == "done":
                    sources = event.get("sources", [])
                    message_id = event.get("message_id")
                elif event.get("type") == "error":
                    return False, f"Stream error: {event.get('error', 'unknown')}", []

            full_content = "".join(content_parts)
            return True, full_content, sources

        except requests.exceptions.Timeout:
            return False, "__TIMEOUT__", []
        except Exception as e:
            return False, f"Exception: {e}", []

    def send_with_retry(self, message: str, turn: int) -> Tuple[bool, str, List[Dict]]:
        """Send message with rate-limit retry (exponential backoff)."""
        backoff_times = [60, 120, 180]

        for attempt in range(4):  # 1 initial + 3 retries
            success, content, sources = self.send_message_stream(message, turn)

            if content == "__RATE_LIMITED__":
                if attempt < 3:
                    wait = backoff_times[attempt]
                    print(f"  {Colors.YELLOW}Rate limited. Waiting {wait}s (attempt {attempt+1}/3)...{Colors.END}")
                    time.sleep(wait)
                    continue
                else:
                    print(f"  {Colors.RED}Rate limited after 3 retries. Giving up.{Colors.END}")
                    return False, "Rate limited - max retries exceeded", []

            if content == "__TIMEOUT__":
                if attempt < 3:
                    wait = 30
                    print(f"  {Colors.YELLOW}Timeout. Waiting {wait}s (attempt {attempt+1}/3)...{Colors.END}")
                    time.sleep(wait)
                    continue
                else:
                    return False, "Timeout - max retries exceeded", []

            return success, content, sources

        return False, "Max retries exceeded", []

    # ─── Validation ──────────────────────────────────────────────────────

    def validate_recall(
        self, response: str, concept_ids: List[int], turn: int
    ) -> Dict[str, Any]:
        """
        Check if response contains synonyms for the referenced concepts.

        A concept is considered "recalled" if at least 1 synonym appears in the response.
        Overall pass: 50%+ of referenced concepts recalled.
        """
        response_lower = response.lower()
        found_concepts = []
        missing_concepts = []

        for cid in concept_ids:
            concept = CONCEPT_REGISTRY.get(cid)
            if not concept:
                continue

            hit = any(syn.lower() in response_lower for syn in concept["synonyms"])
            if hit:
                found_concepts.append(concept["label"])
            else:
                missing_concepts.append(concept["label"])

        total = len(concept_ids)
        found_count = len(found_concepts)
        recall_rate = found_count / total if total > 0 else 0
        passed = recall_rate >= 0.5

        # Calculate distance: max distance from the turn where concept was seeded
        max_distance = max(turn - cid for cid in concept_ids) if concept_ids else 0

        # Bucket the distance
        if max_distance <= 5:
            bucket = "<=5"
        elif max_distance <= 10:
            bucket = "<=10"
        elif max_distance <= 20:
            bucket = "<=20"
        elif max_distance <= 50:
            bucket = "<=50"
        else:
            bucket = "<=100"

        result = {
            "turn": turn,
            "concept_ids": concept_ids,
            "found": found_concepts,
            "missing": missing_concepts,
            "recall_rate": recall_rate,
            "passed": passed,
            "max_distance": max_distance,
            "bucket": bucket,
        }
        self.recall_results.append(result)
        return result

    # ─── DB Checkpoints ──────────────────────────────────────────────────

    def checkpoint_facts(self, turn: int) -> Dict[str, Any]:
        """Query PostgreSQL via docker exec for fact stats at this turn."""
        self._checkpoint_header(turn)

        conv_id = self.conversation_id
        checkpoint: Dict[str, Any] = {"turn": turn, "timestamp": datetime.now().isoformat()}

        def run_sql(sql: str) -> str:
            """Execute SQL in the postgres container."""
            try:
                result = subprocess.run(
                    [
                        "docker", "exec", "rag_transcript_postgres",
                        "psql", "-U", "postgres", "-d", "rag_transcript",
                        "-t", "-A", "-c", sql,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                return result.stdout.strip()
            except subprocess.TimeoutExpired:
                return "TIMEOUT"
            except Exception as e:
                return f"ERROR: {e}"

        # Fact count
        count_str = run_sql(
            f"SELECT COUNT(*) FROM conversation_facts WHERE conversation_id = '{conv_id}'"
        )
        try:
            fact_count = int(count_str)
        except (ValueError, TypeError):
            fact_count = -1
        checkpoint["fact_count"] = fact_count
        print(f"  Facts: {fact_count}")

        # Category breakdown
        categories_str = run_sql(
            f"SELECT category, COUNT(*) FROM conversation_facts "
            f"WHERE conversation_id = '{conv_id}' GROUP BY category ORDER BY COUNT(*) DESC"
        )
        checkpoint["categories"] = categories_str
        if categories_str and categories_str not in ("TIMEOUT", ""):
            for line in categories_str.split("\n"):
                if "|" in line:
                    print(f"    {line.strip()}")

        # Facts with access reinforcement
        accessed_str = run_sql(
            f"SELECT COUNT(*) FROM conversation_facts "
            f"WHERE conversation_id = '{conv_id}' AND access_count > 0"
        )
        try:
            accessed_count = int(accessed_str)
        except (ValueError, TypeError):
            accessed_count = -1
        checkpoint["facts_accessed"] = accessed_count
        print(f"  Facts accessed (reinforced): {accessed_count}")

        # Importance stats
        importance_str = run_sql(
            f"SELECT ROUND(AVG(importance)::numeric, 2), MIN(importance), MAX(importance) "
            f"FROM conversation_facts WHERE conversation_id = '{conv_id}'"
        )
        checkpoint["importance_stats"] = importance_str
        if importance_str and "|" in importance_str:
            print(f"  Importance (avg|min|max): {importance_str}")

        # Recent facts
        recent_str = run_sql(
            f"SELECT fact_key, importance, category FROM conversation_facts "
            f"WHERE conversation_id = '{conv_id}' ORDER BY created_at DESC LIMIT 3"
        )
        checkpoint["recent_facts"] = recent_str
        if recent_str and recent_str not in ("TIMEOUT", ""):
            print(f"  Recent facts:")
            for line in recent_str.split("\n"):
                if line.strip():
                    print(f"    {line.strip()}")

        self.checkpoints.append(checkpoint)
        return checkpoint

    # ─── Run phases ──────────────────────────────────────────────────────

    def run_turn(self, turn: int, question: str, concept_ids: List[int], is_recall: bool):
        """Execute a single turn: send message, validate recall if needed."""
        # Print turn info
        prefix = f"  T{turn:3d}"
        recall_tag = f" {Colors.MAGENTA}[RECALL {','.join(str(c) for c in concept_ids)}]{Colors.END}" if is_recall else ""
        q_preview = question[:65] + "..." if len(question) > 65 else question
        print(f"{prefix}: {q_preview}{recall_tag}")

        # Send message
        success, content, sources = self.send_with_retry(question, turn)

        if not success:
            status_icon = f"{Colors.RED}ERR{Colors.END}"
            print(f"{prefix}  {status_icon} {content[:100]}")
            self.errors.append({"turn": turn, "error": content})
            return

        self.responses[turn] = content
        content_preview = content[:120].replace("\n", " ") + "..." if len(content) > 120 else content.replace("\n", " ")
        src_count = len(sources)
        print(f"{prefix}  {Colors.GREEN}OK{Colors.END} ({len(content)} chars, {src_count} sources)")
        print(f"{prefix}  {Colors.DIM}{content_preview}{Colors.END}")

        # Validate recall
        if is_recall and concept_ids:
            result = self.validate_recall(content, concept_ids, turn)
            if result["passed"]:
                print(f"{prefix}  {Colors.GREEN}RECALL OK{Colors.END} ({result['recall_rate']:.0%}) dist={result['max_distance']} [{', '.join(result['found'])}]")
            else:
                print(f"{prefix}  {Colors.RED}RECALL FAIL{Colors.END} ({result['recall_rate']:.0%}) dist={result['max_distance']}")
                if result["found"]:
                    print(f"{prefix}    Found: {', '.join(result['found'])}")
                print(f"{prefix}    Missing: {', '.join(result['missing'])}")

    def run(self):
        """Execute the full 110-turn stress test."""
        self._header("Memory Stress Test - 110 Turns")
        print(f"Collection: {self.collection_id}")
        print(f"Delay between turns: {self.delay}s")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Health check
        if not self.check_health():
            print(f"\n{Colors.RED}Aborting: backend not reachable{Colors.END}")
            return

        # Create or reuse conversation
        if not self.conversation_id:
            self.conversation_id = self.create_conversation()
            if not self.conversation_id:
                print(f"\n{Colors.RED}Aborting: failed to create conversation{Colors.END}")
                return
        else:
            print(f"{Colors.GREEN}OK{Colors.END} Resuming conversation: {self.conversation_id}")

        print(f"\nConversation ID: {self.conversation_id}")
        print(f"Resume from turn: {self.resume_from}")

        # Build flat list of all turns
        all_turns = []
        for _, phase_turns in ALL_PHASES:
            all_turns.extend(phase_turns)

        # Run phases
        for phase_name, phase_turns in ALL_PHASES:
            # Skip if all turns in this phase are before resume_from
            if all(t[0] < self.resume_from for t in phase_turns):
                continue

            self._phase_header(phase_name)

            for turn_num, question, concept_ids, is_recall in phase_turns:
                if turn_num < self.resume_from:
                    continue

                self.run_turn(turn_num, question, concept_ids, is_recall)

                # DB checkpoint
                if turn_num in CHECKPOINT_TURNS:
                    self.checkpoint_facts(turn_num)

                # Inter-turn delay
                if turn_num < 110:
                    time.sleep(self.delay)

        # Generate report
        self.generate_report()

    # ─── Report ──────────────────────────────────────────────────────────

    def generate_report(self):
        """Compile and print final test report."""
        elapsed = time.time() - self.start_time
        self._header("STRESS TEST REPORT")

        print(f"Conversation: {self.conversation_id}")
        print(f"Duration: {elapsed/60:.1f} minutes")
        print(f"Turns completed: {len(self.responses)}")
        print(f"Errors: {len(self.errors)}")

        # ── Recall by distance bucket ────────────────────────────────
        print(f"\n{Colors.BOLD}Recall by Distance Bucket{Colors.END}")
        print(f"{'─'*60}")

        bucket_stats: Dict[str, Dict[str, int]] = {}
        for bucket_name in SUCCESS_CRITERIA:
            bucket_stats[bucket_name] = {"passed": 0, "total": 0}

        for result in self.recall_results:
            b = result["bucket"]
            if b in bucket_stats:
                bucket_stats[b]["total"] += 1
                if result["passed"]:
                    bucket_stats[b]["passed"] += 1

        all_buckets_pass = True
        for bucket_name, threshold in SUCCESS_CRITERIA.items():
            stats = bucket_stats[bucket_name]
            if stats["total"] == 0:
                rate_str = "N/A"
                status = f"{Colors.DIM}SKIP{Colors.END}"
            else:
                rate = stats["passed"] / stats["total"]
                rate_str = f"{rate:.0%} ({stats['passed']}/{stats['total']})"
                if rate >= threshold:
                    status = f"{Colors.GREEN}PASS{Colors.END}"
                else:
                    status = f"{Colors.RED}FAIL{Colors.END}"
                    all_buckets_pass = False

            print(f"  {bucket_name:>8}  {rate_str:>15}  (min: {threshold:.0%})  {status}")

        # ── Phase 6 final validation ─────────────────────────────────
        print(f"\n{Colors.BOLD}Phase 6 Final Validation (Turns 101-110){Colors.END}")
        print(f"{'─'*60}")

        phase6_results = [r for r in self.recall_results if r["turn"] >= 101]
        phase6_passed = sum(1 for r in phase6_results if r["passed"])
        phase6_total = len(phase6_results)
        phase6_ok = phase6_passed >= 7 if phase6_total >= 10 else phase6_passed >= phase6_total * 0.7

        for r in phase6_results:
            status = f"{Colors.GREEN}PASS{Colors.END}" if r["passed"] else f"{Colors.RED}FAIL{Colors.END}"
            concepts = ", ".join(str(c) for c in r["concept_ids"])
            found = ", ".join(r["found"]) if r["found"] else "-"
            missing = ", ".join(r["missing"]) if r["missing"] else "-"
            print(f"  T{r['turn']:3d}  [{concepts:>12}]  {r['recall_rate']:.0%}  dist={r['max_distance']:3d}  {status}")
            if r["missing"]:
                print(f"        Missing: {missing}")

        print(f"\n  Phase 6: {phase6_passed}/{phase6_total} passed (need 7/10)")
        phase6_status = f"{Colors.GREEN}PASS{Colors.END}" if phase6_ok else f"{Colors.RED}FAIL{Colors.END}"
        print(f"  Status: {phase6_status}")

        # ── Fact growth ──────────────────────────────────────────────
        print(f"\n{Colors.BOLD}Fact Growth at Checkpoints{Colors.END}")
        print(f"{'─'*60}")

        fact_counts = []
        monotonic = True
        for cp in self.checkpoints:
            count = cp.get("fact_count", -1)
            fact_counts.append(count)
            if len(fact_counts) > 1 and count < fact_counts[-2] and count >= 0:
                monotonic = False
            accessed = cp.get("facts_accessed", "?")
            print(f"  Turn {cp['turn']:3d}: {count:4d} facts  (accessed: {accessed})")

        mono_status = f"{Colors.GREEN}PASS{Colors.END}" if monotonic else f"{Colors.RED}FAIL{Colors.END}"
        print(f"\n  Monotonic growth: {mono_status}")

        # ── Errors ───────────────────────────────────────────────────
        if self.errors:
            print(f"\n{Colors.BOLD}Errors{Colors.END}")
            print(f"{'─'*60}")
            for err in self.errors:
                print(f"  Turn {err['turn']}: {err['error'][:100]}")

        # ── Overall verdict ──────────────────────────────────────────
        print(f"\n{'='*60}")
        overall = all_buckets_pass and phase6_ok and monotonic
        if overall:
            print(f"{Colors.GREEN}{Colors.BOLD}  OVERALL: PASS{Colors.END}")
        else:
            print(f"{Colors.RED}{Colors.BOLD}  OVERALL: FAIL{Colors.END}")
            if not all_buckets_pass:
                print(f"  - One or more distance buckets below threshold")
            if not phase6_ok:
                print(f"  - Phase 6 final validation failed ({phase6_passed}/10)")
            if not monotonic:
                print(f"  - Fact count did not grow monotonically")
        print(f"{'='*60}\n")

        # Save report to file
        self._save_report(overall)

    def _save_report(self, overall_pass: bool):
        """Save structured report to JSON."""
        report_path = os.path.join(
            os.path.dirname(__file__), "..",
            f"tests/memory_stress_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        report = {
            "conversation_id": self.conversation_id,
            "collection_id": self.collection_id,
            "overall_pass": overall_pass,
            "turns_completed": len(self.responses),
            "duration_minutes": (time.time() - self.start_time) / 60,
            "recall_results": self.recall_results,
            "checkpoints": self.checkpoints,
            "errors": self.errors,
            "timestamp": datetime.now().isoformat(),
        }
        try:
            os.makedirs(os.path.dirname(report_path), exist_ok=True)
            with open(report_path, "w") as f:
                json.dump(report, f, indent=2, default=str)
            print(f"Report saved: {report_path}")
        except Exception as e:
            print(f"Warning: Could not save report: {e}")


def main():
    parser = argparse.ArgumentParser(description="100+ Turn Memory Stress Test")
    parser.add_argument(
        "--collection-id",
        default=DEFAULT_COLLECTION_ID,
        help=f"Collection ID to test against (default: {DEFAULT_COLLECTION_ID})",
    )
    parser.add_argument(
        "--auth-token",
        default=os.environ.get("AUTH_TOKEN"),
        help="Bearer token for API auth (or set AUTH_TOKEN env var)",
    )
    parser.add_argument(
        "--conversation-id",
        default=None,
        help="Resume an existing conversation instead of creating new",
    )
    parser.add_argument(
        "--resume-from",
        type=int,
        default=1,
        help="Resume from this turn number (default: 1)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Seconds between turns (default: 2.0)",
    )
    parser.add_argument(
        "--base-url",
        default=BASE_URL,
        help=f"API base URL (default: {BASE_URL})",
    )
    args = parser.parse_args()

    # Resolve auth token
    auth_token = args.auth_token
    if not auth_token:
        print(f"{Colors.BLUE}Generating auth token from NEXTAUTH_SECRET...{Colors.END}")
        auth_token = MemoryStressTestRunner.generate_auth_token()
    if not auth_token:
        print(f"{Colors.RED}No auth token available. Use --auth-token or set NEXTAUTH_SECRET in backend/.env{Colors.END}")
        sys.exit(1)

    runner = MemoryStressTestRunner(
        collection_id=args.collection_id,
        auth_token=auth_token,
        base_url=args.base_url,
        conversation_id=args.conversation_id,
        resume_from=args.resume_from,
        delay=args.delay,
    )
    runner.run()


if __name__ == "__main__":
    main()
