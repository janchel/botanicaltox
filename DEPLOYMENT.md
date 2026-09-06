╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║     CRABLOX — DEPLOYMENT GUIDE                                              ║
║     GitHub Push & Fresh Machine Setup                                        ║
║     August 2026                                                              ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝


═══════════════════════════════════════════════════════════════════════════════
1. FILES TO PUSH TO GITHUB
═══════════════════════════════════════════════════════════════════════════════

1.1  INCLUDE — These files go to GitHub
─────────────────────────────────────────

    Core Application:
      app.py                       Flask web server (main entry)
      database.py                  SQLite user database & auth helpers
      ai_explainer.py              AI explanation module
      extract_features.py          SMILES → RDKit descriptors
      train_common.py              Shared training / evaluation logic
      train_activity.py            CLI activity trainer
      train_toxicity.py            CLI toxicity trainer
      evaluate.py                  CLI model evaluation
      predict.py                   CLI prediction
      plant_predict.py             Plant compound lookup database
      requirements.txt             Python dependencies
      run.sh                       Launcher (uses venv automatically)
      README.md                    Project overview
      CHANGELOG_2026-08-16.md      Change log / tracing
      .env.example                 Template for environment configuration

    Templates (13 files):
      templates/base.html
      templates/index.html
      templates/login.html
      templates/register.html
      templates/admin_users.html
      templates/team.html
      templates/train.html
      templates/train_result.html
      templates/predict.html
      templates/predict_result.html
      templates/plant.html
      templates/plant_result.html
      templates/ranking.html
      templates/ranking_result.html
      templates/settings.html

    Datasets (sample files for testing & demo):
      datasets/medchem_training.csv       91 compounds (training)
      datasets/medchem_prediction.csv     50 compounds (prediction)
      datasets/flavonoid_training.csv     30+12 compounds (training)
      datasets/flavonoid_prediction.csv   15 compounds (prediction)
      datasets/training_sample.csv        10 compounds (quick test)
      datasets/prediction_sample.csv      5 compounds (quick test)
      datasets/training_toxicity.csv      10 compounds (toxicity)

    Config:
      .env.example                 Template for AI API key
      .gitignore                   Ignore rules

    Documentation:
      GUIDE.md                     Technical installation / production guide
      USER_GUIDE.md                Student-facing user manual
      DEPLOYMENT.md                This file

    Models (starter models):
      models/README.md             (Create: "Place .pkl files here")
      Optional: keep 1-2 starter .pkl files for demo


