import sys
from pathlib import Path

import pytest

# Ensure backend package is importable when running pytest from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.youtube import YouTubeService, YouTubeDownloadError


@pytest.mark.parametrize(
    "url,expected_id",
    [
        ("https://www.youtube.com/watch?v=VIDEO12345", "VIDEO12345"),
        ("https://www.youtube.com/watch?v=VIDEO12345&t=30s", "VIDEO12345"),
        ("https://youtu.be/VIDEO12345", "VIDEO12345"),
        ("https://youtu.be/VIDEO12345?si=abc", "VIDEO12345"),
        ("https://www.youtube.com/embed/VIDEO12345", "VIDEO12345"),
        ("https://www.youtube.com/v/VIDEO12345", "VIDEO12345"),
        ("https://www.youtube.com/shorts/VIDEO12345", "VIDEO12345"),
        ("https://www.youtube.com/shorts/VIDEO12345?feature=share", "VIDEO12345"),
        ("https://www.youtube.com/live/VIDEO12345", "VIDEO12345"),
        ("https://www.youtube.com/live/VIDEO12345?si=xyz", "VIDEO12345"),
        ("https://m.youtube.com/watch?v=VIDEO12345", "VIDEO12345"),
        ("https://music.youtube.com/watch?v=VIDEO12345", "VIDEO12345"),
    ],
)
def test_extract_video_id_variants(url: str, expected_id: str) -> None:
    service = YouTubeService()

    video_id = service.extract_video_id(url)

    assert video_id == expected_id


def test_extract_video_id_invalid_url_raises() -> None:
    service = YouTubeService()

    with pytest.raises(YouTubeDownloadError):
        service.extract_video_id("https://example.com/not-a-youtube-link")
