"""
extract_features.py
-------------------
Convert SMILES strings into numerical molecular descriptors using RDKit.

This module is derived from the FINAL_MCS_TRAINING_2026.ipynb notebook.
It reads compounds from an Excel/CSV file, generates ~210 standard RDKit
descriptors plus Wiener, Zagreb M1, and Zagreb M2 topological indices,
and writes the feature matrix to a CSV file.

Usage:
    python extract_features.py --input datasets/compounds.xlsx --output datasets/features.csv
"""

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit.Chem import Descriptors
from rdkit.ML.Descriptors import MoleculeDescriptors

warnings.filterwarnings("ignore")


def parse_smiles_column(df: pd.DataFrame) -> str:
    """Auto-detect the SMILES column (case-insensitive)."""
    for col in df.columns:
        if col.strip().lower() in ("smiles", "smile", "canonical_smiles"):
            return col
    # Fallback: take the first column that looks like SMILES
    for col in df.columns:
        sample = str(df[col].dropna().iloc[0]) if len(df) > 0 else ""
        if any(c in sample for c in ("C", "N", "O", "=", "(", ")")):
            return col
    raise ValueError(
        "Could not auto-detect a SMILES column. "
        "Ensure the file has a column named 'Smiles' or 'SMILES'."
    )


def load_compounds(path: str) -> pd.DataFrame:
    """Load compounds from an Excel or CSV file."""
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(path)
    elif path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    else:
        raise ValueError(f"Unsupported file format: {path.suffix}. Use .xlsx or .csv")


def create_molecules(smiles_series: pd.Series) -> list:
    """Convert SMILES strings to RDKit Mol objects (with explicit hydrogens)."""
    mol_list = []
    failed = 0
    for i, smi in enumerate(smiles_series):
        try:
            mol = Chem.MolFromSmiles(str(smi))
            if mol is None:
                print(f"  [WARNING] Could not parse SMILES at row {i}: {smi}")
                failed += 1
                mol_list.append(None)
            else:
                mol = Chem.AddHs(mol)
                mol_list.append(mol)
        except Exception as e:
            print(f"  [WARNING] Error at row {i} ({smi}): {e}")
            failed += 1
            mol_list.append(None)
    if failed:
        print(f"  {failed} SMILES failed to parse (will be dropped).")
    return mol_list


def compute_all_rdkit_descriptors(mol_list: list) -> pd.DataFrame:
    """Compute all ~210 RDKit molecular descriptors."""
    descriptor_names = [x[0] for x in Descriptors._descList]
    calculator = MoleculeDescriptors.MolecularDescriptorCalculator(descriptor_names)

    values = []
    for mol in mol_list:
        if mol is None:
            values.append([np.nan] * len(descriptor_names))
        else:
            values.append(list(calculator.CalcDescriptors(mol)))

    result = pd.DataFrame(values, columns=descriptor_names)
    # Clean inf/NaN values that break scikit-learn
    result = result.replace([np.inf, -np.inf], np.nan).fillna(0)
    return result.clip(lower=-1e10, upper=1e10)


def wiener_index(mol) -> float:
    """
    Wiener index: sum of shortest-path (topological) distances between every
    pair of heavy atoms in the molecular graph.
    """
    mol_noh = Chem.RemoveHs(mol)
    dist_matrix = Chem.GetDistanceMatrix(mol_noh)
    return float(np.sum(dist_matrix) / 2)


def zagreb_indices(mol) -> tuple:
    """
    First (M1) and Second (M2) Zagreb indices, computed on the heavy-atom graph.

    M1 = sum of squared vertex degrees.
    M2 = sum, over all bonds, of the product of the degrees of its two endpoint atoms.
    """
    mol_noh = Chem.RemoveHs(mol)
    degrees = [atom.GetDegree() for atom in mol_noh.GetAtoms()]
    m1 = sum(d ** 2 for d in degrees)
    m2 = sum(
        bond.GetBeginAtom().GetDegree() * bond.GetEndAtom().GetDegree()
        for bond in mol_noh.GetBonds()
    )
    return m1, m2


def compute_topological_indices(mol_list: list) -> pd.DataFrame:
    """Compute Wiener, Zagreb M1, and Zagreb M2 indices."""
    wiener_vals, m1_vals, m2_vals = [], [], []
    for mol in mol_list:
        if mol is None:
            wiener_vals.append(np.nan)
            m1_vals.append(np.nan)
            m2_vals.append(np.nan)
        else:
            wiener_vals.append(wiener_index(mol))
            m1, m2 = zagreb_indices(mol)
            m1_vals.append(m1)
            m2_vals.append(m2)

    result = pd.DataFrame({
        "WienerIndex": wiener_vals,
        "Zagreb_M1": m1_vals,
        "Zagreb_M2": m2_vals,
    })
    # Clean inf/NaN values
    result = result.replace([np.inf, -np.inf], np.nan).fillna(0)
    return result.clip(lower=-1e10, upper=1e10)


def main():
    parser = argparse.ArgumentParser(
        description="Extract molecular descriptors from SMILES compounds."
    )
    parser.add_argument(
        "--input", "-i", required=True,
        help="Path to input Excel (.xlsx) or CSV (.csv) file containing SMILES."
    )
    parser.add_argument(
        "--output", "-o", default="datasets/features.csv",
        help="Path to output CSV file for the feature matrix (default: datasets/features.csv)."
    )
    parser.add_argument(
        "--smiles-col", default=None,
        help="Name of the SMILES column (auto-detected if not provided)."
    )
    args = parser.parse_args()

    print(f"[1/4] Loading compounds from: {args.input}")
    df = load_compounds(args.input)
    print(f"  Loaded {len(df)} rows.")

    smiles_col = args.smiles_col or parse_smiles_column(df)
    print(f"  Using SMILES column: '{smiles_col}'")

    print("[2/4] Creating molecular objects...")
    mol_list = create_molecules(df[smiles_col])

    # Drop rows where mol parsing failed
    valid_mask = [m is not None for m in mol_list]
    if not all(valid_mask):
        df = df[valid_mask].reset_index(drop=True)
        mol_list = [m for m in mol_list if m is not None]

    print(f"  {len(mol_list)} molecules successfully parsed.")

    print("[3/4] Computing RDKit descriptors (~210 descriptors)...")
    desc_df = compute_all_rdkit_descriptors(mol_list)
    print(f"  Computed {desc_df.shape[1]} descriptors.")

    print("[4/4] Computing topological indices (Wiener, Zagreb M1, M2)...")
    topo_df = compute_topological_indices(mol_list)
    print(f"  Computed {topo_df.shape[1]} topological indices.")

    # Combine everything
    original_cols = [c for c in df.columns if c != "mol"]
    result = pd.concat(
        [df[original_cols].reset_index(drop=True), desc_df, topo_df], axis=1
    )

    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.suffix.lower() == ".xlsx":
        result.to_excel(output_path, index=False)
    else:
        result.to_csv(output_path, index=False)

    print(f"\nDone! Feature matrix saved to: {output_path}")
    print(f"  Shape: {result.shape[0]} rows × {result.shape[1]} columns")
    return result


if __name__ == "__main__":
    main()
