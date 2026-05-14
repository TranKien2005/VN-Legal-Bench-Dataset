import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from model_benchmark.scripts.run_task import run_task
from model_benchmark.utils.tasks import TASK_IDS


def main() -> None:
    parser = argparse.ArgumentParser(description="Run all benchmark tasks against a 9Router model.")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--model", default=os.getenv("BENCHMARK_MODEL") or os.getenv("LLM_MODEL"))
    args = parser.parse_args()
    for task_id in TASK_IDS:
        run_task(task_id, args.limit, args.model)


if __name__ == "__main__":
    main()
