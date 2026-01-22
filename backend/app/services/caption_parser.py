"""
VTT caption parser utility.

Parses WebVTT captions into transcript segments compatible with Whisper output format.
"""
import re
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


def parse_vtt_timestamp(timestamp: str) -> float:
    """
    Parse VTT timestamp to seconds.

    Args:
        timestamp: VTT format timestamp (e.g., "00:01:23.456" or "01:23.456")

    Returns:
        Time in seconds as float
    """
    parts = timestamp.strip().split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    elif len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    else:
        return float(parts[0])


def clean_vtt_text(text: str) -> str:
    """
    Clean VTT text by removing formatting tags and normalizing whitespace.

    Args:
        text: Raw VTT text potentially containing tags

    Returns:
        Cleaned text
    """
    # Remove VTT formatting tags like <c>, </c>, <00:01:23.456>
    text = re.sub(r"<[^>]+>", "", text)
    # Remove position/alignment cues
    text = re.sub(r"align:start position:\d+%", "", text)
    # Normalize whitespace
    text = " ".join(text.split())
    return text.strip()


def parse_vtt_to_segments(vtt_content: str) -> List[Dict]:
    """
    Parse WebVTT captions into transcript segments.

    Handles YouTube's VTT format which often has overlapping/duplicate segments
    where text is incrementally revealed.

    Args:
        vtt_content: Raw VTT file content

    Returns:
        List of segments matching Whisper format:
        [
            {"start": 0.0, "end": 2.5, "text": "Hello world"},
            {"start": 2.5, "end": 5.0, "text": "Next segment"},
        ]
    """
    segments = []
    lines = vtt_content.split("\n")

    # Skip WEBVTT header
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("WEBVTT"):
            i += 1
            continue
        if line.startswith("Kind:") or line.startswith("Language:"):
            i += 1
            continue
        if not line:
            i += 1
            continue
        break

    # Parse cues
    current_start = None
    current_end = None
    current_text_lines = []

    while i < len(lines):
        line = lines[i].strip()

        # Skip empty lines and cue identifiers (numeric or NOTE)
        if not line or line.isdigit() or line.startswith("NOTE"):
            if current_text_lines and current_start is not None:
                # Save current segment
                text = clean_vtt_text(" ".join(current_text_lines))
                if text:
                    segments.append({
                        "start": current_start,
                        "end": current_end,
                        "text": text,
                        "speaker": None,
                    })
                current_text_lines = []
                current_start = None
                current_end = None
            i += 1
            continue

        # Check for timestamp line (e.g., "00:00:00.000 --> 00:00:02.500")
        timestamp_match = re.match(
            r"(\d{1,2}:)?(\d{2}):(\d{2}[.,]\d{3})\s*-->\s*(\d{1,2}:)?(\d{2}):(\d{2}[.,]\d{3})",
            line
        )
        if timestamp_match:
            # Save previous segment if exists
            if current_text_lines and current_start is not None:
                text = clean_vtt_text(" ".join(current_text_lines))
                if text:
                    segments.append({
                        "start": current_start,
                        "end": current_end,
                        "text": text,
                        "speaker": None,
                    })
                current_text_lines = []

            # Parse new timestamps
            parts = line.split("-->")
            current_start = parse_vtt_timestamp(parts[0].strip().split()[0])
            # Handle potential style metadata after end timestamp
            end_part = parts[1].strip().split()[0]
            current_end = parse_vtt_timestamp(end_part)
            i += 1
            continue

        # This is a text line
        if current_start is not None:
            current_text_lines.append(line)
        i += 1

    # Don't forget the last segment
    if current_text_lines and current_start is not None:
        text = clean_vtt_text(" ".join(current_text_lines))
        if text:
            segments.append({
                "start": current_start,
                "end": current_end,
                "text": text,
                "speaker": None,
            })

    # Merge overlapping/duplicate segments
    merged_segments = merge_overlapping_segments(segments)

    logger.info(f"[Caption Parser] Parsed {len(segments)} raw segments, merged to {len(merged_segments)}")
    return merged_segments


def merge_overlapping_segments(segments: List[Dict]) -> List[Dict]:
    """
    Merge overlapping or near-duplicate segments.

    YouTube VTT often has overlapping timestamps where text is revealed incrementally.
    This function merges these into clean, non-overlapping segments.

    Args:
        segments: Raw parsed segments with potential overlaps

    Returns:
        Merged segments with clean boundaries
    """
    if not segments:
        return []

    # Sort by start time
    sorted_segments = sorted(segments, key=lambda s: (s["start"], s["end"]))

    merged = []
    current = None

    for segment in sorted_segments:
        if current is None:
            current = segment.copy()
            continue

        # Check for significant overlap (start times within 0.5s)
        time_overlap = abs(segment["start"] - current["start"]) < 0.5

        # Check if text is a superset/subset
        current_text = current["text"].lower()
        new_text = segment["text"].lower()
        text_overlap = (
            new_text.startswith(current_text[:20]) or
            current_text.startswith(new_text[:20]) or
            new_text in current_text or
            current_text in new_text
        )

        if time_overlap and text_overlap:
            # Keep the longer text and extend end time
            if len(segment["text"]) > len(current["text"]):
                current["text"] = segment["text"]
            current["end"] = max(current["end"], segment["end"])
        else:
            # No overlap, save current and start new
            merged.append(current)
            current = segment.copy()

    # Don't forget the last segment
    if current:
        merged.append(current)

    return merged


def segments_to_full_text(segments: List[Dict]) -> str:
    """
    Convert segments to full transcript text.

    Args:
        segments: List of segment dictionaries

    Returns:
        Full transcript as a single string
    """
    return " ".join(seg["text"] for seg in segments if seg.get("text"))


def get_transcript_stats(segments: List[Dict]) -> Dict:
    """
    Calculate transcript statistics from segments.

    Args:
        segments: List of segment dictionaries

    Returns:
        Dictionary with word_count, duration_seconds, segment_count
    """
    full_text = segments_to_full_text(segments)
    word_count = len(full_text.split())

    duration = 0.0
    if segments:
        duration = max(seg.get("end", 0) for seg in segments)

    return {
        "word_count": word_count,
        "duration_seconds": duration,
        "segment_count": len(segments),
    }
