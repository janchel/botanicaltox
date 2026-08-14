"""
app.py — Flask Web Application
===============================
Web interface for the Drug AI ML pipeline. Students can:
  - Upload training data (CSV) → train models → view graphs & metrics
  - Upload prediction data (CSV) → get predictions → download results

Run:
    python3 app.py
    Then open http://localhost:5000 in a browser.
"""

import io
import os
import uuid
from pathlib import Path
from datetime import datetime

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, send_file, session, jsonify, Response, stream_with_context,
)
from werkzeug.utils import secure_filename

# ── Import our ML modules ───────────────────────────────────────────────────
from rdkit import Chem
from rdkit.Chem import Draw
from extract_features import (
    parse_smiles_column,
    create_molecules,
    compute_all_rdkit_descriptors,
    compute_topological_indices,
)
from train_common import (
    load_features_and_labels,
    train_random_forest,
    evaluate_model,
    save_model,
)
from ai_explainer import is_available as ai_is_available, explain_stream
from plant_predict import search_plant_compounds, search_by_species_and_activity

# ── App Setup ───────────────────────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = "drug-ai-2026-secret-key-change-in-production"
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB max upload
app.config["UPLOAD_FOLDER"] = Path(__file__).resolve().parent / "uploads"
app.config["MODEL_FOLDER"] = Path(__file__).resolve().parent / "models"
app.config["OUTPUT_FOLDER"] = Path(__file__).resolve().parent / "outputs"
app.config["SESSION_FOLDER"] = Path(__file__).resolve().parent / "sessions"

for folder in ["UPLOAD_FOLDER", "MODEL_FOLDER", "OUTPUT_FOLDER", "SESSION_FOLDER"]:
    app.config[folder].mkdir(parents=True, exist_ok=True)


def cleanup_old_sessions(max_age_hours: int = 24):
    """Delete session folders older than max_age_hours to free disk space."""
    import shutil
    import time
    session_root = app.config["SESSION_FOLDER"]
    if not session_root.exists():
        return
    now = time.time()
    cutoff = now - (max_age_hours * 3600)
    deleted = 0
    for child in session_root.iterdir():
        if child.is_dir():
            try:
                mtime = child.stat().st_mtime
                if mtime < cutoff:
                    shutil.rmtree(child)
                    deleted += 1
            except Exception:
                pass
    if deleted:
        print(f"  🧹 Cleaned up {deleted} old session(s) older than {max_age_hours}h")


# Run cleanup on startup
cleanup_old_sessions()

ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_session_dir() -> Path:
    """Each browser session gets its own folder for outputs."""
    sid = session.get("session_id")
    if not sid:
        sid = uuid.uuid4().hex[:12]
        session["session_id"] = sid
    d = app.config["SESSION_FOLDER"] / sid
    d.mkdir(parents=True, exist_ok=True)
    return d


def fig_to_b64(fig) -> str:
    """Convert a matplotlib figure to a base64 PNG string for inline HTML."""
    import base64
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def mol_to_b64(mol) -> str | None:
    """Convert an RDKit Mol object to a base64 PNG string."""
    import base64
    if mol is None:
        return None
    try:
        img = Draw.MolToImage(mol, size=(250, 150))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("utf-8")
    except Exception:
        return None


def list_available_models() -> dict:
    """Scan models/ folder and return {model_name: {activity: path, toxicity: path}}."""
    models = {}
    model_dir = app.config["MODEL_FOLDER"]
    if not model_dir.exists():
        return models
    for f in sorted(model_dir.iterdir()):
        if f.suffix == ".pkl":
            name = f.stem  # e.g., "activity_library1" or "toxicity_default"
            if name.startswith("activity_"):
                model_name = name[9:]  # after "activity_"
                models.setdefault(model_name, {})["activity"] = str(f)
            elif name.startswith("toxicity_"):
                model_name = name[9:]  # after "toxicity_"
                models.setdefault(model_name, {})["toxicity"] = str(f)
    return models


def classify_compound(mol) -> str:
    """Classify a molecule into chemical categories from its structure."""
    if mol is None:
        return "Unknown"
    tags = []
    mol_noh = Chem.RemoveHs(mol)
    arom_atoms = sum(1 for a in mol_noh.GetAtoms() if a.GetIsAromatic())
    if arom_atoms > 0:
        tags.append("Aromatic" if arom_atoms > 3 else "Small aromatic")
    rings = mol_noh.GetRingInfo().NumRings()
    if rings > 0 and not arom_atoms:
        tags.append("Cyclic")
    halogens = {"F": "Fluorinated", "Cl": "Chlorinated", "Br": "Brominated", "I": "Iodinated"}
    for a in mol_noh.GetAtoms():
        sym = a.GetSymbol()
        if sym in halogens:
            tags.append(halogens[sym])
            break
    if arom_atoms > 0:
        ring_atoms = mol_noh.GetRingInfo().AtomRings()
        hetero = any(any(mol_noh.GetAtomWithIdx(i).GetAtomicNum() not in (6,) for i in ring) for ring in ring_atoms)
        if hetero:
            tags.append("Heterocycle")
    acid = Chem.MolFromSmarts("C(=O)[OH]")
    if acid and mol_noh.HasSubstructMatch(acid):
        tags.append("Acid")
    amine = Chem.MolFromSmarts("[NX3;!$(NC=O)]")
    if amine and mol_noh.HasSubstructMatch(amine):
        tags.append("Amine")
    alcohol = Chem.MolFromSmarts("[OX2H]")
    if alcohol and mol_noh.HasSubstructMatch(alcohol):
        tags.append("Alcohol/Phenol" if arom_atoms > 0 else "Alcohol")
    ester = Chem.MolFromSmarts("C(=O)O[!H]")
    if ester and mol_noh.HasSubstructMatch(ester):
        tags.append("Ester")
    carbonyl = Chem.MolFromSmarts("[CX3](=O)[#6]")
    if carbonyl and mol_noh.HasSubstructMatch(carbonyl) and "Ester" not in tags and "Acid" not in tags:
        tags.append("Ketone/Aldehyde")
    if rings == 0:
        heavy = mol_noh.GetNumAtoms()
        carbons = sum(1 for a in mol_noh.GetAtoms() if a.GetAtomicNum() == 6)
        if carbons > 4 and carbons / max(heavy, 1) > 0.8:
            tags.append("Alkane")
    if not tags:
        tags.append("Small molecule")
    # Clean up: "Acid" supersedes "Alcohol" (COOH is not a free alcohol)
    if "Acid" in tags and "Alcohol" in tags:
        tags.remove("Alcohol")
    return " | ".join(tags)


