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
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import (
    GroupShuffleSplit,
    RandomizedSearchCV,
    StratifiedGroupKFold,
    StratifiedKFold,
    train_test_split,
)


# ── Model metadata (notebook-inspired) ──────────────────────────────────────

def attach_model_metadata(model, descriptor_cols, impute_medians):
    """Attach training-time cleaning metadata to a model.

    The descriptor columns and median-imputation values are stored on the
    object so that, at PREDICTION time, the exact same preprocessing the
    model learned on can be reproduced (instead of fill-with-0).
    """
    try:
        model._descriptor_cols = list(descriptor_cols)
        model._impute_medians = dict(impute_medians)
    except Exception:
        pass
    return model


def align_features_for_model(X: pd.DataFrame, model) -> pd.DataFrame:
    """Align a prediction feature matrix to what a model was trained on.

    - Uses the model's stored descriptor columns (falling back to
      feature_names_in_ for models saved before metadata existed).
    - Fills missing/inf/extreme values with the model's TRAINING medians
      when available, otherwise with 0 (legacy behaviour).
    """
    expected = getattr(model, "_descriptor_cols", None)
    if expected is None:
        expected = getattr(model, "feature_names_in_", None)
    if expected is None:
        return X

    X_aligned = X.reindex(columns=list(expected)).replace([np.inf, -np.inf], np.nan)
    X_aligned = X_aligned.mask(X_aligned.abs() > 1e10)

    medians = getattr(model, "_impute_medians", None)
    if medians is not None:
        X_aligned = X_aligned.fillna(pd.Series(medians))
    else:
        X_aligned = X_aligned.fillna(0)
    return X_aligned


def calibrated_estimator(model):
    """Return the underlying classifier for feature_importances_ access.

    CalibratedClassifierCV wraps the real RandomForest; use its fitted
    `estimator` attribute, otherwise the model itself.
    """
    return getattr(model, "estimator", model)


# ── Data Loading ────────────────────────────────────────────────────────────

def load_features_and_labels(
    features_path: str,
    label_col: str,
    id_col: str | None = None,
    smiles_col: str = "Smiles",
) -> tuple[pd.DataFrame, pd.Series, list, dict]:
    """
    Load the feature matrix and extract the target label column.

    Automatically drops non-feature columns (compound IDs, SMILES, mol, any
    already-present label columns) from X.

    Returns (X, y, descriptor_cols, impute_medians) — the descriptor columns
    and median-imputation dict are needed to attach as model metadata so
    predictions use the same preprocessing.

    Cleaning follows the notebook's clean_descriptor_matrix:
      1. Replace inf with NaN
      2. Mask extreme values (|x| > 1e10)
      3. Drop columns with >5% NaN (unstable descriptors)
      4. Impute remaining NaN with column medians
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

    # Clean: replace inf → NaN, mask extreme values
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.mask(X.abs() > 1e10)

    # Drop columns with >5% NaN (unstable descriptors — same as notebook)
    nan_frac = X.isna().mean()
    keep_cols = nan_frac[nan_frac <= 0.05].index.tolist()
    if not keep_cols:
        keep_cols = list(X.columns[:1])  # safety: never empty
    X = X[keep_cols]

    # Impute remaining NaN with column medians (same as notebook)
    impute_medians = X.median().to_dict()
    X = X.fillna(impute_medians)

    # Clip extreme values
    X = X.clip(lower=-1e10, upper=1e10)

    print(f"  Features: {X.shape[1]} columns, {X.shape[0]} samples")
    print(f"  Labels:   class distribution =\n{y.value_counts().to_string()}")
    return X, y, keep_cols, impute_medians


# ── Model Training ──────────────────────────────────────────────────────────

def train_random_forest(
    X: pd.DataFrame,
    y: pd.Series,
    random_state: int = 42,
    tune: bool = True,
    n_iter: int = 60,
    cv_folds: int = 5,
    groups: pd.Series | None = None,
    calibrate: bool = True,
) -> tuple[object, dict]:
    """
    Train a Random Forest classifier with optional hyperparameter tuning.

    Notebook-inspired improvements:
      - Scaffold-aware split/CV (pass `groups`, e.g. InChIKey scaffold blocks)
        so near-duplicate compounds never leak across train/test.
      - Probability calibration (CalibratedClassifierCV) so raw RF
        probabilities can be meaningfully multiplied into a priority score.

    Parameters
    ----------
    tune : bool
        If True, run RandomizedSearchCV. If False, use sensible defaults.
    n_iter : int
        Number of randomized search iterations.
    cv_folds : int
        Cross-validation folds for hyperparameter search.
    groups : pd.Series, optional
        Per-row group labels (e.g. scaffold group ids). When provided, the
        train/test split and CV become group-aware.
    calibrate : bool
        Wrap the final model in CalibratedClassifierCV.

    Returns
    -------
    model : classifier
        Trained (and optionally calibrated) model.
    best_params : dict
        Best hyperparameters found (or defaults if tune=False).
    """
    # ── Scaffold-aware split when groups are provided ──
    if groups is not None:
        gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=random_state)
        tr_idx, te_idx = next(gss.split(X, y, groups=groups))
        X_train, X_test = X.iloc[tr_idx], X.iloc[te_idx]
        y_train, y_test = y.iloc[tr_idx], y.iloc[te_idx]
        groups_train = groups.iloc[tr_idx]
        leaked = set(groups_train) & set(groups.iloc[te_idx])
        if leaked:
            print(f"  ⚠️  Scaffold leakage detected ({len(leaked)} groups shared) — check group data.")
        print(f"  Scaffold-aware split — Train: {X_train.shape[0]} | Test: {X_test.shape[0]}")
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, stratify=y, random_state=random_state
        )
        groups_train = None
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

        if groups_train is not None:
            # Scaffold-grouped CV (never leaks near-duplicates into a fold)
            n_groups = groups_train.nunique()
            group_folds = max(2, min(actual_folds, n_groups))
            cv = StratifiedGroupKFold(n_splits=group_folds, shuffle=True, random_state=random_state)
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
            search.fit(X_train, y_train, groups=groups_train)
        else:
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

    # ── Calibrate probabilities (isotonic for larger data, sigmoid otherwise) ──
    if calibrate:
        method = "isotonic" if len(X_train) >= 1000 else "sigmoid"
        cal_folds = max(2, min(5, len(X_train)))
        model = CalibratedClassifierCV(model, method=method, cv=cal_folds)
        model.fit(X_train, y_train)
        print(f"  Probabilities calibrated ({method})")

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
    importances = calibrated_estimator(model).feature_importances_
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


def save_model_with_metadata(model, path: str, descriptor_cols, impute_medians):
    """Persist a model together with its training-time cleaning metadata.

    The metadata (kept descriptor columns + median imputation values) is
    attached to the model object so predictions can reproduce the exact
    preprocessing the model learned on.
    """
    attach_model_metadata(model, descriptor_cols, impute_medians)
    save_model(model, path)


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
