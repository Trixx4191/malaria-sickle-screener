"""run_pipeline.py — Phase 2.1 reproducible end-to-end runner.

One command to generate artifacts:
  data (optional) -> features -> train -> evaluate

Examples:
  python src/pipeline/run_pipeline.py
  python src/pipeline/run_pipeline.py --skip-download
  python src/pipeline/run_pipeline.py --model random_forest
"""

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.utils.config import MODEL_FILE, FEATURE_MATRIX, FIGURES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        choices=["all", "clinvar", "1kg"],
        default="all",
        help="Which data to download (passed through to src/data/download.py).",
    )
    parser.add_argument(
        "--model",
        choices=["all", "logistic", "random_forest"],
        default="random_forest",
        help="Which model(s) to train (passed to src/models/train.py).",
    )
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--skip-features", action="store_true")
    parser.add_argument("--skip-train", action="store_true")
    parser.add_argument("--skip-evaluate", action="store_true")

    args = parser.parse_args()

    # Import locally to keep this runner lightweight.
    import subprocess

    def run(cmd: list[str]):
        print("\n>>", " ".join(cmd))
        subprocess.check_call(cmd)

    # 1) download
    if not args.skip_download:
        run([sys.executable, "src/data/download.py", "--dataset", args.dataset])

    # 2) build features
    if not args.skip_features:
        run([sys.executable, "src/data/build_features.py"])

    if not FEATURE_MATRIX.exists():
        raise FileNotFoundError(f"Feature matrix not found at {FEATURE_MATRIX}")

    # 3) train
    if not args.skip_train:
        run([sys.executable, "src/models/train.py", "--model", args.model])

    if not MODEL_FILE.exists():
        raise FileNotFoundError(f"Trained model not found at {MODEL_FILE}")

    # 4) evaluate
    if not args.skip_evaluate:
        run([sys.executable, "src/models/evaluate.py"])

    print("\n=== Pipeline complete ===")
    print("Feature matrix:", FEATURE_MATRIX)
    print("Model file:", MODEL_FILE)
    print("Figures dir:", FIGURES)


if __name__ == "__main__":
    main()

