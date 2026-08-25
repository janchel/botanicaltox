╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║     CRABLOX — USER GUIDE                                                     ║
║     How to Predict Plant Compound Toxicity                              ║
║     Version 3.2 — August 2026                                                  ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝


WHAT IS THIS APP?
─────────────────
CRABLOX is a Machine Learning prediction tool for plant toxicity. It predicts the toxicity of
chemical compounds found in plants:

  1. TOXICITY   — Is this compound likely toxic to humans?
  2. ACTIVITY   — Does this compound have biological activity?

It uses Random Forest classifiers trained on molecular descriptors calculated
by RDKit (a chemistry toolkit). Students upload compound data, train models,
and get predictions — all through a web browser.

⚠️  IMPORTANT: These are COMPUTATIONAL predictions, not lab results.
    Always validate predictions with experimental testing.


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
    │  217 STANDARD DESCRIPTORS (computed automatically)          │
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
    │  4 TOPOLOGICAL INDICES (also automatic)                     │
    │                                                              │
    │  Wiener Index   — molecular compactness                     │
    │  Zagreb M1/M2   — branching complexity                      │
    │  Balaban J      — molecular shape                           │
    │                                                              │
    │  TOTAL: 221 numerical features from ONE SMILES string       │
    └──────────────────────────────────────────────────────────────┘

    ⚠️  Requires RDKit 2026.03+ (conda-forge). The old pip rdkit-pypi
        package (2022.09) only gives 208 descriptors and does NOT
        match the Colab notebook's descriptor set.

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


