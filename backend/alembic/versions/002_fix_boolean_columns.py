"""Fix Boolean column types

Revision ID: 002_fix_boolean
Revises: 001_initial
Create Date: 2024-01-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_fix_boolean'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fix transcripts.has_speaker_labels: String -> Boolean
    # PostgreSQL can cast string 'false'/'true' to boolean, but we need to handle the conversion
    op.execute("""
        ALTER TABLE transcripts
        ALTER COLUMN has_speaker_labels
        TYPE BOOLEAN
        USING CASE
            WHEN has_speaker_labels = 'false' OR has_speaker_labels = 'False' OR has_speaker_labels = '0' THEN FALSE
            WHEN has_speaker_labels = 'true' OR has_speaker_labels = 'True' OR has_speaker_labels = '1' THEN TRUE
            ELSE FALSE
        END
    """)

    # Fix chunks.is_indexed: String -> Boolean
    op.execute("""
        ALTER TABLE chunks
        ALTER COLUMN is_indexed
        TYPE BOOLEAN
        USING CASE
            WHEN is_indexed = 'false' OR is_indexed = 'False' OR is_indexed = '0' THEN FALSE
            WHEN is_indexed = 'true' OR is_indexed = 'True' OR is_indexed = '1' THEN TRUE
            ELSE FALSE
        END
    """)

    # Fix message_chunk_references.was_used_in_response: String -> Boolean
    op.execute("""
        ALTER TABLE message_chunk_references
        ALTER COLUMN was_used_in_response
        TYPE BOOLEAN
        USING CASE
            WHEN was_used_in_response = 'false' OR was_used_in_response = 'False' OR was_used_in_response = '0' THEN FALSE
            WHEN was_used_in_response = 'true' OR was_used_in_response = 'True' OR was_used_in_response = '1' THEN TRUE
            ELSE TRUE
        END
    """)


def downgrade() -> None:
    # Revert back to String type
    op.execute("""
        ALTER TABLE transcripts
        ALTER COLUMN has_speaker_labels
        TYPE VARCHAR
        USING CASE
            WHEN has_speaker_labels THEN 'true'
            ELSE 'false'
        END
    """)

    op.execute("""
        ALTER TABLE chunks
        ALTER COLUMN is_indexed
        TYPE VARCHAR
        USING CASE
            WHEN is_indexed THEN 'true'
            ELSE 'false'
        END
    """)

    op.execute("""
        ALTER TABLE message_chunk_references
        ALTER COLUMN was_used_in_response
        TYPE VARCHAR
        USING CASE
            WHEN was_used_in_response THEN 'true'
            ELSE 'false'
        END
    """)