# ═══════════════════════════════════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    """Landing page — choose Train or Predict."""
    return render_template("index.html")


# ── TRAIN ROUTE ─────────────────────────────────────────────────────────────

@app.route("/train", methods=["GET", "POST"])
def train():
    """
    GET:  Show the training upload form.
    POST: Process the uploaded CSV, train models, and show results.
    """
    if request.method == "GET":
        return render_template("train.html")

    # ── POST: handle upload ──
    file = request.files.get("dataset")
    if not file or file.filename == "":
        flash("Please select a file to upload.", "error")
        return redirect(url_for("train"))

    if not allowed_file(file.filename):
        flash("Only CSV and Excel (.xlsx) files are allowed.", "error")
        return redirect(url_for("train"))

    train_activity = request.form.get("task_activity") == "activity"
    train_toxicity = request.form.get("task_toxicity") == "toxicity"
    custom_task_name = request.form.get("task_name", "").strip()

    if not train_activity and not train_toxicity:
        flash("Select at least one task to train.", "error")
        return redirect(url_for("train"))

    tune = request.form.get("tune") == "on"

    sess_dir = get_session_dir()
    filename = secure_filename(file.filename)
    upload_path = sess_dir / filename
    file.save(str(upload_path))

    try:
        # 1. Extract features
        df = pd.read_csv(upload_path) if upload_path.suffix == ".csv" else pd.read_excel(upload_path)
        smiles_col = parse_smiles_column(df)

        # ── Duplicate detection ──
        dupes = df[smiles_col].duplicated()
        if dupes.any():
            dup_count = dupes.sum()
            # Check for conflicting labels
            conflicts = 0
            activity_label_col = "Activity_Label" if "Activity_Label" in df.columns else None
            toxicity_label_col = "Toxicity_Label" if "Toxicity_Label" in df.columns else None
            for smi in df.loc[dupes, smiles_col].unique():
                rows = df[df[smiles_col] == smi]
                if activity_label_col and rows[activity_label_col].nunique() > 1:
                    conflicts += 1
                elif toxicity_label_col and rows[toxicity_label_col].nunique() > 1:
                    conflicts += 1
            if conflicts > 0:
                flash(
                    f"⚠️ Found {dup_count} duplicate SMILES, {conflicts} with conflicting labels. "
                    "Conflicting duplicates were removed. Review your data.",
                    "error"
                )
                # Remove all copies of conflicting duplicates
                conflict_smiles = set()
                for smi in df.loc[dupes, smiles_col].unique():
                    rows = df[df[smiles_col] == smi]
                    if activity_label_col and rows[activity_label_col].nunique() > 1:
                        conflict_smiles.add(smi)
                    elif toxicity_label_col and rows[toxicity_label_col].nunique() > 1:
                        conflict_smiles.add(smi)
                df = df[~df[smiles_col].isin(conflict_smiles)]
            else:
                flash(
                    f"ℹ️ Found {dup_count} duplicate SMILES with identical labels — kept first occurrence.",
                    "info"
                )
            # Deduplicate: keep first occurrence
            df = df.drop_duplicates(subset=[smiles_col], keep="first").reset_index(drop=True)

        mol_list = create_molecules(df[smiles_col])
        failed_count = sum(1 for m in mol_list if m is None)
        if failed_count:
            flash(
                f"⚠️ {failed_count} of {len(mol_list)} SMILES failed to parse and were dropped. "
                "Check your CSV for invalid SMILES strings.",
                "error"
            )
        valid_mask = [m is not None for m in mol_list]
        if not all(valid_mask):
            df = df[valid_mask].reset_index(drop=True)
            mol_list = [m for m in mol_list if m is not None]

        desc_df = compute_all_rdkit_descriptors(mol_list)
        topo_df = compute_topological_indices(mol_list)

        # Combine — keep label columns in the saved file for load_features_and_labels
        meta_cols = {"Compound_ID", "Name", "Smiles", "mol"}
        keep_cols = [c for c in df.columns if c not in meta_cols]
        feats = pd.concat(
            [df[keep_cols].reset_index(drop=True), desc_df, topo_df], axis=1
        )

        # Save features (includes label columns for load_features_and_labels)
        features_path = sess_dir / "features.csv"
        feats.to_csv(features_path, index=False)

        # 2. Train selected tasks
        model_name = request.form.get("model_name", "default").strip().lower()
        model_name = "".join(c for c in model_name if c.isalnum() or c in "_-") or "default"

        tasks_to_train = []
        if train_activity:
            task_name = custom_task_name if custom_task_name else "activity"
            label_col_name = request.form.get("label_col", "").strip() or "Activity_Label"
            tasks_to_train.append(("activity", label_col_name, task_name))
        if train_toxicity:
            task_name = custom_task_name if custom_task_name else "toxicity"
            label_col_name = request.form.get("label_col", "").strip() or "Toxicity_Label"
            tasks_to_train.append(("toxicity", label_col_name, task_name))

        all_metrics = {}
        all_graphs = {}
        all_best_params = {}
        combined_task_names = []
        overwritten = False

        for task_key, label_col, display_name in tasks_to_train:
            X, y = load_features_and_labels(str(features_path), label_col)
            model, best_params, splits = train_random_forest(
                X, y, random_state=42, tune=tune, n_iter=30 if tune else 0,
            )
            X_train, X_test, y_train, y_test = splits

            # Evaluate
            eval_dir = sess_dir / f"eval_{task_key}"
            eval_dir.mkdir(exist_ok=True)
            metrics = evaluate_model(
                model, X_train, X_test, y_train, y_test,
                task_name=task_key.title(), output_dir=str(eval_dir),
            )
            all_metrics[task_key] = metrics
            combined_task_names.append(display_name.title() if display_name not in ("activity", "toxicity") else task_key.title())

            # ROC Curve
            from sklearn.metrics import roc_curve, roc_auc_score, confusion_matrix
            y_test_proba = model.predict_proba(X_test)[:, 1]
            y_train_proba = model.predict_proba(X_train)[:, 1]
            fpr_tr, tpr_tr, _ = roc_curve(y_train, y_train_proba)
            fpr_te, tpr_te, _ = roc_curve(y_test, y_test_proba)
            fig, ax = plt.subplots(figsize=(5, 4))
            ax.plot(fpr_tr, tpr_tr, label=f"Train AUC={roc_auc_score(y_train, y_train_proba):.3f}")
            ax.plot(fpr_te, tpr_te, label=f"Test AUC={roc_auc_score(y_test, y_test_proba):.3f}")
            ax.plot([0, 1], [0, 1], "k--", alpha=0.3)
            ax.set_xlabel("FPR"); ax.set_ylabel("TPR")
            ax.set_title(f"ROC — {task_key.title()}")
            ax.legend(fontsize=9); fig.tight_layout()
            all_graphs[f"roc_{task_key}"] = fig_to_b64(fig); plt.close(fig)

            # Confusion Matrix
            cm = confusion_matrix(y_test, model.predict(X_test))
            fig, ax = plt.subplots(figsize=(4, 3.5))
            sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", ax=ax,
                        xticklabels=["Neg", "Pos"], yticklabels=["Neg", "Pos"])
            ax.set_xlabel("Predicted"); ax.set_ylabel("Actual")
            ax.set_title(f"CM — {task_key.title()}")
            fig.tight_layout()
            all_graphs[f"cm_{task_key}"] = fig_to_b64(fig); plt.close(fig)

            # Feature Importance
            importances = model.feature_importances_
            idx = np.argsort(importances)[::-1][:15]
            fig, ax = plt.subplots(figsize=(7, 5))
            ax.barh(range(len(idx)), importances[idx][::-1], align="center", color="steelblue")
            ax.set_yticks(range(len(idx)))
            ax.set_yticklabels([X.columns[i] for i in idx[::-1]], fontsize=8)
            ax.set_xlabel("Importance")
            ax.set_title(f"Top 15 Features — {task_key.title()}")
            fig.tight_layout()
            all_graphs[f"importance_{task_key}"] = fig_to_b64(fig); plt.close(fig)

            # Topological Indices
            topo_indices = ["WienerIndex", "Zagreb_M1", "Zagreb_M2", "BalabanJ"]
            topo_imps = {}
            for feat_name in topo_indices:
                if feat_name in X.columns:
                    col_idx = list(X.columns).index(feat_name)
                    topo_imps[feat_name] = importances[col_idx]
            if topo_imps:
                fig, ax = plt.subplots(figsize=(5, 3.5))
                labels = list(topo_imps.keys())
                values = list(topo_imps.values())
                colors = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12"]
                bars = ax.barh(labels[::-1], values[::-1], color=colors[::-1])
                ax.set_xlabel("Importance")
                ax.set_title(f"Topological Indices — {task_key.title()}")
                for bar, val in zip(bars, values[::-1]):
                    ax.text(bar.get_width() + 0.0003, bar.get_y() + bar.get_height()/2,
                            f"{val:.4f}", va="center", fontsize=9)
                fig.tight_layout()
                all_graphs[f"topo_{task_key}"] = fig_to_b64(fig)
                all_graphs[f"topo_data_{task_key}"] = {k: round(v, 6) for k, v in topo_imps.items()}
                plt.close(fig)

            # Save model
            model_path = sess_dir / f"{task_key}_model.pkl"
            save_model(model, str(model_path))
            shared_path = app.config["MODEL_FOLDER"] / f"{task_key}_{model_name}.pkl"
            if shared_path.exists():
                overwritten = True
            save_model(model, str(shared_path))

            if tune and best_params:
                all_best_params[task_key] = best_params

        # 7. Render results
        preview_cols = [c for c in df.columns if c not in ("mol",)]
        dataset_preview = df[preview_cols].head(10).to_dict(orient="records")
        dataset_columns = list(preview_cols)

        return render_template(
            "train_result.html",
            tasks=combined_task_names,
            all_metrics=all_metrics,
            all_graphs=all_graphs,
            all_best_params=all_best_params if tune else None,
            n_samples=len(df),
            n_features=desc_df.shape[1] + topo_df.shape[1],
            tune=tune,
            model_name=model_name,
            dataset_preview=dataset_preview,
            dataset_columns=dataset_columns,
            overwritten=overwritten,
        )

    except KeyError as e:
        flash(f"Missing column: {e}. Make sure your CSV has the required label column(s).", "error")
        return redirect(url_for("train"))
    except ValueError as e:
        flash(f"Data error: {e}", "error")
        return redirect(url_for("train"))
    except Exception as e:
        flash(f"Unexpected error: {e}", "error")
        return redirect(url_for("train"))


