import re

from model_benchmark.scorers.base import score_short_answer
from model_benchmark.utils.normalize import normalize_for_match, normalize_loose


def normalize_date(text: str) -> str:
    raw = normalize_for_match(text)
    match = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", raw)
    if match:
        day, month, year = match.groups()
        return f"{int(day):02d}/{int(month):02d}/{year}"
    match = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", raw)
    if match:
        year, month, day = match.groups()
        return f"{int(day):02d}/{int(month):02d}/{year}"
    return raw


def infer_question_type(sample: dict) -> str:
    uid = sample.get("uid", "")
    if "bench_2_3_docid_" in uid:
        return "doc_id_from_excerpt"
    if "bench_2_3_article_" in uid:
        return "article_from_excerpt"
    if "bench_2_3_effective_" in uid:
        return "effective_date_from_doc_id"
    if "bench_2_3_signer_" in uid:
        return "signer_from_doc_id"
    return "metadata_exact"


def _basic_result(sample: dict, qtype: str, method: str, is_correct: bool) -> dict:
    return {
        "uid": sample.get("uid"),
        "task_id": sample.get("task_id"),
        "question_type": qtype,
        "scoring_method": method,
        "score": 1.0 if is_correct else 0.0,
        "is_correct": bool(is_correct),
        "gold_answer": sample.get("answer", ""),
        "model_answer": sample.get("model_answer", ""),
    }


def score_task_2_3(sample: dict) -> dict:
    qtype = infer_question_type(sample)
    gold = sample.get("answer", "")
    pred = sample.get("model_answer", "")
    pred_norm = normalize_loose(pred)
    gold_norm = normalize_loose(gold)

    if qtype == "doc_id_from_excerpt":
        is_correct = pred_norm == gold_norm or gold_norm in pred_norm
        return _basic_result(sample, qtype, "doc_id_contains_match", is_correct)

    if qtype == "article_from_excerpt":
        is_correct = pred_norm == gold_norm or gold_norm in pred_norm
        return _basic_result(sample, qtype, "article_contains_match", is_correct)

    if qtype == "effective_date_from_doc_id":
        is_correct = normalize_date(pred) == normalize_date(gold)
        return _basic_result(sample, qtype, "date_exact_match", is_correct)

    if qtype == "signer_from_doc_id":
        is_correct = pred_norm == gold_norm or gold_norm in pred_norm
        return _basic_result(sample, qtype, "signer_normalized_match", is_correct)

    result = score_short_answer(sample)
    result["question_type"] = qtype
    return result
