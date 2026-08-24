"""
app.py — Flask Web Application
===============================
Web interface for the BotanicalTox ML pipeline. Students can:
  - Upload training data (CSV) → train models → view graphs & metrics
  - Upload prediction data (CSV) → get predictions → download results

Run:
    python3 app.py
    Then open http://localhost:5001 in a browser.
"""

import io
import os
import json
import uuid
import functools
from pathlib import Path
from datetime import datetime

# ── Cap BLAS/OpenMP threads BEFORE numpy/rdkit are imported ────────────────
# RDKit + numpy are not thread/fork-safe under gunicorn's workers. Letting
# them spawn many threads inside forked workers causes random crashes (e.g.
# "An = numpy.dot(A, Bn)" aborts) and slows down single training requests.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

# Load .env file if present (python-dotenv is optional — falls back to env vars)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

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
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)

# ── Import our ML modules ───────────────────────────────────────────────────
from rdkit import Chem
from rdkit.Chem import Draw
from extract_features import (
    parse_smiles_column,
    create_molecules,
    compute_all_rdkit_descriptors,
    compute_topological_indices,
    clean_descriptor_matrix,
    scaffold_id,
)
from train_common import (
    load_features_and_labels,
    train_random_forest,
    evaluate_model,
    save_model,
    save_model_with_metadata,
    align_features_for_model,
    calibrated_estimator,
)
from ai_explainer import is_available as ai_is_available, explain_stream
from plant_predict import search_plant_compounds, search_by_species_and_activity

# ── Import database module ──────────────────────────────────────────────────
from database import init_db, close_db, create_default_admin, User

# ── App Setup ───────────────────────────────────────────────────────────────

app = Flask(__name__, instance_relative_config=True)
app.secret_key = os.environ.get("SECRET_KEY", "botanicaltox-2026-secret-key-change-in-production")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB max upload
app.config["UPLOAD_FOLDER"] = Path(__file__).resolve().parent / "uploads"
app.config["MODEL_FOLDER"] = Path(__file__).resolve().parent / "models"
app.config["OUTPUT_FOLDER"] = Path(__file__).resolve().parent / "outputs"
app.config["SESSION_FOLDER"] = Path(__file__).resolve().parent / "sessions"
app.config["AVATAR_FOLDER"] = Path(app.instance_path) / "avatars"

for folder in ["UPLOAD_FOLDER", "MODEL_FOLDER", "OUTPUT_FOLDER", "SESSION_FOLDER", "AVATAR_FOLDER"]:
    app.config[folder].mkdir(parents=True, exist_ok=True)

# ── Flask-Login Setup ───────────────────────────────────────────────────────
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "info"

@login_manager.user_loader
def load_user(user_id):
    return User.get(int(user_id))

# Initialize database and create default admin
with app.app_context():
    init_db()
    create_default_admin()

# Register database teardown
app.teardown_appcontext(close_db)

@app.context_processor
def inject_global_template_vars():
    """Make admin-facing counts available to every template."""
    pending_count = None
    try:
        if current_user.is_authenticated and current_user.role == "admin":
            pending_count = User.count_pending()
    except Exception:
        pending_count = None
    return {"pending_count": pending_count}

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


# ── Model ownership tracking ────────────────────────────────────────────────

MODEL_OWNERS_FILE = "owners.json"
PROTECTED_MODELS = {"default", "legacy"}


def get_model_owners() -> dict:
    """Load {model_name: owner_username} from models/owners.json."""
    path = app.config["MODEL_FOLDER"] / MODEL_OWNERS_FILE
    if not path.exists():
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_model_owner(model_name: str, owner: str):
    """Record who owns a trained model in models/owners.json."""
    path = app.config["MODEL_FOLDER"] / MODEL_OWNERS_FILE
    owners = get_model_owners()
    owners[model_name] = owner
    with open(path, "w") as f:
        json.dump(owners, f, indent=2)


def model_owner(model_name: str) -> str:
    """Return the owner username for a model.

    Models without recorded ownership are attributed to 'admin'
    (pre-existing / starter models), so regular users can't delete them.
    """
    owners = get_model_owners()
    return owners.get(model_name, "admin")