# ── PREDICT ROUTE ───────────────────────────────────────────────────────────

@app.route("/predict", methods=["GET", "POST"])
def predict():
    """
    GET:  Show the prediction upload form.
    POST: Process uploaded CSV, run predictions, show results.
    """
    if request.method == "GET":
        available_models = list_available_models()
        return render_template("predict.html",
                              available_models=available_models)

    # ── POST: handle upload ──
    file = request.files.get("dataset")
    if not file or file.filename == "":
        flash("Please select a file to upload.", "error")
        return redirect(url_for("predict"))

    if not allowed_file(file.filename):
        flash("Only CSV and Excel (.xlsx) files are allowed.", "error")
        return redirect(url_for("predict"))

    predict_activity = request.form.get("predict_activity") == "on"
    predict_toxicity = request.form.get("predict_toxicity") == "on"

    if not predict_activity and not predict_toxicity:
        flash("Select at least one prediction task.", "error")
        return redirect(url_for("predict"))

    sess_dir = get_session_dir()
    filename = secure_filename(file.filename)
    upload_path = sess_dir / filename
    file.save(str(upload_path))

    try:
        import joblib

        # Load data
        df = pd.read_csv(upload_path) if upload_path.suffix == ".csv" else pd.read_excel(upload_path)

        # Check for SMILES column → extract features
        try:
            smiles_col = parse_smiles_column(df)
        except ValueError:
            smiles_col = None

        # ── Duplicate detection for prediction ──
        if smiles_col:
            dupes = df[smiles_col].duplicated()
            if dupes.any():
                dup_count = dupes.sum()
                df = df.drop_duplicates(subset=[smiles_col], keep="first").reset_index(drop=True)
                flash(
                    f"ℹ️ Found {dup_count} duplicate SMILES in prediction data — kept first occurrence.",
                    "info"
                )

        if smiles_col:
            mol_list = create_molecules(df[smiles_col])
            failed_count = sum(1 for m in mol_list if m is None)
            if failed_count:
                flash(
                    f"⚠️ {failed_count} of {len(mol_list)} SMILES failed to parse and were dropped. "
                    "Check your CSV for invalid SMILES strings.",
                    "error"
                )
            valid_mask = [m is not None for m in mol_list]
            if not all(valid_mask):
                df = df[valid_mask].reset_index(drop=True)
                mol_list = [m for m in mol_list if m is not None]

            desc_df = compute_all_rdkit_descriptors(mol_list)
            topo_df = compute_topological_indices(mol_list)
            X = pd.concat([desc_df, topo_df], axis=1)
        else:
            # Assume pre-computed features
            drop_cols = {"Compound_ID", "Name", "Smiles", "mol", "Activity_Label", "Toxicity_Label"}
            X = df.drop(columns=list(drop_cols & set(df.columns)), errors="ignore")
            X = X.select_dtypes(include=[np.number])

        results = df.copy()
        graphs = {}

        # Get selected model name
        selected_model = request.form.get("model_name", "default").strip()
        if not selected_model:
            selected_model = "default"

        # Activity prediction
        if predict_activity:
            act_path = app.config["MODEL_FOLDER"] / f"activity_{selected_model}.pkl"
            if not act_path.exists():
                # Fallback: try old naming
                act_path = app.config["MODEL_FOLDER"] / "activity.pkl"
            if act_path.exists():
                act_model = joblib.load(act_path)
                try:
                    expected = act_model.feature_names_in_
                    X_aligned = X.reindex(columns=expected, fill_value=0)
                except Exception:
                    X_aligned = X
                results["Activity_Prediction"] = act_model.predict(X_aligned)
                try:
                    results["Activity_Score"] = act_model.predict_proba(X_aligned)[:, 1].round(4)
                except Exception:
                    pass

                # Distribution pie chart
                fig, ax = plt.subplots(figsize=(4, 4))
                counts = results["Activity_Prediction"].value_counts()
                labels = [f"{'Active' if k==1 else 'Inactive'} ({v})" for k, v in counts.items()]
                ax.pie(counts, labels=labels, autopct="%1.1f%%",
                       colors=["#2ecc71", "#e74c3c"], startangle=90)
                ax.set_title("Activity Predictions")
                fig.tight_layout()
                graphs["activity_pie"] = fig_to_b64(fig); plt.close(fig)

        # Toxicity prediction
        if predict_toxicity:
            tox_path = app.config["MODEL_FOLDER"] / f"toxicity_{selected_model}.pkl"
            if not tox_path.exists():
                tox_path = app.config["MODEL_FOLDER"] / "toxicity.pkl"
            if tox_path.exists():
                tox_model = joblib.load(tox_path)
                try:
                    expected = tox_model.feature_names_in_
                    X_aligned = X.reindex(columns=expected, fill_value=0)
                except Exception:
                    X_aligned = X
                results["Toxicity_Prediction"] = tox_model.predict(X_aligned)
                try:
                    results["Toxicity_Score"] = tox_model.predict_proba(X_aligned)[:, 1].round(4)
                except Exception:
                    pass

                fig, ax = plt.subplots(figsize=(4, 4))
                counts = results["Toxicity_Prediction"].value_counts()
                labels = [f"{'Toxic' if k==1 else 'Safe'} ({v})" for k, v in counts.items()]
                ax.pie(counts, labels=labels, autopct="%1.1f%%",
                       colors=["#2ecc71", "#e74c3c"], startangle=90)
                ax.set_title("Toxicity Predictions")
                fig.tight_layout()
                graphs["toxicity_pie"] = fig_to_b64(fig); plt.close(fig)

        # ── Add human-readable labels and chemical class ──
        if "Activity_Prediction" in results.columns:
            results["Activity_Label_Text"] = results["Activity_Prediction"].map(
                {1: "Active (inhibits OXA-23)", 0: "Inactive"}
            )
        if "Toxicity_Prediction" in results.columns:
            results["Toxicity_Label_Text"] = results["Toxicity_Prediction"].map(
                {1: "Toxic to humans", 0: "Safe"}
            )
        results["Chemical_Class"] = [classify_compound(m) for m in mol_list]

        # ── Generate molecule structure images (first 8) ──
        mol_images = []
        if smiles_col and mol_list:
            for i, mol in enumerate(mol_list[:50]):
                img_b64 = mol_to_b64(mol)
                if img_b64:
                    compound_id = str(df.iloc[i].get("Compound_ID", f"Cmp {i+1}"))
                    mol_images.append({"id": compound_id, "image": img_b64})
        graphs["mol_images"] = mol_images
        graphs["total_molecules"] = len(mol_list)

        # Save results
        result_path = sess_dir / "predictions.csv"
        results.to_csv(result_path, index=False)

        # ── Build prediction summary for AI explainer ──
        prediction_summary = {
            "task": [],
            "total_compounds": len(results),
            "activity_counts": {},
            "toxicity_counts": {},
            "top_features": [],
        }
        if predict_activity:
            prediction_summary["task"].append("activity")
            act_counts = results.get("Activity_Prediction", pd.Series()).value_counts().to_dict()
            prediction_summary["activity_counts"] = {
                "active": int(act_counts.get(1, 0)),
                "inactive": int(act_counts.get(0, 0)),
            }
        if predict_toxicity:
            prediction_summary["task"].append("toxicity")
            tox_counts = results.get("Toxicity_Prediction", pd.Series()).value_counts().to_dict()
            prediction_summary["toxicity_counts"] = {
                "toxic": int(tox_counts.get(1, 0)),
                "safe": int(tox_counts.get(0, 0)),
            }
        prediction_summary["task"] = " and ".join(prediction_summary["task"]) or "activity and toxicity"

        # Get top features from the activity model if available
        if predict_activity:
            act_path = app.config["MODEL_FOLDER"] / f"activity_{selected_model}.pkl"
            if not act_path.exists():
                act_path = app.config["MODEL_FOLDER"] / "activity.pkl"
            if act_path.exists():
                act_model = joblib.load(act_path)
                try:
                    feature_names = act_model.feature_names_in_
                    importances = act_model.feature_importances_
                    top_idx = np.argsort(importances)[::-1][:5]
                    prediction_summary["top_features"] = [
                        {"feature": str(feature_names[i]), "importance": round(float(importances[i]), 4)}
                        for i in top_idx
                    ]
                except Exception:
                    pass

        # Store in session as JSON for the /explain endpoint
        import json as _json
        session["prediction_summary"] = _json.dumps(prediction_summary)

        # Preview table (first 20 rows)
        # Preview table — show all result columns
        preview_cols = [c for c in results.columns if c not in ("mol",)]
        preview = results[preview_cols].head(20).to_dict(orient="records")
        columns = list(results[preview_cols].columns)

        return render_template(
            "predict_result.html",
            graphs=graphs,
            preview=preview,
            columns=columns,
            total_rows=len(results),
            result_filename=result_path.name,
            session_id=session.get("session_id"),
            ai_available=ai_is_available(),
        )

    except Exception as e:
        flash(f"Error during prediction: {e}", "error")
        return redirect(url_for("predict"))


