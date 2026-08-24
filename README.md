# 🌿 BotanicalTox

**Plant Toxicity Prediction Website** — a web-based machine learning tool that predicts the **activity against OXA-23** (a carbapenem-resistant bacterial enzyme) and **toxicity to humans** of chemical compounds found in plants.

Built by **The Science and Technology Education Center (STEC) — Batch of 2027**.

**Research Focus**: Discovering plant-based compounds that can inhibit OXA-23 β-lactamase and restore antibiotic effectiveness, while remaining safe for human use.

---

## ✨ Features

- **Train ML models** — upload CSV/Excel with SMILES + labels, train Random Forest classifiers, view metrics, ROC curves, confusion matrices, and feature importance.
- **Export test results** — after training, download the held-out **test-set predictions** and a one-row **metrics summary** as CSV (mirrors the students' Colab notebook 1.6a/2.6a).
- **Predict compounds** — upload SMILES and get instant activity & toxicity predictions (downloadable as CSV).
- **Plant search** — enter a plant name; the app looks up its known compounds (PubChem) and predicts their properties.
- **Rank compounds** — sort candidates by a priority score (Activity × Safety), so the top compounds are both likely active AND non-toxic.
- **Team page** — public page showcasing student members with profiles and pictures.
- **User accounts** — login/registration with **admin approval**, and admin **promote/demote** of other admins.
- **Model ownership** — only the owner (or an admin) can delete a trained model.

### ML pipeline highlights (v3)
- **Scaffold-aware splitting** — no near-duplicate leakage between train/test.
- **Probability calibration** — trustworthy, comparable scores.
- **Training-median imputation** — consistent preprocessing at prediction time.
- **Robust descriptor cleaning** — handles RDKit edge cases.

---

## 🚀 Quick Start

### 1. Setup
```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install "numpy<2"             # required by rdkit-pypi
```

### 2. Configure (optional)
```bash
cp .env.example .env
# Set SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD, AI_API_KEY
```

### 3. Run
```bash
./run.sh                          # uses venv automatically
# or
python3 app.py
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

These are the actual datasets used by the STEC research notebook (`final_destination.ipynb`) — upload them directly in the **Train** page to reproduce the study's models:

| File | Contents |
|------|----------|
| `toxicity_compounds.csv` | 1,156 FDA drug records (DILIst) — `Compound_ID, Smiles, Toxicity_Label` |
| `_ACTIVITY__105_COMPOUNDS_FINAL_TRAINING.csv` | 105 compounds (30 active / 75 inactive) against OXA-family β-lactamases |
| `prediction_compounds.xlsx` | 289-row flavonoid screening library (`Compound_ID, Smiles`) |

After training on these, run a prediction on `prediction_compounds.xlsx` and view the **Rank** page for the `Priority = Activity × Safety` shortlist.

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

## 📚 Documentation

- **`USER_GUIDE.md`** — full how-to for students
- **`DEPLOYMENT.md`** — setup on a fresh machine / production
- **`CHANGELOG_2026-08-16.md`** — record of changes from the original "Drug AI" app
- **`models/README.md`** — trained model conventions

---

## ⚠️ Notes

- Predictions are **computational** — always validate with experimental testing.
- The AI explainer is optional; if no API key is set (or the network is unavailable) it is disabled gracefully.
- `refinedd_code.ipynb` and `final_destination.ipynb` are experimental research notebooks (not part of the web app). `final_destination.ipynb` is the students' reference implementation: crash-safe RDKit descriptors (excludes `BalabanJ`/`Ipc`/`AvgIpc`), scaffold-aware splitting, isotonic/sigmoid calibration, `Priority = Activity × Safety`, and test-set CSV exports. It reads its data from `datasets/` (or bare filenames, e.g. in Colab).

---

© 2026 BotanicalTox — Plant Toxicity Prediction. All Rights Reserved by The Science and Technology Education Center (STEC), Batch of 2027.
