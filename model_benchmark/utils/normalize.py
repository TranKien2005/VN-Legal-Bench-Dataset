import difflib
import re
import unicodedata
from collections import Counter


LETTER_TO_INDEX = {"a": 0, "b": 1, "c": 2, "d": 3}


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def normalize_for_match(text: str) -> str:
    text = unicodedata.normalize("NFC", str(text or ""))
    text = text.replace(" ", " ")
    text = normalize_spaces(text)
    return text.strip(' "\'`.,;:')


def normalize_loose(text: str) -> str:
    text = normalize_for_match(text).lower()
    text = re.sub(r"[^0-9a-zA-ZÀ-ỹ/\- ]+", " ", text)
    return normalize_spaces(text)


def normalize_article_text(text: str) -> str:
    text = unicodedata.normalize("NFC", str(text or ""))
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"(?<!\w)(\d+|[a-zA-Zà-ỹđĐ])\s*[\.)\-]\s+", " ", text)
    text = re.sub(r"[^0-9a-zA-ZÀ-ỹ\s]", " ", text)
    return normalize_spaces(text)


def token_f1(prediction: str, gold: str) -> float:
    pred_tokens = normalize_loose(prediction).split()
    gold_tokens = normalize_loose(gold).split()
    if not pred_tokens and not gold_tokens:
        return 1.0
    if not pred_tokens or not gold_tokens:
        return 0.0
    common = Counter(pred_tokens) & Counter(gold_tokens)
    num_same = sum(common.values())
    if num_same == 0:
        return 0.0
    precision = num_same / len(pred_tokens)
    recall = num_same / len(gold_tokens)
    return 2 * precision * recall / (precision + recall)


def char_similarity(prediction: str, gold: str) -> float:
    return difflib.SequenceMatcher(None, normalize_loose(prediction), normalize_loose(gold)).ratio()


def length_ratio(prediction: str, gold: str) -> float:
    pred_len = len(normalize_loose(prediction))
    gold_len = len(normalize_loose(gold))
    if pred_len == 0 and gold_len == 0:
        return 1.0
    if pred_len == 0 or gold_len == 0:
        return 0.0
    return min(pred_len, gold_len) / max(pred_len, gold_len)


def extract_choice_index(text: str) -> int | None:
    cleaned = normalize_for_match(text).lower()
    match = re.match(r"^([abcd])(?:[\.)\s]|$)", cleaned)
    if match:
        return LETTER_TO_INDEX[match.group(1)]
    return None


def extract_json_object(text: str) -> dict | None:
    import json

    raw = str(text or "").strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(raw[start:end + 1])
    except Exception:
        return None
