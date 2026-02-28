#!/usr/bin/env python3
"""
Reset a test user for re-testing signup/checkout flows.

Usage:
    docker compose exec app python scripts/reset_test_user.py simon.chiasd1@gmail.com

This deletes all data for the user, allowing you to test the signup flow again.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.base import SessionLocal


def reset_user(email: str) -> bool:
    """Delete all records for a user by email."""
    db = SessionLocal()

    try:
        # First, find the user
        result = db.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": email}
        )
        row = result.fetchone()

        if not row:
            print(f"❌ User not found: {email}")
            return False

        user_id = str(row[0])
        print(f"Found user: {email} (ID: {user_id})")

        # Delete in order of foreign key dependencies
        tables_to_clean = [
            ("message_chunk_references",
             """DELETE FROM message_chunk_references
                WHERE message_id IN (
                    SELECT m.id FROM messages m
                    JOIN conversations c ON m.conversation_id = c.id
                    WHERE c.user_id = :user_id
                )"""),
            ("messages",
             """DELETE FROM messages
                WHERE conversation_id IN (
                    SELECT id FROM conversations WHERE user_id = :user_id
                )"""),
            ("conversation_sources",
             """DELETE FROM conversation_sources
                WHERE conversation_id IN (
                    SELECT id FROM conversations WHERE user_id = :user_id
                )"""),
            ("conversation_facts",
             """DELETE FROM conversation_facts
                WHERE conversation_id IN (
                    SELECT id FROM conversations WHERE user_id = :user_id
                )"""),
            ("conversation_insights",
             """DELETE FROM conversation_insights
                WHERE conversation_id IN (
                    SELECT id FROM conversations WHERE user_id = :user_id
                )"""),
            ("conversations", "DELETE FROM conversations WHERE user_id = :user_id"),
            ("chunks", "DELETE FROM chunks WHERE user_id = :user_id"),
            ("transcripts",
             """DELETE FROM transcripts
                WHERE video_id IN (SELECT id FROM videos WHERE user_id = :user_id)"""),
            ("jobs", "DELETE FROM jobs WHERE user_id = :user_id"),
            ("videos", "DELETE FROM videos WHERE user_id = :user_id"),
            ("collections", "DELETE FROM collections WHERE user_id = :user_id"),
            ("usage_events", "DELETE FROM usage_events WHERE user_id = :user_id"),
            ("subscriptions", "DELETE FROM subscriptions WHERE user_id = :user_id"),
            ("users", "DELETE FROM users WHERE id = :user_id"),
        ]

        for table_name, query in tables_to_clean:
            try:
                result = db.execute(text(query), {"user_id": user_id})
                count = result.rowcount
                if count > 0:
                    print(f"  ✓ {table_name}: {count} row(s) deleted")
            except Exception as e:
                # Table might not exist or other issue
                if "does not exist" in str(e):
                    print(f"  - {table_name}: skipped (table doesn't exist)")
                else:
                    print(f"  ⚠ {table_name}: {e}")

        db.commit()
        print(f"\n✅ User {email} has been completely reset. You can test signup again.")
        return True

    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/reset_test_user.py <email>")
        print("Example: python scripts/reset_test_user.py simon.chiasd1@gmail.com")
        sys.exit(1)

    email = sys.argv[1]

    # Safety check - prevent accidental deletion of non-test accounts
    if not any(pattern in email.lower() for pattern in ["test", "simon", "demo", "dev"]):
        confirm = input(f"⚠️  '{email}' doesn't look like a test account. Are you sure? (yes/no): ")
        if confirm.lower() != "yes":
            print("Aborted.")
            sys.exit(1)

    success = reset_user(email)
    sys.exit(0 if success else 1)
