"""Conservative bilingual parsing. Ambiguous lines stay visible for correction."""
import re
import unicodedata
from dataclasses import dataclass

HAN = re.compile(r'[\u3400-\u9fff]')
LATIN = re.compile(r'[A-Za-z]')


def normalize(text):
    return ' '.join(unicodedata.normalize('NFKC', text).casefold().split())


def valid_pair(chinese, english):
    return bool(HAN.search(chinese) and LATIN.search(english) and not HAN.search(english)
                and chinese.strip() and english.strip())


@dataclass
class Parsed:
    source: str
    chinese: str = ''
    english: str = ''
    error: str = ''


def parse_line(line):
    raw = line.strip().rstrip('\\').strip()
    text = re.sub(r'^\s*(?:(?:\d+|[一二三四五六七八九十]+)[.、)）:]|[（(]\d+[)）]|[-*•])\s*', '', raw)
    if not text or re.fullmatch(r'[\d\s.、()（）-]+', text):
        return None
    # Candidate boundaries come from explicit separators or a script transition.
    candidates = set()
    for match in re.finditer(r'\s*[:：,，=＝\t]\s*|\s+[-–—]\s+', text):
        candidates.add((text[:match.start()].strip(), text[match.end():].strip()))
    for match in re.finditer(r'\s+', text):
        candidates.add((text[:match.start()].strip(), text[match.end():].strip()))
    pairs = set()
    for left, right in candidates:
        if HAN.search(left) and not LATIN.search(left) and LATIN.search(right) and not HAN.search(right):
            pairs.add((left, right))
        if HAN.search(right) and not LATIN.search(right) and LATIN.search(left) and not HAN.search(left):
            pairs.add((right, left))
    # Prefer explicit boundaries so punctuation is never silently part of a word.
    clean = {(c.strip(' :：,，=＝\t-–—'), e.strip(' :：,，=＝\t-–—')) for c, e in pairs}
    if len(clean) == 1:
        c, e = clean.pop()
        return Parsed(raw, c, e)
    return Parsed(raw, error='无法可靠识别，请填写中文和英文')


def parse_text(text):
    return [item for line in text.splitlines() if (item := parse_line(line)) is not None]
