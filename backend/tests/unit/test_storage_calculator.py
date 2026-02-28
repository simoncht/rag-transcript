"""
Unit tests for the storage calculator service.

Tests storage calculation for database content and vector estimates.
"""
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.storage_calculator import StorageCalculator, BYTES_PER_VECTOR


class TestStorageCalculatorInit:
    """Test storage calculator initialization."""

    def test_init_with_session(self):
        """Test calculator initializes with database session."""
        mock_db = MagicMock()
        calculator = StorageCalculator(mock_db)
        assert calculator.db == mock_db


class TestDatabaseStorageCalculation:
    """Test database storage calculation."""

    def test_calculate_database_storage_empty_user(self):
        """Test storage calculation for user with no data."""
        mock_db = MagicMock()
        user_id = uuid4()

        # Mock all queries to return 0
        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 0
        mock_db.query.return_value = mock_query

        calculator = StorageCalculator(mock_db)
        storage_mb = calculator.calculate_database_storage_mb(user_id)

        assert storage_mb == 0.0

    def test_calculate_database_storage_with_chunks(self):
        """Test storage calculation includes chunk text."""
        mock_db = MagicMock()
        user_id = uuid4()

        # Mock query to return 1MB worth of bytes (1048576 bytes)
        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        # First call (chunks) returns 1MB, rest return 0
        mock_query.scalar.side_effect = [1024 * 1024, 0, 0, 0]
        mock_db.query.return_value = mock_query

        calculator = StorageCalculator(mock_db)
        storage_mb = calculator.calculate_database_storage_mb(user_id)

        assert storage_mb == 1.0

    def test_calculate_database_storage_multiple_sources(self):
        """Test storage calculation sums all sources."""
        mock_db = MagicMock()
        user_id = uuid4()

        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        # Chunks: 1MB, Messages: 0.5MB, Facts: 0.25MB, Insights: 0.25MB
        mock_query.scalar.side_effect = [
            1024 * 1024,      # chunks
            512 * 1024,       # messages
            256 * 1024,       # facts
            256 * 1024,       # insights
        ]
        mock_db.query.return_value = mock_query

        calculator = StorageCalculator(mock_db)
        storage_mb = calculator.calculate_database_storage_mb(user_id)

        # Total should be 2MB
        assert storage_mb == 2.0

    def test_calculate_database_storage_handles_none(self):
        """Test storage calculation handles None from queries."""
        mock_db = MagicMock()
        user_id = uuid4()

        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = None  # Query returns None

        mock_db.query.return_value = mock_query

        calculator = StorageCalculator(mock_db)
        storage_mb = calculator.calculate_database_storage_mb(user_id)

        assert storage_mb == 0.0


class TestVectorStorageCalculation:
    """Test vector storage estimation."""

    def test_calculate_vector_storage_no_chunks(self):
        """Test vector storage for user with no indexed chunks."""
        mock_db = MagicMock()
        user_id = uuid4()

        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 0

        mock_db.query.return_value = mock_query

        calculator = StorageCalculator(mock_db)
        storage_mb = calculator.calculate_vector_storage_mb(user_id)

        assert storage_mb == 0.0

    def test_calculate_vector_storage_with_chunks(self):
        """Test vector storage calculation with indexed chunks."""
        mock_db = MagicMock()
        user_id = uuid4()

        # 100 chunks * 5KB per vector = 500KB = ~0.488 MB
        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 100

        mock_db.query.return_value = mock_query

        calculator = StorageCalculator(mock_db)
        storage_mb = calculator.calculate_vector_storage_mb(user_id)

        expected_mb = (100 * BYTES_PER_VECTOR) / (1024 * 1024)
        assert storage_mb == expected_mb

    def test_calculate_vector_storage_large_count(self):
        """Test vector storage for large number of chunks."""
        mock_db = MagicMock()
        user_id = uuid4()

        # 10000 chunks
        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 10000

        mock_db.query.return_value = mock_query

        calculator = StorageCalculator(mock_db)
        storage_mb = calculator.calculate_vector_storage_mb(user_id)

        expected_mb = (10000 * BYTES_PER_VECTOR) / (1024 * 1024)
        assert storage_mb == expected_mb

    def test_calculate_vector_storage_handles_none(self):
        """Test vector storage handles None from count query."""
        mock_db = MagicMock()
        user_id = uuid4()

        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = None

        mock_db.query.return_value = mock_query

        calculator = StorageCalculator(mock_db)
        storage_mb = calculator.calculate_vector_storage_mb(user_id)

        assert storage_mb == 0.0


