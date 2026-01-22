"""
YouTube video downloader service using yt-dlp.

Handles downloading audio from YouTube videos and extracting metadata.
Supports caption extraction for faster transcription when available.
"""
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from uuid import UUID
import yt_dlp

from app.core.config import settings
from app.services.storage import storage_service
from app.services.caption_parser import (
    parse_vtt_to_segments,
    segments_to_full_text,
    get_transcript_stats,
)

logger = logging.getLogger(__name__)


class YouTubeDownloadError(Exception):
    """Exception raised when YouTube download fails."""

    pass


class YouTubeService:
    """Service for downloading and processing YouTube videos."""

    def __init__(self):
        self.max_duration = settings.max_video_duration_seconds
        self.max_file_size = (
            settings.max_video_file_size_mb * 1024 * 1024
        )  # Convert to bytes
        self._default_headers = {
            # Modern desktop UA helps avoid 403s on some videos
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://www.youtube.com",
            "Referer": "https://www.youtube.com",
        }

    def _normalize_url(self, url: str) -> str:
        """
        Normalize YouTube URLs to canonical watch form so yt-dlp avoids odd query params.
        """
        video_id = self.extract_video_id(url)
        return f"https://www.youtube.com/watch?v={video_id}"

    def _common_yt_opts(
        self, player_client: Optional[str] = None, referer: Optional[str] = None
    ) -> Dict:
        """
        Shared yt-dlp options to reduce 403/availability issues.
        """
        client_profiles: List[str] = (
            [player_client] if player_client else ["android", "web", "ios"]
        )
        headers = dict(self._default_headers)
        if referer:
            headers["Referer"] = referer

        return {
            "http_headers": headers,
            "extractor_args": {
                "youtube": {
                    # Try multiple client profiles; Android often avoids rate/region blocks
                    "player_client": client_profiles,
                }
            },
            "geo_bypass": True,
            "geo_bypass_country": "US",
            "nocheckcertificate": True,
            # Force IPv4 to avoid IPv6-only blocks that can manifest as 403s
            "source_address": "0.0.0.0",
        }

    def extract_video_id(self, url: str) -> str:
        """
        Extract YouTube video ID from URL.

        Args:
            url: YouTube URL

        Returns:
            YouTube video ID

        Raises:
            YouTubeDownloadError: If URL is invalid
        """
        import re

        # Support common YouTube URL shapes including watch, short links,
        # embeds, legacy /v, shorts, and live URLs.
        patterns = [
            # Standard watch + short youtu.be links
            r"(?:youtube\.com/(?:watch\?v=|shorts/|live/)|youtu\.be/)([^&\n?#/]+)",
            # Embed URLs
            r"youtube\.com/embed/([^&\n?#/]+)",
            # Legacy /v URLs
            r"youtube\.com/v/([^&\n?#/]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        raise YouTubeDownloadError(f"Could not extract video ID from URL: {url}")

    def get_video_info(self, url: str) -> Dict:
        """
        Extract video metadata without downloading.

        Args:
            url: YouTube URL

        Returns:
            Dictionary containing video metadata

        Raises:
            YouTubeDownloadError: If metadata extraction fails
        """
        normalized_url = self._normalize_url(url)

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            **self._common_yt_opts(referer=normalized_url),
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(normalized_url, download=False)

                # Extract chapter information if available
                chapters = None
                if info.get("chapters"):
                    chapters = [
                        {
                            "title": chapter.get("title", f"Chapter {i+1}"),
                            "start_time": chapter.get("start_time", 0),
                            "end_time": chapter.get("end_time", 0),
                        }
                        for i, chapter in enumerate(info["chapters"])
                    ]

                # Parse upload date
                upload_date = None
                if info.get("upload_date"):
                    try:
                        upload_date = datetime.strptime(info["upload_date"], "%Y%m%d")
                    except ValueError:
                        pass

                metadata = {
                    "youtube_id": info.get("id"),
                    "title": info.get("title"),
                    "description": info.get("description"),
                    "channel_name": info.get("uploader") or info.get("channel"),
                    "channel_id": info.get("channel_id"),
                    "thumbnail_url": info.get("thumbnail"),
                    "duration_seconds": info.get("duration"),
                    "upload_date": upload_date,
                    "view_count": info.get("view_count"),
                    "like_count": info.get("like_count"),
                    "language": info.get("language"),
                    "chapters": chapters,
                }

                return metadata

        except yt_dlp.utils.DownloadError as e:
            raise YouTubeDownloadError(f"Failed to extract video info: {str(e)}")
        except Exception as e:
            raise YouTubeDownloadError(
                f"Unexpected error extracting video info: {str(e)}"
            )

    def validate_video(self, metadata: Dict) -> Tuple[bool, Optional[str]]:
        """
        Validate video before download.

        Args:
            metadata: Video metadata from get_video_info()

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check duration
        duration = metadata.get("duration_seconds")
        if duration and duration > self.max_duration:
            max_hours = self.max_duration / 3600
            return (
                False,
                f"Video is too long ({duration/3600:.1f} hours). Maximum duration is {max_hours} hours.",
            )

        # Check if video is available
        if not metadata.get("youtube_id"):
            return False, "Video is not available or URL is invalid."

        return True, None

    def download_audio(
        self,
        url: str,
        user_id: UUID,
        video_id: UUID,
        progress_callback: Optional[callable] = None,
    ) -> Tuple[str, float]:
        """
        Download audio from YouTube video.

        Args:
            url: YouTube URL
            user_id: User ID for storage isolation
            video_id: Video ID for storage path
            progress_callback: Optional callback function(progress_dict)

        Returns:
            Tuple of (storage_path, file_size_mb)

        Raises:
            YouTubeDownloadError: If download fails
        """
        normalized_url = self._normalize_url(url)
        # Create temporary directory for download
        temp_dir = Path(tempfile.mkdtemp())
        output_template = str(temp_dir / "audio.%(ext)s")

        def build_ydl_opts(player_client: str, fmt: str):
            opts = {
                "format": fmt,
                "outtmpl": output_template,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
                # Keep downloads resilient to transient 403s/throttling
                "noplaylist": True,
                "retries": 3,
                "fragment_retries": 3,
                "http_chunk_size": 10
                * 1024
                * 1024,  # 10MB chunks to avoid huge range requests
                "concurrent_fragment_downloads": 3,
                "quiet": False,
                "no_warnings": False,
                "extract_flat": False,
                **self._common_yt_opts(
                    player_client=player_client, referer=normalized_url
                ),
            }

            # Add progress hook if provided
            if progress_callback:

                def progress_hook(d):
                    if d["status"] == "downloading":
                        progress_callback(
                            {
                                "status": "downloading",
                                "downloaded_bytes": d.get("downloaded_bytes", 0),
                                "total_bytes": d.get("total_bytes")
                                or d.get("total_bytes_estimate", 0),
                                "speed": d.get("speed", 0),
                                "eta": d.get("eta", 0),
                            }
                        )
                    elif d["status"] == "finished":
                        progress_callback(
                            {"status": "processing", "message": "Converting to MP3..."}
                        )

                opts["progress_hooks"] = [progress_hook]
            return opts

        try:
            # Try multiple client profiles and format fallbacks to dodge 403/region blocks
            client_candidates = ["android", "ios", "web"]
            format_candidates = [
                "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
                "bestaudio/best",
            ]
            errors = []
            download_success = False

            for client in client_candidates:
                for fmt in format_candidates:
                    try:
                        with yt_dlp.YoutubeDL(build_ydl_opts(client, fmt)) as ydl:
                            ydl.download([normalized_url])
                        download_success = True
                        break
                    except yt_dlp.utils.DownloadError as e:
                        # Remove any partial files before retrying with another strategy
                        for leftover in temp_dir.glob("audio.*"):
                            try:
                                leftover.unlink()
                            except Exception:
                                pass
                        errors.append(f"{client}/{fmt}: {str(e)}")
                    except Exception as e:
                        errors.append(f"{client}/{fmt}: {str(e)}")
                if download_success:
                    break

            if not download_success:
                raise YouTubeDownloadError(
                    "Failed to download audio after trying multiple strategies "
                    f"(last errors: {' | '.join(errors[-3:])})"
                )

            # Find downloaded file
            audio_file = None
            for ext in ["mp3", "m4a", "webm", "opus"]:
                potential_file = temp_dir / f"audio.{ext}"
                if potential_file.exists():
                    audio_file = potential_file
                    break

            if not audio_file or not audio_file.exists():
                raise YouTubeDownloadError("Downloaded audio file not found")

            # Check file size
            file_size_bytes = audio_file.stat().st_size
            if file_size_bytes > self.max_file_size:
                raise YouTubeDownloadError(
                    f"Audio file too large ({file_size_bytes / (1024*1024):.1f} MB). "
                    f"Maximum size is {settings.max_video_file_size_mb} MB."
                )

            # Upload to storage
            with open(audio_file, "rb") as f:
                storage_path = storage_service.upload_audio(
                    user_id=user_id,
                    video_id=video_id,
                    file_stream=f,
                    filename=audio_file.name,
                )

            # Calculate file size in MB
            file_size_mb = file_size_bytes / (1024 * 1024)

            # Clean up temp directory
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)

            return storage_path, file_size_mb

        except yt_dlp.utils.DownloadError as e:
            raise YouTubeDownloadError(f"Failed to download audio: {str(e)}")
        except Exception as e:
            raise YouTubeDownloadError(f"Unexpected error downloading audio: {str(e)}")
        finally:
            # Ensure cleanup
            import shutil

            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    def get_captions(
        self,
        video_id: str,
        preferred_langs: Optional[List[str]] = None,
    ) -> Optional[Dict]:
        """
        Extract YouTube auto-captions without downloading video.

        This is significantly faster than downloading and transcribing with Whisper
        (1-4 seconds vs 15-90 seconds) for videos that have captions available.

        Args:
            video_id: YouTube video ID (not full URL)
            preferred_langs: List of preferred language codes (default: ["en", "en-US", "en-GB"])

        Returns:
            Dictionary matching Whisper output format if captions available:
            {
                "full_text": "Complete transcript...",
                "segments": [{"start": 0.0, "end": 2.5, "text": "Hello", "speaker": None}, ...],
                "language": "en",
                "word_count": 1234,
                "duration_seconds": 600.0,
            }
            Returns None if captions are unavailable.
        """
        if not settings.enable_caption_extraction:
            logger.info(f"[Captions] Caption extraction disabled, skipping for {video_id}")
            return None

        if preferred_langs is None:
            preferred_langs = [settings.caption_preferred_language, "en", "en-US", "en-GB"]

        url = f"https://www.youtube.com/watch?v={video_id}"

        ydl_opts = {
            "writeautomaticsub": True,
            "writesubtitles": True,
            "subtitleslangs": preferred_langs,
            "subtitlesformat": "vtt",
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            **self._common_yt_opts(),
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                # Check for available subtitles
                subtitles = info.get("subtitles", {})
                automatic_captions = info.get("automatic_captions", {})

                # Try manual subtitles first (usually higher quality)
                vtt_content = None
                detected_lang = None

                for lang in preferred_langs:
                    # Check manual subtitles
                    if lang in subtitles:
                        for sub_info in subtitles[lang]:
                            if sub_info.get("ext") == "vtt":
                                vtt_url = sub_info.get("url")
                                if vtt_url:
                                    vtt_content = self._download_vtt(vtt_url)
                                    detected_lang = lang
                                    logger.info(f"[Captions] Found manual subtitles for {video_id} in {lang}")
                                    break
                        if vtt_content:
                            break

                    # Check automatic captions
                    if not vtt_content and lang in automatic_captions:
                        for sub_info in automatic_captions[lang]:
                            if sub_info.get("ext") == "vtt":
                                vtt_url = sub_info.get("url")
                                if vtt_url:
                                    vtt_content = self._download_vtt(vtt_url)
                                    detected_lang = lang
                                    logger.info(f"[Captions] Found auto-captions for {video_id} in {lang}")
                                    break
                        if vtt_content:
                            break

                if not vtt_content:
                    logger.info(f"[Captions] No captions available for {video_id}")
                    return None

                # Parse VTT content
                segments = parse_vtt_to_segments(vtt_content)

                if not segments:
                    logger.warning(f"[Captions] Parsed VTT but got no segments for {video_id}")
                    return None

                full_text = segments_to_full_text(segments)
                stats = get_transcript_stats(segments)

                logger.info(
                    f"[Captions] Successfully extracted {len(segments)} segments, "
                    f"{stats['word_count']} words for {video_id}"
                )

                return {
                    "full_text": full_text,
                    "segments": segments,
                    "language": detected_lang or "en",
                    "word_count": stats["word_count"],
                    "duration_seconds": stats["duration_seconds"],
                }

        except Exception as e:
            logger.warning(f"[Captions] Caption extraction failed for {video_id}: {e}")
            return None

    def _download_vtt(self, url: str) -> Optional[str]:
        """
        Download VTT content from URL.

        Args:
            url: URL to VTT file

        Returns:
            VTT content as string, or None on failure
        """
        import urllib.request
        import urllib.error

        try:
            req = urllib.request.Request(url, headers=self._default_headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.read().decode("utf-8")
        except (urllib.error.URLError, Exception) as e:
            logger.warning(f"[Captions] Failed to download VTT: {e}")
            return None


# Global YouTube service instance
youtube_service = YouTubeService()
