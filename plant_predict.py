"""
plant_predict.py
----------------
Look up known chemical compounds from medicinal plants.
Returns SMILES strings ready for prediction.

No API calls — all compound data is embedded for reliability and speed.
"""

# ── Plant → Known Compounds (with SMILES) ──────────────────────────────────
# Each entry: common_name → [{name, smiles, formula}]

PLANT_COMPOUNDS = {
    "artemisia annua": [
        {"name": "Artemisinin", "smiles": "CC1CCC2C(C(=O)OC3C2C4(CCC(C4)C(C)(C)O3)C)C", "formula": "C15H22O5"},
        {"name": "Arteannuin B", "smiles": "CC1CCC2C(C(=O)OC3C2C4(CCC(C4)C=C3)C)C", "formula": "C15H20O3"},
        {"name": "Artemisinic acid", "smiles": "CC1CCC2C(C(=O)O)C3(C=CC(C3)C(C)(C)O)CC2=C1C", "formula": "C15H22O3"},
        {"name": "Scopoletin", "smiles": "COC1=C(C=C2C(=C1)C=CC(=O)O2)O", "formula": "C10H8O4"},
        {"name": "Artemetin", "smiles": "COC1=C(C=C(C=C1)C2=CC(=O)C3=C(O2)C(=C(C=C3O)OC)OC)OC", "formula": "C20H20O8"},
        {"name": "Chrysosplenol D", "smiles": "COC1=C(C=C(C=C1)C2=CC(=O)C3=C(O2)C(=C(C=C3O)OC)O)OC", "formula": "C19H18O8"},
    ],
    "curcuma longa": [
        {"name": "Curcumin", "smiles": "COC1=C(C=CC(=C1)C=CC(=O)CC(=O)C=CC2=CC(=C(C=C2)O)OC)O", "formula": "C21H20O6"},
        {"name": "Demethoxycurcumin", "smiles": "COC1=C(C=CC(=C1)C=CC(=O)CC(=O)C=CC2=CC=C(C=C2)O)O", "formula": "C20H18O5"},
        {"name": "Bisdemethoxycurcumin", "smiles": "C1=CC(=CC=C1C=CC(=O)CC(=O)C=CC2=CC=C(C=C2)O)O", "formula": "C19H16O4"},
        {"name": "Turmerone", "smiles": "CC1=CC(=O)CC(C1)C(C)CC2=CC=C(C=C2)C", "formula": "C15H20O"},
    ],
    "azadirachta indica": [
        {"name": "Azadirachtin", "smiles": "CC(=O)OC1CC2C3(C=CC(=O)OC3)C4(C(C2(C5C1(C56C(O6)C(=O)OC)O)C)C(=O)OC4C)C", "formula": "C35H44O16"},
        {"name": "Nimbin", "smiles": "CC(=O)OC1CC2C3(C=CC(=O)OC3)C4(C(C2(C5C1(C56C(=O)OC6)C)C)C(=O)OC4C)C", "formula": "C30H36O9"},
        {"name": "Gedunin", "smiles": "CC1(C=CC(=O)C2(C1CC3C4(C2C(=O)C=C5C4(CCC5(C)C)C)C)C)C", "formula": "C28H34O7"},
    ],
    "zingiber officinale": [
        {"name": "6-Gingerol", "smiles": "CCCCCC(CC(=O)CCC1=CC(=C(C=C1)O)OC)O", "formula": "C17H26O4"},
        {"name": "6-Shogaol", "smiles": "CCCCCC=CC(=O)CCC1=CC(=C(C=C1)O)OC", "formula": "C17H24O3"},
        {"name": "Zingerone", "smiles": "CC(=O)CCC1=CC(=C(C=C1)O)OC", "formula": "C11H14O3"},
        {"name": "Zingiberene", "smiles": "CC1=CCC(C=C1)CCC(C)C=C", "formula": "C15H24"},
    ],
    "allium sativum": [
        {"name": "Allicin", "smiles": "C=CCS(=O)SCC=C", "formula": "C6H10OS2"},
        {"name": "Diallyl disulfide", "smiles": "C=CCSSCC=C", "formula": "C6H10S2"},
        {"name": "S-Allyl cysteine", "smiles": "C=CCSCC(C(=O)O)N", "formula": "C6H11NO2S"},
    ],
    "camellia sinensis": [
        {"name": "Epigallocatechin gallate", "smiles": "C1C(C(OC2=CC(=CC(=C21)O)O)C3=CC(=C(C(=C3)O)O)O)OC(=O)C4=CC(=C(C(=C4)O)O)O", "formula": "C22H18O11"},
        {"name": "Caffeine", "smiles": "CN1C=NC2=C1C(=O)N(C(=O)N2C)C", "formula": "C8H10N4O2"},
        {"name": "Epicatechin", "smiles": "C1C(C(OC2=CC(=CC(=C21)O)O)C3=CC(=C(C=C3)O)O)O", "formula": "C15H14O6"},
    ],
    "cannabis sativa": [
        {"name": "Cannabidiol", "smiles": "CCCCCC1=CC(=C(C(=C1)O)C2C=C(CCC2C(=C)C)C)O", "formula": "C21H30O2"},
        {"name": "Tetrahydrocannabinol", "smiles": "CCCCCC1=CC2=C(C3C=C(CCC3C(O2)(C)C)C)C(=C1)O", "formula": "C21H30O2"},
        {"name": "Cannabigerol", "smiles": "CCCCCC1=CC(=C(C(=C1)O)CC=C(C)CCC=C(C)C)O", "formula": "C21H32O2"},
    ],
    "panax ginseng": [
        {"name": "Ginsenoside Rb1", "smiles": "CC(=CCCC(C)(C1CCC2(C1C(CC3C2(CCC4C3(CCC(C4(C)C)OC5C(C(C(C(O5)CO)O)O)OC6C(C(C(CO6)O)O)O)C)C)O)C)OC7C(C(C(C(O7)CO)O)O)O)C", "formula": "C54H92O23"},
        {"name": "Ginsenoside Rg1", "smiles": "CC(=CCCC(C)(C1CCC2(C1C(CC3C2(CCC4C3(CCC(C4(C)C)OC5C(C(C(C(O5)CO)O)O)O)C)C)O)C)O)C", "formula": "C42H72O14"},
    ],
    "ginkgo biloba": [
        {"name": "Ginkgolide B", "smiles": "CC1C2C3C4(C(C1O)C(=O)OC5C4(O6)C(C2(C)C)(O6)C35O)C(C)(C)C", "formula": "C20H24O10"},
        {"name": "Quercetin", "smiles": "C1=CC(=C(C=C1C2=C(C(=O)C3=C(C=C(C=C3O2)O)O)O)O)O", "formula": "C15H10O7"},
        {"name": "Kaempferol", "smiles": "C1=CC(=CC=C1C2=C(C(=O)C3=C(C=C(C=C3O2)O)O)O)O", "formula": "C15H10O6"},
    ],
    "catharanthus roseus": [
        {"name": "Vinblastine", "smiles": "CCC1(CC2CN3CCC4=C(C5=C(C=CC(=C5)OC)N4)C(C3CC2)(C(=O)OC)O)C(=O)N(C6CC7C8(C(=O)OC(C8O)(C(=O)OC)C(=O)N9CCCC9C7=CC=C6)C)C1=O", "formula": "C46H58N4O9"},
        {"name": "Vincristine", "smiles": "CCC1(CC2CN3CCC4=C(C5=C(C=CC(=C5)OC)N4)C(C3CC2)(C(=O)OC)O)C(=O)N(C6CC7C8(C(=O)OC(C8O)(C(=O)OC)C(=O)N9CCCC9C7=CC=C6)C)C1=O", "formula": "C46H56N4O10"},
        {"name": "Ajmalicine", "smiles": "COC(=O)C1=COC(C2C1CCN3C2CC4=C(C3)C5=CC=CC=C5N4)C", "formula": "C21H24N2O3"},
    ],
    "salvia officinalis": [
        {"name": "Carnosic acid", "smiles": "CC(C)C1=C(C(=C2CCC3C(CCC(C3(C)C)C(=O)O)(C2=C1)C)O)O", "formula": "C20H28O4"},
        {"name": "Rosmarinic acid", "smiles": "C1=CC(=C(C=C1CC(C(=O)O)OC(=O)C=CC2=CC(=C(C=C2)O)O)O)O", "formula": "C18H16O8"},
        {"name": "Ursolic acid", "smiles": "CC1CCC2(CCC3(C(=CCC4C3(CCC5C4(CCC(C5(C)C)O)C)C)C2C1C)C)C(=O)O", "formula": "C30H48O3"},
    ],
    "piper nigrum": [
        {"name": "Piperine", "smiles": "C1CCN(CC1)C(=O)C=CC=CC2=CC3=C(C=C2)OCO3", "formula": "C17H19NO3"},
        {"name": "Beta-caryophyllene", "smiles": "CC1=CCCC(=C)CCC2C(C1)C2(C)C", "formula": "C15H24"},
    ],
    "aloe vera": [
        {"name": "Aloin", "smiles": "C1=CC2=C(C(=C1)O)C(=O)C3=C(C2=O)C=C(C=C3O)COC4C(C(C(C(O4)CO)O)O)O", "formula": "C21H22O9"},
        {"name": "Aloe-emodin", "smiles": "C1=CC2=C(C(=C1)O)C(=O)C3=C(C2=O)C=C(C=C3O)CO", "formula": "C15H10O5"},
        {"name": "Emodin", "smiles": "CC1=CC(=C2C(=C1)C(=O)C3=C(C2=O)C=C(C=C3O)O)O", "formula": "C15H10O5"},
    ],
    "moringa oleifera": [
        {"name": "Quercetin", "smiles": "C1=CC(=C(C=C1C2=C(C(=O)C3=C(C=C(C=C3O2)O)O)O)O)O", "formula": "C15H10O7"},
        {"name": "Kaempferol", "smiles": "C1=CC(=CC=C1C2=C(C(=O)C3=C(C=C(C=C3O2)O)O)O)O", "formula": "C15H10O6"},
        {"name": "Rutin", "smiles": "CC1C(C(C(C(O1)OCC2C(C(C(C(O2)OC3=C(OC4=CC(=CC(=C4C3=O)O)O)C5=CC(=C(C=C5)O)O)O)O)O)O)O)O", "formula": "C27H30O16"},
    ],
    "withania somnifera": [
        {"name": "Withaferin A", "smiles": "CC1=C(C(=O)OC2C1(C3CCC4C(C3(CC2)C)CCC5C4(CCC(=O)C5(C)C)C)C)C", "formula": "C28H38O6"},
        {"name": "Withanolide A", "smiles": "CC1=C(C(=O)OC2C1(C3CCC4C(C3(CC2O)C)CCC5C4(CCC(=O)C5(C)C)C)C)C", "formula": "C28H38O7"},
    ],
    "cinnamomum verum": [
        {"name": "Cinnamaldehyde", "smiles": "C1=CC=C(C=C1)C=CC=O", "formula": "C9H8O"},
        {"name": "Eugenol", "smiles": "COC1=C(C=CC(=C1)CC=C)O", "formula": "C10H12O2"},
        {"name": "Coumarin", "smiles": "C1=CC=C2C(=C1)C=CC(=O)O2", "formula": "C9H6O2"},
    ],
    "thymus vulgaris": [
        {"name": "Thymol", "smiles": "CC1=CC(=C(C=C1)C(C)C)O", "formula": "C10H14O"},
        {"name": "Carvacrol", "smiles": "CC1=CC(=C(C=C1)C(C)C)O", "formula": "C10H14O"},
        {"name": "p-Cymene", "smiles": "CC1=CC=C(C=C1)C(C)C", "formula": "C10H14"},
    ],
    "syzygium aromaticum": [
        {"name": "Eugenol", "smiles": "COC1=C(C=CC(=C1)CC=C)O", "formula": "C10H12O2"},
        {"name": "Beta-caryophyllene", "smiles": "CC1=CCCC(=C)CCC2C(C1)C2(C)C", "formula": "C15H24"},
    ],
    "centella asiatica": [
        {"name": "Asiaticoside", "smiles": "CC1C(C(C(C(O1)OC2C(C(COC2O)OC(=O)C34CCC(CC3)C(=C)C4C5CCC6(C5(CC7C6(CCC(C7(C)CO)O)C)C)C)O)O)O)O", "formula": "C48H78O19"},
        {"name": "Asiatic acid", "smiles": "CC1CCC2(CCC3(C(=CCC4C3(CCC5C4(CCC(C5(C)CO)O)C)C)C2C1C)C)C(=O)O", "formula": "C30H48O5"},
    ],
    "ocimum sanctum": [
        {"name": "Eugenol", "smiles": "COC1=C(C=CC(=C1)CC=C)O", "formula": "C10H12O2"},
        {"name": "Ursolic acid", "smiles": "CC1CCC2(CCC3(C(=CCC4C3(CCC5C4(CCC(C5(C)C)O)C)C)C2C1C)C)C(=O)O", "formula": "C30H48O3"},
        {"name": "Apigenin", "smiles": "C1=CC(=CC=C1C2=CC(=O)C3=C(C=C(C=C3O2)O)O)O", "formula": "C15H10O5"},
    ],
    "taxus brevifolia": [
        {"name": "Paclitaxel", "smiles": "CC1=C2C(C(=O)C3(C(CC4C(C3C(C(C2(C)C)(CC1OC(=O)C(C(C5=CC=CC=C5)NC(=O)C6=CC=CC=C6)O)O)OC(=O)C7=CC=CC=C7)(CO4)OC(=O)C)O)C)OC(=O)C", "formula": "C47H51NO14"},
        {"name": "10-Deacetylbaccatin III", "smiles": "CC1=C2C(C(=O)C3(C(CC4C(C3C(C(C2(C)C)(CC1O)O)O)(CO4)OC(=O)C)O)C)OC(=O)C", "formula": "C29H36O10"},
    ],
}


