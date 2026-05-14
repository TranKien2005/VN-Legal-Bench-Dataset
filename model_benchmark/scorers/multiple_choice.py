from model_benchmark.utils.normalize import extract_choice_index, normalize_loose


def score_multiple_choice(sample: dict) -> dict:
    options = sample.get("options") or []
    gold = sample.get("answer", "")
    pred = sample.get("model_answer", "")
    normalized_pred = normalize_loose(pred)
    normalized_gold = normalize_loose(gold)

    selected = None
    match_source = None
    matches = [option for option in options if normalize_loose(option) and normalize_loose(option) in normalized_pred]
    if len(matches) == 1:
        selected = matches[0]
        match_source = "option_text"
    elif normalized_gold and normalized_gold in normalized_pred:
        selected = gold
        match_source = "gold_text"
    elif normalized_pred == normalized_gold:
        selected = gold
        match_source = "exact_text"
    else:
        choice_index = extract_choice_index(pred)
        if choice_index is not None and choice_index < len(options):
            selected = options[choice_index]
            match_source = "choice_letter"

    is_correct = normalize_loose(selected or "") == normalized_gold
    return {
        "uid": sample.get("uid"),
        "task_id": sample.get("task_id"),
        "scoring_method": "multiple_choice_normalized",
        "score": 1.0 if is_correct else 0.0,
        "is_correct": bool(is_correct),
        "selected_answer": selected,
        "match_source": match_source,
        "gold_answer": gold,
        "model_answer": pred,
    }
