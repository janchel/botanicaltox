╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║     BotanicalTox — USER GUIDE                                                     ║
║     How to Predict Plant Compound Toxicity                              ║
║     Version 3.1 — August 2026                                                  ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝


WHAT IS THIS APP?
─────────────────
BotanicalTox is a Machine Learning prediction tool for plant toxicity. It predicts the toxicity of
chemical compounds found in plants:

  1. TOXICITY   — Is this compound likely toxic to humans?
  2. ACTIVITY   — Does this compound have biological activity?

It uses Random Forest classifiers trained on molecular descriptors calculated
by RDKit (a chemistry toolkit). Students upload compound data, train models,
and get predictions — all through a web browser.

⚠️  IMPORTANT: These are COMPUTATIONAL predictions, not lab results.
    Always validate predictions with experimental testing.


═══════════════════════════════════════════════════════════════════════════════
LOGIN — Accessing the Site
═══════════════════════════════════════════════════════════════════════════════

    The landing (home) page is PUBLIC — anyone can view it without logging in.
    The Train / Predict / Plant / Rank features require a login.

    When a guest clicks a protected link (e.g. "Train"), they are sent to the
    Login page. After signing in, they are returned to the page they requested.

  1.1  First Run — Default Admin
  ─────────────────────────────
      On the first launch, a default admin account is created:
        Username:  admin
        Password:  admin123   (CHANGE THIS AFTER FIRST LOGIN!)

      ⚠️  To change it, set ADMIN_USERNAME and ADMIN_PASSWORD in a .env file
          BEFORE the first run, then delete the instance/users.db file.

  1.2  Creating User Accounts (Admin Approval Required)
  ─────────────────────────────────────────────────────
      Any user can click "Register" to create their own account.

      New accounts are created in a PENDING state — they cannot log in
      until an administrator approves them.

      ⚠️  After registering, wait for an admin to approve your account.
          You will see: "Registration submitted! An administrator must
          approve your account before you can log in."

      Once approved, the account gets the "user" role and full access to
      Train / Predict / Plant / Rank features.

  1.3  Admin — Approving New Users
  ─────────────────────────────────
      Admins see a "Users" button in the navigation bar (with a badge
      showing how many registrations are pending).

      Click "Users" → the management page lists every account:
        • Approve  — allow a pending user to log in
        • Reject   — suspend an approved user (blocks login again)
        • Promote  — grant a user the admin role (so they can also approve
                     users and manage the site)
        • Demote   — remove a user's admin role
        • Delete   — permanently remove an account (with confirmation)

      The admin account itself cannot be promoted/demoted/rejected/deleted
      (self-protection), and the LAST admin cannot be demoted (avoids lockout).

  1.4  Logging Out
  ─────────────────────────────
      Click your username (top-right) → Logout.

      Sessions expire when the browser is closed. Protected pages redirect
      to the login page if you are not signed in.

  1.4b  Changing Your Password
  ─────────────────────────────
      Any logged-in user can change their own password from
      Settings → "Change Password":
        • Current Password (to verify it's really you)
        • New Password (min 6 characters)
        • Confirm New Password

      The default admin password should be changed here after first login.

  1.5  Public Pages
  ─────────────────────────────
      These pages do NOT require login:
        • Home (/)            — landing page
        • Team (/team)        — student members & their profiles
        • Login / Register    — auth pages

  1.6  Team Profiles & the Team Page
  ─────────────────────────────────────
      The TEAM page (public) shows the student members behind the project.
      It is a CURATED list — not every registered user appears on it.

      • Only approved users explicitly marked as a "Team member" by the
        ADMIN (Users → "Team" button) are shown on the page.
      • Each member customizes their own profile from
        Settings → "Your Profile":
          - Full Name
          - Course / Program
          - Bio (short intro)
          - Profile Picture (PNG / JPG / GIF / WebP)
      • Admins are shown as "Project Lead", others as "Team Member".
      • Profile pictures are stored in instance/avatars/.
      • A member with no profile yet still appears (showing just their
        username + default icon), so the admin can pre-add the team list.


═══════════════════════════════════════════════════════════════════════════════
BEFORE YOU START — The Workflow
═══════════════════════════════════════════════════════════════════════════════

    ┌──────────┐      ┌──────────────┐      ┌──────────────┐
    │  TRAIN   │ ───→ │   PREDICT    │ ───→ │  DOWNLOAD    │
    │  Model   │      │  Compounds   │      │  Results     │
    └──────────┘      └──────────────┘      └──────────────┘

    ⚠️  YOU MUST TRAIN BEFORE YOU CAN PREDICT.

    Training teaches the model what "active" and "toxic" look like.
    Prediction uses that knowledge on new, unseen compounds.

    You can also use the PLANT SEARCH feature to look up known compounds
    from medicinal plants and predict them instantly.


═══════════════════════════════════════════════════════════════════════════════
1. TRAINING — Teach the Model
═══════════════════════════════════════════════════════════════════════════════

    ⚡  MODEL IMPROVEMENTS (from refinedd_code.ipynb):
      • Scaffold-aware splitting — near-duplicate compounds (same scaffold)
        never leak across train/test, giving honest evaluation scores.
      • Probability calibration — prediction scores are calibrated so they
        can be meaningfully compared / multiplied into a priority score.
      • Robust feature cleaning — missing/extreme descriptor values are
        imputed with training medians, and the same values are reused when
        predicting, so scores stay consistent with what the model learned.

1.1  Prepare Your Training Data
─────────────────────────────────

    Create a CSV or Excel file with these columns:

    ┌──────────────┬─────────────────────┬────────────────┬─────────────────┐
    │ Compound_ID  │ Smiles              │ Activity_Label │ Toxicity_Label  │
    ├──────────────┼─────────────────────┼────────────────┼─────────────────┤
    │ CMP001       │ CCO                 │ 1              │ 0               │
    │ CMP002       │ CCCC                │ 1              │ 1               │
    │ CMP003       │ CC(=O)O             │ 0              │ 0               │
    │ CMP004       │ C1=CC=CC=C1         │ 0              │ 1               │
    │ CMP005       │ CCN(CC)CC           │ 1              │ 0               │
    └──────────────┴─────────────────────┴────────────────┴─────────────────┘

    REQUIRED COLUMNS:
      • Smiles           — The chemical structure in SMILES notation
      • Activity_Label   — 1 = Active (inhibits OXA-23), 0 = Inactive
      • Toxicity_Label   — 1 = Toxic to humans, 0 = Safe

    You only need ONE label column, depending on which task you're training:
      - Training ACTIVITY model → need Activity_Label
      - Training TOXICITY model → need Toxicity_Label

    Compound_ID is optional — it's preserved in output but not used for ML.

    FILE FORMAT:  .csv (comma-separated) or .xlsx (Excel)
    FILE SIZE:    Up to 50 MB

1.1b  Why Only SMILES and Labels?
────────────────────────────────────

    You might wonder: "Don't I need Molecular Weight, LogP, or other
    chemical properties in my CSV?"

    SHORT ANSWER: No. RDKit calculates ALL of that for you.

    LONG ANSWER: The SMILES string is a complete description of a
    molecule's 2D structure — every atom, every bond. From just that
    text, RDKit automatically computes:

    ┌──────────────────────────────────────────────────────────────┐
    │  208 STANDARD DESCRIPTORS (computed automatically)          │
    │                                                              │
    │  Molecular Weight (MolWt)       LogP (MolLogP)              │
    │  Polar Surface Area (TPSA)      H-Bond Donors (NumHDonors)  │
    │  H-Bond Acceptors (NumHAcceptors)  Rotatable Bonds          │
    │  Ring Count, Aromatic Rings     Fraction Csp3               │
    │  Bertz CT complexity index      Hall-Kier alpha             │
    │  BCUT descriptors (6)           EState descriptors          │
    │  PEOE / SMR / SlogP VSA (30+)   Morgan fingerprints         │
    │  Fragment counts (85+)          ... and 80+ more            │
    │                                                              │
    │  3 TOPOLOGICAL INDICES (also automatic)                     │
    │                                                              │
    │  Wiener Index   — molecular compactness                     │
    │  Zagreb M1/M2   — branching complexity                      │
    │  Balaban J      — molecular shape                           │
    │                                                              │
    │  TOTAL: 211 numerical features from ONE SMILES string       │
    └──────────────────────────────────────────────────────────────┘

    This is why your CSV only needs TWO columns:
      • Smiles       → The structure (input)
      • Label        → The answer you know (1 or 0)

    Everything else is computed by RDKit. You don't need to look up
    or calculate any chemical properties yourself.

    ANALOGY: It's like giving a chef a recipe (SMILES) instead of
    listing every nutrient in the dish. The chef (RDKit) figures out
    all the nutritional facts from the recipe.


1.2  Upload and Train
───────────────────────

    1. Open the web app → click "Train Model"
    2. Drag & drop your CSV/Excel file (or click to browse)
    3. Select the task(s): "Activity (OXA-23)" and/or "Toxicity (Human)".
       You can train BOTH at once if your CSV has both label columns.
    4. (Optional) Enter a TASK NAME — e.g., "Flavonoid vs Alkaloid" or
       "Blood-Brain Barrier". This name appears in results instead of
       "Activity" or "Toxicity". Leave blank to use the defaults.
    5. (Optional) Enter a LABEL COLUMN NAME if your CSV uses a
       different column (e.g., "Flavonoid_Label"). Auto-detected if blank.
    6. Enter a MODEL / DATASET NAME (e.g., "library1", "fda_approved").
    7. Optional: Enable "Hyperparameter Tuning" for better accuracy.
    8. Click "Train Model"

    ⚠️  USING AN EXISTING NAME will overwrite the previous model.
    ⚠️  DUPLICATE SMILES are detected and handled:
        - Same SMILES, same label → first copy kept, rest dropped.
        - Same SMILES, different labels → all conflicting copies removed.
    A warning message will tell you what happened.


1.3  What to Check After Training
───────────────────────────────────

    After training completes, review these sections:

    ┌─────────────────────────────────────────────────────────────────┐
    │  🗄️  TRAINING DATASET PREVIEW                                  │
    │                                                                 │
    │  Shows the first 10 rows of your uploaded data — Compound IDs,  │
    │  SMILES, and labels. Use this to VERIFY your data was loaded    │
    │  correctly before trusting the model's results.                │
    │                                                                 │
    │  Class distribution is shown: "Class 1: 14 | Class 0: 16"      │
    │  Model/dataset name is displayed in the header.                 │
    └─────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────┐
    │  📊 SUMMARY CARDS (top of page)                                │
    │                                                                 │
    │  Test Accuracy  →  Overall correct predictions (0 to 1)        │
    │  Test ROC-AUC   →  How well the model separates classes        │
    │  Test F1 Score  →  Balance of precision and recall             │
    │  Test MCC       →  Matthews Correlation Coefficient            │
    │                                                                 │
    │  GOOD scores:   > 0.7 on all metrics                           │
    │  GREAT scores:  > 0.85  (needs 100+ compounds to achieve)      │
    │  LOW scores:    < 0.5  → need more training data               │
    └─────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────┐
    │  📈 ROC CURVE                                                   │
    │                                                                 │
    │  Shows the trade-off between true positives and false positives.│
    │  The closer the curve to the top-left corner, the better.       │
    │  AUC = 1.0 means perfect separation.                            │
    │  AUC = 0.5 means random guessing (diagonal line).              │
    └─────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────┐
    │  🔲 CONFUSION MATRIX                                            │
    │                                                                 │
    │  Shows correct vs incorrect predictions on the test set:        │
    │                                                                 │
    │              Predicted Neg   Predicted Pos                      │
    │  Actual Neg     ✅ TN           ❌ FP                           │
    │  Actual Pos     ❌ FN           ✅ TP                           │
    │                                                                 │
    │  TN = True Negative (correctly predicted inactive/safe)         │
    │  TP = True Positive (correctly predicted active/toxic)          │
    │  FP = False Positive (wrongly predicted active/toxic)           │
    │  FN = False Negative (wrongly predicted inactive/safe)          │
    └─────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────┐
    │  📊 FEATURE IMPORTANCE (Top 15)                                 │
    │                                                                 │
    │  Shows which molecular properties the model found most useful.  │
    │  Common top features: MolWt, MolLogP, TPSA, NumHDonors.        │
    │  Longer bars = more important for the prediction.               │
    └─────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────┐
    │  🔬 TOPOLOGICAL INDICES (Wiener, Zagreb, Balaban)              │
    │                                                                 │
    │  These graph-theory indices measure molecular shape and         │
    │  connectivity. They are ALWAYS computed but may not rank high   │
    │  in small datasets. The chart shows their exact importance.     │
    └─────────────────────────────────────────────────────────────────┘

    ⚠️  TROUBLESHOOTING LOW SCORES:
        • Training Accuracy = 1.0 but Test Accuracy is low?
          → Overfitting. You need MORE training data (50+ compounds).
        • Both train and test scores are low?
          → Your data may not separate well. Try different descriptors.
        • All scores are 1.0?
          → Suspiciously perfect. Check for data leakage (same compounds
            in train and test). The app now uses SCAFFOLD-AWARE splitting,
            which prevents near-duplicate compounds from leaking across
            train/test, so test scores are more honest than before.


1.4  The Model Is Saved
─────────────────────────

    After training, the model is automatically saved with your chosen name:
      models/activity_library1.pkl   — Activity classifier for "library1"
      models/toxicity_library1.pkl   — Toxicity classifier for "library1"

    Each saved model also stores its training-time preprocessing
    (calibration settings + descriptor medians) so predictions are always
    consistent with how the model was trained.

    You can train MULTIPLE models with different names — they won't
    overwrite each other. Only training with the SAME name overwrites.

    You do NOT need to train again unless you have new data.
    Just go straight to PREDICT and select your model from the dropdown.


═══════════════════════════════════════════════════════════════════════════════
2. PREDICTION — Test New Compounds
═══════════════════════════════════════════════════════════════════════════════

2.1  Prepare Your Prediction Data
───────────────────────────────────

    Create a CSV or Excel file with a Smiles column:

    ┌──────────────┬──────────────────────────────────────────┐
    │ Compound_ID  │ Smiles                                   │
    ├──────────────┼──────────────────────────────────────────┤
    │ NEW001       │ CCN(CC)CC                                │
    │ NEW002       │ CN1C=NC2=C1C(=O)N(C(=O)N2C)C             │
    │ NEW003       │ CC(C)CC1=CC=C(C=C1)C(C)C(=O)O            │
    └──────────────┴──────────────────────────────────────────┘

    REQUIRED:  Smiles column
    OPTIONAL:  Compound_ID (preserved in output)

    ⚠️  DO NOT use the same file you used for training!
        Predicting on training data gives artificially high scores.
        Always predict on NEW, unseen compounds.

    TEST FILES INCLUDED:
      datasets/training_sample.csv    — 10 compounds for training
      datasets/prediction_sample.csv  — 5 compounds for prediction
      datasets/training_toxicity.csv  — 10 compounds (toxicity only)

2.1b  Why Only SMILES? (No Labels)
────────────────────────────────────

    Prediction CSV is simpler than training CSV — you only need SMILES.

    WHY NO LABELS? Because that's what you're trying to FIND OUT.
    You don't know yet if the compound is active or toxic — that's
    exactly what the model will predict for you.

    Just like training, RDKit automatically computes all 211 molecular
    descriptors from each SMILES string. You don't need to add any
    chemical properties to the file.

    The OUTPUT will have these ADDED columns:
      Activity_Prediction  → 1 (active) or 0 (inactive)
      Activity_Score       → Confidence (0.00 to 1.00)
      Toxicity_Prediction  → 1 (toxic) or 0 (safe)
      Toxicity_Score       → Confidence (0.00 to 1.00)

    So your 2-column input becomes a 6-column result.

2.1c  Why a Separate Dataset for Prediction?
──────────────────────────────────────────────

    Imagine you're studying for a test:

      TRAINING DATA  =  Your textbook and practice problems (with answers)
      PREDICTION DATA =  The actual exam (no answers — you figure them out)

    If you used the same compounds for both, you'd be "testing" on
    material you already memorized. The scores would look perfect,
    but tell you nothing about how the model performs on NEW compounds.

    This is called DATA LEAKAGE — one of the most common mistakes
    in machine learning. Always predict on compounds the model has
    NEVER seen before.


2.2  Upload and Predict
─────────────────────────

    1. Open the web app → click "Predict Compounds"
    2. Select your trained model from the dropdown
       (e.g., "Library1 (Activity, Toxicity)")
    3. Drag & drop your prediction CSV/Excel file
    4. Check "Activity" and/or "Toxicity" (both by default)
    4. Click "Predict"


2.3  Understanding the Results
────────────────────────────────

    ┌─────────────────────────────────────────────────────────────────┐
    │  📊 PIE CHARTS                                                  │
    │                                                                 │
    │  Shows the overall distribution of predictions:                 │
    │  - Green = Active/Safe                                          │
    │  - Red = Inactive/Toxic                                         │
    │                                                                 │
    │  This gives a quick overview of your compound library.          │
    └─────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────┐
    │  🧬 COMPOUND STRUCTURES                                         │
    │                                                                 │
    │  Shows the 2D chemical structure of the first 8 compounds.      │
    │  Atoms are labeled (C, H, N, O, etc.) and bonds are shown.      │
    │  This is the same visualization as RDKit's MolToImage().        │
    └─────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────┐
    │  📋 RESULTS TABLE                                                │
    │                                                                 │
    │  Columns in the output:                                          │
    │                                                                 │
    │  Activity_Prediction  → 1 = Active, 0 = Inactive (green/red)   │
    │  Activity_Score       → Probability of being active (0 to 1)    │
    │  Toxicity_Prediction  → 1 = Toxic, 0 = Safe (green/red)        │
    │  Toxicity_Score       → Probability of being toxic (0 to 1)     │
    │                                                                 │
    │  HOW TO READ SCORES:                                             │
    │    > 0.75  = High confidence prediction                         │
    │    0.5-0.75 = Moderate confidence                               │
    │    < 0.5   = Low confidence (close to random)                   │
    │                                                                 │
    │  Scores are CALIBRATED probabilities — they can be compared     │
    │  directly across compounds (e.g., 0.9 really is twice as likely │
    │  as 0.45). Raw Random Forest scores used to cluster near 0/1;  │
    │  the app now calibrates them so the numbers are honest.        │
    │                                                                 │
    │  EXAMPLE:                                                        │
    │    Activity_Score = 0.92  → Very likely ACTIVE against OXA-23   │
    │    Toxicity_Score  = 0.23  → Likely SAFE (low toxicity risk)    │
    └─────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────┐
    │  🤖 AI EXPLANATION (optional)                                   │
    │                                                                 │
    │  Click "Explain These Results" to get an AI-generated breakdown │
    │  of what the predictions mean, which features were important,   │
    │  and what the limitations are.                                  │
    │                                                                 │
    │  This is HELPFUL FOR LEARNING but the AI is not the predictor — │
    │  the Random Forest model is. The AI only explains the results.  │
    │                                                                 │
    │  Uses ~2,000 tokens. Only one explanation per prediction run    │
    │  to manage costs.                                               │
    └─────────────────────────────────────────────────────────────────┘


2.4  Download Results
───────────────────────

    Click "Download Full Results (CSV)" to save the complete prediction
    table. This file can be opened in Excel, Google Sheets, or any
    spreadsheet application.


═══════════════════════════════════════════════════════════════════════════════
3. PLANT SEARCH — Predict from Medicinal Plants
═══════════════════════════════════════════════════════════════════════════════

    Instead of uploading SMILES, you can search by plant name. The app
    has a built-in database of 21 medicinal plants with 80+ known compounds.

3.1  How to Use
─────────────────

    1. Open the web app → click "Search by Plant"
    2. Type a plant name (scientific or common name)
    3. OPTIONAL: Upload a photo of the plant
       → The photo is for VISUAL REFERENCE only
       → It is NOT used for identification
       → The prediction uses the PLANT NAME you typed
    4. Click "Search & Predict"

3.2  What Plant Names Work
────────────────────────────

    You can use either scientific or common names:

    ┌────────────────────────────┬──────────────────────┐
    │  Scientific Name           │  Common Names        │
    ├────────────────────────────┼──────────────────────┤
    │  Artemisia annua           │  sweet wormwood      │
    │  Curcuma longa             │  turmeric            │
    │  Azadirachta indica        │  neem                │
    │  Zingiber officinale       │  ginger              │
    │  Allium sativum            │  garlic              │
    │  Camellia sinensis         │  green tea, tea      │
    │  Cannabis sativa           │  cannabis, marijuana │
    │  Panax ginseng             │  ginseng             │
    │  Ginkgo biloba             │  ginkgo              │
    │  Catharanthus roseus       │  periwinkle          │
    │  Salvia officinalis        │  sage                │
    │  Ocimum sanctum            │  holy basil, tulsi   │
    │  Moringa oleifera          │  moringa             │
    │  Piper nigrum              │  black pepper        │
    │  Aloe vera                 │  aloe                │
    │  Centella asiatica         │  gotu kola           │
    │  Withania somnifera        │  ashwagandha         │
    │  Cinnamomum verum          │  cinnamon            │
    │  Syzygium aromaticum       │  clove               │
    │  Thymus vulgaris           │  thyme               │
    │  Taxus brevifolia          │  pacific yew         │
    └────────────────────────────┴──────────────────────┘

    Partial names also work: "artemisia" matches "Artemisia annua".

3.3  Plant Photo Upload
─────────────────────────

    • The photo is OPTIONAL — you only need a plant name.
    • If you upload a photo, it appears beside the results for reference.
    • The photo is NOT analyzed by AI or image recognition.
    • Accepted formats: JPG, PNG, WebP.
    • The plant name you type is what drives the chemical lookup.

    WHY NO IMAGE RECOGNITION?
    Plant identification from photos requires a separate deep learning
    model (CNN) trained on thousands of herbarium images. This app
    focuses on molecular prediction, not image classification.

3.4  Plant Results
────────────────────

    The results page shows:
      • Your uploaded photo (if any) beside the plant name
      • Chemical structures of the first 8 compounds found
      • Prediction table: each compound's activity & toxicity
      • AI explanation (optional — click "Explain These Results")

    Download the full results as CSV for further analysis.


═══════════════════════════════════════════════════════════════════════════════
4. QUICK REFERENCE — Common Questions
═══════════════════════════════════════════════════════════════════════════════

Q: Do I need to train before predicting?
A: YES. Training creates the model (.pkl file). Without a trained model,
   there is nothing to predict with. Train once, predict many times.

Q: Can I use the same file for training and prediction?
A: NO. This is a critical ML mistake. Always predict on NEW compounds
   that were NOT in the training data.

Q: What does a score of 0.85 mean?
A: The model is 85% confident in its prediction. Scores close to 0.5
   mean the model is unsure — treat these predictions with caution.
   Because the model's probabilities are CALIBRATED, this percentage
   is now trustworthy and can be compared across compounds.

Q: What is probability calibration?
A: Random Forest scores naturally bunch up near 0 or 1, which makes
   them unreliable as percentages. The app calibrates them (isotonic or
   sigmoid) so a score of 0.80 genuinely means "80% likely". This is
   important when scores are combined into a ranking.

Q: What is scaffold-aware splitting?
A: Chemically similar compounds (same molecular scaffold) are kept on
   the same side of the train/test split. This stops the model from
   "cheating" by having a near-twin of a test compound in its training
   data — giving you honest evaluation scores instead of inflated ones.

Q: How many compounds do I need to train?
A: Minimum 20-30 for basic functionality. 100+ for reliable results.
   500+ for publication-quality models.

Q: Why are my test scores much lower than training scores?
A: This is overfitting. The model memorized the training data but
   can't generalize. Add more training data.

Q: The AI explanation costs tokens — can I skip it?
A: Yes, it's entirely optional. The prediction results are always shown.
   The AI only adds an educational explanation when you click the button.

Q: Can I train multiple models with different datasets?
A: YES. Give each training run a different name (e.g., "library1",
   "natural_products"). All models are saved and you pick which one
   to use from the dropdown on the Predict page.

Q: What happens if I train with the same name twice?
A: The old model is overwritten. A yellow warning banner confirms this.

Q: Why did hyperparameter tuning fail with "n_splits cannot be greater"?
A: Your dataset is too small. The app now auto-reduces CV folds for
   small datasets (e.g., from 5-fold to 3-fold). Add more compounds
   for better tuning results.

Q: Can I see what data I trained with after training?
A: YES. The training results page shows a "Training Dataset" table
   with the first 10 rows — Compound IDs, SMILES, and labels.

Q: Are my uploaded files saved permanently?
A: No. They're auto-cleaned after 24 hours. Trained models (.pkl files)
   are kept until you overwrite or delete them.

Q: Who can delete a trained model?
A: Only the OWNER (the user who trained it) or an ADMIN. Other users see
   a "Owner only" lock on models they don't own. The "default" and
   "legacy" starter models are protected (admin-only deletion).

Q: Can I train a model for something other than Activity/Toxicity?
A: YES. Put your label in ANY column (e.g., "Flavonoid_Label"), type
   that column name in the "Label Column Name" field, and optionally
   give it a custom "Task Name" like "Flavonoid vs Alkaloid".
   The pipeline is label-agnostic — it learns whatever you tell it to.

Q: What happens if my CSV has duplicate compounds?
A: The app automatically detects duplicate SMILES. If labels match,
   the first copy is kept. If labels conflict, all copies are removed
   and you'll see a warning to review your data.

Q: What do the topological indices (Wiener, Zagreb) mean?
A: They measure molecular shape and branching complexity. Higher Wiener
   index = more spread-out molecule. Higher Zagreb M₁ = more branching.
   These are always included in the feature matrix.


═══════════════════════════════════════════════════════════════════════════════
5. CSV FILE FORMATS — Quick Copy-Paste Templates
═══════════════════════════════════════════════════════════════════════════════

5.1  Training CSV Template
────────────────────────────

    Copy this into a file named "training_data.csv":

    Compound_ID,Smiles,Activity_Label,Toxicity_Label
    CMP001,CCO,1,0
    CMP002,CCCC,1,1
    CMP003,CC(=O)O,0,0
    CMP004,C1=CC=CC=C1,0,1
    CMP005,CCN(CC)CC,1,0
    CMP006,CN1C=NC2=C1C(=O)N(C(=O)N2C)C,0,0
    CMP007,CC(C)CC1=CC=C(C=C1)C(C)C(=O)O,1,1
    CMP008,C1CC1,0,0
    CMP009,CCCCN,1,0
    CMP010,CCCCCCCC,0,1

    Activity_Label:  1 = Active against OXA-23, 0 = Inactive
    Toxicity_Label:  1 = Toxic to humans, 0 = Safe


5.2  Prediction CSV Template
──────────────────────────────

    Copy this into a file named "predict_these.csv":

    Compound_ID,Smiles
    NEW001,CCN(CC)CC
    NEW002,CN1C=NC2=C1C(=O)N(C(=O)N2C)C
    NEW003,CC(C)CC1=CC=C(C=C1)C(C)C(=O)O
    NEW004,C1CCCCC1
    NEW005,COC1=CC=C(C=C1)OC

    Only Smiles is required. Compound_ID is optional but helpful.


═══════════════════════════════════════════════════════════════════════════════
6. INTERPRETING SCORES — A Student's Guide
═══════════════════════════════════════════════════════════════════════════════

    Prediction Type     Score    Interpretation
    ───────────────     ─────    ──────────────
    Activity_Score      > 0.8    Very likely ACTIVE — candidate for testing
    Activity_Score      0.5-0.8  Possibly active — moderate confidence
    Activity_Score      < 0.5    Likely INACTIVE — low priority

    Toxicity_Score      > 0.8    HIGH toxicity risk — handle with care
    Toxicity_Score      0.5-0.8  Moderate toxicity concern
    Toxicity_Score      < 0.5    Likely SAFE — low toxicity risk

    ⚠️  REMEMBER: These are COMPUTATIONAL predictions, not experimental
        results. A high activity score does not mean the compound WILL
        work in the lab — it means the model thinks it's worth testing.


═══════════════════════════════════════════════════════════════════════════════
7. HOW RDKit WORKS — Behind the Scenes
═══════════════════════════════════════════════════════════════════════════════

    This section explains how the app converts SMILES into numbers the
    Random Forest can learn from. Understanding this helps you interpret
    feature importance graphs and debug poor predictions.

7.1  What is RDKit?
─────────────────────

    RDKit is an open-source cheminformatics toolkit — you give it a
    chemical structure (SMILES) and it calculates numerical properties.

    Analogy: RDKit is a translator. It takes the "language" of chemistry
    (SMILES) and converts it to the "language" of math (numbers), which
    machine learning algorithms understand.

7.2  Step-by-Step: SMILES → Numbers → Training
────────────────────────────────────────────────

    STEP 1 — PARSE THE MOLECULE

    SMILES: CCO
    RDKit reads:  C — C — O — H  (+ implicit hydrogens)
    It builds an internal graph where atoms = nodes, bonds = edges.

    STEP 2 — COMPUTE 211 DESCRIPTORS

    From the molecular graph, RDKit calculates everything:

    ┌──────────────────────┬────────────────────┬──────────────────┐
    │  Descriptor          │  What It Measures   │  Ethanol Value   │
    ├──────────────────────┼────────────────────┼──────────────────┤
    │  MolWt               │  Molecular weight   │  46.07           │
    │  MolLogP             │  Lipophilicity      │  -0.24           │
    │  TPSA                │  Polar surface area │  20.23           │
    │  NumHDonors          │  H-bond donors      │  1               │
    │  NumHAcceptors       │  H-bond acceptors   │  1               │
    │  NumRotatableBonds   │  Flexibility        │  0               │
    │  FractionCSP3        │  sp3 carbon ratio   │  1.0             │
    │  RingCount           │  Number of rings    │  0               │
    │  NumAromaticRings    │  Aromatic rings     │  0               │
    │  BalabanJ            │  Molecular shape    │  0.0             │
    │  WienerIndex         │  Compactness        │  1.0             │
    │  ... 200+ more       │                    │                  │
    └──────────────────────┴────────────────────┴──────────────────┘

    Compare with BENZENE (C1=CC=CC=C1):
    MolWt=78.1, NumAromaticRings=1, RingCount=1, FractionCSP3=0.0

    This is why benzene and ethanol are easily separated — their
    descriptors are completely different.

    STEP 3 — BUILD THE FEATURE MATRIX

    │ Smiles │ MolWt │ MolLogP │ TPSA │ Rings │ ... │ Label │
    │ CCO    │  46.1 │  -0.24  │ 20.2 │   0   │ ... │   0   │
    │ C1=C.. │  78.1 │   2.13  │  0.0 │   1   │ ... │   1   │
    │ CC(=O) │  60.1 │  -0.17  │ 37.3 │   0   │ ... │   0   │
    90 rows × 211 columns = 18,990 data points to learn from.

    STEP 4 — RANDOM FOREST LEARNS RULES

    The model finds patterns like:
    • "If NumAromaticRings > 0 AND MolLogP > 1.5 → Active"
    • "If FractionCSP3 > 0.8 AND MolWt < 100 → Inactive"

    These rules are stored in the .pkl file.

    STEP 5 — PREDICT NEW COMPOUNDS

    New SMILES → same RDKit descriptors → model applies its rules → result.

7.3  What Makes a Good Feature?
─────────────────────────────────

    The Feature Importance chart ranks descriptors by usefulness.
    Chemically meaningful features at the top = good sign.

    │ Rank │ Feature           │ Why It Matters                     │
    │  1   │ NumAromaticRings  │ Aromatic rings affect drug binding │
    │  2   │ MolLogP           │ Lipophilicity affects absorption   │
    │  3   │ TPSA              │ Polar surface affects permeability │
    │  4   │ NumHDonors        │ H-bonds affect target interaction  │
    │  5   │ FractionCSP3      │ 3D shape affects binding pocket    │

    If top features make chemical sense, the model found real patterns
    — not random noise.

7.4  Compounds vs. Descriptors — The Overfitting Problem
──────────────────────────────────────────────────────────

    211 descriptors but only 10 compounds? The model has more "questions"
    than "answers" — it memorizes but cannot generalize.

    │ Compounds │ Expected Model Quality                    │
    │ 10-30     │ Demo only — expect overfitting            │
    │ 30-100    │ Moderate — some patterns emerge           │
    │ 100-500   │ Good — reliable predictions              │
    │ 500+      │ Excellent — publication quality           │

    Rule of thumb: 3-5 compounds per important descriptor.
    Since ~10-15 descriptors usually matter, 50+ compounds is solid.

═══════════════════════════════════════════════════════════════════════════════


═══════════════════════════════════════════════════════════════════════════════

7. HOW RDKit WORKS — Behind the Scenes
═══════════════════════════════════════════════════════════════════════════════

    This section explains how the app converts a SMILES string into
    numbers the Random Forest can learn from. Understanding this helps
    you interpret feature importance graphs and debug bad predictions.

7.1  What is RDKit?
─────────────────────

    RDKit is an open-source cheminformatics toolkit. It reads chemical
    structures (SMILES) and computes numerical properties — exactly
    what machine learning needs as input.

    Analogy: RDKit is like a translator. It takes the "language" of
    chemistry (SMILES) and translates it into the "language" of math
    (numbers), which the Random Forest understands.

7.2  Step-by-Step: SMILES → Numbers → Training
────────────────────────────────────────────────

    STEP 1: PARSE THE MOLECULE
    ───────────────────────────
    SMILES:    CCO
    RDKit reads this as:  C — C — O — H (plus implicit hydrogens)
    It builds an internal graph: atoms are nodes, bonds are edges.

    STEP 2: ADD HYDROGENS (optional)
    ──────────────────────────────────
    Ethanol (CCO) has 2 carbons, 1 oxygen, and 6 hydrogens.
    RdKit can add explicit hydrogens for certain calculations.

    STEP 3: COMPUTE DESCRIPTORS
    ─────────────────────────────
    RDKit calculates 211 numbers from the molecular graph:

    ┌──────────────────────┬────────────────────┬──────────────────┐
    │  Descriptor          │  What It Measures   │  Ethanol Value   │
    ├──────────────────────┼────────────────────┼──────────────────┤
    │  MolWt               │  Molecular weight   │  46.07 g/mol     │
    │  MolLogP             │  Lipophilicity      │  -0.24           │
    │  TPSA                │  Polar surface area │  20.23 Å²        │
    │  NumHDonors          │  H-bond donors      │  1               │
    │  NumHAcceptors       │  H-bond acceptors   │  1               │
    │  NumRotatableBonds   │  Flexibility        │  0               │
    │  FractionCSP3        │  sp3 carbon ratio   │  1.0             │
    │  RingCount           │  Number of rings    │  0               │
    │  NumAromaticRings    │  Aromatic rings     │  0               │
    │  BalabanJ            │  Molecular shape    │  0.0             │
    │  WienerIndex         │  Compactness        │  1.0             │
    │  ... and ~200 more   │                     │                  │
    └──────────────────────┴────────────────────┴──────────────────┘

    Compare to BENZENE (C1=CC=CC=C1):
    ┌──────────────────────┬────────────────────┐
    │  Descriptor          │  Benzene Value     │
    ├──────────────────────┼────────────────────┤
    │  MolWt               │  78.11 g/mol       │
    │  NumAromaticRings    │  1                 │
    │  RingCount           │  1                 │
    │  FractionCSP3        │  0.0               │
    │  NumHDonors          │  0                 │
    └──────────────────────┴────────────────────┘

    This is why ethanol and benzene are easily separated — their
    descriptors are very different.

    STEP 4: BUILD A FEATURE MATRIX
    ────────────────────────────────
    For 90 training compounds:
    ┌────────┬───────┬────────┬──────┬──────┬─────┬─────┐
    │ Smiles │ MolWt │ MolLogP│ TPSA │ Rings│ ... │Label│
    ├────────┼───────┼────────┼──────┼──────┼─────┼─────┤
    │ CCO    │  46.1 │  -0.24 │ 20.2 │   0  │ ... │  0  │
    │ C1=CC..│  78.1 │   2.13 │  0.0 │   1  │ ... │  1  │
    │ CC(=O)O│  60.1 │  -0.17 │ 37.3 │   0  │ ... │  0  │
    └────────┴───────┴────────┴──────┴──────┴─────┴─────┘
    90 rows × 211 columns = 18,990 numbers for the model to learn from.

    STEP 5: TRAIN THE RANDOM FOREST
    ─────────────────────────────────
    The Random Forest reads the feature matrix and learns rules like:
    • "If NumAromaticRings > 0 AND MolLogP > 1.5 → likely Active"
    • "If FractionCSP3 > 0.8 AND MolWt < 100 → likely Inactive"

    These rules are stored in the .pkl model file.

    STEP 6: PREDICT NEW COMPOUNDS
    ───────────────────────────────
    New SMILES → same RDKit descriptors → model applies its rules → prediction.

7.3  What Makes a Good Feature?
─────────────────────────────────

    The "Feature Importance" chart shows which descriptors the model
    relied on most. Chemically meaningful features at the top = good sign.

    │ Rank │ Feature           │ Why It Matters                     │
    │──────│───────────────────│────────────────────────────────────│
    │  1   │ NumAromaticRings  │ Aromatic rings affect drug binding │
    │  2   │ MolLogP           │ Lipophilicity affects absorption   │
    │  3   │ TPSA              │ Polar surface affects permeability │
    │  4   │ NumHDonors        │ H-bonds affect target interaction  │
    │  5   │ FractionCSP3      │ 3D shape affects binding pocket    │

    If the top features are chemically interpretable, the model is
    learning real structure-activity relationships — not noise.

7.4  Data Size vs. Descriptors
────────────────────────────────

    With 211 descriptors but only 10 compounds, the model has more
    "questions" than "answers" — it can memorize but not generalize.
    This causes overfitting.

    ┌─────────────────────┬──────────────────────────────────┐
    │  Compounds          │  Expected Model Quality          │
    ├─────────────────────┼──────────────────────────────────┤
    │  10-30              │  Basic demo — expect overfitting │
    │  30-100             │  Moderate — some patterns emerge │
    │  100-500            │  Good — reliable predictions     │
    │  500+               │  Excellent — publication quality │
    └─────────────────────┴──────────────────────────────────┘

    Rule of thumb: You want at least 3-5 compounds per descriptor
    you expect to be important. Since only ~10-15 descriptors usually
    matter, 50+ compounds is a reasonable minimum.

═══════════════════════════════════════════════════════════════════════════════
