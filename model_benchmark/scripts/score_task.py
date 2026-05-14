import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from model_benchmark.scorers.base import score_short_answer
from model_benchmark.scorers.multiple_choice import score_multiple_choice
from model_benchmark.scorers.task_2_3 import score_task_2_3
from model_benchmark.scorers.task_3_1 import score_task_3_1
from model_benchmark.utils.io import load_json, save_json
from model_benchmark.utils.paths import task_result_dir
from model_benchmark.utils.tasks import TASK_IDS


def score_sample(sample: dict, task_id: str, judge_model: str | None = None) -> dict:
    if task_id in {"task_1_2", "task_2_4", "task_2_6"}:
        return score_multiple_choice(sample)
    if task_id == "task_2_2":
        return score_short_answer(sample, article_mode=True)
    if task_id == "task_2_3":
        return score_task_2_3(sample)
    if task_id == "task_3_1":
        return score_task_3_1(sample, judge_model=judge_model)
    return score_short_answer(sample)


def summarize(scores: list[dict], model: str, task_id: str) -> dict:
    n = len(scores)
    correct = sum(1 for item in scores if item.get("is_correct"))
    summary = {
        "model": model,
        "task_id": task_id,
        "num_samples": n,
        "accuracy": round(correct / n, 4) if n else 0.0,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    for metric in ["token_f1", "char_similarity", "length_ratio", "judge_score"]:
        values = [float(item[metric]) for item in scores if item.get(metric) is not None]
        if values:
            summary[f"avg_{metric}"] = round(sum(values) / len(values), 4)
    if task_id == "task_3_1":
        acceptable = [item for item in scores if item.get("judge_result", {}).get("is_acceptable")]
        summary["acceptable_rate"] = round(len(acceptable) / n, 4) if n else 0.0
    return summary


def resolve_task_dir(task_id: str, model: str, results_dir: str | None = None) -> Path:
    if results_dir:
        base_dir = Path(results_dir)
        return base_dir if base_dir.name == task_id else base_dir / task_id
    return task_result_dir(model, task_id)


def score_task(
    task_id: str,
    model: str,
    judge_model: str | None = None,
    results_dir: str | None = None,
    force: bool = False,
) -> tuple[Path, Path] | None:
    out_dir = resolve_task_dir(task_id, model, results_dir)
    responses_path = out_dir / "responses.json"
    scores_path = out_dir / "scores.json"
    summary_path = out_dir / "summary.json"

    if not responses_path.exists():
        raise FileNotFoundError(f"Responses not found: {responses_path}")
    if scores_path.exists() and summary_path.exists() and not force:
        print(f"Skip existing scores: {out_dir} (use --force to rescore)")
        return None

    responses = load_json(responses_path)
    actual_model = model or (responses[0].get("model") if responses else "unknown")
    scores = [score_sample(sample, task_id, judge_model=judge_model) for sample in responses]
    save_json(scores_path, scores)
    save_json(summary_path, summarize(scores, actual_model, task_id))
    print(f"Saved scores to {scores_path}")
    print(f"Saved summary to {summary_path}")
    return scores_path, summary_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Score benchmark responses for one task.")
    parser.add_argument("--task", required=True, choices=TASK_IDS)
    parser.add_argument("--model", default=os.getenv("BENCHMARK_MODEL") or os.getenv("LLM_MODEL"), help="Model/folder name under model_benchmark/results when --results-dir is not provided.")
    parser.add_argument("--results-dir", help="Path to a model result folder or a specific task result folder to score.")
    parser.add_argument("--force", action="store_true", help="Rescore even if scores.json and summary.json already exist.")
    parser.add_argument("--judge-model", default=os.getenv("BENCHMARK_JUDGE_MODEL") or os.getenv("BENCHMARK_MODEL") or os.getenv("LLM_MODEL"))
    args = parser.parse_args()
    score_task(args.task, args.model, args.judge_model, results_dir=args.results_dir, force=args.force)


if __name__ == "__main__":
    main()
