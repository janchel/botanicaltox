╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║     Drug AI — Web-Based Molecular Activity & Toxicity Prediction             ║
║     Installation, Configuration & User Guide                                 ║
║     Version 1.0 — July 2026                                                  ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝


TABLE OF CONTENTS
─────────────────

  0. FILE INVENTORY — Web vs CLI
  1. SYSTEM REQUIREMENTS
  2. INSTALLATION
  3. CONFIGURATION
  4. STARTING & STOPPING THE WEB SERVER
  5. USING THE WEB APPLICATION
  6. USING THE CLI SCRIPTS
  7. FILE FORMATS & DATA PREPARATION
  8. TROUBLESHOOTING
  9. PRODUCTION DEPLOYMENT


═══════════════════════════════════════════════════════════════════════════════
0. FILE INVENTORY — What to Copy for Migration
═══════════════════════════════════════════════════════════════════════════════

0.1  Web-Based Application (Flask)
────────────────────────────────────

    These files are REQUIRED to run the web interface.  Copy ALL of them
    to a new server to deploy the web app.

    Core:
      app.py                     ← Flask web server (main entry point)
      ai_explainer.py            ← AI explanation module (OpenAI-compatible)
      extract_features.py        ← SMILES → RDKit descriptor extraction
      train_common.py            ← Shared training/evaluation logic
      requirements.txt           ← Python dependencies

    Templates (HTML):
      templates/base.html              ← Shared layout (navbar, styles, Bootstrap)
      templates/index.html             ← Home page (Train / Predict cards)
      templates/train.html             ← Upload form for training
      templates/train_result.html      ← Training results, metrics & graphs
      templates/predict.html           ← Upload form for prediction
      templates/predict_result.html    ← Prediction results & AI explanation

    Config (optional):
      .env.example               ← Template for AI API key
      .gitignore                 ← Prevents secrets in version control

    Directories to create (can be empty):
      models/                    ← Trained .pkl models stored here
      uploads/                   ← Temporary file uploads
      sessions/                  ← Per-user session data (auto-created)
      outputs/                   ← CLI graphs & reports
      datasets/                  ← Sample/input data files


0.2  Standalone CLI Scripts (No Web Server)
─────────────────────────────────────────────

    These scripts run from the terminal.  They do NOT need Flask or
    the templates/ folder.  Only Python + the ML dependencies.

    Core:
      extract_features.py        ← SMILES → numerical descriptors
      train_common.py            ← Shared training & evaluation functions
      train_activity.py          ← Train activity Random Forest
      train_toxicity.py          ← Train toxicity Random Forest
      evaluate.py                ← Evaluate a saved model
      predict.py                 ← Predict new compounds from CLI
      requirements.txt           ← Python dependencies

    Note: train_activity.py, train_toxicity.py, evaluate.py, and
          predict.py all import from extract_features.py and
          train_common.py — so those two are always required.


