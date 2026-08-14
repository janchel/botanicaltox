"""
evaluate.py
-----------
Standalone model evaluation: load a saved model and a feature matrix,
then compute all metrics and generate diagnostic plots.

Usage:
    python evaluate.py --model models/activity.pkl --features datasets/features.csv --label-col Activity_Label
    python evaluate.py --model models/toxicity.pkl --features datasets/features.csv --label-col Toxicity_Label
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import joblib
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
    precision_recall_curve,
)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns


def load_model(path: str):
    """Load a saved joblib model."""
    if not Path(path).exists():
        raise FileNotFoundError(f"Model not found: {path}")
    return joblib.load(path)


def evaluate_standalone(model, X: pd.DataFrame, y: pd.Series,
                        task_name: str, output_dir: str = "outputs"):
    """Run a full evaluation suite and save results."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "graphs").mkdir(parents=True, exist_ok=True)
    (out / "reports").mkdir(parents=True, exist_ok=True)

    y_pred = model.predict(X)
    y_proba = model.predict_proba(X)[:, 1]

    n_classes = len(np.unique(y))
    
    print(f"\n  Samples:    {len(y)}")
    print(f"  Classes:    {n_classes}")
    print(f"  Distribution:\n{y.value_counts().to_string()}\n")

    print(f"  Accuracy:   {accuracy_score(y, y_pred):.4f}")

    if n_classes == 2:
        print(f"  ROC-AUC:    {roc_auc_score(y, y_proba):.4f}")
        print(f"  Precision:  {precision_score(y, y_pred, zero_division=0):.4f}")
        print(f"  Recall:     {recall_score(y, y_pred, zero_division=0):.4f}")
        print(f"  F1 Score:   {f1_score(y, y_pred, zero_division=0):.4f}")
        print(f"  MCC:        {matthews_corrcoef(y, y_pred):.4f}")

    print(f"\n  Classification Report:\n")
    print(classification_report(y, y_pred, zero_division=0))

    if n_classes == 2:
        # ROC Curve
        fpr, tpr, _ = roc_curve(y, y_proba)
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.plot(fpr, tpr, label=f"AUC = {roc_auc_score(y, y_proba):.3f}")
        ax.plot([0, 1], [0, 1], "k--", alpha=0.4)
        ax.set_xlabel("False Positive Rate")
        ax.set_ylabel("True Positive Rate")
        ax.set_title(f"ROC Curve – {task_name}")
        ax.legend()
        fig.tight_layout()
        fig.savefig(out / "graphs" / f"{task_name.lower()}_eval_roc.png", dpi=150)
        plt.close(fig)
        print(f"  ROC curve saved.")

        # Precision-Recall Curve
        precision, recall, _ = precision_recall_curve(y, y_proba)
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.plot(recall, precision)
        ax.set_xlabel("Recall")
        ax.set_ylabel("Precision")
        ax.set_title(f"Precision-Recall Curve – {task_name}")
        fig.tight_layout()
        fig.savefig(out / "graphs" / f"{task_name.lower()}_eval_pr.png", dpi=150)
        plt.close(fig)
        print(f"  PR curve saved.")

    # Confusion Matrix
    cm = confusion_matrix(y, y_pred)
    labels = [f"Class {i}" for i in range(n_classes)]
    fig, ax = plt.subplots(figsize=(5, 4))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", ax=ax,
                xticklabels=labels, yticklabels=labels)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title(f"Confusion Matrix – {task_name}")
    fig.tight_layout()
    fig.savefig(out / "graphs" / f"{task_name.lower()}_eval_cm.png", dpi=150)
    plt.close(fig)
    print(f"  Confusion matrix saved.")


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate a saved Random Forest model on a feature matrix."
    )
    parser.add_argument("--model", "-m", required=True, help="Path to .pkl model.")
    parser.add_argument("--features", "-f", required=True, help="Path to feature CSV/Excel.")
    parser.add_argument("--label-col", "-l", required=True, help="Target column name.")
    parser.add_argument("--output-dir", "-o", default="outputs", help="Output directory.")
    args = parser.parse_args()

    task_name = Path(args.model).stem.replace("_", " ").title()

    print(f"[1/3] Loading model: {args.model}")
    model = load_model(args.model)

    print(f"[2/3] Loading features: {args.features}")
    path = Path(args.features)
    if path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)

    if args.label_col not in df.columns:
        raise KeyError(f"Label column '{args.label_col}' not found.")

    y = df[args.label_col]
    drop_cols = {args.label_col}
    for col in ["Compound_ID", "Name", "Smiles", "mol", "Activity_Label", "Toxicity_Label"]:
        if col in df.columns:
            drop_cols.add(col)
    X = df.drop(columns=list(drop_cols & set(df.columns)), errors="ignore")
    X = X.select_dtypes(include=[np.number])

    print(f"[3/3] Evaluating...")
    evaluate_standalone(model, X, y, task_name, args.output_dir)
    print("\nDone!")


if __name__ == "__main__":
    main()
