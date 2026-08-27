import re
import string
from collections import Counter

PRINTABLE = set(string.printable)


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def printable_ratio(text: str) -> float:
    if not text:
        return 0.0
    printable = sum(1 for char in text if char in PRINTABLE or char.isalnum() or char.isspace())
    return printable / len(text)


def replacement_ratio(text: str) -> float:
    if not text:
        return 0.0
    return text.count("\ufffd") / len(text)


def control_character_ratio(text: str) -> float:
    if not text:
        return 0.0
    control = sum(1 for char in text if ord(char) < 32 and char not in "\n\r\t")
    return control / len(text)


def average_word_length(text: str) -> float:
    words = re.findall(r"\b\w+\b", text)
    if not words:
        return 0.0
    return sum(len(word) for word in words) / len(words)


def duplicate_line_ratio(lines: list[str]) -> float:
    if not lines:
        return 0.0
    normalized = [line.strip() for line in lines if line.strip()]
    if not normalized:
        return 0.0
    counts = Counter(normalized)
    duplicates = sum(count - 1 for count in counts.values() if count > 1)
    return duplicates / len(normalized)


def rects_overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def overlap_ratio(rects: list[tuple[float, float, float, float]]) -> float:
    if len(rects) < 2:
        return 0.0
    overlapping = 0
    comparisons = 0
    for index, rect in enumerate(rects):
        for other in rects[index + 1 :]:
            comparisons += 1
            if rects_overlap(rect, other):
                overlapping += 1
    return overlapping / comparisons if comparisons else 0.0


def coverage_ratio(box_area: float, page_area: float) -> float:
    if page_area <= 0:
        return 0.0
    return min(1.0, box_area / page_area)


def estimate_columns(block_rects: list[tuple[float, float, float, float]], page_width: float) -> int:
    if not block_rects or page_width <= 0:
        return 1
    centers = sorted(((rect[0] + rect[2]) / 2 for rect in block_rects))
    if len(centers) < 2:
        return 1
    gaps = [centers[index + 1] - centers[index] for index in range(len(centers) - 1)]
    threshold = page_width * 0.12
    columns = 1 + sum(1 for gap in gaps if gap >= threshold)
    return min(columns, 4)


def block_order_irregularity(block_rects: list[tuple[float, float, float, float]]) -> float:
    if len(block_rects) < 2:
        return 0.0
    reading_order = sorted(block_rects, key=lambda rect: (round(rect[1], 1), rect[0]))
    original_indices = {rect: index for index, rect in enumerate(block_rects)}
    inversions = 0
    pairs = 0
    for left in range(len(reading_order)):
        for right in range(left + 1, len(reading_order)):
            pairs += 1
            if original_indices[reading_order[left]] > original_indices[reading_order[right]]:
                inversions += 1
    return inversions / pairs if pairs else 0.0


def compute_layout_complexity(
    *,
    probable_columns: int,
    irregular_block_order: float,
    vector_drawing_count: int,
    table_candidate_count: int,
) -> float:
    column_factor = 0.0 if probable_columns <= 1 else min(1.0, (probable_columns - 1) / 3)
    vector_factor = min(1.0, vector_drawing_count / 50.0)
    table_factor = min(1.0, table_candidate_count / 3.0)
    score = (
        0.30 * column_factor
        + 0.30 * irregular_block_order
        + 0.20 * vector_factor
        + 0.20 * table_factor
    )
    return round(min(1.0, score), 4)


LIST_LINE_PATTERN = re.compile(r"^(\u2022|\-|\*|\d+[\.\)])\s+\S")


def looks_like_list_line(text: str) -> bool:
    return bool(LIST_LINE_PATTERN.match(text.strip()))


def ends_with_terminal_punctuation(text: str) -> bool:
    stripped = text.strip()
    return bool(stripped) and stripped[-1] in ".!?;:"


def looks_like_table_header(text: str) -> bool:
    tokens = [token for token in re.split(r"\s{2,}|\t", text.strip()) if token]
    return len(tokens) >= 3 and text == text.upper()


def looks_like_formula_or_code(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if any(token in stripped for token in ("=", "∑", "∫", "sqrt", "frac")):
        return True
    return bool(re.search(r"[{}();<>]|def |class |import |#include", stripped))