1.2  EXCLUDE — Do NOT push these to GitHub
────────────────────────────────────────────

    Secrets:
      .env                         Contains API keys & secret key — NEVER commit

    User Database:
      instance/                    Flask instance folder (SQLite users.db)

    Virtual Environment:
      venv/                        Local Python environment

    Runtime / Cache:
      __pycache__/                 Python bytecode cache
      *.pyc                        Compiled Python files
      sessions/                    User session data (auto-cleaned, temp)
      uploads/                     Uploaded files (temp)

    Generated / Old:
      outputs/                     Generated graphs and reports
      datasets/features.csv        Auto-generated descriptors
      datasets/medchem_features.csv Auto-generated descriptors
      datasets/dup_test.csv        Test artifact
      models/*.pkl                 Too many test models — keep 0-2 max
      models/owners.json           Runtime-generated model ownership map
                                    (rebuilt automatically when models train)

    OS Files:
      ._*                          macOS resource forks
      .DS_Store                    macOS folder metadata


1.3  Recommended .gitignore
─────────────────────────────

    # Secrets
    .env
    .env.*
    !.env.example

    # Python
    __pycache__/
    *.pyc
    *.pyo

    # Virtual environment
    venv/
    .venv/

    # Flask instance folder (contains SQLite user database)
    instance/

    # Runtime
    sessions/
    uploads/

    # Generated output
    outputs/
    datasets/features.csv
    datasets/medchem_features.csv

    # Too many models — keep only starter ones
    models/*.pkl
    !models/activity_legacy.pkl
    !models/toxicity_legacy.pkl

    # OS
    ._*
    .DS_Store
    server.log
    server.pid


═══════════════════════════════════════════════════════════════════════════════
2. TECH STACK (Install on New Machine)
═══════════════════════════════════════════════════════════════════════════════

2.1  System Requirements
──────────────────────────

    • OS:            Linux (Ubuntu 20.04+), macOS 12+, or Windows WSL2
    • Python:        3.10 or newer
    • RAM:           2 GB minimum, 4 GB recommended
    • Disk:          1 GB free (app + dependencies + datasets)
    • Network:       Port 5001 open for web access

2.2  Python Packages
──────────────────────

    All in requirements.txt:

    │ Package       │ Purpose                              │ Min Version     │
    │───────────────│──────────────────────────────────────│──────────────────│
    │ rdkit         │ Molecular descriptor calculation     │ 2026.03+ (conda)│
    │ pandas        │ CSV/data handling                    │ 2.0              │
    │ scikit-learn  │ Random Forest ML                     │ 1.3              │
    │ matplotlib    │ Graph generation                     │ 3.7              │
    │ seaborn       │ Confusion matrix heatmaps            │ 0.12             │
    │ numpy         │ Numerical computation                │ 1.24             │
    │ openpyxl      │ Excel file support                   │ 3.1              │
    │ joblib        │ Model save/load                      │ 1.3              │
    │ flask         │ Web framework                        │ 3.0              │
    │ flask-login   │ User authentication & sessions       │ 0.6              │
    │ gunicorn      │ Production WSGI server               │ 22.0             │
    │ openai        │ AI explainer client                  │ 1.0              │

    ⚠️  CRITICAL: RDKit version matters!

        The app now requires RDKit 2026.03+ (217 molecular descriptors).
        The old pip package "rdkit-pypi" is stuck at 2022.09 (208 descriptors)
        and does NOT match the Colab notebook's descriptor set.

        USE CONDA/MINIFORGE (not pip) for RDKit:
            conda create -n crablox python=3.10 rdkit=2026.03 -c conda-forge

        If you use pip's rdkit-pypi, you get 208 descriptors and your
        ranking results will NOT match the notebook (Spearman ~0.86).
        With conda's RDKit 2026+, you get 217 descriptors (Spearman ~0.90).

2.3  Optional
───────────────

    │ Tool          │ Purpose                              │
    │───────────────│──────────────────────────────────────│
    │ nginx         │ Reverse proxy for production         │
    │ certbot       │ SSL certificates (Let's Encrypt)     │
    │ systemd       │ Auto-start on boot (Linux)           │


═══════════════════════════════════════════════════════════════════════════════
3. FRESH MACHINE SETUP — Step by Step
═══════════════════════════════════════════════════════════════════════════════

3.1  Clone the Repository
───────────────────────────

    git clone https://github.com/janchel/botanicaltox.git
    cd botanicaltox

3.2  Install Miniforge (conda) — RECOMMENDED
──────────────────────────────────────────────

    # Download and install Miniforge (lightweight conda)
    curl -L -O "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh"
    bash Miniforge3-Linux-x86_64.sh -b -p $HOME/miniforge3
    source $HOME/miniforge3/bin/activate

    # Create the crablox environment with RDKit 2026+
    conda create -n crablox python=3.10 rdkit=2026.03 -c conda-forge -y
    conda activate crablox

    # Install remaining dependencies via pip
    pip install -r requirements.txt

    ⚠️  DO NOT install rdkit-pypi via pip — it's stuck at 2022.09 (208 descriptors).
        The conda-forge rdkit package gives you 2026.03+ (217 descriptors),
        which matches the Colab notebook's descriptor set exactly.

3.3  Alternative: pip Virtual Environment (NOT RECOMMENDED)
────────────────────────────────────────────────────────────

    ⚠️  This gives you RDKit 2022.09 (208 descriptors), which does NOT
        match the Colab notebook. Use conda (section 3.2) instead.

    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    pip install "numpy<2"

3.4  Create Required Directories
──────────────────────────────────

    mkdir -p models uploads sessions outputs/datasets

    # models/ must exist (place .pkl files here)
    # uploads/ and sessions/ are auto-created at runtime
    # outputs/ for CLI-generated graphs and reports
    # instance/ is auto-created for the SQLite user database

3.5  Configure Security & AI Explanation
──────────────────────────────────────────

    cp .env.example .env
    nano .env

      # Required for production — generate a strong secret key:
      #   python -c "import secrets; print(secrets.token_hex(32))"
      SECRET_KEY=your-random-hex-string

      # Default admin credentials (only used on first run):
      ADMIN_USERNAME=admin
      ADMIN_PASSWORD=choose-a-strong-password

      # Optional: AI_API_KEY for AI explanations

    ⚠️  The app works without a .env file, but uses insecure defaults.
        The default admin is created as admin on first launch.

3.6  Start the Server
──────────────────────

    # Easiest — launcher detects conda env automatically:
    ./run.sh

    # The launcher prefers conda env (~/miniforge3/envs/crablox/)
    # over the pip venv. It prints the RDKit version on startup.

    # Development (single user):
    conda activate crablox
    python3 app.py

    # Or directly:
    ~/miniforge3/envs/crablox/bin/python app.py

    # Production (multi-user):
    conda activate crablox
    gunicorn -w 4 -b 0.0.0.0:5001 app:app

    # Open: http://localhost:5001

3.7  Verify Installation
──────────────────────────

    curl http://localhost:5001/
    # Should return the public CRABLOX homepage HTML

    curl http://localhost:5001/train
    # Should redirect (302) to /login?next=%2Ftrain for guests

3.8  First Login & User Approval
───────────────────────────────────

    • Open http://localhost:5001/login
    • Sign in with the default admin (admin) or the
      ADMIN_USERNAME / ADMIN_PASSWORD from your .env file
    • ⚠️  Change the admin password after first login

    New user registrations require admin approval:
    • Users click "Register" → their account is created as PENDING
    • The admin sees a "Users" button in the navbar (with a count badge)
    • Admin opens "Users" → clicks Approve to grant login access
    • Admins can also Reject (suspend) or Delete accounts


═══════════════════════════════════════════════════════════════════════════════
4. CONFIGURATION REFERENCE
═══════════════════════════════════════════════════════════════════════════════

4.1  Environment Variables (.env)
────────────────────────────────────

    Set these in .env or as system environment variables:

    │ Variable        │ Default                          │ Purpose           │
    │─────────────────│──────────────────────────────────│───────────────────│
    │ SECRET_KEY      │ insecure built-in                │ Session signing   │
    │ ADMIN_USERNAME  │ admin                            │ First admin user  │
    │ ADMIN_PASSWORD  │                                  │ First admin pass  │
    │ AI_API_KEY      │ (none)                           │ AI explainer      │
    │ AI_BASE_URL     │ https://ai.rebelstack.fun        │ AI endpoint       │
    │ AI_MODEL        │ jandel/free                      │ AI model name     │

4.2  App Settings (in app.py)
───────────────────────────────

    │ Setting                │ Default   │ Change For               │
    │────────────────────────│───────────│──────────────────────────│
    │ Port                   │ 5001      │ Different port           │
    │ Debug Mode             │ True      │ Set False in production  │
    │ Secret Key             │ Built-in  │ Set via .env (SECRET_KEY)│
    │ Max Upload Size        │ 50 MB     │ Larger datasets          │
    │ Session Cleanup        │ 24 hours  │ Change retention period  │

4.3  Production Hardening
───────────────────────────

    • Set SECRET_KEY in .env to a random string
    • Set debug=False in app.run()
    • Change the default admin password immediately after first login
    • Use gunicorn instead of Flask dev server
    • Put behind nginx reverse proxy
    • Set up SSL with Let's Encrypt
    • See GUIDE.md Section 9 for full production setup


═══════════════════════════════════════════════════════════════════════════════
5. GITHUB REPOSITORY STRUCTURE
═══════════════════════════════════════════════════════════════════════════════

    botanicaltox/
    ├── .gitignore
    ├── .env.example
    ├── requirements.txt
    ├── app.py                       ← Main entry point
    ├── run.sh                       ← Auto-detects conda/pip env
    ├── ai_explainer.py
    ├── extract_features.py
    ├── train_common.py
    ├── train_activity.py
    ├── train_toxicity.py
    ├── evaluate.py
    ├── predict.py
    ├── plant_predict.py
    ├── GUIDE.md
    ├── USER_GUIDE.md
    ├── DEPLOYMENT.md
    ├── templates/
    │   ├── base.html
    │   ├── index.html
    │   ├── train.html
    │   ├── train_result.html
    │   ├── predict.html
    │   ├── predict_result.html
    │   ├── plant.html
    │   ├── plant_result.html
    │   ├── ranking.html
    │   ├── ranking_result.html
    │   └── settings.html
    ├── datasets/
    │   ├── medchem_training.csv
    │   ├── medchem_prediction.csv
    │   ├── flavonoid_training.csv
    │   ├── flavonoid_prediction.csv
    │   ├── training_sample.csv
    │   ├── prediction_sample.csv
    │   └── training_toxicity.csv
    └── models/
        └── README.md                ← "Place trained .pkl files here"

    NOT pushed (in .gitignore):
      .env  instance/  venv/  sessions/  uploads/  outputs/  __pycache__/  *.pyc


═══════════════════════════════════════════════════════════════════════════════
6. QUICK DEPLOY CHECKLIST
═══════════════════════════════════════════════════════════════════════════════

    [ ] Push code to GitHub (files in Section 1.1 only)
    [ ] On new machine: git clone <repo-url>
    [ ] Install Miniforge: bash Miniforge3-Linux-x86_64.sh -b -p $HOME/miniforge3
    [ ] source $HOME/miniforge3/bin/activate
    [ ] conda create -n crablox python=3.10 rdkit=2026.03 -c conda-forge -y
    [ ] conda activate crablox
    [ ] pip install -r requirements.txt
    [ ] mkdir -p models uploads sessions outputs/datasets
    [ ] (Optional) cp .env.example .env and set SECRET_KEY + admin password
    [ ] ./run.sh  (or: gunicorn -w 4 -b 0.0.0.0:5001 app:app)
    [ ] Open http://localhost:5001 → login with admin 
    [ ] Change the admin password after first login
    [ ] Upload datasets/medchem_training.csv → Train → Predict

═══════════════════════════════════════════════════════════════════════════════
