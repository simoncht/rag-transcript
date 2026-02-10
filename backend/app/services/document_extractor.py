"""
Document text extraction service using Kreuzberg.

Extracts text and metadata from uploaded documents (PDF, DOCX, PPTX, XLSX, TXT, etc.).
Kreuzberg handles OCR-based PDF extraction with Tesseract and supports many formats.
"""
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExtractedPage:
    """A single page of extracted text."""

    page_number: int
    text: str
    # Optional section headings detected on this page
    headings: List[str] = field(default_factory=list)


@dataclass
class ExtractionResult:
    """Result of document text extraction."""

    full_text: str
    pages: List[ExtractedPage]
    page_count: int
    word_count: int
    content_type: str
    metadata: Dict  # Author, creation date, etc.
    language: Optional[str] = None


class DocumentExtractor:
    """
    Extracts text from documents using Kreuzberg.

    Supports: PDF, DOCX, PPTX, XLSX, TXT, MD, HTML, EPUB, CSV, RTF, EML.
    Falls back to basic text reading for simple formats.
    """

    # Formats that Kreuzberg handles
    KREUZBERG_FORMATS = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls",
                          ".html", ".htm", ".epub", ".rtf", ".eml", ".msg"}

    # Formats we handle with basic text reading
    PLAINTEXT_FORMATS = {".txt", ".md", ".markdown", ".csv"}

    async def extract(self, file_path: str, content_type: str) -> ExtractionResult:
        """
        Extract text and metadata from a document file.

        Args:
            file_path: Path to the document file
            content_type: Content type identifier (pdf, docx, etc.)

        Returns:
            ExtractionResult with text, pages, and metadata
        """
        path = Path(file_path)
        ext = path.suffix.lower()

        if ext in self.PLAINTEXT_FORMATS:
            return self._extract_plaintext(path, content_type)

        if ext in self.KREUZBERG_FORMATS:
            return await self._extract_with_kreuzberg(path, content_type)

        raise ValueError(f"Unsupported file extension: {ext}")

    async def _extract_with_kreuzberg(
        self, path: Path, content_type: str
    ) -> ExtractionResult:
        """Extract text using Kreuzberg library."""
        try:
            from kreuzberg import extract_file

            result = await extract_file(path)

            # Kreuzberg returns an ExtractionResult with .content (text) and .metadata
            full_text = result.content if result.content else ""
            metadata = {}
            if result.metadata:
                metadata = {k: v for k, v in result.metadata.items() if v is not None}

            # Split text into pages using form feeds or heuristic page breaks
            pages = self._split_into_pages(full_text, content_type)

            word_count = len(full_text.split())

            logger.info(
                f"[Document Extractor] Kreuzberg extracted {word_count} words, "
                f"{len(pages)} pages from {path.name}"
            )

            # Prefer metadata page count (real PDF pages) over split-based count
            real_page_count = metadata.get("page_count") or len(pages)

            return ExtractionResult(
                full_text=full_text,
                pages=pages,
                page_count=real_page_count,
                word_count=word_count,
                content_type=content_type,
                metadata=metadata,
            )

        except ImportError:
            logger.error(
                "Kreuzberg is not installed. Install it with: pip install kreuzberg"
            )
            raise RuntimeError(
                "Kreuzberg library is required for document extraction. "
                "Install with: pip install kreuzberg"
            )
        except Exception as e:
            logger.error(f"[Document Extractor] Kreuzberg extraction failed: {e}")
            raise

    def _extract_plaintext(self, path: Path, content_type: str) -> ExtractionResult:
        """Extract text from plain text files."""
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="latin-1")

        word_count = len(text.split())

        # For CSV, keep as-is; for others, split on double newlines as "pages"
        if content_type == "csv":
            pages = [ExtractedPage(page_number=1, text=text)]
        else:
            pages = self._split_into_pages(text, content_type)

        logger.info(
            f"[Document Extractor] Plaintext extracted {word_count} words, "
            f"{len(pages)} pages from {path.name}"
        )

        return ExtractionResult(
            full_text=text,
            pages=pages,
            page_count=len(pages),
            word_count=word_count,
            content_type=content_type,
            metadata={},
        )

    def _split_into_pages(
        self, text: str, content_type: str
    ) -> List[ExtractedPage]:
        """
        Split extracted text into pages.

        Uses form feed characters (\f) as primary delimiter (common in PDF extraction),
        falls back to large paragraph breaks for other formats.
        """
        if not text.strip():
            return []

        # Try form feed splitting first (PDF, DOCX often have these)
        if "\f" in text:
            raw_pages = text.split("\f")
        else:
            # For documents without page markers, treat as single page
            # or split by large gaps (3+ newlines)
            import re
            raw_pages = re.split(r"\n{4,}", text)
            if len(raw_pages) <= 1:
                raw_pages = [text]

        pages = []
        for i, page_text in enumerate(raw_pages, 1):
            page_text = page_text.strip()
            if not page_text:
                continue

            # Detect headings (lines that look like section titles)
            headings = self._detect_headings(page_text)

            pages.append(
                ExtractedPage(
                    page_number=i,
                    text=page_text,
                    headings=headings,
                )
            )

        return pages if pages else [ExtractedPage(page_number=1, text=text.strip())]

    def _detect_headings(self, text: str) -> List[str]:
        """
        Detect section headings in text using heuristics.

        Headings are typically:
        - Short lines (< 100 chars) followed by longer text
        - Lines in ALL CAPS
        - Lines starting with numbering (1., 1.1, I., A.)
        - Markdown headings (# lines)
        """
        import re

        headings = []
        lines = text.split("\n")

        for line in lines[:20]:  # Only check first 20 lines per page
            line = line.strip()
            if not line or len(line) > 100:
                continue

            # Markdown headings
            if re.match(r"^#{1,6}\s+", line):
                headings.append(re.sub(r"^#{1,6}\s+", "", line))
                continue

            # ALL CAPS lines (likely section headers)
            if line.isupper() and len(line) > 3 and len(line) < 80:
                headings.append(line.title())
                continue

            # Numbered sections: "1. Title" or "1.1 Title" or "Chapter 1:"
            if re.match(r"^(\d+\.?\d*\.?\s+|Chapter\s+\d+|Section\s+\d+)", line, re.I):
                headings.append(line)
                continue

        return headings[:3]  # Limit to 3 headings per page


# Global instance
document_extractor = DocumentExtractor()
