# BotanicalTox — Change Log
**Date:** 2026-08-16
**Scope:** All changes applied to this repository on this date (from the original "Drug AI" codebase to the current "BotanicalTox" application).

---

## 1. Application rename & rebrand
- Renamed **"Drug AI" → "BotanicalTox"** (Plant Toxicity Prediction website).
- Updated titles, navbar brand, hero text, footer, `app.py` docstring, and startup banner.
- Changed the colour theme to a botanical green; added a two-line footer:
  > `BotanicalTox © 2026 — Plant Toxicity Prediction`
  > `All Rights Reserved · The Science and Technology Education Center (STEC) · Batch of 2027`
- Port: `5000` → `5001` (app.py, DEPLOYMENT.md, models/README.md, USER_GUIDE.md).

## 2. User authentication & access control
- Added **Flask-Login** + **SQLite** user database (`instance/users.db` via `database.py`).
- New pages: `templates/login.html`, `templates/register.html`.
- Routes: `/login`, `/register`, `/logout`; protected ML routes with `@login_required`.
- Default admin: `admin` / `admin123` (configurable via `.env` — `ADMIN_USERNAME`, `ADMIN_PASSWORD`).
- **Admin approval flow**: self-registered users start PENDING; admin approves/rejects/deletes from the User Management page (`/admin/users`).
- **Admin role management**: admins can **Promote/Demote** users to/from the admin role.
  - Guards: cannot change own role; cannot demote the **last admin**; invalid roles rejected.
- Public landing page (`/`); guests prompted to log in only when clicking protected features.

## 3. Team page & profiles
- New public **Team** page (`/team`, `templates/team.html`) showing curated student members.
- Profile system: members edit **full name, course, bio, avatar** from **Settings → Your Profile**.
- Avatars stored in `instance/avatars/user<id>.<ext>`; served via `/avatar/<id>`.
- Admin marks users as team members via the **Team / Unmark** toggle (only `is_team=1` users appear).
- Seeded **7 placeholder team members** (usernames `msantos`, `jramirez`, `areyes`, `mbautista`, `cmendoza`, `rcruz`, `bvillanueva`; password `stec2027`).

## 4. Model ownership & deletion rules
- Trained models are now **owned** by the user who created them (`models/owners.json`).
- **Only the owner or an admin** can delete a model; others see a 🔒 "Owner only" badge.
- `default` / `legacy` models are protected (admin-only deletion).

## 5. Machine-learning pipeline upgrade *(ported from `refinedd_code.ipynb`)*
- **Scaffold-aware splitting** — near-duplicate compounds (same InChIKey scaffold) never leak across train/test (`GroupShuffleSplit` + `StratifiedGroupKFold`).
- **Probability calibration** — models wrapped in `CalibratedClassifierCV` (isotonic for large data, sigmoid otherwise) so scores are meaningful.
- **Robust feature cleaning** — `clean_descriptor_matrix()`: replaces `inf`, masks extreme values (>1e10), drops columns >5% missing, imputes with **training medians**.
- **Training metadata stored with each model** (`_descriptor_cols`, `_impute_medians`) so prediction reuses the exact training-time preprocessing instead of fill-with-0.
- Updated feature alignment in `predict`, `plant`, `ranking`, and CLI `predict.py` via `align_features_for_model()`.
- **AI explainer fix**: OpenAI client construction no longer crashes prediction when a SOCKS proxy is configured (uses `httpx.Client(trust_env=False)` + graceful fallback).
- `medchem` model retrained with the new pipeline (calibrated, metadata attached).

## 6. Environment & tooling
- `requirements.txt`: added `flask-login`, `python-dotenv`.
- `python-dotenv` import made **optional** (graceful fallback).
- Created **`run.sh`** launcher (auto-uses `venv/`).
- `python3 app.py` made to work again by installing `flask-login` + `python-dotenv` into the user site-packages (system pip blocked by read-only `~/.local/bin`).

## 7. Configuration & docs
- `.env.example` updated with `SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`.
- `DEPLOYMENT.md` and `USER_GUIDE.md` updated for all the above.
- `.gitignore` updated to ignore `venv/`, `instance/`, `*.ipynb`, `models/owners.json`.

---

## ⚠️ CSV columns — **NO changes**
The required input CSV/Excel columns are **unchanged** from the original app:

| Purpose | Required columns | Optional |
|---------|------------------|----------|
| **Training** | `Smiles`, plus `Activity_Label` and/or `Toxicity_Label` (or a custom label column name) | `Compound_ID` |
| **Prediction** | `Smiles` (auto-detected; also supports pre-computed feature files) | `Compound_ID`, `Name` |

The pipeline changes were **internal only** (feature cleaning, splitting, calibration) — you do **not** need to reformat any existing data files.

*Examples verified on this date:*
- `datasets/medchem_training.csv` → `Compound_ID, Smiles, Activity_Label, Toxicity_Label`
- `datasets/medchem_prediction.csv` → `Compound_ID, Smiles`
