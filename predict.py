"""
predict.py
----------
Load trained models and predict activity and toxicity for new compounds.

Accepts:
  - A CSV/Excel file with SMILES (auto-extracts features via RDKit)
  - A CSV/Excel file with pre-computed features (skips RDKit)

Usage:
    python predict.py --input new_compounds.csv --smiles-col Smiles
    python predict.py --input new_features.csv  (pre-computed features, no RDKit needed)
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import joblib
import numpy as np
import pandas as pd


def predict_on_features(model, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray | None]:
    """Return (class_predictions, probability_scores)."""
    preds = model.predict(X)
    try:
        probas = model.predict_proba(X)[:, 1]
    except Exception:
        probas = None
    return preds, probas


def main():
    parser = argparse.ArgumentParser(
        description="Predict activity & toxicity for new compounds."
    )
    parser.add_argument(
        "--input", "-i", required=True,
        help="Path to input file (CSV/Excel with SMILES or pre-computed features)."
    )
    parser.add_argument(
        "--activity-model", default="models/activity.pkl",
        help="Path to trained activity model."
    )
    parser.add_argument(
        "--toxicity-model", default="models/toxicity.pkl",
        help="Path to trained toxicity model."
    )
    parser.add_argument(
        "--output", "-o", default="outputs/predictions.csv",
        help="Path to save prediction results."
    )
    parser.add_argument(
        "--smiles-col", default=None,
        help="SMILES column name. If provided, features will be extracted via RDKit."
    )
    parser.add_argument(
        "--skip-toxicity", action="store_true",
        help="Skip toxicity prediction (activity only)."
    )
    parser.add_argument(
        "--skip-activity", action="store_true",
        help="Skip activity prediction (toxicity only)."
    )
    args = parser.parse_args()

    # ── Load input ──
    input_path = Path(args.input)
    if input_path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(input_path)
    else:
        df = pd.read_csv(input_path)

    print(f"Loaded {len(df)} compounds from: {args.input}")

    # ── Feature extraction if SMILES column is provided ──
    if args.smiles_col:
        print(f"Extracting features from SMILES column: '{args.smiles_col}'")
        from extract_features import (
            compute_all_rdkit_descriptors,
            compute_topological_indices,
            create_molecules,
        )
        mol_list = create_molecules(df[args.smiles_col])
        valid = [m is not None for m in mol_list]
        if not all(valid):
            print(f"  Dropping {sum(not v for v in valid)} unparseable SMILES.")
            df = df[valid].reset_index(drop=True)
            mol_list = [m for m in mol_list if m is not None]

        desc_df = compute_all_rdkit_descriptors(mol_list)
        topo_df = compute_topological_indices(mol_list)
        X = pd.concat([desc_df, topo_df], axis=1)
    else:
        # Assume the file already contains features
        drop_cols = set()
        for col in ["Compound_ID", "Name", "Smiles", "mol",
                     "Activity_Label", "Toxicity_Label"]:
            if col in df.columns:
                drop_cols.add(col)
        X = df.drop(columns=list(drop_cols & set(df.columns)), errors="ignore")
        X = X.select_dtypes(include=[np.number])

    print(f"Feature matrix: {X.shape[0]} rows × {X.shape[1]} columns")

    # ── Prediction ──
    results = df.copy()

    if not args.skip_activity:
        act_path = Path(args.activity_model)
        if act_path.exists():
            print(f"Loading activity model: {act_path}")
            act_model = joblib.load(act_path)
            from train_common import align_features_for_model
            X_aligned = align_features_for_model(X, act_model)
            preds, probas = predict_on_features(act_model, X_aligned)
            results["Activity_Prediction"] = preds
            if probas is not None:
                results["Activity_Score"] = probas.round(4)
        else:
            print(f"Activity model not found: {act_path} — skipping.")

    if not args.skip_toxicity:
        tox_path = Path(args.toxicity_model)
        if tox_path.exists():
            print(f"Loading toxicity model: {tox_path}")
            tox_model = joblib.load(tox_path)
            from train_common import align_features_for_model
            X_aligned = align_features_for_model(X, tox_model)
            preds, probas = predict_on_features(tox_model, X_aligned)
            results["Toxicity_Prediction"] = preds
            if probas is not None:
                results["Toxicity_Score"] = probas.round(4)
        else:
            print(f"Toxicity model not found: {tox_path} — skipping.")

    # ── Save ──
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.suffix.lower() == ".xlsx":
        results.to_excel(output_path, index=False)
    else:
        results.to_csv(output_path, index=False)

    print(f"\nPredictions saved to: {output_path}")
    print(f"Columns: {list(results.columns)}")

    # Quick summary
    if "Activity_Prediction" in results:
        print(f"\nActivity predictions: {results['Activity_Prediction'].value_counts().to_dict()}")
    if "Toxicity_Prediction" in results:
        print(f"Toxicity predictions: {results['Toxicity_Prediction'].value_counts().to_dict()}")


if __name__ == "__main__":
    main()