0.3  File Dependency Map
──────────────────────────

    ┌─────────────────────────────────────────────────────────────┐
    │                     SHARED CORE                             │
    │  extract_features.py        train_common.py                │
    │  (descriptor engine)        (ML training & evaluation)      │
    └──────────┬──────────────────────┬──────────────────────────┘
               │                      │
     ┌─────────┴─────────┐  ┌─────────┴──────────┐
     │   CLI SCRIPTS     │  │   WEB APP (Flask)  │
     │                   │  │                    │
     │ train_activity.py │  │ app.py             │
     │ train_toxicity.py │  │ ai_explainer.py    │
     │ evaluate.py       │  │ templates/*.html   │
     │ predict.py        │  │                    │
     └───────────────────┘  └────────────────────┘

    To migrate ONLY the web app:  copy all files in section 0.1.
    To migrate ONLY the CLI:      copy all files in section 0.2.
    To migrate BOTH:              copy everything (they share the core).


0.4  Quick Migration Checklist
────────────────────────────────

    [ ] Copy files listed in 0.1 (web) or 0.2 (CLI)
    [ ] Create empty directories: models/ uploads/ sessions/ outputs/
    [ ] python3 -m venv venv && source venv/bin/activate
    [ ] pip install -r requirements.txt
    [ ] pip install "numpy<2"              # if rdkit NumPy conflict
    [ ] (Optional) cp .env.example .env     # for AI explanations
    [ ] python3 app.py                      # start web server
    [ ] Open http://localhost:5000


═══════════════════════════════════════════════════════════════════════════════
1. SYSTEM REQUIREMENTS
═══════════════════════════════════════════════════════════════════════════════

  • Operating System:  Linux, macOS, or Windows (with WSL)
  • Python:            3.10 or newer
  • RAM:               4 GB minimum (8 GB recommended for hyperparameter tuning)
  • Disk:              ~500 MB for Python packages + space for datasets
  • Network:           Port 5000 must be available (for web server)


═══════════════════════════════════════════════════════════════════════════════
2. INSTALLATION
═══════════════════════════════════════════════════════════════════════════════

2.1  Clone or Copy the Project
────────────────────────────────

    The project is located at:

        /home/jandel/devops/Ethan2/drug_ai

    To use it elsewhere, copy the entire drug_ai/ folder to your target machine.


2.2  Install Python (if not already installed)
────────────────────────────────────────────────

    # Ubuntu / Debian
    sudo apt update
    sudo apt install python3 python3-pip python3-venv

    # Verify
    python3 --version    # Should show 3.10+


2.3  (Optional) Create a Virtual Environment
──────────────────────────────────────────────

    cd /home/jandel/devops/Ethan2/drug_ai

    python3 -m venv venv
    source venv/bin/activate     # Linux/macOS
    # OR: venv\Scripts\activate  # Windows


2.4  Install Required Packages
────────────────────────────────

    cd /home/jandel/devops/Ethan2/drug_ai
    pip install -r requirements.txt

    This installs:
      • rdkit          — Molecular descriptor calculation
      • pandas         — Data handling
      • scikit-learn   — Random Forest machine learning
      • matplotlib     — Graph generation
      • seaborn        — Confusion matrix heatmaps
      • numpy          — Numerical computation
      • openpyxl       — Excel file support
      • joblib         — Model save/load
      • flask          — Web server
      • gunicorn       — Production WSGI server

    ⚠️  IMPORTANT: rdkit-pypi requires NumPy < 2.
        If you get errors like "_ARRAY_API not found", run:
            pip install "numpy<2"


2.5  Verify Installation
──────────────────────────

    cd /home/jandel/devops/Ethan2/drug_ai
    python3 -c "from app import app; print('✅ Installation successful!')"

    Expected output:  ✅ Installation successful!


═══════════════════════════════════════════════════════════════════════════════
3. CONFIGURATION
═══════════════════════════════════════════════════════════════════════════════

3.1  Default Settings (in app.py)
───────────────────────────────────

    | Setting             | Default            | Description                     |
    |─────────────────────|────────────────────|─────────────────────────────────|
    | Server Host         | 0.0.0.0            | Listen on all network interfaces |
    | Server Port         | 5000               | HTTP port                       |
    | Max Upload Size     | 50 MB              | Maximum CSV/Excel file size     |
    | Debug Mode          | True (dev only)    | Auto-reload on code changes     |
    | Secret Key          | Built-in default   | Change for production           |

3.2  Changing the Port
───────────────────────

    Edit the last line of app.py:

        app.run(host="0.0.0.0", port=8080, debug=True)
        #                            ^^^^ change port here

3.3  Changing Upload Size Limit
─────────────────────────────────

    In app.py, find:

        app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

    Change to your desired limit (in bytes).

3.4  Production Security
──────────────────────────

    For production, change the secret key:

        app.secret_key = "your-random-secret-string-here"


═══════════════════════════════════════════════════════════════════════════════
4. STARTING & STOPPING THE WEB SERVER
═══════════════════════════════════════════════════════════════════════════════

4.1  Development Mode (Single User)
─────────────────────────────────────

    START:
        cd /home/jandel/devops/Ethan2/drug_ai
        python3 app.py

        You will see:
        =======================================================
          🧪  Drug AI — Web Interface
          Open:  http://localhost:5000
        =======================================================
        * Running on http://127.0.0.1:5000

    ACCESS:
        Open a browser and go to:  http://localhost:5000

        From another computer on the same network:
            http://<THIS-MACHINE-IP>:5000
            (Example: http://192.168.5.123:5000)

    STOP:
        Press Ctrl+C in the terminal where it's running.


4.2  Running in the Background
────────────────────────────────

    START (background):
        cd /home/jandel/devops/Ethan2/drug_ai
        nohup python3 app.py > server.log 2>&1 &
        echo $! > server.pid

    CHECK if running:
        ps aux | grep "app.py"

    STOP:
        kill $(cat server.pid)
        # OR:
        pkill -f "python3 app.py"

    VIEW logs:
        tail -f server.log


4.3  Production Mode (Multi-User) with Gunicorn
─────────────────────────────────────────────────

    START:
        cd /home/jandel/devops/Ethan2/drug_ai
        gunicorn -w 4 -b 0.0.0.0:5000 app:app

        Options:
          -w 4        4 worker processes (set to 2× CPU cores)
          -b 0.0.0.0  Listen on all interfaces
          --daemon    Run in background
          --log-file server.log

    STOP:
        pkill gunicorn

    With systemd (auto-start on boot):
        See Section 9 for complete systemd service setup.


═══════════════════════════════════════════════════════════════════════════════
5. USING THE WEB APPLICATION
═══════════════════════════════════════════════════════════════════════════════

5.1  Home Page (http://localhost:5000)
────────────────────────────────────────

    • Two main options: "Train Model" and "Predict Compounds"
    • Overview of the technology stack (RDKit, 211+ descriptors, Random Forest)


5.2  Training a Model
───────────────────────

    Step 1: Prepare your CSV file
        Your CSV must have:
          - A SMILES column (auto-detected)
          - A label column: Activity_Label or Toxicity_Label
          - Labels: 1 = Active/Toxic, 0 = Inactive/Safe

        See Section 7 for detailed format.

    Step 2: Open the Train page
        Click "Train Model" on the home page.

    Step 3: Upload and configure
        a) Drag & drop your CSV or click to browse
        b) Select task: Activity (OXA-23) or Toxicity (Human)
        c) Optionally specify label column name (auto-detected if blank)
        d) Optional: Enable hyperparameter tuning (better results, slower)

    Step 4: Click "Train Model"
        The server will:
          1. Extract ~211 molecular descriptors via RDKit
          2. Compute Wiener, Zagreb M1, and M2 topological indices
          3. Split data into train/test sets (80/20)
          4. Train a Random Forest classifier
          5. Generate evaluation metrics and graphs

    Step 5: View Results
        You'll see:
          • Summary cards (Accuracy, ROC-AUC, F1, MCC)
          • Detailed metrics table (train vs test)
          • ROC curve chart
          • Confusion matrix
          • Top 15 feature importance chart
          • Best hyperparameters (if tuning was enabled)


5.3  Predicting New Compounds
───────────────────────────────

    Step 1: Train models first (see 5.2) or use pre-trained models
        Models are stored in: drug_ai/models/activity.pkl
                              drug_ai/models/toxicity.pkl

    Step 2: Prepare prediction CSV
        Must have a SMILES column.
        See Section 7 for format.

    Step 3: Open Predict page
        Click "Predict Compounds" on the home page.

    Step 4: Upload and predict
        a) Drag & drop your CSV
        b) Check "Activity" and/or "Toxicity" tasks
        c) Click "Predict"

    Step 5: View and Download Results
        • Results table with predictions (Active/Inactive, Toxic/Safe)
        • Probability scores included
        • Pie charts showing distribution
        • "Download Full CSV" button to save results


═══════════════════════════════════════════════════════════════════════════════
6. USING THE CLI SCRIPTS
═══════════════════════════════════════════════════════════════════════════════

    The command-line scripts are alternatives to the web interface.

6.1  Extract Features
───────────────────────

    python3 extract_features.py --input datasets/compounds.csv --output datasets/features.csv

    Options:
      -i, --input       Input CSV/Excel with SMILES column
      -o, --output      Output CSV for feature matrix
      --smiles-col      SMILES column name (auto-detected if omitted)


6.2  Train Activity Model
───────────────────────────

    python3 train_activity.py --features datasets/features.csv --model-output models/activity.pkl

    Options:
      -f, --features    Feature matrix CSV
      -m, --model-output  Where to save the .pkl model
      --label-col       Target column name (default: Activity_Label)
      --no-tune         Skip hyperparameter tuning (faster)
      --seed            Random seed (default: 42)


6.3  Train Toxicity Model
───────────────────────────

    python3 train_toxicity.py --features datasets/features.csv --model-output models/toxicity.pkl

    (Same options as train_activity.py, default label: Toxicity_Label)


6.4  Evaluate a Model
───────────────────────

    python3 evaluate.py --model models/activity.pkl --features datasets/features.csv --label-col Activity_Label


6.5  Predict New Compounds (CLI)
──────────────────────────────────

    # With SMILES (auto-extracts features):
    python3 predict.py --input new_compounds.csv --smiles-col Smiles

    # With pre-computed features:
    python3 predict.py --input new_features.csv

    Options:
      --activity-model   Path to activity .pkl (default: models/activity.pkl)
      --toxicity-model   Path to toxicity .pkl (default: models/toxicity.pkl)
      --output, -o       Results output path (default: outputs/predictions.csv)
      --skip-activity    Only predict toxicity
      --skip-toxicity    Only predict activity


═══════════════════════════════════════════════════════════════════════════════
7. FILE FORMATS & DATA PREPARATION
═══════════════════════════════════════════════════════════════════════════════

7.1  Training Data Format
───────────────────────────

    Required columns:
      • Smiles          — SMILES string of the compound
      • Activity_Label  — 1 (active against OXA-23) or 0 (inactive)
      • Toxicity_Label  — 1 (toxic to humans) or 0 (safe)

    Optional columns:
      • Compound_ID     — Identifier (preserved in output, not used for ML)

    Example (compounds.csv):

        Compound_ID,Smiles,Activity_Label,Toxicity_Label
        CMP001,CCO,1,0
        CMP002,CCCC,1,1
        CMP003,CC(=O)O,0,0
        CMP004,C1=CC=CC=C1,0,1

    NOTES:
      • You only need the label column for the task you're training.
        (e.g., only Activity_Label if training activity model)
      • Both CSV (.csv) and Excel (.xlsx) formats are accepted.


7.2  Prediction Data Format
─────────────────────────────

    Required columns:
      • Smiles  — SMILES string of the compound to predict

    Optional columns:
      • Compound_ID  — Identifier (preserved in output)

    Example (new_compounds.csv):

        Compound_ID,Smiles
        CMP101,CCN(CC)CC
        CMP102,CN1C=NC2=C1C(=O)N(C(=O)N2C)C


7.3  Data Sources for Real Projects
─────────────────────────────────────

    For building a production model, collect labeled data from:

      • ChEMBL (https://www.ebi.ac.uk/chembl/)
        — Bioactivity data for OXA-23 related targets

      • DILIrank (FDA)
        — Human hepatotoxicity labels

      • Therapeutics Data Commons (TDC)
        — Standardized ADMET benchmarks


═══════════════════════════════════════════════════════════════════════════════
8. TROUBLESHOOTING
═══════════════════════════════════════════════════════════════════════════════

8.1  "Command 'python' not found"
───────────────────────────────────

    Use python3 instead of python:
        python3 app.py


8.2  "AttributeError: _ARRAY_API not found" (rdkit + numpy conflict)
───────────────────────────────────────────────────────────────────────

    rdkit-pypi needs NumPy < 2. Fix:
        pip install "numpy<2"


8.3  "Port 5000 already in use"
─────────────────────────────────

    Either stop the existing process:
        pkill -f "python3 app.py"

    Or use a different port (see Section 3.2).


8.4  "Label column 'Activity_Label' not found"
────────────────────────────────────────────────

    Your CSV is missing the label column or it has a different name.
    Either:
      a) Rename your label column to Activity_Label or Toxicity_Label, OR
      b) Type your actual column name in the "Label Column Name" field.


8.5  "Could not auto-detect a SMILES column"
───────────────────────────────────────────────

    Ensure your CSV has a column named exactly "Smiles" or "SMILES".


8.6  Upload fails / no response
─────────────────────────────────

    • Check file size — max is 50 MB by default
    • Ensure file is valid CSV or .xlsx format
    • Check Flask console for error messages


8.7  Blank graphs or missing images
─────────────────────────────────────

    Matplotlib needs a non-interactive backend. The app sets 'Agg' by default.
    If graphs are still broken:
        export MPLBACKEND=Agg


8.8  Server accessible locally but not from other computers
─────────────────────────────────────────────────────────────

    • Ensure the server is bound to 0.0.0.0 (not 127.0.0.1)
    • Check firewall:  sudo ufw allow 5000
    • Check that other computers can ping this machine


═══════════════════════════════════════════════════════════════════════════════
9. PRODUCTION DEPLOYMENT
═══════════════════════════════════════════════════════════════════════════════

9.1  Gunicorn + systemd (Ubuntu/Debian)
─────────────────────────────────────────

    Create a systemd service file:

        sudo nano /etc/systemd/system/drug-ai.service

    Paste:

        [Unit]
        Description=Drug AI Web Application
        After=network.target

        [Service]
        User=jandel
        WorkingDirectory=/home/jandel/devops/Ethan2/drug_ai
        ExecStart=/usr/bin/python3 -m gunicorn -w 4 -b 0.0.0.0:5000 app:app
        Restart=always
        RestartSec=5

        [Install]
        WantedBy=multi-user.target

    Enable and start:

        sudo systemctl enable drug-ai
        sudo systemctl start drug-ai
        sudo systemctl status drug-ai


9.2  Gunicorn + Nginx Reverse Proxy (with SSL)
─────────────────────────────────────────────────

    Install nginx:

        sudo apt install nginx

    Nginx config (/etc/nginx/sites-available/drug-ai):

        server {
            listen 80;
            server_name your-domain.com;

            client_max_body_size 100M;

            location / {
                proxy_pass http://127.0.0.1:5000;
                proxy_set_header Host $host;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            }
        }

    Enable:

        sudo ln -s /etc/nginx/sites-available/drug-ai /etc/nginx/sites-enabled/
        sudo nginx -t
        sudo systemctl reload nginx

    For SSL, add Certbot (Let's Encrypt):

        sudo apt install certbot python3-certbot-nginx
        sudo certbot --nginx -d your-domain.com


═══════════════════════════════════════════════════════════════════════════════
QUICK REFERENCE CARD
═══════════════════════════════════════════════════════════════════════════════

    START SERVER:
        cd /home/jandel/devops/Ethan2/drug_ai && python3 app.py

    STOP SERVER:
        Ctrl+C  (or pkill -f "python3 app.py")

    WEB INTERFACE:
        http://localhost:5000

    TRAIN (CLI):
        python3 train_activity.py --features datasets/features.csv
        python3 train_toxicity.py --features datasets/features.csv

    PREDICT (CLI):
        python3 predict.py --input new_compounds.csv --smiles-col Smiles

    HELP:
        python3 <script>.py --help

    ── MIGRATION ──

    WEB APP FILES (copy these to a new server):
        app.py  ai_explainer.py  extract_features.py  train_common.py
        requirements.txt  .env.example  .gitignore
        templates/*.html

    CLI FILES (copy these for terminal-only use):
        extract_features.py  train_common.py  train_activity.py
        train_toxicity.py  evaluate.py  predict.py  requirements.txt

    DIRECTORIES TO CREATE:
        models/  uploads/  sessions/  outputs/  datasets/

    QUICK SETUP:
        pip install -r requirements.txt
        pip install "numpy<2"
        python3 app.py

═══════════════════════════════════════════════════════════════════════════════