# ── PLANT PREDICT ROUTE ────────────────────────────────────────────────────

@app.route("/plant", methods=["GET", "POST"])
def plant():
    """
    GET:  Show the plant upload form (photo + name).
    POST: Search PubChem for the plant's compounds, predict activity & toxicity.
    """
    if request.method == "GET":
        available_models = list_available_models()
        has_models = len(available_models) > 0
        return render_template("plant.html", has_models=has_models,
                              available_models=available_models)

    plant_name = request.form.get("plant_name", "").strip()
    if not plant_name:
        flash("Please enter a plant name.", "error")
        return redirect(url_for("plant"))

    # Save uploaded photo (optional)
    photo_b64 = None
    photo_file = request.files.get("plant_photo")
    if photo_file and photo_file.filename:
        import base64 as _b64
        photo_b64 = _b64.b64encode(photo_file.read()).decode("utf-8")

    sess_dir = get_session_dir()

    try:
        import joblib

        # Search PubChem
        compounds = search_plant_compounds(plant_name)
        if not compounds:
            # Try alternative search
            compounds = search_by_species_and_activity(plant_name)

        if not compounds:
            flash(
                f"No compounds found for '{plant_name}' in PubChem. "
                "Try a different plant name (scientific name works best, e.g. 'Artemisia annua').",
                "error"
            )
            return redirect(url_for("plant"))

        # Convert to DataFrame and extract features
        import pandas as pd
        df = pd.DataFrame(compounds)
        smiles_list = df["smiles"].tolist()

        from extract_features import create_molecules, compute_all_rdkit_descriptors, compute_topological_indices
        mol_list = create_molecules(pd.Series(smiles_list))
        failed_count = sum(1 for m in mol_list if m is None)
        if failed_count:
            flash(
                f"⚠️ {failed_count} of {len(mol_list)} SMILES failed to parse and were dropped.",
                "error"
            )
        valid = [m is not None for m in mol_list]
        df = df[valid].reset_index(drop=True)
        mol_list = [m for m in mol_list if m is not None]

        if not mol_list:
            flash("None of the compounds could be parsed. Try a different plant.", "error")
            return redirect(url_for("plant"))

        desc_df = compute_all_rdkit_descriptors(mol_list)
        topo_df = compute_topological_indices(mol_list)
        X = pd.concat([desc_df, topo_df], axis=1)

        results = df.copy()
        graphs = {}

        # Generate molecule images (first 8)
        mol_images = []
        for i, mol in enumerate(mol_list[:50]):
            img_b64 = mol_to_b64(mol)
            if img_b64:
                mol_images.append({
                    "id": df.iloc[i].get("name", f"Cmp {i+1}"),
                    "image": img_b64,
                })
        graphs["total_molecules"] = len(mol_list)
        graphs["mol_images"] = mol_images

        # Get selected model name
        selected_model = request.form.get("model_name", "default").strip()
        if not selected_model:
            selected_model = "default"

        # Activity prediction
        act_path = app.config["MODEL_FOLDER"] / f"activity_{selected_model}.pkl"
        if not act_path.exists():
            act_path = app.config["MODEL_FOLDER"] / "activity.pkl"
        if act_path.exists():
            act_model = joblib.load(act_path)
            try:
                expected = act_model.feature_names_in_
                X_aligned = X.reindex(columns=expected, fill_value=0)
            except Exception:
                X_aligned = X
            results["Activity_Prediction"] = act_model.predict(X_aligned)
            try:
                results["Activity_Score"] = act_model.predict_proba(X_aligned)[:, 1].round(4)
            except Exception:
                pass

        # Toxicity prediction
        tox_path = app.config["MODEL_FOLDER"] / f"toxicity_{selected_model}.pkl"
        if not tox_path.exists():
            tox_path = app.config["MODEL_FOLDER"] / "toxicity.pkl"
        if tox_path.exists():
            tox_model = joblib.load(tox_path)
            try:
                expected = tox_model.feature_names_in_
                X_aligned = X.reindex(columns=expected, fill_value=0)
            except Exception:
                X_aligned = X
            results["Toxicity_Prediction"] = tox_model.predict(X_aligned)
            try:
                results["Toxicity_Score"] = tox_model.predict_proba(X_aligned)[:, 1].round(4)
            except Exception:
                pass

        # ── Add human-readable labels and chemical class ──
        if "Activity_Prediction" in results.columns:
            results["Activity_Label_Text"] = results["Activity_Prediction"].map(
                {1: "Active (inhibits OXA-23)", 0: "Inactive"}
            )
        if "Toxicity_Prediction" in results.columns:
            results["Toxicity_Label_Text"] = results["Toxicity_Prediction"].map(
                {1: "Toxic to humans", 0: "Safe"}
            )
        results["Chemical_Class"] = [classify_compound(m) for m in mol_list]

        # Build preview
        preview_cols = ["name", "smiles", "formula", "Chemical_Class"]
        for col in ["Activity_Prediction", "Activity_Score", "Toxicity_Prediction", "Toxicity_Score"]:
            if col in results.columns:
                preview_cols.append(col)

        preview = results[preview_cols].to_dict(orient="records")
        columns = list(preview_cols)

        # Build AI context
        prediction_summary = {
            "task": "plant compound activity and toxicity",
            "total_compounds": len(results),
            "activity_counts": {},
            "toxicity_counts": {},
            "top_features": [],
        }
        if "Activity_Prediction" in results.columns:
            act_counts = results["Activity_Prediction"].value_counts().to_dict()
            prediction_summary["activity_counts"] = {
                "active": int(act_counts.get(1, 0)),
                "inactive": int(act_counts.get(0, 0)),
            }
        if "Toxicity_Prediction" in results.columns:
            tox_counts = results["Toxicity_Prediction"].value_counts().to_dict()
            prediction_summary["toxicity_counts"] = {
                "toxic": int(tox_counts.get(1, 0)),
                "safe": int(tox_counts.get(0, 0)),
            }

        import json as _json
        session["prediction_summary"] = _json.dumps(prediction_summary)

        # Save results
        result_path = sess_dir / "plant_predictions.csv"
        results.to_csv(result_path, index=False)

        return render_template(
            "plant_result.html",
            plant_name=plant_name,
            photo_b64=photo_b64,
            compounds_found=len(results),
            graphs=graphs,
            preview=preview,
            columns=columns,
            result_filename=result_path.name,
            session_id=session.get("session_id"),
            ai_available=ai_is_available(),
        )

    except Exception as e:
        flash(f"Error: {e}", "error")
        return redirect(url_for("plant"))


