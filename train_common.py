"""
train_common.py
---------------
Shared training utilities for Random Forest classifiers used by both
train_activity.py and train_toxicity.py.

Handles: data loading, train/test split, model training, hyperparameter
tuning via RandomizedSearchCV, evaluation, and model persistence.
"""

import argparse
import json
from pathlib import Path
from typing import Tuple

import joblib
import matplotlib
matplotlib.use("Agg")  # non-interactive backend for headless environments
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import StratifiedKFold, RandomizedSearchCV, train_test_split


# ── Data Loading ────────────────────────────────────────────────────────────

def load_features_and_labels(
    features_path: str,
    label_col: str,
    id_col: str | None = None,
    smiles_col: str = "Smiles",
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Load the feature matrix and extract the target label column.

    Automatically drops non-feature columns (compound IDs, SMILES, mol, any
    already-present label columns) from X.
    """
    path = Path(features_path)
    if path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)

    if label_col not in df.columns:
        raise KeyError(
            f"Label column '{label_col}' not found in {features_path}. "
            f"Available columns: {list(df.columns)}"
        )

    y = df[label_col]

    # Drop columns that are not features
    drop_cols = {label_col}
    if id_col and id_col in df.columns:
        drop_cols.add(id_col)
    for extra in ["Compound_ID", "Name", smiles_col, "mol"]:
        if extra in df.columns:
            drop_cols.add(extra)

    # Also drop any other label-like columns to avoid data leakage
    for col in ("Activity_Label", "Toxicity_Label", "activity", "toxicity"):
        if col in df.columns and col != label_col:
            drop_cols.add(col)

    X = df.drop(columns=list(drop_cols & set(df.columns)), errors="ignore")

    # Ensure all feature columns are numeric; drop non-numeric
    X = X.select_dtypes(include=[np.number])

    # Clean infinite/NaN values that break scikit-learn
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(0)
    # Clip extreme values to float32-safe range
    X = X.clip(lower=-1e10, upper=1e10)

    print(f"  Features: {X.shape[1]} columns, {X.shape[0]} samples")
    print(f"  Labels:   class distribution =\n{y.value_counts().to_string()}")
    return X, y


# ── Model Training ──────────────────────────────────────────────────────────

def train_random_forest(
    X: pd.DataFrame,
    y: pd.Series,
    random_state: int = 42,
    tune: bool = True,
    n_iter: int = 60,
    cv_folds: int = 5,
) -> tuple[RandomForestClassifier, dict]:
    """
    Train a Random Forest classifier with optional hyperparameter tuning.

    Parameters
    ----------
    tune : bool
        If True, run RandomizedSearchCV. If False, use sensible defaults.
    n_iter : int
        Number of randomized search iterations.
    cv_folds : int
        Cross-validation folds for hyperparameter search.

    Returns
    -------
    model : RandomForestClassifier
        Trained model.
    best_params : dict
        Best hyperparameters found (or defaults if tune=False).
    """
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=random_state
    )

    print(f"  Train set: {X_train.shape[0]} | Test set: {X_test.shape[0]}")

    if tune:
        # Auto-adjust CV folds for small datasets
        min_class_count = min(y_train.value_counts())
        actual_folds = min(cv_folds, min_class_count, 5)
        if actual_folds < 2:
            actual_folds = 2
        if actual_folds < cv_folds:
            print(f"  ⚠️  Small dataset detected — reduced CV from {cv_folds} to {actual_folds} folds")

        param_dist = {
            "n_estimators": [100, 200, 300, 500],
            "max_depth": [None, 10, 20, 30, 50],
            "min_samples_split": [2, 5, 10],
            "min_samples_leaf": [1, 2, 4],
            "max_features": ["sqrt", "log2", None],
            "class_weight": ["balanced", "balanced_subsample", None],
            "bootstrap": [True, False],
        }

        cv = StratifiedKFold(n_splits=actual_folds, shuffle=True, random_state=random_state)
        search = RandomizedSearchCV(
            RandomForestClassifier(random_state=random_state),
            param_distributions=param_dist,
            n_iter=n_iter,
            cv=cv,
            scoring="roc_auc",
            n_jobs=-1,
            random_state=random_state,
            verbose=1,
        )
        search.fit(X_train, y_train)
        model = search.best_estimator_
        best_params = search.best_params_
        print(f"  Best params: {best_params}")
        print(f"  Best CV ROC-AUC: {search.best_score_:.4f}")
    else:
        model = RandomForestClassifier(
            n_estimators=300,
            class_weight="balanced",
            random_state=random_state,
            n_jobs=-1,
        )
        model.fit(X_train, y_train)
        best_params = model.get_params()

    return model, best_params, (X_train, X_test, y_train, y_test)


# ── Evaluation ──────────────────────────────────────────────────────────────

def evaluate_model(
    model: RandomForestClassifier,
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    y_train: pd.Series,
    y_test: pd.Series,
    task_name: str,
    output_dir: str = "outputs",
) -> dict:
    """
    Compute metrics on train and test sets, generate ROC curve and confusion
    matrix plots, and return a metrics dictionary.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "graphs").mkdir(parents=True, exist_ok=True)
    (out / "reports").mkdir(parents=True, exist_ok=True)

    y_train_pred = model.predict(X_train)
    y_test_pred = model.predict(X_test)

    y_train_proba = model.predict_proba(X_train)[:, 1]
    y_test_proba = model.predict_proba(X_test)[:, 1]

    metrics = {
        "task": task_name,
        "train": {
            "accuracy": round(accuracy_score(y_train, y_train_pred), 4),
            "roc_auc": round(roc_auc_score(y_train, y_train_proba), 4),
            "precision": round(precision_score(y_train, y_train_pred, zero_division=0), 4),
            "recall": round(recall_score(y_train, y_train_pred, zero_division=0), 4),
            "f1": round(f1_score(y_train, y_train_pred, zero_division=0), 4),
            "mcc": round(matthews_corrcoef(y_train, y_train_pred), 4),
        },
        "test": {
            "accuracy": round(accuracy_score(y_test, y_test_pred), 4),
            "roc_auc": round(roc_auc_score(y_test, y_test_proba), 4),
            "precision": round(precision_score(y_test, y_test_pred, zero_division=0), 4),
            "recall": round(recall_score(y_test, y_test_pred, zero_division=0), 4),
            "f1": round(f1_score(y_test, y_test_pred, zero_division=0), 4),
            "mcc": round(matthews_corrcoef(y_test, y_test_pred), 4),
        },
    }

    print("\n  ── Training Set ──")
    for k, v in metrics["train"].items():
        print(f"    {k}: {v}")
    print("  ── Test Set ──")
    for k, v in metrics["test"].items():
        print(f"    {k}: {v}")

    # ── ROC Curve ──
    fpr_train, tpr_train, _ = roc_curve(y_train, y_train_proba)
    fpr_test, tpr_test, _ = roc_curve(y_test, y_test_proba)

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(fpr_train, tpr_train, label=f"Train (AUC={metrics['train']['roc_auc']:.3f})")
    ax.plot(fpr_test, tpr_test, label=f"Test (AUC={metrics['test']['roc_auc']:.3f})")
    ax.plot([0, 1], [0, 1], "k--", alpha=0.4)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title(f"ROC Curve – {task_name}")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "graphs" / f"{task_name.lower().replace(' ', '_')}_roc.png", dpi=150)
    plt.close(fig)

    # ── Confusion Matrix ──
    cm = confusion_matrix(y_test, y_test_pred)
    fig, ax = plt.subplots(figsize=(5, 4))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", ax=ax,
                xticklabels=["Negative", "Positive"],
                yticklabels=["Negative", "Positive"])
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title(f"Confusion Matrix – {task_name} (Test)")
    fig.tight_layout()
    fig.savefig(out / "graphs" / f"{task_name.lower().replace(' ', '_')}_cm.png", dpi=150)
    plt.close(fig)

    # ── Feature Importance ──
    importances = model.feature_importances_
    indices = np.argsort(importances)[::-1][:20]  # top 20
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(range(len(indices)), importances[indices][::-1], align="center")
    ax.set_yticks(range(len(indices)))
    ax.set_yticklabels([X_train.columns[i] for i in indices[::-1]], fontsize=8)
    ax.set_xlabel("Importance")
    ax.set_title(f"Top 20 Feature Importances – {task_name}")
    fig.tight_layout()
    fig.savefig(out / "graphs" / f"{task_name.lower().replace(' ', '_')}_importance.png", dpi=150)
    plt.close(fig)

    # ── Save metrics JSON ──
    metrics_path = out / "reports" / f"{task_name.lower().replace(' ', '_')}_metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"  Metrics saved to: {metrics_path}")

    return metrics


def save_model(model, path: str):
    """Persist the trained model to disk."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)
    print(f"  Model saved to: {path}")


def build_cli(task_name: str, label_col: str) -> argparse.ArgumentParser:
    """Create a standard CLI argument parser for training scripts."""
    parser = argparse.ArgumentParser(
        description=f"Train a Random Forest classifier for {task_name} prediction."
    )
    parser.add_argument(
        "--features", "-f", default="datasets/features.csv",
        help="Path to the feature matrix CSV/Excel file."
    )
    parser.add_argument(
        "--label-col", default=label_col,
        help=f"Name of the target label column (default: {label_col})."
    )
    parser.add_argument(
        "--model-output", "-m", default=f"models/{task_name.lower().replace(' ', '_')}.pkl",
        help="Path to save the trained model (.pkl)."
    )
    parser.add_argument(
        "--output-dir", "-o", default="outputs",
        help="Directory for evaluation outputs."
    )
    parser.add_argument(
        "--no-tune", action="store_true",
        help="Skip hyperparameter tuning (use sensible defaults)."
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducibility."
    )
    return parser
