import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class SegmentItem:
    segment_index: int
    source_text: str
    book: Optional[str] = None
    chapter: Optional[int] = None
    verse_start: Optional[int] = None
    verse_end: Optional[int] = None


VERSE_PATTERN = re.compile(
    r"^(?:(?P<book>[1-3]?\s?[A-Za-z]+)\s+)?(?P<chapter>\d+):(?P<verse_start>\d+)(?:-(?P<verse_end>\d+))?\s+(?P<text>.+)$"
)


def clean_source_text(text: str) -> str:
    text = text.replace("\ufeff", "")
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")
    text = text.strip()
    return text


def split_into_segments(text: str) -> list[SegmentItem]:
    cleaned = clean_source_text(text)

    if not cleaned:
        return []

    raw_lines = [line.strip() for line in cleaned.split("\n") if line.strip()]

    if not raw_lines:
        raw_lines = [cleaned]

    segments: list[SegmentItem] = []

    for idx, line in enumerate(raw_lines, start=1):
        match = VERSE_PATTERN.match(line)

        if match:
            book = match.group("book")
            chapter = int(match.group("chapter"))
            verse_start = int(match.group("verse_start"))
            verse_end = match.group("verse_end")
            verse_end_int = int(verse_end) if verse_end else verse_start
            source_text = match.group("text").strip()

            segments.append(
                SegmentItem(
                    segment_index=idx,
                    book=book,
                    chapter=chapter,
                    verse_start=verse_start,
                    verse_end=verse_end_int,
                    source_text=source_text,
                )
            )
        else:
            segments.append(
                SegmentItem(
                    segment_index=idx,
                    source_text=line,
                )
            )

    return segments
