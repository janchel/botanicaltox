"""
train_activity.py
-----------------
Train a Random Forest classifier to predict compound activity against OXA-23.

Usage:
    python train_activity.py --features datasets/features.csv --model-output models/activity.pkl
"""

import sys
from pathlib import Path

# Allow running from the drug_ai directory
sys.path.insert(0, str(Path(__file__).resolve().parent))

from train_common import (
    build_cli,
    evaluate_model,
    load_features_and_labels,
    save_model,
    train_random_forest,
)


def main():
    parser = build_cli("Activity", "Activity_Label")
    args = parser.parse_args()

    print("=" * 60)
    print("  Random Forest – Activity (OXA-23) Prediction")
    print("=" * 60)

    print(f"\n[1/3] Loading features from: {args.features}")
    X, y = load_features_and_labels(args.features, args.label_col)

    print(f"\n[2/3] Training Random Forest classifier...")
    model, best_params, splits = train_random_forest(
        X, y, random_state=args.seed, tune=not args.no_tune
    )
    X_train, X_test, y_train, y_test = splits

    print(f"\n[3/3] Evaluating model...")
    evaluate_model(model, X_train, X_test, y_train, y_test, "Activity", args.output_dir)

    save_model(model, args.model_output)
    print("\nDone! Activity model is ready.")


if __name__ == "__main__":
    main()
