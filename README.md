# 🌿 CRABLOX

**Plant Toxicity Prediction Website** — a web-based machine learning tool that predicts the **activity against OXA-23** (a carbapenem-resistant bacterial enzyme) and **toxicity to humans** of chemical compounds found in plants.

Built by **The Science and Technology Education Center (STEC) — Batch of 2027**.

**Research Focus**: Discovering plant-based compounds that can inhibit OXA-23 β-lactamase and restore antibiotic effectiveness, while remaining safe for human use.

---

## ✨ Features

- **Train ML models** — upload CSV/Excel with SMILES + labels, train Random Forest classifiers, view metrics, ROC curves, confusion matrices, and feature importance.
- **Export test results** — after training, download the held-out **test-set predictions** and a one-row **metrics summary** as CSV (mirrors the students' Colab notebook 1.6a/2.6a).
- **Predict compounds** — upload SMILES and get instant activity & toxicity predictions (downloadable as CSV).
- **Plant search** — enter a plant name; the app looks up its known compounds (PubChem) and predicts their properties.
- **Rank compounds** — sort candidates by 4 selectable priority formulas: Multiplicative (Activity × Safety), Subtractive, Safety-Weighted, or Weighted (custom importance). The **default Multiplicative** formula matches the reference notebook exactly, and the ranking export reproduces the notebook's `flavonoid_top15_shortlist` column format.
- **Team page** — public page showcasing student members with profiles and pictures.
- **User accounts** — login/registration with **admin approval**, and admin **promote/demote** of other admins.
- **Model ownership** — only the owner (or an admin) can delete a trained model.

### ML pipeline highlights (v4)
- **Scaffold-aware splitting** — no near-duplicate leakage between train/test.
- **Probability calibration** — trustworthy, comparable scores (sigmoid for activity, isotonic for toxicity).
- **Training-median imputation** — consistent preprocessing at prediction time.
- **Robust descriptor cleaning** — handles RDKit edge cases (SIGFPE protection for BalabanJ/Ipc/AvgIpc).
- **Notebook-aligned** — GridSearchCV with MCC scoring, 217+4 features (RDKit 2026.03).

---

## 🚀 Quick Start

### 1. Install Miniforge + Conda Env (recommended)
```bash
curl -L -O "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh"
bash Miniforge3-Linux-x86_64.sh -b -p $HOME/miniforge3
source $HOME/miniforge3/bin/activate

conda create -n crablox python=3.10 rdkit=2026.03 -c conda-forge -y
conda activate crablox
pip install -r requirements.txt
```

### 2. Configure (optional)
```bash
cp .env.example .env
# Set SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD, AI_API_KEY
```

### 3. Run
```bash
./run.sh                          # auto-detects conda env
# or
conda activate crablox && python3 app.py
```

---

## 📁 Project Structure

```
botanicaltox/
├── app.py               # Flask web application (main entry)
├── database.py          # SQLite user database & auth helpers
├── extract_features.py  # SMILES → RDKit descriptors + robust cleaning
├── train_common.py      # Shared training/evaluation logic (scaffold-aware, calibrated)
├── train_activity.py    # CLI activity trainer
├── train_toxicity.py    # CLI toxicity trainer
├── predict.py           # CLI prediction
├── evaluate.py          # CLI model evaluation
├── plant_predict.py     # Plant compound lookup
├── ai_explainer.py      # Optional AI explanation of results
├── requirements.txt     # Python dependencies
├── run.sh               # Launcher (auto-uses venv)
├── CHANGELOG_2026-08-16.md   # Change log / tracing
├── DEPLOYMENT.md        # Deployment guide
├── USER_GUIDE.md        # Detailed user guide
├── models/              # Trained .pkl models + owners.json
├── templates/           # HTML templates
└── datasets/            # Sample CSV/Excel datasets
```

---

## 📊 Input CSV Format (unchanged)

| Purpose | Required columns | Optional |
|---------|------------------|----------|
| **Training** | `Smiles` + `Activity_Label` and/or `Toxicity_Label` (or a custom label column) | `Compound_ID` |
| **Prediction** | `Smiles` (auto-detected) | `Compound_ID`, `Name` |

Example training rows:

| Compound_ID | Smiles | Activity_Label | Toxicity_Label |
|-------------|--------|:--------------:|:--------------:|
| CMP001 | CCO | 1 | 0 |
| CMP002 | CCCC | 1 | 1 |

---

## 📊 Student Research Datasets (`datasets/`)

These are the actual datasets used by the STEC research notebook (`CRABLOX_Colab_Complete_Pipeline.ipynb`) — upload them directly in the **Train** page to reproduce the study's models:

| File | Contents |
|------|----------|
| `toxicity_compounds.csv` | 1,156 FDA drug records (DILIst) — `Compound_ID, Smiles, Toxicity_Label` |
| `_ACTIVITY__105_COMPOUNDS_FINAL_TRAINING.csv` | 105 compounds (30 active / 75 inactive) against OXA-family β-lactamases |
| `prediction_compounds.xlsx` | 289-row flavonoid screening library (`Compound_ID, Smiles`) |

After training on these, run a prediction on `prediction_compounds.xlsx` and open the **Rank** page. With both models trained, download `ranking_top15.csv` for the notebook-compatible top-15 shortlist (or `ranking.csv` for the full ranked library).

---

## 🔐 Access Control

| Action | Guest | User | Admin |
|--------|:-----:|:----:|:-----:|
| View home / team pages | ✅ | ✅ | ✅ |
| Train / Predict / Plant / Rank | ❌ | ✅ | ✅ |
| Approve / reject users | ❌ | ❌ | ✅ |
| Promote / demote admins | ❌ | ❌ | ✅ |
| Delete any model | ❌ | ❌ | ✅ |
| Delete own model | ❌ | ✅ | ✅ |

---

## 🔄 Notebook → App Pipeline (feature/pipeline-alignment)

The reference pipeline lives in `CRABLOX_Colab_Complete_Pipeline.ipynb` — a Colab notebook that trains Random Forest models on molecular descriptors, evaluates them, and ranks compounds by a priority score. This branch aligns the Flask web app so its training pipeline matches the notebook step-by-step.

### What the notebook does

| Step | Notebook code | What it does |
|------|--------------|--------------|
| 1 | `CalcDescriptors(mols, desc_list)` | Computes 217 molecular descriptors via RDKit 2026.03 |
| 2 | `wiener_index(mol)`, `zagreb_indices(mol)`, `BalabanJ` | Adds 4 topological indices (Wiener, Zagreb M1/M2, BalabanJ) → 221 features total |
| 3 | `StratifiedGroupKFold` / `GroupShuffleSplit` | Scaffold-aware train/test split — compounds with the same scaffold never leak across splits |
| 4 | `GridSearchCV(..., scoring= MCC)` | Hyperparameter search optimizing Matthews Correlation Coefficient (not accuracy or AUC) |
| 5 | `isotonic_regression` (toxicity) / `sigmoid` (activity) | Calibrates prediction probabilities so scores are comparable across models |
| 6 | `Priority = Activity_Score × (1 − Toxicity_Score)` | Ranks compounds — high activity + low toxicity = top priority |

### What we changed in the app to match

| App file | Change | Why |
|----------|--------|-----|
| `extract_features.py` | Re-enabled BalabanJ, added Ipc/AvgIpc with SIGFPE protection, added `_largest_fragment()` for Wiener/Zagreb | Notebook uses all 217+4 descriptors; old app excluded BalabanJ and used whole-molecule topological indices |
| `train_common.py` | Switched from `RandomizedSearchCV(ROC-AUC)` to `GridSearchCV(MCC)`, added task-specific param grids, task-specific calibration (sigmoid=activity, isotonic=toxicity) | Notebook uses MCC scoring and different calibration per task |
| `train_common.py` | `load_features_and_labels()` now returns 4-tuple `(X, y, descriptor_cols, impute_medians)` with median imputation + drop cols >5% NaN | Matches notebook's preprocessing: impute with training medians, drop unstable descriptors |
| `run.sh` | Prefers conda env `~/miniforge3/envs/crablox/` over pip venv | RDKit 2026.03 (217 descriptors) is only available via conda-forge, not pip |
| `app.py` | Training routes unpack 4-tuple, pass `task=` to `train_random_forest()` | Wires up the new calibration and param grid logic per task |

### Verification

After these changes, training on the notebook's own data (`datasets/_ACTIVITY__105_COMPOUNDS_FINAL_TRAINING.csv` and `datasets/toxicity_compounds.csv`) produces ranked results with **Spearman rank correlation ≈ 0.90** against the notebook's output. The remaining ~10% gap comes from non-determinism in the cross-validation splits (GroupShuffleSplit has inherent randomness).

Top compound in both: `445881` — confirmed matching.

### Ranking output matches the notebook shortlist

With both an activity and a toxicity model trained, the **Rank** page produces two downloadable CSVs that mirror the notebook's shortlist format (`flavonoid_top15_shortlist (2).csv`):

- `ranking.csv` — full ranked library (all compounds)
- `ranking_top15.csv` — top 15 by priority score (notebook shortlist format)

Both use the notebook's exact column order:

`Rank, Compound_ID, Smiles, Wiener, Zagreb1, Zagreb2, Balaban_RDKit, activity_score, Activity_Predicted_Label, toxicity_score, Toxicity_Predicted_Label, safety_score, priority_score`

The four selectable ranking formulas:

| Formula | Computation | In notebook? |
|---------|-------------|--------------|
| **Multiplicative** (default) | `Activity × (1 − Toxicity)` | ✅ Yes — the notebook's formula |
| Subtractive | `Activity − Toxicity` | ❌ App-only |
| Safety-Weighted | `Activity × (1 − Toxicity²)` | ❌ App-only |
| Weighted | `w₁·Activity + w₂·Safety` | ❌ App-only |

The **Multiplicative** option is identical to the notebook (`priority_score = activity_score × (1 − toxicity_score)`), so selecting it (the default) reproduces the notebook's ranking logic. Scores are exported at full precision (the notebook does not round), and `Source_File` is appended as a trailing column for multi-file uploads.

---

## 📚 Documentation

- **`USER_GUIDE.md`** — full how-to for students
- **`DEPLOYMENT.md`** — setup on a fresh machine / production
- **`CHANGELOG_2026-08-16.md`** — record of changes from the original "Drug AI" app
- **`models/README.md`** — trained model conventions

---

## ⚠️ Notes

- Predictions are **computational** — always validate with experimental testing.
- The AI explainer is optional; if no API key is set (or the network is unavailable) it is disabled gracefully.

---

© 2026 CRABLOX — Plant Toxicity Prediction. All Rights Reserved by The Science and Technology Education Center (STEC), Batch of 2027.