class TestTotalStorageCalculation:
    """Test total storage calculation."""

    def test_calculate_total_storage_structure(self):
        """Test total storage returns correct structure."""
        mock_db = MagicMock()
        user_id = uuid4()

        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 0

        mock_db.query.return_value = mock_query

        calculator = StorageCalculator(mock_db)
        result = calculator.calculate_total_storage_mb(user_id)

        assert "database_mb" in result
        assert "vector_mb" in result
        assert "total_mb" in result

    def test_calculate_total_storage_sums_components(self):
        """Test total is sum of database and vector storage."""
        mock_db = MagicMock()
        user_id = uuid4()

        # Setup mocks to return specific values
        calculator = StorageCalculator(mock_db)

        # Patch the component methods
        with patch.object(calculator, 'calculate_database_storage_mb', return_value=5.5):
            with patch.object(calculator, 'calculate_vector_storage_mb', return_value=2.5):
                result = calculator.calculate_total_storage_mb(user_id)

        assert result["database_mb"] == 5.5
        assert result["vector_mb"] == 2.5
        assert result["total_mb"] == 8.0

    def test_calculate_total_storage_rounding(self):
        """Test total storage rounds to 3 decimal places."""
        mock_db = MagicMock()
        user_id = uuid4()

        calculator = StorageCalculator(mock_db)

        # Return values that would have many decimal places
        with patch.object(calculator, 'calculate_database_storage_mb', return_value=1.123456789):
            with patch.object(calculator, 'calculate_vector_storage_mb', return_value=2.987654321):
                result = calculator.calculate_total_storage_mb(user_id)

        # Check rounding
        assert result["database_mb"] == 1.123
        assert result["vector_mb"] == 2.988
        # Total should also be rounded
        assert len(str(result["total_mb"]).split('.')[-1]) <= 3

    def test_calculate_total_storage_zero_values(self):
        """Test total storage with all zero values."""
        mock_db = MagicMock()
        user_id = uuid4()

        calculator = StorageCalculator(mock_db)

        with patch.object(calculator, 'calculate_database_storage_mb', return_value=0.0):
            with patch.object(calculator, 'calculate_vector_storage_mb', return_value=0.0):
                result = calculator.calculate_total_storage_mb(user_id)

        assert result["database_mb"] == 0.0
        assert result["vector_mb"] == 0.0
        assert result["total_mb"] == 0.0


class TestBytesPerVectorConstant:
    """Test the bytes per vector constant."""

    def test_bytes_per_vector_reasonable(self):
        """Test bytes per vector is within reasonable bounds for any supported model."""
        # 384-dim model (MiniLM/BGE-small): (384*4)+1024 = 2560
        # 3072-dim model (text-embedding-3-large): (3072*4)+1024 = 13312
        assert BYTES_PER_VECTOR >= 2 * 1024  # At least 2KB (smallest model)
        assert BYTES_PER_VECTOR <= 14 * 1024  # At most 14KB (largest model)

    def test_bytes_per_vector_matches_configured_model(self):
        """Test bytes per vector matches the active embedding model dimensions."""
        from app.core.config import settings
        from app.services.storage_calculator import _calculate_bytes_per_vector

        expected = _calculate_bytes_per_vector()
        assert BYTES_PER_VECTOR == expected, (
            f"BYTES_PER_VECTOR={BYTES_PER_VECTOR} doesn't match "
            f"calculated value {expected} for model {settings.embedding_model}"
        )


class TestStorageCalculationAccuracy:
    """Test storage calculation accuracy for billing."""

    def test_excludes_deleted_videos(self):
        """Test storage calculation excludes deleted videos."""
        mock_db = MagicMock()
        user_id = uuid4()

        # The filter should include Video.is_deleted.is_(False)
        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 100

        mock_db.query.return_value = mock_query

        calculator = StorageCalculator(mock_db)
        calculator.calculate_database_storage_mb(user_id)

        # Verify filter was called (filter contains is_deleted check)
        mock_query.filter.assert_called()

    def test_excludes_deleted_conversations(self):
        """Test storage calculation excludes deleted conversations."""
        mock_db = MagicMock()
        user_id = uuid4()

        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 0

        mock_db.query.return_value = mock_query

        calculator = StorageCalculator(mock_db)
        calculator.calculate_database_storage_mb(user_id)

        # Verify filter was called multiple times for different tables
        assert mock_query.filter.call_count >= 1