# ── RANKING ROUTE — Top Compounds ─────────────────────────────────────────

@app.route("/ranking", methods=["GET", "POST"])
def ranking():
    """
    GET:  Show ranking upload form.
    POST: Predict all compounds, sort by combined score, show top 10.
    """
    if request.method == "GET":
        available_models = list_available_models()
        return render_template("ranking.html", available_models=available_models)

    files = request.files.getlist("datasets")
    valid_files = [f for f in files if f.filename and allowed_file(f.filename)]
    if not valid_files:
        flash("Please select at least one CSV or Excel file to upload.", "error")
        return redirect(url_for("ranking"))

    sess_dir = get_session_dir()

    try:
        import joblib

        # Merge all uploaded CSVs with source tracking
        all_dfs = []
        for f in valid_files:
            fname = secure_filename(f.filename)
            upload_path = sess_dir / fname
            f.save(str(upload_path))
            df_part = pd.read_csv(upload_path) if upload_path.suffix == ".csv" else pd.read_excel(upload_path)
            try:
                smi_col = parse_smiles_column(df_part)
            except ValueError:
                flash(f"File '{f.filename}' has no SMILES column. Skipped.", "error")
                continue
            df_part["Source_File"] = f.filename  # track origin
            all_dfs.append(df_part)

        if not all_dfs:
            flash("No valid files with SMILES columns found.", "error")
            return redirect(url_for("ranking"))

        df = pd.concat(all_dfs, ignore_index=True)
        n_before = len(df)

        # Deduplicate: keep first occurrence of each SMILES
        try:
            smiles_col = parse_smiles_column(df)
        except ValueError:
            flash("Could not find SMILES column in merged data.", "error")
            return redirect(url_for("ranking"))

        dupes = df[smiles_col].duplicated()
        if dupes.any():
            dup_count = dupes.sum()
            df = df.drop_duplicates(subset=[smiles_col], keep="first").reset_index(drop=True)
            flash(f"ℹ️ Merged {len(valid_files)} files ({n_before} compounds). Removed {dup_count} duplicate SMILES — kept first occurrence.", "info")
        else:
            flash(f"ℹ️ Merged {len(valid_files)} files: {n_before} total compounds, no duplicates found.", "info")

        try:
            smiles_col = parse_smiles_column(df)
        except ValueError:
            smiles_col = None

        if not smiles_col:
            flash("Could not find a SMILES column in your file.", "error")
            return redirect(url_for("ranking"))

        mol_list = create_molecules(df[smiles_col])
        failed = sum(1 for m in mol_list if m is None)
        if failed:
            flash(f"⚠️ {failed} SMILES failed to parse and were dropped.", "error")
        valid = [m is not None for m in mol_list]
        if not all(valid):
            df = df[valid].reset_index(drop=True)
            mol_list = [m for m in mol_list if m is not None]

        desc_df = compute_all_rdkit_descriptors(mol_list)
        topo_df = compute_topological_indices(mol_list)
        X = pd.concat([desc_df, topo_df], axis=1)
        results = df.copy()

        selected_model = request.form.get("model_name", "default").strip() or "default"
        tasks_found = []

        # Activity prediction
        act_path = app.config["MODEL_FOLDER"] / f"activity_{selected_model}.pkl"
        if not act_path.exists():
            act_path = app.config["MODEL_FOLDER"] / "activity.pkl"
        if act_path.exists():
            act_model = joblib.load(act_path)
            try:
                Xa = X.reindex(columns=act_model.feature_names_in_, fill_value=0)
            except Exception:
                Xa = X
            results["Activity_Prediction"] = act_model.predict(Xa)
            try:
                results["Activity_Score"] = act_model.predict_proba(Xa)[:, 1].round(4)
            except Exception:
                pass
            tasks_found.append("activity")

        # Toxicity prediction
        tox_path = app.config["MODEL_FOLDER"] / f"toxicity_{selected_model}.pkl"
        if not tox_path.exists():
            tox_path = app.config["MODEL_FOLDER"] / "toxicity.pkl"
        if tox_path.exists():
            tox_model = joblib.load(tox_path)
            try:
                Xt = X.reindex(columns=tox_model.feature_names_in_, fill_value=0)
            except Exception:
                Xt = X
            results["Toxicity_Prediction"] = tox_model.predict(Xt)
            try:
                results["Toxicity_Score"] = tox_model.predict_proba(Xt)[:, 1].round(4)
            except Exception:
                pass
            tasks_found.append("toxicity")

        if not tasks_found:
            flash("No trained models found for the selected name.", "error")
            return redirect(url_for("ranking"))

        # Combined score: Activity - Toxicity (high activity + low toxicity = best)
        if "Activity_Score" in results.columns and "Toxicity_Score" in results.columns:
            results["Combined_Score"] = (results["Activity_Score"] - results["Toxicity_Score"]).round(4)
            sort_col = "Combined_Score"
        elif "Activity_Score" in results.columns:
            results["Combined_Score"] = results["Activity_Score"]
            sort_col = "Combined_Score"
        else:
            results["Combined_Score"] = 1.0 - results["Toxicity_Score"]
            sort_col = "Combined_Score"

        # Sort and take top 15
        results = results.sort_values(sort_col, ascending=False).head(15).reset_index(drop=True)

        # Add chemical class and labels
        mol_list_ranked = create_molecules(pd.Series(results[smiles_col].tolist()))
        results["Chemical_Class"] = [classify_compound(m) for m in mol_list_ranked]
        if "Activity_Prediction" in results.columns:
            results["Activity_Label_Text"] = results["Activity_Prediction"].map(
                {1: "Active (inhibits OXA-23)", 0: "Inactive"})
        if "Toxicity_Prediction" in results.columns:
            results["Toxicity_Label_Text"] = results["Toxicity_Prediction"].map(
                {1: "Toxic to humans", 0: "Safe"})

        # Generate molecule images for top 10
        mol_images = []
        for i, mol in enumerate(mol_list_ranked[:10]):
            img_b64 = mol_to_b64(mol)
            if img_b64:
                cid = str(results.iloc[i].get("Compound_ID", f"#{i+1}"))
                mol_images.append({"id": cid, "image": img_b64})

        preview_cols = ["Compound_ID", smiles_col, "Chemical_Class", "Source_File"]
        for c in ["Activity_Prediction", "Activity_Score", "Toxicity_Prediction", "Toxicity_Score", "Combined_Score"]:
            if c in results.columns:
                preview_cols.append(c)
        preview = results[preview_cols].head(15).to_dict(orient="records")
        columns = list(preview_cols)

        result_path = sess_dir / "ranking.csv"
        results.to_csv(result_path, index=False)

        return render_template(
            "ranking_result.html",
            preview=preview, columns=columns,
            mol_images=mol_images,
            model_name=selected_model,
            tasks=" + ".join(tasks_found),
            result_filename=result_path.name,
            session_id=session.get("session_id"),
        )

    except Exception as e:
        flash(f"Error: {e}", "error")
        return redirect(url_for("ranking"))