# ── Common Name Aliases (maps common names → scientific names) ─────────────

COMMON_NAMES = {
    "ginger": "zingiber officinale",
    "turmeric": "curcuma longa",
    "neem": "azadirachta indica",
    "garlic": "allium sativum",
    "green tea": "camellia sinensis",
    "tea": "camellia sinensis",
    "cannabis": "cannabis sativa",
    "marijuana": "cannabis sativa",
    "ginseng": "panax ginseng",
    "ginkgo": "ginkgo biloba",
    "sweet wormwood": "artemisia annua",
    "wormwood": "artemisia annua",
    "periwinkle": "catharanthus roseus",
    "sage": "salvia officinalis",
    "holy basil": "ocimum sanctum",
    "tulsi": "ocimum sanctum",
    "black pepper": "piper nigrum",
    "pepper": "piper nigrum",
    "aloe": "aloe vera",
    "moringa": "moringa oleifera",
    "gotu kola": "centella asiatica",
    "ashwagandha": "withania somnifera",
    "cinnamon": "cinnamomum verum",
    "clove": "syzygium aromaticum",
    "thyme": "thymus vulgaris",
    "pacific yew": "taxus brevifolia",
    "yew": "taxus brevifolia",
    "rosy periwinkle": "catharanthus roseus",
}