def can_delete_model(model_name: str, user) -> bool:
    """Whether a user may delete a given model.

    Admins can delete anything. Regular users can only delete their own,
    non-protected models.
    """
    if user.role == "admin":
        return True
    if model_name.lower() in PROTECTED_MODELS:
        return False
    return model_owner(model_name) == user.username


def canonicalize_smiles(smi: str) -> str | None:
    """Return the RDKit-canonical form of a SMILES string, or None if invalid.

    Canonicalization lets us detect structurally identical molecules even when
    they were written with different (non-identical) SMILES strings.
    """
    try:
        mol = Chem.MolFromSmiles(str(smi))
        return Chem.MolToSmiles(mol) if mol is not None else None
    except Exception:
        return None


def dedup_by_canonical_smiles(df: pd.DataFrame, smiles_col: str, keep: str = "first") -> tuple[pd.DataFrame, int]:
    """Deduplicate rows whose SMILES are structurally identical.

    Compares RDKit-canonical SMILES rather than raw text, so equivalent
    representations of the same molecule count as duplicates. Rows with
    unparseable SMILES are kept here (they are reported/dropped later by
    create_molecules). Returns (deduplicated_df, number_of_duplicates_removed).
    """
    canon = df[smiles_col].map(canonicalize_smiles)
    dupes = canon.duplicated(keep=keep) & canon.notna()
    out = df[~dupes].reset_index(drop=True)
    return out, int(dupes.sum())


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
#  AUTH ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

def admin_required(f):
    """Decorator — restrict a route to admin users."""
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if current_user.role != "admin":
            flash("You do not have permission to access this page.", "error")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    """User login page."""
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Please enter both username and password.", "error")
            return render_template("login.html")

        user = User.get_by_username(username)
        if user and user.check_password(password):
            if not user.approved:
                flash(
                    "Your account is pending admin approval. "
                    "You will be able to log in once an administrator approves your registration.",
                    "info"
                )
                return render_template("login.html")
            login_user(user)
            flash(f"Welcome back, {username}!", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("index"))
        else:
            flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """User registration page. New accounts require admin approval."""
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if not username or not password:
            flash("Please enter both username and password.", "error")
            return render_template("register.html")

        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("register.html")

        try:
            # Self-registered users are created as pending (approved=False)
            user = User.create(username, password, role="user", approved=False)
            flash(
                "Registration submitted! An administrator must approve your account "
                "before you can log in.",
                "success"
            )
            return redirect(url_for("login"))
        except ValueError as e:
            flash(str(e), "error")

    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    """Log out the current user."""
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ── ADMIN — USER MANAGEMENT ─────────────────────────────────────────────────

@app.route("/admin/users")
@admin_required
def admin_users():
    """Admin page: list all users and manage approvals."""
    users = User.list_all()
    pending_count = User.count_pending()
    return render_template(
        "admin_users.html",
        users=users,
        pending_count=pending_count,
        current_uid=current_user.id,
    )


