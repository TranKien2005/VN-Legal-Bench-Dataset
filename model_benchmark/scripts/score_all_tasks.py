import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from model_benchmark.scripts.score_task import score_task
from model_benchmark.utils.paths import RESULTS_ROOT, safe_model_name
from model_benchmark.utils.tasks import TASK_IDS


def main() -> None:
    parser = argparse.ArgumentParser(description="Score all benchmark tasks for one model result folder.")
    parser.add_argument(
        "--model",
        default=os.getenv("BENCHMARK_MODEL") or os.getenv("LLM_MODEL"),
        help="Model/folder name under model_benchmark/results, e.g. --model llama3 scores model_benchmark/results/llama3.",
    )
    parser.add_argument(
        "--results-dir",
        help="Path to the model result folder containing task_*/responses.json. Overrides --model folder resolution.",
    )
    parser.add_argument("--force", action="store_true", help="Rescore tasks even if scores.json and summary.json already exist.")
    parser.add_argument("--skip-missing", action="store_true", help="Skip tasks without responses.json instead of failing.")
    parser.add_argument("--judge-model", default=os.getenv("BENCHMARK_JUDGE_MODEL") or os.getenv("BENCHMARK_MODEL") or os.getenv("LLM_MODEL"))
    args = parser.parse_args()

    model_results_dir = Path(args.results_dir) if args.results_dir else RESULTS_ROOT / safe_model_name(args.model)
    for task_id in TASK_IDS:
        task_dir = model_results_dir / task_id
        if args.skip_missing and not (task_dir / "responses.json").exists():
            print(f"Skip missing responses: {task_dir}")
            continue
        score_task(task_id, args.model, args.judge_model, results_dir=str(model_results_dir), force=args.force)


if __name__ == "__main__":
    main()
