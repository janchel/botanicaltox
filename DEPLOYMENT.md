╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║     BotanicalTox — DEPLOYMENT GUIDE                                              ║
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

    │ Package       │ Purpose                              │
    │───────────────│──────────────────────────────────────│
    │ rdkit         │ Molecular descriptor calculation     │
    │ pandas        │ CSV/data handling                    │
    │ scikit-learn  │ Random Forest ML                     │
    │ matplotlib    │ Graph generation                     │
    │ seaborn       │ Confusion matrix heatmaps            │
    │ numpy         │ Numerical computation                │
    │ openpyxl      │ Excel file support                   │
    │ joblib        │ Model save/load                      │
    │ flask         │ Web framework                        │
    │ flask-login   │ User authentication & sessions       │
    │ gunicorn      │ Production WSGI server               │
    │ openai        │ AI explainer client                  │

    ⚠️  IMPORTANT: rdkit-pypi requires NumPy < 2.
        If you get "_ARRAY_API not found" errors:
            pip install "numpy<2"

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

    git clone https://github.com/YOUR_USER/drug_ai.git
    cd drug_ai

3.2  Create Virtual Environment
─────────────────────────────────

    python3 -m venv venv
    source venv/bin/activate          # Linux/macOS
    # OR: venv\Scripts\activate       # Windows

3.3  Install Dependencies
───────────────────────────

    pip install -r requirements.txt

    # Fix NumPy compatibility if needed:
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
───────────────────────

    # Easiest — launcher uses the venv automatically:
    ./run.sh

    # Development (single user) — use the venv:
    source venv/bin/activate
    python3 app.py

    # Or directly:
    venv/bin/python app.py

    # Production (multi-user):
    gunicorn -w 4 -b 0.0.0.0:5001 app:app

    # Open: http://localhost:5001

    ⚠️  New auth dependencies (flask-login, python-dotenv) must be installed.
        If you get "ModuleNotFoundError: No module named 'flask_login'",
        activate the venv (source venv/bin/activate) before running, or run
        ./run.sh which picks the venv automatically.

3.7  Verify Installation
──────────────────────────

    curl http://localhost:5001/
    # Should return the public BotanicalTox homepage HTML

    curl http://localhost:5001/train
    # Should redirect (302) to /login?next=%2Ftrain for guests

3.8  First Login & User Approval
───────────────────────────────────

    • Open http://localhost:5001/login
    • Sign in with the default admin (admin /  ) or the
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

4.1  Environment Variables
────────────────────────────

    Set these in .env or as system environment variables:

    │ Variable       │ Default                          │ Purpose         │
    │────────────────│──────────────────────────────────│─────────────────│
4.1  Environment Variables (.env)
─────────────────────────────────────

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

    drug_ai/
    ├── .gitignore
    ├── .env.example
    ├── requirements.txt
    ├── app.py                       ← Main entry point
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
    [ ] python3 -m venv venv && source venv/bin/activate
    [ ] pip install -r requirements.txt
    [ ] pip install "numpy<2"
    [ ] mkdir -p models uploads sessions
    [ ] (Optional) cp .env.example .env and set SECRET_KEY + admin password
    [ ] python3 app.py
    [ ] Open http://localhost:5001 → login with admin / 
    [ ] Change the admin password after first login
    [ ] Upload datasets/medchem_training.csv → Train → Predict

═══════════════════════════════════════════════════════════════════════════════
