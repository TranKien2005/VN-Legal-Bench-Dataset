from model_benchmark.utils.normalize import (
    char_similarity,
    length_ratio,
    normalize_article_text,
    normalize_for_match,
    normalize_loose,
    token_f1,
)


def score_short_answer(sample: dict, article_mode: bool = False) -> dict:
    gold = sample.get("answer", "")
    pred = sample.get("model_answer", "")
    if article_mode:
        normalized_gold = normalize_article_text(gold)
        normalized_pred = normalize_article_text(pred)
    else:
        normalized_gold = normalize_for_match(gold)
        normalized_pred = normalize_for_match(pred)

    exact = normalized_pred == normalized_gold
    loose_exact = normalize_loose(pred) == normalize_loose(gold)
    return {
        "uid": sample.get("uid"),
        "task_id": sample.get("task_id"),
        "scoring_method": "normalized_exact_match",
        "score": 1.0 if exact or loose_exact else 0.0,
        "is_correct": bool(exact or loose_exact),
        "exact_match": bool(exact),
        "loose_exact_match": bool(loose_exact),
        "token_f1": round(token_f1(pred, gold), 4),
        "char_similarity": round(char_similarity(pred, gold), 4),
        "length_ratio": round(length_ratio(pred, gold), 4),
        "gold_answer": gold,
        "model_answer": pred,
    }
