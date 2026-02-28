"""
YouTube content and discovery provider.

Provides:
- Video search via YouTube Data API (with pagination) or yt-dlp (fallback)
- Channel subscription support
- Topic-based content discovery
- Metadata fetching and validation

Uses YouTube Data API for search if YOUTUBE_API_KEY is configured (enables true pagination).
Falls back to yt-dlp if no API key (client-side pagination only).
"""
import re
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple

import httpx
import yt_dlp

from app.core.config import settings
from app.providers.base import (
    ContentProvider,
    DiscoveryProvider,
    SearchResult,
    ContentMetadata,
    SourceInfo,
    ValidationResult,
    DiscoveredContentData,
)

logger = logging.getLogger(__name__)

# Thread pool for running yt-dlp (which is synchronous)
_executor = ThreadPoolExecutor(max_workers=3)


def _parse_iso8601_duration(duration: str) -> int:
    """Parse ISO 8601 duration format (PT1H2M3S) to seconds."""
    if not duration:
        return 0
    pattern = re.compile(
        r"PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?"
    )
    match = pattern.match(duration)
    if not match:
        return 0
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return hours * 3600 + minutes * 60 + seconds


class YouTubeProvider(ContentProvider, DiscoveryProvider):
    """
    YouTube content and discovery provider.

    Supports two modes:
    - With API key: Uses YouTube Data API for search (true server-side pagination)
    - Without API key: Uses yt-dlp for search (client-side pagination only)
    """

    API_BASE_URL = "https://www.googleapis.com/youtube/v3"

    # YouTube API category IDs for content type filtering
    CATEGORY_MAP = {
        "education": "27",  # Education (tutorials, lessons, courses)
        "howto": "26",      # Howto & Style (how-to guides)
        "tech": "28",       # Science & Technology
        "entertainment": "24",  # Entertainment
    }

    def __init__(self):
        self.api_key = getattr(settings, "youtube_api_key", None) or ""
        self._ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "ignoreerrors": True,
        }

    @property
    def source_type(self) -> str:
        return "youtube"

    @property
    def display_name(self) -> str:
        return "YouTube"

    def has_api_key(self) -> bool:
        """Check if YouTube API key is configured."""
        return bool(self.api_key and len(self.api_key) > 10)

    def is_configured(self) -> bool:
        """Always configured - yt-dlp works without API key."""
        return True

    def get_supported_source_types(self) -> List[str]:
        """Return supported discovery source types."""
        return ["youtube_channel", "youtube_topic"]

    # =========================================================================
    # SEARCH - Hybrid (API with pagination OR yt-dlp fallback)
    # =========================================================================

    def _parse_date_filter(self, date_filter: str) -> Optional[str]:
        """Parse date filter to ISO 8601 format for YouTube API."""
        from datetime import timezone

        if not date_filter:
            return None

        now = datetime.now(timezone.utc)

        if date_filter == "week":
            target_date = now - timedelta(days=7)
        elif date_filter == "month":
            target_date = now - timedelta(days=30)
        elif date_filter == "year":
            target_date = now - timedelta(days=365)
        else:
            # Assume it's already an ISO date string
            return date_filter

        return target_date.strftime("%Y-%m-%dT%H:%M:%SZ")

    async def search(
        self,
        query: str,
        max_results: int = 25,
        page_token: Optional[str] = None,
        duration: Optional[str] = None,
        published_after: Optional[str] = None,
        order: Optional[str] = None,
        category: Optional[str] = None,
        **kwargs,
    ) -> Tuple[List[SearchResult], Optional[str], Optional[str], int]:
        """
        Search YouTube for videos.

        Args:
            query: Search query string
            max_results: Results per page (max 50 for API, 100 for yt-dlp)
            page_token: Token for next/previous page (API mode only)
            duration: Duration filter (short, medium, long)
            published_after: Published after filter (ISO date or week/month/year)
            order: Sort order (relevance, date, viewCount)
            category: Content category (education, howto, tech, entertainment)
            **kwargs: Additional options

        Returns:
            Tuple of (results, next_page_token, prev_page_token, total_results)
            - For API mode: tokens enable true pagination
            - For yt-dlp mode: tokens are None (client-side pagination)
        """
        if self.has_api_key():
            return await self._search_with_api(
                query, max_results, page_token,
                duration=duration,
                published_after=published_after,
                order=order,
                category=category,
                **kwargs
            )
        else:
            return await self._search_with_ytdlp(
                query, max_results,
                duration_filter=duration,
                **kwargs
            )

    async def _search_with_api(
        self,
        query: str,
        max_results: int,
        page_token: Optional[str],
        duration: Optional[str] = None,
        published_after: Optional[str] = None,
        order: Optional[str] = None,
        category: Optional[str] = None,
        **kwargs,
    ) -> Tuple[List[SearchResult], Optional[str], Optional[str], int]:
        """Search using YouTube Data API (supports true pagination)."""
        max_results = min(max(1, max_results), 50)  # API limit is 50

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1: Search for video IDs
            search_params = {
                "key": self.api_key,
                "q": query,
                "type": "video",
                "part": "snippet",
                "maxResults": max_results,
                "videoEmbeddable": "true",
                "order": order or "relevance",
            }

            if page_token:
                search_params["pageToken"] = page_token

            # Apply duration filter (short: <4min, medium: 4-20min, long: >20min)
            if duration and duration in ("short", "medium", "long"):
                search_params["videoDuration"] = duration

            # Apply published after filter
            if published_after:
                parsed_date = self._parse_date_filter(published_after)
                if parsed_date:
                    search_params["publishedAfter"] = parsed_date

            # Apply category filter
            if category and category in self.CATEGORY_MAP:
                search_params["videoCategoryId"] = self.CATEGORY_MAP[category]

            try:
                search_resp = await client.get(
                    f"{self.API_BASE_URL}/search",
                    params=search_params,
                )
                search_resp.raise_for_status()
                search_data = search_resp.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"YouTube API search error: {e.response.status_code}")
                # Fall back to yt-dlp on API error
                return await self._search_with_ytdlp(query, max_results, **kwargs)

            items = search_data.get("items", [])
            next_page_token = search_data.get("nextPageToken")
            prev_page_token = search_data.get("prevPageToken")
            total_results = search_data.get("pageInfo", {}).get("totalResults", 0)

            if not items:
                return [], None, None, 0

            # Step 2: Get video details (duration, view counts)
            video_ids = [item["id"]["videoId"] for item in items]

            try:
                details_resp = await client.get(
                    f"{self.API_BASE_URL}/videos",
                    params={
                        "key": self.api_key,
                        "id": ",".join(video_ids),
                        "part": "contentDetails,statistics",
                    },
                )
                details_resp.raise_for_status()
                details_data = details_resp.json()
            except httpx.HTTPStatusError:
                details_data = {"items": []}

            # Create lookup for details
            details_map = {
                item["id"]: item for item in details_data.get("items", [])
            }

            # Step 3: Build results
            results = []
            for item in items:
                video_id = item["id"]["videoId"]
                snippet = item["snippet"]
                details = details_map.get(video_id, {})
                content_details = details.get("contentDetails", {})
                statistics = details.get("statistics", {})

                # Parse published date
                published_at = None
                if snippet.get("publishedAt"):
                    try:
                        published_at = datetime.fromisoformat(
                            snippet["publishedAt"].replace("Z", "+00:00")
                        )
                    except ValueError:
                        pass

                results.append(
                    SearchResult(
                        id=video_id,
                        title=snippet.get("title", ""),
                        description=snippet.get("description", ""),
                        thumbnail_url=snippet.get("thumbnails", {}).get("medium", {}).get("url"),
                        source_type="youtube",
                        content_type="video",
                        duration_seconds=_parse_iso8601_duration(content_details.get("duration", "")),
                        published_at=published_at,
                        channel_name=snippet.get("channelTitle"),
                        channel_id=snippet.get("channelId"),
                        view_count=int(statistics.get("viewCount", 0)) if statistics.get("viewCount") else None,
                        metadata={
                            "url": f"https://www.youtube.com/watch?v={video_id}",
                        },
                    )
                )

            return results, next_page_token, prev_page_token, total_results

    async def _search_with_ytdlp(
        self,
        query: str,
        max_results: int,
        duration_filter: Optional[str] = None,
        **kwargs,
    ) -> Tuple[List[SearchResult], Optional[str], Optional[str], int]:
        """Search using yt-dlp (no pagination support)."""
        # Request more results to allow for client-side filtering
        fetch_results = min(max(1, max_results * 2), 100) if duration_filter else min(max(1, max_results), 100)

        loop = asyncio.get_event_loop()
        entries = await loop.run_in_executor(
            _executor,
            self._search_sync,
            query,
            fetch_results,
        )

        if not entries:
            return [], None, None, 0

        results = []
        for entry in entries:
            if not entry:
                continue

            video_id = entry.get("id") or entry.get("url", "").split("=")[-1]
            if not video_id:
                continue

            # Parse duration
            duration_val = entry.get("duration")
            if isinstance(duration_val, str):
                try:
                    duration_val = int(duration_val)
                except ValueError:
                    duration_val = None

            # Parse view count
            view_count = entry.get("view_count")
            if isinstance(view_count, str):
                try:
                    view_count = int(view_count.replace(",", ""))
                except ValueError:
                    view_count = None

            # Get thumbnail
            thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"
            thumbnails = entry.get("thumbnails", [])
            if thumbnails:
                for thumb in thumbnails:
                    if thumb.get("width", 0) >= 320:
                        thumbnail_url = thumb.get("url", thumbnail_url)
                        break

            results.append(
                SearchResult(
                    id=video_id,
                    title=entry.get("title", "Unknown"),
                    description=entry.get("description", ""),
                    thumbnail_url=thumbnail_url,
                    source_type="youtube",
                    content_type="video",
                    duration_seconds=duration_val,
                    published_at=None,  # Not available in flat extract
                    channel_name=entry.get("channel") or entry.get("uploader"),
                    channel_id=entry.get("channel_id") or entry.get("uploader_id"),
                    view_count=view_count,
                    metadata={
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                    },
                )
            )

        # Apply client-side duration filter for yt-dlp mode
        if duration_filter:
            filtered_results = []
            for r in results:
                if r.duration_seconds is None:
                    continue  # Skip videos without duration info
                if duration_filter == "short" and r.duration_seconds < 240:  # <4 min
                    filtered_results.append(r)
                elif duration_filter == "medium" and 240 <= r.duration_seconds <= 1200:  # 4-20 min
                    filtered_results.append(r)
                elif duration_filter == "long" and r.duration_seconds > 1200:  # >20 min
                    filtered_results.append(r)
            results = filtered_results[:max_results]
        else:
            results = results[:max_results]

        # yt-dlp doesn't support pagination - return all results, no tokens
        return results, None, None, len(results)

    def _search_sync(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Synchronous search using yt-dlp."""
        ydl_opts = {
            **self._ydl_opts,
            "extract_flat": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
                if not result or "entries" not in result:
                    return []
                return [entry for entry in result["entries"] if entry]
        except Exception as e:
            logger.error(f"yt-dlp search error: {e}")
            return []

    # =========================================================================
    # METADATA - Always uses yt-dlp (no API quota cost)
    # =========================================================================

    async def get_metadata(self, source_identifier: str) -> ContentMetadata:
        """Fetch full metadata for a YouTube video using yt-dlp."""
        loop = asyncio.get_event_loop()

        def _get_info():
            ydl_opts = {
                **self._ydl_opts,
                "extract_flat": False,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(
                    f"https://www.youtube.com/watch?v={source_identifier}",
                    download=False,
                )

        try:
            info = await loop.run_in_executor(_executor, _get_info)
        except Exception as e:
            logger.error(f"Failed to get metadata for {source_identifier}: {e}")
            raise ValueError(f"Failed to fetch video metadata: {source_identifier}")

        if not info:
            raise ValueError(f"Video not found: {source_identifier}")

        # Parse upload date
        published_at = None
        upload_date = info.get("upload_date")
        if upload_date and len(upload_date) == 8:
            try:
                published_at = datetime.strptime(upload_date, "%Y%m%d")
            except ValueError:
                pass

        # Get best thumbnail
        thumbnail_url = f"https://i.ytimg.com/vi/{source_identifier}/maxresdefault.jpg"
        thumbnails = info.get("thumbnails", [])
        for thumb in sorted(thumbnails, key=lambda t: t.get("width", 0), reverse=True):
            if thumb.get("url"):
                thumbnail_url = thumb["url"]
                break

        return ContentMetadata(
            id=source_identifier,
            title=info.get("title", ""),
            description=info.get("description", ""),
            source_type="youtube",
            content_type="video",
            thumbnail_url=thumbnail_url,
            duration_seconds=info.get("duration"),
            published_at=published_at,
            channel_name=info.get("channel") or info.get("uploader"),
            channel_id=info.get("channel_id") or info.get("uploader_id"),
            language=info.get("language"),
            view_count=info.get("view_count"),
            like_count=info.get("like_count"),
            tags=info.get("tags", []),
        )

    async def validate(self, source_identifier: str) -> ValidationResult:
        """Validate that a YouTube video can be processed."""
        try:
            metadata = await self.get_metadata(source_identifier)
        except ValueError as e:
            return ValidationResult(is_valid=False, error_message=str(e))

        warnings = []

        # Check duration
        max_duration = getattr(settings, "max_video_duration_seconds", 14400)
        if metadata.duration_seconds and metadata.duration_seconds > max_duration:
            return ValidationResult(
                is_valid=False,
                error_message=f"Video duration ({metadata.duration_seconds}s) exceeds maximum ({max_duration}s)",
            )

        if metadata.duration_seconds and metadata.duration_seconds < 10:
            warnings.append("Video is very short (< 10 seconds)")

        return ValidationResult(is_valid=True, warnings=warnings)

    # =========================================================================
    # DISCOVERY - Channel/Topic checking
    # =========================================================================

    async def check_for_new_content(
        self,
        source_type: str,
        source_identifier: str,
        since: datetime,
        config: Optional[Dict[str, Any]] = None,
    ) -> List[DiscoveredContentData]:
        """Check a YouTube source for new content."""
        if source_type == "youtube_channel":
            return await self._check_channel(source_identifier, since, config)
        elif source_type == "youtube_topic":
            return await self._check_topic(source_identifier, since, config)
        else:
            logger.warning(f"Unknown source type: {source_type}")
            return []

    async def _check_channel(
        self,
        channel_identifier: str,
        since: datetime,
        config: Optional[Dict[str, Any]] = None,
    ) -> List[DiscoveredContentData]:
        """Check a YouTube channel for new videos using yt-dlp."""
        loop = asyncio.get_event_loop()

        def _get_channel_videos():
            ydl_opts = {
                **self._ydl_opts,
                "extract_flat": True,
                "playlistend": 10,
            }

            if channel_identifier.startswith("UC"):
                url = f"https://www.youtube.com/channel/{channel_identifier}/videos"
            elif channel_identifier.startswith("@"):
                url = f"https://www.youtube.com/{channel_identifier}/videos"
            else:
                url = f"https://www.youtube.com/@{channel_identifier}/videos"

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)

        try:
            result = await loop.run_in_executor(_executor, _get_channel_videos)
        except Exception as e:
            logger.error(f"Failed to check channel {channel_identifier}: {e}")
            return []

        if not result or "entries" not in result:
            return []

        discovered = []
        for entry in result["entries"]:
            if not entry:
                continue

            video_id = entry.get("id")
            if not video_id:
                continue

            thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"

            discovered.append(
                DiscoveredContentData(
                    source_identifier=video_id,
                    content_type="video",
                    title=entry.get("title", "Unknown"),
                    description=entry.get("description", ""),
                    thumbnail_url=thumbnail_url,
                    published_at=None,
                    metadata={
                        "duration": entry.get("duration"),
                        "channel": entry.get("channel") or entry.get("uploader"),
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                    },
                )
            )

        return discovered

    async def _check_topic(
        self,
        topic: str,
        since: datetime,
        config: Optional[Dict[str, Any]] = None,
    ) -> List[DiscoveredContentData]:
        """Search for new videos matching a topic."""
        try:
            results, _, _, _ = await self.search(topic, max_results=10)
        except Exception as e:
            logger.error(f"Failed to search topic '{topic}': {e}")
            return []

        return [
            DiscoveredContentData(
                source_identifier=r.id,
                content_type="video",
                title=r.title,
                description=r.description,
                thumbnail_url=r.thumbnail_url,
                published_at=r.published_at,
                metadata=r.to_dict(),
            )
            for r in results
        ]

    async def get_source_info(
        self,
        source_type: str,
        source_identifier: str,
    ) -> SourceInfo:
        """Get display info for a YouTube source."""
        if source_type == "youtube_channel":
            return await self._get_channel_info(source_identifier)
        elif source_type == "youtube_topic":
            return SourceInfo(
                identifier=source_identifier,
                display_name=f"Topic: {source_identifier}",
                description=f"Videos about {source_identifier}",
            )
        else:
            raise ValueError(f"Unknown source type: {source_type}")

    async def _get_channel_info(self, channel_identifier: str) -> SourceInfo:
        """Get YouTube channel information using yt-dlp."""
        loop = asyncio.get_event_loop()

        def _get_info():
            ydl_opts = {
                **self._ydl_opts,
                "extract_flat": True,
                "playlistend": 1,
            }

            if channel_identifier.startswith("UC"):
                url = f"https://www.youtube.com/channel/{channel_identifier}"
            elif channel_identifier.startswith("@"):
                url = f"https://www.youtube.com/{channel_identifier}"
            else:
                url = f"https://www.youtube.com/@{channel_identifier}"

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)

        try:
            info = await loop.run_in_executor(_executor, _get_info)
        except Exception as e:
            logger.error(f"Failed to get channel info: {e}")
            raise ValueError(f"Failed to fetch channel: {channel_identifier}")

        if not info:
            raise ValueError(f"Channel not found: {channel_identifier}")

        thumbnail_url = None
        thumbnails = info.get("thumbnails", [])
        for thumb in thumbnails:
            if thumb.get("url"):
                thumbnail_url = thumb["url"]
                break

        return SourceInfo(
            identifier=info.get("channel_id") or info.get("id") or channel_identifier,
            display_name=info.get("channel") or info.get("uploader") or "Unknown Channel",
            display_image_url=thumbnail_url,
            description=info.get("description", ""),
            subscriber_count=info.get("channel_follower_count"),
            video_count=info.get("playlist_count"),
        )

    async def get_channel_id_from_url(self, url: str) -> Optional[str]:
        """Extract channel ID from various YouTube channel URL formats."""
        channel_match = re.search(r"youtube\.com/channel/(UC[\w-]+)", url)
        if channel_match:
            return channel_match.group(1)

        handle_match = re.search(r"youtube\.com/@([\w.-]+)", url)
        custom_match = re.search(r"youtube\.com/(?:c|user)/([\w.-]+)", url)

        identifier = None
        if handle_match:
            identifier = f"@{handle_match.group(1)}"
        elif custom_match:
            identifier = custom_match.group(1)

        if identifier:
            try:
                info = await self._get_channel_info(identifier)
                return info.identifier
            except Exception as e:
                logger.warning(f"Failed to resolve channel URL {url}: {e}")

        return None
