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
import os
import signal
import sys
import warnings
from pathlib import Path

# Cap BLAS/OpenMP threads before numpy/rdkit import (see app.py for why).
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit.Chem import Descriptors
from rdkit.ML.Descriptors import MoleculeDescriptors

warnings.filterwarnings("ignore")


class _SIGFPEError(Exception):
    """Raised when a SIGFPE signal is caught (floating-point exception)."""
    pass


def _sigfpe_handler(signum, frame):
    raise _SIGFPEError("SIGFPE: floating-point exception")


def _sigfpe_protected(fn, mol):
    """Call an RDKit descriptor function with SIGFPE protection.

    Descriptors that call CharacteristicPolynomial (BalabanJ, Ipc, AvgIpc)
    can trigger SIGFPE via numpy.dot — a C-level signal that Python's
    except won't catch.  We install a temporary handler and return NaN
    on failure so the molecule isn't lost entirely.
    """
    old_handler = signal.signal(signal.SIGFPE, _sigfpe_handler)
    try:
        return fn(mol)
    except (_SIGFPEError, Exception):
        return np.nan
    finally:
        signal.signal(signal.SIGFPE, old_handler)


# Descriptors known to call CharacteristicPolynomial — need SIGFPE guard
_SIGFPE_RISK_DESCRIPTORS = {"BalabanJ", "Ipc"}


def _safe_balaban_j(mol):
    """Compute BalabanJ with SIGFPE protection."""
    return _sigfpe_protected(Descriptors.BalabanJ, mol)


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
    """Compute all ~210 RDKit molecular descriptors, fault-tolerantly.

    Some RDKit descriptors (e.g. MaxEStateIndex / EStateIndices) can raise
    for particular molecules (overflow). One bad molecule used to crash the
    whole batch (and the request). Now each molecule is guarded:
      - fast path: compute all descriptors at once;
      - on failure: recompute descriptor-by-descriptor, skipping any that
        raise and leaving a NaN for that cell (later imputed/cleaned).
    """
    _EXCLUDE_DESCRIPTORS = set()  # all descriptors included; SIGFPE-risk ones handled in _safe_row
    descriptor_names = [
        x[0] for x in Descriptors._descList if x[0] not in _EXCLUDE_DESCRIPTORS
    ]
    descriptor_fns = dict(Descriptors._descList)
    calculator = MoleculeDescriptors.MolecularDescriptorCalculator(descriptor_names)

    def _safe_row(mol):
        # Wrap batch computation with SIGFPE guard — BalabanJ in the
        # calculator can trigger a C-level floating-point exception that
        # Python's except won't catch.
        old_handler = signal.signal(signal.SIGFPE, _sigfpe_handler)
        try:
            row = list(calculator.CalcDescriptors(mol))
            signal.signal(signal.SIGFPE, old_handler)
            return row
        except (_SIGFPEError, Exception):
            signal.signal(signal.SIGFPE, old_handler)
            pass
        # Fallback: one descriptor at a time so a single failure can't
        # wipe out the whole molecule's features.
        row = []
        for name in descriptor_names:
            try:
                if name in _SIGFPE_RISK_DESCRIPTORS:
                    row.append(_sigfpe_protected(descriptor_fns[name], mol))
                else:
                    row.append(descriptor_fns[name](mol))
            except Exception:
                row.append(np.nan)
        return row

    values = []
    for mol in mol_list:
        if mol is None:
            values.append([np.nan] * len(descriptor_names))
        else:
            values.append(_safe_row(mol))

    result = pd.DataFrame(values, columns=descriptor_names)
    # Clean inf/NaN values that break scikit-learn
    result = result.replace([np.inf, -np.inf], np.nan).fillna(0)
    return result.clip(lower=-1e10, upper=1e10)


def _largest_fragment(mol):
    """Return the largest connected fragment of a molecule.

    For salts or multi-component SMILES (e.g. 'CC(=O)O.[Na]'), topological
    indices are undefined across disconnected fragments.  We use the largest
    fragment (by atom count) — consistent with the notebook's approach.
    """
    mol_noh = Chem.RemoveHs(mol)
    frags = Chem.GetMolFrags(mol_noh, asMols=True, sanitizeFrags=False)
    if not frags:
        return mol_noh
    return max(frags, key=lambda m: m.GetNumAtoms())


def wiener_index(mol) -> float:
    """
    Wiener index: sum of shortest-path (topological) distances between every
    pair of heavy atoms in the molecular graph.
    Computed on the largest connected fragment (handles salts properly).
    """
    frag = _largest_fragment(mol)
    dist_matrix = Chem.GetDistanceMatrix(frag)
    return float(np.sum(dist_matrix) / 2)


def zagreb_indices(mol) -> tuple:
    """
    First (M1) and Second (M2) Zagreb indices, computed on the heavy-atom graph.
    Computed on the largest connected fragment (handles salts properly).

    M1 = sum of squared vertex degrees.
    M2 = sum, over all bonds, of the product of the degrees of its two endpoint atoms.
    """
    frag = _largest_fragment(mol)
    degrees = [atom.GetDegree() for atom in frag.GetAtoms()]
    m1 = sum(d ** 2 for d in degrees)
    m2 = sum(
        bond.GetBeginAtom().GetDegree() * bond.GetEndAtom().GetDegree()
        for bond in frag.GetBonds()
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


# ── Notebook-inspired improvements (refinedd_code.ipynb) ────────────────────

def scaffold_id(smiles):
    """First block of the InChIKey = the molecule's constitution (ignores
    stereochemistry/tautomer details). Compounds sharing this are treated as
    the same 'group' so near-duplicates never split across train/test."""
    if smiles is None:
        return None
    mol = Chem.MolFromSmiles(str(smiles))
    if mol is None:
        return None
    return Chem.MolToInchiKey(mol).split("-")[0]


def clean_descriptor_matrix(df, descriptor_cols, impute_medians=None):
    """Robust descriptor cleaning ported from refinedd_code.ipynb.

    - Replaces inf with NaN
    - Treats extreme-magnitude finite values (|x| > 1e10) as missing (RDKit's
      Ipc descriptor can overflow float32 during fitting otherwise)
    - During TRAINING (impute_medians=None): drops columns that are >5% missing,
      then imputes remaining NaN with the column median. Returns the kept
      columns and the median dict so they can be reused at prediction time.
    - During PREDICTION (impute_medians=dict): reduces to exactly the kept
      columns and fills with the TRAINING medians (never recomputes).

    Returns (X_clean, keep_cols, medians).
    """
    X = df[descriptor_cols].replace([np.inf, -np.inf], np.nan)
    SAFE_MAX = 1e10
    X = X.mask(X.abs() > SAFE_MAX)

    if impute_medians is None:
        nan_frac = X.isna().mean()
        keep_cols = nan_frac[nan_frac <= 0.05].index.tolist()
        if not keep_cols:
            keep_cols = descriptor_cols[:1]  # never return an empty feature set
        X = X[keep_cols]
        medians = X.median().to_dict()
        X = X.fillna(medians)
        return X, keep_cols, medians
    else:
        keep_cols = list(impute_medians.keys())
        X = X[keep_cols].fillna(impute_medians)
        return X, keep_cols, impute_medians


if __name__ == "__main__":
    main()
