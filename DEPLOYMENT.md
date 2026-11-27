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
      run.sh                       Launcher (conda env first, then venv)
      README.md                    Project overview
      CHANGELOG_2026-08-16.md      Change log / tracing
      .env.example                 Template for environment configuration

    Templates (16 files):
      templates/base.html
      templates/index.html
      templates/login.html
      templates/register.html
      templates/admin_users.html
      templates/team.html
      templates/train.html
      templates/train_status.html
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
                     (training on tens of thousands of compounds needs 4 GB+;
                     the 2 GB figure is for small demo datasets only)
    • CPU:           1 vCPU works but training is slow; ≥2 cores recommended
    • Disk:          1 GB free (app + dependencies + datasets)
    • Network:       Port 5001 open for web access

    ⚠️  Small / single-vCPU hosts (1 core, 2 GB RAM):
         export CRABLOX_TRAIN_JOBS=1          # sklearn parallelism; auto-clamped
                                             # to the core count by train_common.py
         export CRABLOX_DESC_BATCH_SIZE=500  # lower RDKit batch = lower peak RAM
         export CRABLOX_TUNE_MAX_ROWS=20000  # subsample cap for grid search

       Training runs in a background thread, so it survives the gunicorn
       request timeout, but it still shares the host's CPU and RAM.

2.2  Python Packages
──────────────────────

    All in requirements.txt:

    │ Package       │ Purpose                              │ Min Version     │
    │───────────────│──────────────────────────────────────│──────────────────│
    │ rdkit         │ Molecular descriptor calculation     │ >=2023.09 (2026.x)│
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
    │ pubchempy     │ (legacy plant lookup; data is built-in)│ 1.0            │
    │ python-dotenv │ Loads .env configuration             │ 1.0              │

    ⚠️  CRITICAL: RDKit version matters!

        The pipeline expects the modern RDKit (2026.x) that exposes 217
        descriptors. Both current distributions provide it:

        • conda-forge:  conda install -c conda-forge rdkit=2026.03
        • PyPI:         pip install rdkit        (requirements.txt pins >=2023.09)

        Do NOT install the legacy "rdkit-pypi" package — it is frozen at
        2022.09 with only 208 descriptors, so the feature set (and therefore
        rankings) will not match the reference notebook.

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

    ℹ️  requirements.txt installs the current PyPI `rdkit` package, which also
        provides 2026.x / 217 descriptors. Just avoid the legacy `rdkit-pypi`.

3.3  Alternative: pip Virtual Environment
────────────────────────────────────────────────────────────

    Works with current releases; this repo's own venv runs RDKit 2026.09,
    pandas 3.x and numpy 2.x. Do not add `pip install "numpy<2"` or install
    the legacy `rdkit-pypi` package.

    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt

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

    ⚠️  SECRET_KEY is required: the app refuses to start if it is missing or
        still set to the .env.example placeholder. On first launch a
        default admin is created: set ADMIN_PASSWORD in .env, otherwise a
        random one-time password is printed.

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

    # Production (multi-user) — worker count should match the host, not a fixed
    # number. Each worker holds its own copy of RDKit/sklearn and training runs
    # inside one of them:
    conda activate crablox
    ./run.sh                       # defaults to 2 workers; see overrides below
    WEB_CONCURRENCY=1 ./run.sh     # single-vCPU / 2 GB host
    CRABLOX_TRAIN_JOBS=1 ./run.sh # keep sklearn single-process on small hosts

    # Do NOT use `gunicorn -w 4` on a 1-core/2 GB box: four workers plus
    # training oversubscribe the CPU and RAM.

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
    • Sign in with the default admin (password from ADMIN_PASSWORD, or the generated one) or the
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
    │ ADMIN_PASSWORD  │ (auto-generated if unset)      │ First admin pass  │
    │ AI_API_KEY      │ (none)                           │ AI explainer      │
    │ AI_BASE_URL     │ https://ai.rebelstack.fun        │ AI endpoint       │
    │ AI_MODEL        │ jandel/free                      │ AI model name     │
    │ CRABLOX_TRAIN_JOBS     │ min(2, cpu_count)       │ sklearn processes │
    │ CRABLOX_DESC_BATCH_SIZE│ 1000                    │ RDKit batch size  │
    │ CRABLOX_TUNE_MAX_ROWS  │ 20000                   │ tuning subsample  │

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
    • See USER_GUIDE.md for student workflows and README.md for the
      notebook-alignment/pipeline details


═══════════════════════════════════════════════════════════════════════════════
5. GITHUB REPOSITORY STRUCTURE
═══════════════════════════════════════════════════════════════════════════════

    botanicaltox/
    ├── .gitignore
    ├── .env.example
    ├── requirements.txt
    ├── app.py                       ← Main entry point
    ├── run.sh                       ← Auto-detects conda then venv
    ├── ai_explainer.py
    ├── extract_features.py
    ├── train_common.py
    ├── train_activity.py
    ├── train_toxicity.py
    ├── evaluate.py
    ├── predict.py
    ├── plant_predict.py
    ├── USER_GUIDE.md
    ├── DEPLOYMENT.md
    ├── templates/
    │   ├── base.html
    │   ├── index.html
    │   ├── login.html
    │   ├── register.html
    │   ├── admin_users.html
    │   ├── team.html
    │   ├── train.html
    │   ├── train_status.html
    │   ├── train_result.html
    │   ├── predict.html
    │   ├── predict_result.html
    │   ├── plant.html
    │   ├── plant_result.html
    │   ├── ranking.html
    │   ├── ranking_result.html
    │   └── settings.html
    ├── datasets/
    │   ├── toxicity_compounds.csv
    │   ├── _ACTIVITY__105_COMPOUNDS_FINAL_TRAINING.csv
    │   ├── prediction_compounds.xlsx
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
    [ ] ./run.sh  (workers default to 2; set WEB_CONCURRENCY=1 and
        CRABLOX_TRAIN_JOBS=1 on a single-vCPU / 2 GB host)
    [ ] Open http://localhost:5001 → login with the admin password from .env (or the generated one)
    [ ] Change the admin password after first login
    [ ] Upload datasets/medchem_training.csv → Train → Predict

═══════════════════════════════════════════════════════════════════════════════