# ── SETTINGS ROUTE — Manage Trained Models ─────────────────────────────────

@app.route("/settings")
def settings():
    """Show all trained models with option to delete."""
    models = list_available_models()
    # Get file sizes
    model_info = {}
    for name, paths in models.items():
        info = {"name": name, "tasks": {}}
        for task, path_str in paths.items():
            p = Path(path_str)
            size_kb = p.stat().st_size / 1024 if p.exists() else 0
            info["tasks"][task] = {"path": path_str, "size_kb": round(size_kb, 1)}
        model_info[name] = info
    return render_template("settings.html", models=model_info)


@app.route("/delete/<model_name>", methods=["POST"])
def delete_model(model_name):
    """Delete both activity and toxicity models for a given name."""
    # Protect default and legacy models
    protected = {"default", "legacy"}
    if model_name.lower() in protected:
        flash(f"Cannot delete the '{model_name}' model. It is protected.", "error")
        return redirect(url_for("settings"))

    model_dir = app.config["MODEL_FOLDER"]
    deleted = []
    for prefix in ("activity_", "toxicity_"):
        path = model_dir / f"{prefix}{model_name}.pkl"
        if path.exists():
            path.unlink()
            deleted.append(path.name)
    if deleted:
        flash(f"Deleted: {', '.join(deleted)}", "success")
    else:
        flash(f"No models found for '{model_name}'.", "error")
    return redirect(url_for("settings"))


# ── AI EXPLAIN ENDPOINT (SSE Streaming) ────────────────────────────────────

@app.route("/explain", methods=["GET"])
def explain():
    """
    Stream an AI-generated explanation of the last prediction results.
    Uses Server-Sent Events for real-time streaming.
    """
    import json as _json

    summary_json = session.get("prediction_summary")
    if not summary_json:
        return jsonify({"error": "No prediction results found. Run a prediction first."}), 400

    prediction_summary = _json.loads(summary_json)

    def generate():
        for event in explain_stream(prediction_summary):
            yield event

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── DOWNLOAD ROUTE ──────────────────────────────────────────────────────────

@app.route("/download/<session_id>/<filename>")
def download(session_id, filename):
    """Serve a result file for download."""
    path = app.config["SESSION_FOLDER"] / session_id / secure_filename(filename)
    if not path.exists():
        flash("File not found. It may have been cleaned up.", "error")
        return redirect(url_for("index"))
    return send_file(path, as_attachment=True, download_name=filename)


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("  🧪  Drug AI — Web Interface")
    print("  Open:  http://localhost:5000")
    print("=" * 55 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=True)
