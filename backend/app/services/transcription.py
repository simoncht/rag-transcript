"""
Transcription service using faster-whisper (CTranslate2).

Handles audio transcription with:
- Segment timestamps
- Language detection
- INT8 quantization for ~4x CPU speedup vs openai-whisper
- Progress tracking
"""
import os
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass
from faster_whisper import WhisperModel

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
    Whisper transcription service using faster-whisper (CTranslate2).

    ~4x faster than openai-whisper on CPU with INT8 quantization.
    """

    def __init__(self, model_name: str = None, device: str = None):
        """
        Initialize faster-whisper transcription service.

        Args:
            model_name: Whisper model name (tiny, base, small, medium, large-v3)
            device: Device to run on ("cpu" or "cuda")
        """
        self.model_name = model_name or settings.whisper_model
        self.device = device or settings.whisper_device

        self.compute_type = getattr(settings, "whisper_compute_type", "int8")

        print(f"Loading faster-whisper model: {self.model_name} ({self.compute_type})")
        self.model = WhisperModel(
            self.model_name,
            device=self.device,
            compute_type=self.compute_type,
        )
        print(f"faster-whisper model loaded on {self.device} ({self.compute_type})")

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

        try:
            transcribe_options = {
                "beam_size": 5,
                "word_timestamps": False,
            }

            if language:
                transcribe_options["language"] = language

            if progress_callback:
                progress_callback(
                    {"status": "transcribing", "message": "Transcribing audio..."}
                )

            # faster-whisper returns (segments_generator, info)
            segments_gen, info = self.model.transcribe(
                audio_path, **transcribe_options
            )

            if progress_callback:
                progress_callback(
                    {"status": "processing", "message": "Processing transcript..."}
                )

            # Consume the generator into a list of segments
            segments = []
            for seg in segments_gen:
                text = seg.text.strip()
                if text:
                    segments.append(
                        TranscriptSegment(
                            text=text,
                            start=seg.start,
                            end=seg.end,
                            speaker=None,
                        )
                    )

            # Build full text
            full_text = " ".join(seg.text.strip() for seg in segments)

            # Calculate duration (from last segment)
            duration_seconds = segments[-1].end if segments else 0.0

            # Count words
            word_count = len(full_text.split())

            # Language from info
            detected_language = info.language or "unknown"

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