@app.route("/admin/users/<int:user_id>/approve", methods=["POST"])
@admin_required
def admin_approve_user(user_id):
    """Approve a pending user registration."""
    if user_id == current_user.id:
        flash("You cannot approve your own account.", "error")
        return redirect(url_for("admin_users"))
    User.set_approved(user_id, True)
    flash(f"User #{user_id} approved.", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:user_id>/reject", methods=["POST"])
@admin_required
def admin_reject_user(user_id):
    """Reject / suspend a user (sets approved=False)."""
    if user_id == current_user.id:
        flash("You cannot reject your own account.", "error")
        return redirect(url_for("admin_users"))
    User.set_approved(user_id, False)
    flash(f"User #{user_id} rejected.", "info")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    """Delete a user account."""
    if user_id == current_user.id:
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("admin_users"))
    User.delete(user_id)
    flash(f"User #{user_id} deleted.", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:user_id>/team", methods=["POST"])
@admin_required
def admin_toggle_team(user_id):
    """Toggle whether a user is shown on the public Team page."""
    if user_id == current_user.id:
        flash("You cannot change your own team membership.", "error")
        return redirect(url_for("admin_users"))
    user = User.get(user_id)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("admin_users"))
    User.set_team(user_id, not user.is_team)
    action = "added to" if not user.is_team else "removed from"
    flash(f"'{user.username}' {action} the team.", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:user_id>/role/<role>", methods=["POST"])
@admin_required
def admin_set_role(user_id, role):
    """Promote a user to admin, or demote an admin back to user.

    Admins can approve/reject registered users and manage the site.
    """
    if role not in ("admin", "user"):
        flash("Invalid role.", "error")
        return redirect(url_for("admin_users"))
    if user_id == current_user.id:
        flash("You cannot change your own role.", "error")
        return redirect(url_for("admin_users"))

    target = User.get(user_id)
    if not target:
        flash("User not found.", "error")
        return redirect(url_for("admin_users"))

    if target.role == role:
        flash(f"'{target.username}' already has the '{role}' role.", "info")
        return redirect(url_for("admin_users"))

    # Prevent demoting the last remaining admin (avoid lockout)
    if target.role == "admin" and role == "user" and User.count_admins() <= 1:
        flash("Cannot demote the last remaining admin.", "error")
        return redirect(url_for("admin_users"))

    User.set_role(user_id, role)
    action = "promoted to admin" if role == "admin" else "demoted to user"
    flash(f"'{target.username}' was {action}.", "success")
    return redirect(url_for("admin_users"))


# ── TEAM PAGE & PROFILES ───────────────────────────────────────────────────

@app.route("/team")
def team():
    """Public page showing the student team members and their profiles."""
    members = User.list_team()
    return render_template("team.html", members=members)


@app.route("/profile", methods=["POST"])
@login_required
def update_profile():
    """Update the current user's profile (name, course, bio, avatar)."""
    full_name = request.form.get("full_name", "").strip()
    course = request.form.get("course", "").strip()
    bio = request.form.get("bio", "").strip()

    avatar_file = request.files.get("avatar")
    avatar_name = current_user.avatar  # keep existing by default

    if avatar_file and avatar_file.filename:
        if not allowed_image(avatar_file.filename):
            flash("Please upload an image file (PNG, JPG, GIF, or WebP).", "error")
            return redirect(url_for("settings"))
        # Secure filename + save as <user_id><ext> in the avatars folder
        ext = Path(avatar_file.filename).suffix.lower()
        avatar_name = f"user{current_user.id}{ext}"
        avatar_path = app.config["AVATAR_FOLDER"] / avatar_name
        # Remove any old avatar with a different extension
        for old in app.config["AVATAR_FOLDER"].glob(f"user{current_user.id}.*"):
            if old.name != avatar_name:
                try:
                    old.unlink()
                except OSError:
                    pass
        avatar_file.save(str(avatar_path))

    User.update_profile(current_user.id, full_name=full_name, course=course,
                        bio=bio, avatar=avatar_name)
    flash("Profile updated successfully!", "success")
    return redirect(url_for("settings"))


@app.route("/change-password", methods=["POST"])
@login_required
def change_password():
    """Let the current user change their own password."""
    current = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")

    if not current or not new_password:
        flash("Please fill in all password fields.", "error")
        return redirect(url_for("settings"))

    if new_password != confirm:
        flash("New passwords do not match.", "error")
        return redirect(url_for("settings"))

    if len(new_password) < 6:
        flash("New password must be at least 6 characters.", "error")
        return redirect(url_for("settings"))

    # Verify the current password before changing it
    user = User.get_by_username(current_user.username)
    if not user or not user.check_password(current):
        flash("Your current password is incorrect.", "error")
        return redirect(url_for("settings"))

    User.change_password(current_user.id, new_password)
    flash("Password changed successfully!", "success")
    return redirect(url_for("settings"))


@app.route("/avatar/<int:user_id>")
def avatar(user_id):
    """Serve a user's avatar image, or a 204 if none exists."""
    user = User.get(user_id)
    if not user or not user.avatar:
        return "", 204
    path = app.config["AVATAR_FOLDER"] / user.avatar
    if not path.exists():
        return "", 204
    return send_file(path)


def allowed_image(filename: str) -> bool:
    """Check if a filename has an allowed image extension."""
    return "." in filename and \
        filename.rsplit(".", 1)[1].lower() in {"png", "jpg", "jpeg", "gif", "webp"}


# ═══════════════════════════════════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    """Landing page — public. No login required to view."""
    return render_template("index.html")


# ── TRAIN ROUTE ─────────────────────────────────────────────────────────────

@app.route("/train", methods=["GET", "POST"])
@login_required
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
            # Deduplicate: keep first occurrence (structure-based)
            df, canon_dup_count = dedup_by_canonical_smiles(df, smiles_col)
            if canon_dup_count:
                flash(
                    f"ℹ️ Removed {canon_dup_count} additional structurally-identical duplicate(s) after label-conflict check.",
                    "info"
                )

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

        # ── Robust cleaning (notebook-inspired): median imputation, keep
        #    stable columns, and reuse these at prediction time ──
        feat_all = pd.concat([desc_df, topo_df], axis=1)
        feat_clean, descriptor_cols, impute_medians = clean_descriptor_matrix(
            feat_all, feat_all.columns
        )

        # Combine — keep label columns in the saved file for load_features_and_labels
        meta_cols = {"Compound_ID", "Name", "Smiles", "mol"}
        keep_cols = [c for c in df.columns if c not in meta_cols]
        feats = pd.concat(
            [df[keep_cols].reset_index(drop=True), feat_clean], axis=1
        )

        # Save features (includes label columns for load_features_and_labels)
        features_path = sess_dir / "features.csv"
        feats.to_csv(features_path, index=False)

        # ── Scaffold groups for leakage-free splitting ──
        scaffold_groups = df[smiles_col].apply(scaffold_id).reset_index(drop=True)
        if scaffold_groups.isna().any():
            scaffold_groups = None  # can't group reliably → fall back to random split

        # 2. Train selected tasks
        model_name = request.form.get("model_name", "default").strip().lower()
        model_name = "".join(c for c in model_name if c.isalnum() or c in "_-") or "default"

        # Validate label columns exist in the uploaded CSV before training
        available_cols = set(df.columns)
        missing_labels = []
        if train_activity:
            act_label = request.form.get("label_col", "").strip() or "Activity_Label"
            if act_label not in available_cols:
                missing_labels.append(f"Activity_Label (needed for activity task)")
        if train_toxicity:
            tox_label = request.form.get("label_col", "").strip() or "Toxicity_Label"
            if tox_label not in available_cols:
                missing_labels.append(f"Toxicity_Label (needed for toxicity task)")
        if missing_labels:
            flash(
                f"Missing label column(s): {', '.join(missing_labels)}. "
                f"Available columns: {', '.join(sorted(available_cols))}",
                "error"
            )
            return redirect(url_for("train"))

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
        export_files = {}  # task_key -> {predictions, metrics} CSV names
        combined_task_names = []
        overwritten = False

        for task_key, label_col, display_name in tasks_to_train:
            X, y = load_features_and_labels(str(features_path), label_col)
            model, best_params, splits = train_random_forest(
                X, y, random_state=42, tune=tune, n_iter=30 if tune else 0,
                groups=scaffold_groups,
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

            # ── Export test-set predictions + metrics CSV (notebook 1.6a/2.6a) ──
            # Mirror the students' Colab notebook: save per-compound held-out test
            # predictions and a one-row metrics summary so Chapter IV has the
            # actual numbers to analyze, not just the on-screen graphs.
            y_test_pred = model.predict(X_test)
            y_test_proba = model.predict_proba(X_test)[:, 1]
            test_ids = (
                df.loc[X_test.index, "Compound_ID"].values
                if "Compound_ID" in df.columns
                else [f"row_{i}" for i in X_test.index]
            )
            test_smiles = (
                df.loc[X_test.index, smiles_col].values
                if smiles_col in df.columns
                else [""] * len(X_test)
            )
            pd.DataFrame({
                "Compound_ID": test_ids,
                "Smiles": test_smiles,
                "True_Label": y_test.values,
                "Predicted_Label": y_test_pred,
                "Predicted_Proba": y_test_proba.round(4),
            }).to_csv(sess_dir / f"{task_key}_test_predictions.csv", index=False)
            pd.DataFrame([dict(metrics["test"])]).to_csv(
                sess_dir / f"{task_key}_test_metrics.csv", index=False
            )
            export_files[task_key] = {
                "predictions": f"{task_key}_test_predictions.csv",
                "metrics": f"{task_key}_test_metrics.csv",
            }

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
            importances = calibrated_estimator(model).feature_importances_
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
            topo_indices = ["WienerIndex", "Zagreb_M1", "Zagreb_M2"]
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

            # Save model (with training-time cleaning metadata)
            model_path = sess_dir / f"{task_key}_model.pkl"
            save_model_with_metadata(model, str(model_path), descriptor_cols, impute_medians)
            shared_path = app.config["MODEL_FOLDER"] / f"{task_key}_{model_name}.pkl"
            if shared_path.exists():
                overwritten = True
            save_model_with_metadata(model, str(shared_path), descriptor_cols, impute_medians)
            # Record who owns this shared model
            save_model_owner(model_name, current_user.username)

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
            n_features=len(descriptor_cols),
            tune=tune,
            model_name=model_name,
            dataset_preview=dataset_preview,
            dataset_columns=dataset_columns,
            overwritten=overwritten,
            export_files=export_files,
            session_id=session.get("session_id"),
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
@login_required
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
            df, dup_count = dedup_by_canonical_smiles(df, smiles_col)
            if dup_count:
                flash(
                    f"ℹ️ Found {dup_count} duplicate SMILES in prediction data (structure-based) — kept first occurrence.",
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
                X_aligned = align_features_for_model(X, act_model)
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
                X_aligned = align_features_for_model(X, tox_model)
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
                    feature_names = getattr(act_model, "_descriptor_cols", None) or act_model.feature_names_in_
                    importances = calibrated_estimator(act_model).feature_importances_
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
@login_required
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
            X_aligned = align_features_for_model(X, act_model)
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
            X_aligned = align_features_for_model(X, tox_model)
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
@login_required
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

        # Check if user wants deduplication (default: True)
        deduplicate = request.form.get("deduplicate", "on") == "on"

        # Deduplicate: keep first occurrence of each SMILES (if enabled)
        try:
            smiles_col = parse_smiles_column(df)
        except ValueError:
            flash("Could not find SMILES column in merged data.", "error")
            return redirect(url_for("ranking"))

        if deduplicate:
            dupes = df[smiles_col].duplicated()
            raw_dup_count = dupes.sum()
            df, dup_count = dedup_by_canonical_smiles(df, smiles_col)
            if dup_count:
                df = df.drop_duplicates(subset=[smiles_col], keep="first").reset_index(drop=True)
                flash(f"ℹ️ Merged {len(valid_files)} files ({n_before} compounds). Removed {dup_count} duplicate SMILES (structure-based) — kept first occurrence.", "info")
            else:
                flash(f"ℹ️ Merged {len(valid_files)} files: {n_before} total compounds, no duplicates found.", "info")
        else:
            flash(f"ℹ️ Merged {len(valid_files)} files: {n_before} total compounds (duplicates kept).", "info")

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
            Xa = align_features_for_model(X, act_model)
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
            Xt = align_features_for_model(X, tox_model)
            results["Toxicity_Prediction"] = tox_model.predict(Xt)
            try:
                results["Toxicity_Score"] = tox_model.predict_proba(Xt)[:, 1].round(4)
            except Exception:
                pass
            tasks_found.append("toxicity")

        if not tasks_found:
            flash("No trained models found for the selected name.", "error")
            return redirect(url_for("ranking"))

        # Priority score (notebook-style): both active AND non-toxic to rank high
        #   Safety  = 1 − Toxicity
        #   Priority = Activity × Safety
        if "Activity_Score" in results.columns and "Toxicity_Score" in results.columns:
            results["Safety_Score"] = (1.0 - results["Toxicity_Score"]).round(4)
            results["Priority_Score"] = (results["Activity_Score"] * results["Safety_Score"]).round(4)
            sort_col = "Priority_Score"
        elif "Activity_Score" in results.columns:
            results["Priority_Score"] = results["Activity_Score"].round(4)
            sort_col = "Priority_Score"
        else:
            results["Safety_Score"] = (1.0 - results["Toxicity_Score"]).round(4)
            results["Priority_Score"] = results["Safety_Score"].round(4)
            sort_col = "Priority_Score"

        # Sort by priority score
        results = results.sort_values(sort_col, ascending=False).reset_index(drop=True)

        # Save FULL results to CSV (before taking top 15)
        result_path = sess_dir / "ranking.csv"
        results.to_csv(result_path, index=False)

        # Take top 15 for display
        results_display = results.head(15).reset_index(drop=True)

        # Add chemical class and labels
        mol_list_ranked = create_molecules(pd.Series(results_display[smiles_col].tolist()))
        results_display["Chemical_Class"] = [classify_compound(m) for m in mol_list_ranked]
        if "Activity_Prediction" in results_display.columns:
            results_display["Activity_Label_Text"] = results_display["Activity_Prediction"].map(
                {1: "Active (inhibits OXA-23)", 0: "Inactive"})
        if "Toxicity_Prediction" in results_display.columns:
            results_display["Toxicity_Label_Text"] = results_display["Toxicity_Prediction"].map(
                {1: "Toxic to humans", 0: "Safe"})

        # Generate molecule images for top 10
        mol_images = []
        for i, mol in enumerate(mol_list_ranked[:10]):
            img_b64 = mol_to_b64(mol)
            if img_b64:
                cid = str(results_display.iloc[i].get("Compound_ID", f"#{i+1}"))
                mol_images.append({"id": cid, "image": img_b64})

        preview_cols = ["Compound_ID", smiles_col, "Chemical_Class", "Source_File"]
        for c in ["Activity_Prediction", "Activity_Score", "Toxicity_Prediction", "Toxicity_Score",
                  "Safety_Score", "Priority_Score"]:
            if c in results_display.columns:
                preview_cols.append(c)
        preview = results_display[preview_cols].to_dict(orient="records")
        columns = list(preview_cols)

        return render_template(
            "ranking_result.html",
            preview=preview, columns=columns,
            mol_images=mol_images,
            model_name=selected_model,
            tasks=" + ".join(tasks_found),
            result_filename=result_path.name,
            session_id=session.get("session_id"),
            deduplicated=deduplicate,
        )

    except Exception as e:
        flash(f"Error: {e}", "error")
        return redirect(url_for("ranking"))


# ── SETTINGS ROUTE — Manage Trained Models ─────────────────────────────────

@app.route("/settings")
@login_required
def settings():
    """Show all trained models with option to delete."""
    models = list_available_models()
    # Get file sizes + ownership info
    model_info = {}
    for name, paths in models.items():
        info = {"name": name, "tasks": {}, "owner": model_owner(name),
                "can_delete": can_delete_model(name, current_user),
                "protected": name.lower() in PROTECTED_MODELS}
        for task, path_str in paths.items():
            p = Path(path_str)
            size_kb = p.stat().st_size / 1024 if p.exists() else 0
            info["tasks"][task] = {"path": path_str, "size_kb": round(size_kb, 1)}
        model_info[name] = info
    return render_template("settings.html", models=model_info)


@app.route("/delete/<model_name>", methods=["POST"])
@login_required
def delete_model(model_name):
    """Delete both activity and toxicity models for a given name.

    Only the model's owner or an admin may delete it.
    """
    # Permission check (owner or admin; protected models are admin-only)
    if not can_delete_model(model_name, current_user):
        if model_name.lower() in PROTECTED_MODELS:
            flash(f"Cannot delete the '{model_name}' model. It is protected.", "error")
        else:
            flash("You can only delete your own trained models.", "error")
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
        # Clean up ownership record
        owners = get_model_owners()
        if model_name in owners:
            del owners[model_name]
            with open(model_dir / MODEL_OWNERS_FILE, "w") as f:
                json.dump(owners, f, indent=2)
    else:
        flash(f"No models found for '{model_name}'.", "error")
    return redirect(url_for("settings"))


# ── AI EXPLAIN ENDPOINT (SSE Streaming) ────────────────────────────────────

@app.route("/explain", methods=["GET"])
@login_required
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
@login_required
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
    print("  🌿  BotanicalTox — Web Interface")
    print("  Open:  http://localhost:5001")
    print("=" * 55 + "\n")
    app.run(host="0.0.0.0", port=5001, debug=True)