1.5  Download Test Results (CSV)
──────────────────────────────────

    On the training results page, each task now has two extra download buttons
    (this mirrors the research notebook's 1.6a/2.6a exports):

    ┌─────────────────────────────────────────────────────────────────┐
    │  ⬇️ TEST PREDICTIONS (CSV)                                      │
    │                                                                 │
    │  One row per compound in the held-out TEST set:                 │
    │     Compound_ID · Smiles · True_Label                           │
    │     Predicted_Label · Predicted_Proba                           │
    │                                                                 │
    │  Perfect for error analysis and your Chapter IV appendix —      │
    │  which test compounds did the model get wrong, and why?         │
    └─────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────┐
    │  ⬇️ TEST METRICS (CSV)                                          │
    │                                                                 │
    │  A one-row summary of the test-set numbers shown on screen      │
    │  (accuracy, ROC-AUC, precision, recall, F1, MCC) — ready to     │
    │  paste into your report instead of typing them by hand.         │
    └─────────────────────────────────────────────────────────────────┘

    Files are named like `toxicity_test_predictions.csv` /
    `toxicity_test_metrics.csv` (and the same for `activity_...`).


1.6  The Student Research Datasets (datasets/)
────────────────────────────────────────────────

    The real datasets used in the STEC research notebook
    (`final_destination.ipynb`) are included so you can reproduce the
    study's models directly in the web app:

      datasets/toxicity_compounds.csv
          → 1,156 FDA drug records (DILIst) — for the TOXICITY task
      datasets/_ACTIVITY__105_COMPOUNDS_FINAL_TRAINING.csv
          → 105 compounds (30 active / 75 inactive) against OXA-family
            β-lactamases — for the ACTIVITY task
      datasets/prediction_compounds.xlsx
          → 289-row flavonoid screening library — for PREDICT / RANK

    Workflow:  Train on the two training files (both tasks), then
    PREDICT with `prediction_compounds.xlsx`, and check the RANK page
    for the Priority = Activity × Safety shortlist.


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

    Just like training, RDKit automatically computes all 221 molecular
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
4. RANKING — Find the Best Drug Candidates
═══════════════════════════════════════════════════════════════════════════════

    The Ranking feature sorts your compounds by a PRIORITY SCORE that
    balances activity AND safety — so the top compounds are both likely
    to work AND likely to be safe.

    This is the key feature for drug discovery: you want compounds that
    are BOTH active against the target AND non-toxic to humans.

4.1  How Ranking Works
───────────────────────

    The app calculates three scores:

    ┌──────────────────┬─────────────────────────────────────────────────┐
    │  Score           │  Formula                                      │
    ├──────────────────┼─────────────────────────────────────────────────┤
    │  Activity_Score  │  P(active against OXA-23) — from ML model    │
    │  Toxicity_Score  │  P(toxic to humans) — from ML model          │
    │  Safety_Score    │  1 − Toxicity_Score = P(non-toxic)           │
    │  Priority_Score  │  Activity_Score × Safety_Score               │
    └──────────────────┴─────────────────────────────────────────────────┘

    WHY MULTIPLY?  (Derringer & Suich, 1980; Wager et al., 2010)
    Both terms are "higher = better" probabilities in [0, 1]. Multiplying
    them rewards compounds only when they score well on BOTH criteria at
    once — rather than letting a high activity score compensate for high
    toxicity.

    EXAMPLE:
      Compound A: Activity=0.9, Toxicity=0.2 → Safety=0.8 → Priority=0.72
      Compound B: Activity=0.9, Toxicity=0.8 → Safety=0.2 → Priority=0.18
      Compound A ranks HIGHER because it's both active AND safe.

4.2  Sample Input Data (CSV Format)
─────────────────────────────────────

    Create a CSV file with a Smiles column:

    ┌──────────────┬──────────────────────────────────────────┐
    │ Compound_ID  │ Smiles                                   │
    ├──────────────┼──────────────────────────────────────────┤
    │ NEW001       │ CCN(CC)CC                                │
    │ NEW002       │ CN1C=NC2=C1C(=O)N(C(=O)N2C)C             │
    │ NEW003       │ CC(C)CC1=CC=C(C=C1)C(C)C(=O)O            │
    └──────────────┴──────────────────────────────────────────┘

    REQUIRED:  Smiles column
    OPTIONAL:  Compound_ID (preserved in output)

    📁 SAMPLE FILE: datasets/prediction_compounds.xlsx (289 compounds)

4.3  Step-by-Step Usage
─────────────────────────

    1. Open the web app → click "Rank Compounds"
    2. Select your trained model from the dropdown
       (e.g., "medchem (Activity, Toxicity)")
    3. Upload your compound file (CSV or Excel with SMILES column)
    4. OPTIONAL: Toggle "Deduplicate by structure" checkbox:
       • CHECKED (default): Removes structurally identical compounds
         before ranking → 15 UNIQUE top compounds
       • UNCHECKED: Keeps all duplicates → matches notebook behavior
         (may show same compound multiple times in top 15)
    5. Click "Rank Top Compounds"

4.4  Sample Output — Top 15 Ranked Compounds
────────────────────────────────────────────

    The results page shows:

    ┌────────┬──────────────┬──────────┬──────────┬──────────┬──────────┐
    │ Rank   │ Compound_ID  │ Activity │ Toxicity │ Safety   │ Priority │
    │        │              │ Score    │ Score    │ Score    │ Score    │
    ├────────┼──────────────┼──────────┼──────────┼──────────┼──────────┤
    │ 🥇 1   │ 10399655     │ 0.914    │ 0.2755   │ 0.7245   │ 0.6622   │
    │ 🥈 2   │ 4788         │ 0.8898   │ 0.3534   │ 0.6466   │ 0.5753   │
    │ 🥉 3   │ 1889         │ 0.9138   │ 0.3978   │ 0.6022   │ 0.5503   │
    │ 4      │ 73201        │ 0.9195   │ 0.4294   │ 0.5706   │ 0.5247   │
    │ 5      │ 439246       │ 0.9077   │ 0.4414   │ 0.5586   │ 0.5070   │
    └────────┴──────────────┴──────────┴──────────┴──────────┴──────────┘

    INTERPRETATION (Medical Standard):
    • Priority_Score > 0.5  → EXCELLENT candidate (both active & safe)
    • Priority_Score 0.3-0.5 → GOOD candidate
    • Priority_Score < 0.3  → LOW priority (weak on at least one)

4.5  Medical Standard Interpretation
────────────────────────────────────

    In pharmaceutical research, a drug candidate must pass BOTH efficacy
    AND safety thresholds:

    ┌─────────────────────┬──────────────────────────────────────────────┐
    │  Priority_Score     │  Medical Interpretation                     │
    ├─────────────────────┼──────────────────────────────────────────────┤
    │  > 0.7              │  EXCELLENT — Top priority for testing       │
    │  0.5 - 0.7          │  VERY GOOD — Strong candidate               │
    │  0.3 - 0.5          │  MODERATE — Consider for further study      │
    │  0.1 - 0.3          │  WEAK — Low priority                        │
    │  < 0.1              │  POOR — Not recommended                     │
    └─────────────────────┴──────────────────────────────────────────────┘

    WHY THIS MATTERS:
    A compound with high activity (0.9) but high toxicity (0.8) gets a
    Priority_Score of 0.18 — too dangerous for clinical use. The Priority
    Score ensures you don't advance toxic compounds just because they're
    active.

4.6  Deduplication Toggle — Important!
────────────────────────────────────

    ⚠️  The ranking has a DEDUPLICATION TOGGLE checkbox.

    CHECKED (default):  Removes structurally identical compounds before
                        ranking. You get 15 UNIQUE top compounds.
                        ✓ Scientifically sound for drug discovery.

    UNCHECKED:  Keeps all duplicates. Shows all rows including repeated
                compounds. This matches the student notebook behavior
                (final_destination.ipynb) for comparison purposes.

    EXAMPLE WITH DUPLICATES (toggle OFF):
      Rank 1: Compound_A  (Priority=0.95)
      Rank 2: Compound_B  (Priority=0.90)
      Rank 3: Compound_A  (Priority=0.95) ← DUPLICATE!
      Rank 4: Compound_A  (Priority=0.95) ← DUPLICATE!

    EXAMPLE WITHOUT DUPLICATES (toggle ON - default):
      Rank 1: Compound_A  (Priority=0.95)
      Rank 2: Compound_B  (Priority=0.90)
      Rank 3: Compound_C  (Priority=0.85)
      ... (all unique compounds)

    RECOMMENDATION:
    • For real drug discovery: USE DEDUPLICATION (default)
    • For comparing with notebook: TURN OFF deduplication

4.7  Download Results
───────────────────────

    Click "Download CSV" to save the complete ranked list. The CSV
    contains ALL compounds (not just top 15), sorted by Priority Score
    from highest to lowest.

    The CSV includes:
    - Compound_ID, Smiles, Source_File
    - Activity_Prediction, Activity_Score
    - Toxicity_Prediction, Toxicity_Score
    - Safety_Score, Priority_Score
    - Chemical_Class, Activity_Label_Text, Toxicity_Label_Text


═══════════════════════════════════════════════════════════════════════════════
5. QUICK REFERENCE — Common Questions
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

Q: Why does the ranking show the same compound multiple times?
A: The ranking has a "Deduplicate by structure" checkbox (checked by
   default). When UNCHECKED, it keeps all duplicates — so the same
   compound may appear multiple times in the top 15. This matches the
   student notebook behavior. For real drug discovery, keep it CHECKED
   to remove duplicates and get 15 unique top compounds.

Q: What do the topological indices (Wiener, Zagreb) mean?
A: They measure molecular shape and branching complexity. Higher Wiener
   index = more spread-out molecule. Higher Zagreb M₁ = more branching.
   These are always included in the feature matrix.


═══════════════════════════════════════════════════════════════════════════════
6. CSV FILE FORMATS — Quick Copy-Paste Templates
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
7. INTERPRETING SCORES — A Student's Guide
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
8. HOW RDKit WORKS — Behind the Scenes
═══════════════════════════════════════════════════════════════════════════════

    This section explains how the app converts a SMILES string into
    numbers the Random Forest can learn from. Understanding this helps
    you interpret feature importance graphs and debug bad predictions.

8.1  What is RDKit?
─────────────────────

    RDKit is an open-source cheminformatics toolkit. It reads chemical
    structures (SMILES) and computes numerical properties — exactly
    what machine learning needs as input.

    Analogy: RDKit is like a translator. It takes the "language" of
    chemistry (SMILES) and translates it into the "language" of math
    (numbers), which the Random Forest understands.

8.2  Step-by-Step: SMILES → Numbers → Training
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
    RDKit calculates 221 numbers from the molecular graph:

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
    90 rows × 221 columns = 19,890 numbers for the model to learn from.

    STEP 5: TRAIN THE RANDOM FOREST
    ─────────────────────────────────
    The Random Forest reads the feature matrix and learns rules like:
    • "If NumAromaticRings > 0 AND MolLogP > 1.5 → likely Active"
    • "If FractionCSP3 > 0.8 AND MolWt < 100 → likely Inactive"

    These rules are stored in the .pkl model file.

    STEP 6: PREDICT NEW COMPOUNDS
    ───────────────────────────────
    New SMILES → same RDKit descriptors → model applies its rules → prediction.

8.3  What Makes a Good Feature?
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

8.4  Data Size vs. Descriptors
────────────────────────────────

    With 221 descriptors but only 10 compounds, the model has more
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