def search_plant_compounds(plant_name: str, max_results: int = 25) -> list[dict]:
    """
    Look up known compounds for a plant from the built-in database.

    Matches against scientific names, common names, and partial matches.
    """
    plant_lower = plant_name.lower().strip()

    # 1. Check common name aliases first
    scientific = COMMON_NAMES.get(plant_lower)
    if scientific:
        plant_lower = scientific

    # 2. Exact match on scientific name
    compounds = PLANT_COMPOUNDS.get(plant_lower)

    # 3. Partial match (e.g., "artemisia" matches "artemisia annua")
    if compounds is None:
        for key, value in PLANT_COMPOUNDS.items():
            if plant_lower in key or key in plant_lower:
                compounds = value
                break

    if compounds is None:
        return []

    # Convert to output format with SMILES
    return [
        {
            "name": c["name"],
            "smiles": c["smiles"],
            "cid": None,
            "formula": c.get("formula", ""),
        }
        for c in compounds[:max_results]
    ]


def search_by_species_and_activity(
    plant_name: str, max_results: int = 25
) -> list[dict]:
    """Fallback: try genus-level match (first word of plant name)."""
    genus = plant_name.strip().split()[0].lower() if plant_name.strip() else ""
    if not genus or genus == plant_name.lower().strip():
        return []

    for key, value in PLANT_COMPOUNDS.items():
        if genus in key:
            return [
                {"name": c["name"], "smiles": c["smiles"], "cid": None, "formula": c.get("formula", "")}
                for c in value[:max_results]
            ]
    return []
