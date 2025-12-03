"""
Storage service abstraction for local and cloud storage.

Provides a unified interface for file storage operations that can be backed by
either local filesystem or Azure Blob Storage.
"""
import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, Optional
from uuid import UUID

from app.core.config import settings


class StorageService(ABC):
    """Abstract base class for storage operations."""

    @abstractmethod
    def upload_audio(self, user_id: UUID, video_id: UUID, file_stream: BinaryIO, filename: str) -> str:
        """
        Upload audio file to storage.

        Args:
            user_id: User ID for isolation
            video_id: Video ID
            file_stream: Binary file stream
            filename: Original filename

        Returns:
            Storage path/URL
        """
        pass

    @abstractmethod
    def download_audio(self, user_id: UUID, video_id: UUID) -> BinaryIO:
        """
        Download audio file from storage.

        Args:
            user_id: User ID
            video_id: Video ID

        Returns:
            Binary file stream
        """
        pass

    @abstractmethod
    def delete_audio(self, user_id: UUID, video_id: UUID) -> bool:
        """
        Delete audio file from storage.

        Args:
            user_id: User ID
            video_id: Video ID

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def save_transcript(self, user_id: UUID, video_id: UUID, transcript_data: dict) -> str:
        """
        Save transcript JSON to storage.

        Args:
            user_id: User ID
            video_id: Video ID
            transcript_data: Transcript data as dictionary

        Returns:
            Storage path/URL
        """
        pass

    @abstractmethod
    def load_transcript(self, user_id: UUID, video_id: UUID) -> Optional[dict]:
        """
        Load transcript JSON from storage.

        Args:
            user_id: User ID
            video_id: Video ID

        Returns:
            Transcript data dict or None if not found
        """
        pass

    @abstractmethod
    def get_storage_usage(self, user_id: UUID) -> float:
        """
        Get total storage usage for a user in MB.

        Args:
            user_id: User ID

        Returns:
            Storage usage in MB
        """
        pass

    @abstractmethod
    def file_exists(self, path: str) -> bool:
        """
        Check if a file exists at the given path.

        Args:
            path: Storage path

        Returns:
            True if file exists
        """
        pass


class LocalStorageService(StorageService):
    """
    Local filesystem storage implementation.

    Stores files in a local directory structure:
    storage/
      audio/
        {user_id}/
          {video_id}/
            audio.mp3
      transcripts/
        {user_id}/
          {video_id}/
            transcript.json
            chunks.json
    """

    def __init__(self, base_path: str = None):
        self.base_path = Path(base_path or settings.local_storage_path)
        self.audio_path = self.base_path / "audio"
        self.transcript_path = self.base_path / "transcripts"

        # Create directories if they don't exist
        self.audio_path.mkdir(parents=True, exist_ok=True)
        self.transcript_path.mkdir(parents=True, exist_ok=True)

    def _get_audio_dir(self, user_id: UUID, video_id: UUID) -> Path:
        """Get audio directory path for a video."""
        return self.audio_path / str(user_id) / str(video_id)

    def _get_transcript_dir(self, user_id: UUID, video_id: UUID) -> Path:
        """Get transcript directory path for a video."""
        return self.transcript_path / str(user_id) / str(video_id)

    def upload_audio(self, user_id: UUID, video_id: UUID, file_stream: BinaryIO, filename: str) -> str:
        """Upload audio file to local storage."""
        # Determine file extension
        ext = Path(filename).suffix or ".mp3"
        audio_dir = self._get_audio_dir(user_id, video_id)
        audio_dir.mkdir(parents=True, exist_ok=True)

        file_path = audio_dir / f"audio{ext}"

        # Write file
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file_stream, f)

        return str(file_path)

    def download_audio(self, user_id: UUID, video_id: UUID) -> BinaryIO:
        """Download audio file from local storage."""
        audio_dir = self._get_audio_dir(user_id, video_id)

        # Find audio file (could have different extensions)
        for ext in [".mp3", ".m4a", ".wav", ".webm"]:
            file_path = audio_dir / f"audio{ext}"
            if file_path.exists():
                return open(file_path, "rb")

        raise FileNotFoundError(f"Audio file not found for video {video_id}")

    def delete_audio(self, user_id: UUID, video_id: UUID) -> bool:
        """Delete audio file from local storage."""
        audio_dir = self._get_audio_dir(user_id, video_id)

        if audio_dir.exists():
            shutil.rmtree(audio_dir)
            return True

        return False

    def save_transcript(self, user_id: UUID, video_id: UUID, transcript_data: dict) -> str:
        """Save transcript JSON to local storage."""
        import json

        transcript_dir = self._get_transcript_dir(user_id, video_id)
        transcript_dir.mkdir(parents=True, exist_ok=True)

        file_path = transcript_dir / "transcript.json"

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(transcript_data, f, indent=2, ensure_ascii=False)

        return str(file_path)

    def load_transcript(self, user_id: UUID, video_id: UUID) -> Optional[dict]:
        """Load transcript JSON from local storage."""
        import json

        transcript_dir = self._get_transcript_dir(user_id, video_id)
        file_path = transcript_dir / "transcript.json"

        if not file_path.exists():
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_storage_usage(self, user_id: UUID) -> float:
        """Get total storage usage for a user in MB."""
        total_bytes = 0

        # Check audio directory
        user_audio_dir = self.audio_path / str(user_id)
        if user_audio_dir.exists():
            for file_path in user_audio_dir.rglob("*"):
                if file_path.is_file():
                    total_bytes += file_path.stat().st_size

        # Check transcript directory
        user_transcript_dir = self.transcript_path / str(user_id)
        if user_transcript_dir.exists():
            for file_path in user_transcript_dir.rglob("*"):
                if file_path.is_file():
                    total_bytes += file_path.stat().st_size

        return total_bytes / (1024 * 1024)  # Convert to MB

    def file_exists(self, path: str) -> bool:
        """Check if a file exists at the given path."""
        return Path(path).exists()


class AzureBlobStorageService(StorageService):
    """
    Azure Blob Storage implementation (for production).

    To be fully implemented when migrating to Azure.
    """

    def __init__(self):
        # TODO: Initialize Azure Blob Storage client
        # from azure.storage.blob import BlobServiceClient
        # self.blob_service_client = BlobServiceClient.from_connection_string(
        #     settings.azure_storage_connection_string
        # )
        raise NotImplementedError("Azure Blob Storage not yet implemented. Use local storage for now.")

    def upload_audio(self, user_id: UUID, video_id: UUID, file_stream: BinaryIO, filename: str) -> str:
        raise NotImplementedError()

    def download_audio(self, user_id: UUID, video_id: UUID) -> BinaryIO:
        raise NotImplementedError()

    def delete_audio(self, user_id: UUID, video_id: UUID) -> bool:
        raise NotImplementedError()

    def save_transcript(self, user_id: UUID, video_id: UUID, transcript_data: dict) -> str:
        raise NotImplementedError()

    def load_transcript(self, user_id: UUID, video_id: UUID) -> Optional[dict]:
        raise NotImplementedError()

    def get_storage_usage(self, user_id: UUID) -> float:
        raise NotImplementedError()

    def file_exists(self, path: str) -> bool:
        raise NotImplementedError()


def get_storage_service() -> StorageService:
    """
    Factory function to get the appropriate storage service based on configuration.

    Returns:
        StorageService instance (Local or Azure)
    """
    if settings.storage_backend == "local":
        return LocalStorageService()
    elif settings.storage_backend == "azure":
        return AzureBlobStorageService()
    else:
        raise ValueError(f"Unknown storage backend: {settings.storage_backend}")


# Global storage service instance
storage_service = get_storage_service()
