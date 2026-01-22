"""
Transcription service using OpenAI Whisper.

Handles audio transcription with:
- Segment timestamps
- Language detection
- Speaker diarization (if supported by model)
- Progress tracking
"""
import os
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass
import whisper

from app.core.config import settings
from app.services.chunking import TranscriptSegment


@dataclass
class TranscriptResult:
    """
    Result from transcription.

    Attributes:
        full_text: Complete transcript text
        segments: List of transcript segments with timestamps
        language: Detected language code
        duration_seconds: Audio duration
        word_count: Total word count
    """

    full_text: str
    segments: List[TranscriptSegment]
    language: str
    duration_seconds: float
    word_count: int


class WhisperTranscriptionService:
    """
    Whisper transcription service.

    Uses OpenAI's Whisper model for speech-to-text with high accuracy.
    """

    def __init__(self, model_name: str = None, device: str = None):
        """
        Initialize Whisper transcription service.

        Args:
            model_name: Whisper model name (tiny, base, small, medium, large)
            device: Device to run on ("cpu" or "cuda")
        """
        self.model_name = model_name or settings.whisper_model
        self.device = device or settings.whisper_device

        # Load Whisper model
        print(f"Loading Whisper model: {self.model_name}")
        self.model = whisper.load_model(self.model_name, device=self.device)
        print(f"Whisper model loaded on {self.device}")

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
    ) -> TranscriptResult:
        """
        Transcribe audio file.

        Args:
            audio_path: Path to audio file
            language: Optional language code (e.g., "en", "es") - auto-detect if None
            progress_callback: Optional callback function for progress updates

        Returns:
            TranscriptResult with full text and segments

        Raises:
            FileNotFoundError: If audio file doesn't exist
            Exception: If transcription fails
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        if progress_callback:
            progress_callback({"status": "loading", "message": "Loading audio file..."})

        # Transcribe with Whisper
        try:
            transcribe_options = {
                "verbose": False,
                "word_timestamps": False,  # Set to True if you want word-level timestamps
            }

            if language:
                transcribe_options["language"] = language

            if progress_callback:
                progress_callback(
                    {"status": "transcribing", "message": "Transcribing audio..."}
                )

            result = self.model.transcribe(audio_path, **transcribe_options)

            if progress_callback:
                progress_callback(
                    {"status": "processing", "message": "Processing transcript..."}
                )

            # Extract segments
            segments = self._extract_segments(result["segments"])

            # Build full text
            full_text = " ".join(seg.text.strip() for seg in segments)

            # Calculate duration (from last segment)
            duration_seconds = segments[-1].end if segments else 0.0

            # Count words
            word_count = len(full_text.split())

            # Detect language
            detected_language = result.get("language", "unknown")

            if progress_callback:
                progress_callback(
                    {"status": "completed", "message": "Transcription completed"}
                )

            return TranscriptResult(
                full_text=full_text,
                segments=segments,
                language=detected_language,
                duration_seconds=duration_seconds,
                word_count=word_count,
            )

        except Exception as e:
            if progress_callback:
                progress_callback(
                    {"status": "failed", "message": f"Transcription failed: {str(e)}"}
                )
            raise Exception(f"Transcription failed: {str(e)}")

    def _extract_segments(
        self, whisper_segments: List[Dict]
    ) -> List[TranscriptSegment]:
        """
        Convert Whisper segments to TranscriptSegment objects.

        Args:
            whisper_segments: Raw segments from Whisper

        Returns:
            List of TranscriptSegment objects
        """
        segments = []

        for seg in whisper_segments:
            # Extract basic info
            text = seg["text"].strip()
            start = seg["start"]
            end = seg["end"]

            # Speaker info (if available from diarization)
            # Note: Basic Whisper doesn't include speaker labels
            # You'd need a separate diarization model for this
            speaker = None

            segment = TranscriptSegment(
                text=text, start=start, end=end, speaker=speaker
            )

            segments.append(segment)

        return segments

    def get_model_info(self) -> Dict:
        """Get information about the loaded model."""
        return {
            "model": self.model_name,
            "device": self.device,
            "multilingual": self.model_name
            not in ["tiny.en", "base.en", "small.en", "medium.en"],
        }


class TranscriptionService:
    """
    High-level transcription service with multiple backend support.

    Currently supports Whisper, could be extended for other services.
    """

    def __init__(self, backend: str = "whisper"):
        """
        Initialize transcription service.

        Args:
            backend: Transcription backend ("whisper", "deepgram", "assemblyai", etc.)
        """
        self.backend = backend

        if backend == "whisper":
            self.service = WhisperTranscriptionService()
        else:
            raise ValueError(f"Unknown transcription backend: {backend}")

    def transcribe_file(
        self,
        audio_path: str,
        language: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
    ) -> TranscriptResult:
        """
        Transcribe audio file.

        Args:
            audio_path: Path to audio file
            language: Optional language code
            progress_callback: Optional progress callback

        Returns:
            TranscriptResult
        """
        return self.service.transcribe(audio_path, language, progress_callback)

    def get_model_info(self) -> Dict:
        """Get model information."""
        info = self.service.get_model_info()
        info["backend"] = self.backend
        return info


# Global transcription service instance
transcription_service = TranscriptionService()
