"""
Multi-format molecular file parser for Hit Screening.
Supports: .smi, .txt, .sdf, .sd, .mol2, .csv, .json (BioAssay), .mzml, .mzxml (LCMS)
All parsers return a unified List[dict] of {"smiles": str, "mol_id": str}.
"""

import os
import re
import csv
from typing import List, Dict, Optional
from rdkit import Chem


def parse_molecules(file_path: str) -> List[Dict[str, str]]:
    """
    Detect file format by extension and parse all molecules into
    a list of {"smiles": ..., "mol_id": ...} dicts.
    """
    ext = os.path.splitext(file_path)[1].lower()

    parser_map = {
        ".smi": _parse_smi,
        ".txt": _parse_smi,
        ".sdf": _parse_sdf,
        ".sd":  _parse_sdf,
        ".mol2": _parse_mol2,
        ".csv": _parse_csv,
        ".json": _parse_bioassay_json,
        ".mzml": _parse_lcms,
        ".mzxml": _parse_lcms,
    }

    parser = parser_map.get(ext)
    if parser is None:
        print(f"⚠️ Unsupported file format: {ext}. Falling back to SMILES reader.")
        parser = _parse_smi

    molecules = parser(file_path)
    print(f"📂 Parsed {len(molecules)} molecules from {os.path.basename(file_path)} ({ext})")
    return molecules


# ─── SMI / TXT parser (existing format) ─────────────────────────────────────

def _parse_smi(file_path: str) -> List[Dict[str, str]]:
    """Parse a .smi or .txt file with one SMILES per line (optional ID as second token)."""
    molecules = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                smiles = parts[0]
                mol_id = parts[1] if len(parts) > 1 else f"Mol-{i+1}"
                # Quick validity check
                mol = Chem.MolFromSmiles(smiles)
                if mol:
                    molecules.append({"smiles": smiles, "mol_id": mol_id})
    except Exception as e:
        print(f"Error parsing SMI file: {e}")
    return molecules


# ─── SDF parser ─────────────────────────────────────────────────────────────

def _parse_sdf(file_path: str) -> List[Dict[str, str]]:
    """Parse .sdf/.sd files using RDKit's SDMolSupplier. Extracts SMILES from 3D structures."""
    molecules = []
    try:
        supplier = Chem.SDMolSupplier(file_path, sanitize=True, removeHs=True)
        for i, mol in enumerate(supplier):
            if mol is None:
                continue
            try:
                smiles = Chem.MolToSmiles(mol)
                # Try to get molecule name from the SDF _Name property
                mol_id = mol.GetProp("_Name") if mol.HasProp("_Name") and mol.GetProp("_Name").strip() else None
                # Fallback to other common ID properties
                if not mol_id:
                    for prop_name in ["ID", "id", "Name", "name", "IDNUMBER", "ChEMBL_ID", "compound_id"]:
                        if mol.HasProp(prop_name) and mol.GetProp(prop_name).strip():
                            mol_id = mol.GetProp(prop_name).strip()
                            break
                if not mol_id:
                    mol_id = f"SDF-{i+1}"
                molecules.append({"smiles": smiles, "mol_id": mol_id})
            except Exception:
                continue
    except Exception as e:
        print(f"Error parsing SDF file: {e}")
    return molecules


# ─── MOL2 parser ────────────────────────────────────────────────────────────

def _parse_mol2(file_path: str) -> List[Dict[str, str]]:
    """
    Parse multi-molecule .mol2 files.
    Splits on @<TRIPOS>MOLECULE blocks and converts each to SMILES via RDKit.
    """
    molecules = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Split into individual molecule blocks
        blocks = re.split(r'(?=@<TRIPOS>MOLECULE)', content)
        blocks = [b for b in blocks if b.strip()]

        for i, block in enumerate(blocks):
            try:
                # Extract the molecule name (line after @<TRIPOS>MOLECULE)
                lines = block.strip().split("\n")
                mol_id = f"MOL2-{i+1}"
                for j, line in enumerate(lines):
                    if "@<TRIPOS>MOLECULE" in line and j + 1 < len(lines):
                        name = lines[j + 1].strip()
                        if name:
                            mol_id = name
                        break

                # Write block to a temp file for RDKit to parse
                temp_mol2 = file_path + f".tmp_block_{i}.mol2"
                with open(temp_mol2, "w") as tmp:
                    tmp.write(block)

                mol = Chem.MolFromMol2File(temp_mol2, sanitize=True, removeHs=True)

                # Cleanup temp file
                if os.path.exists(temp_mol2):
                    os.remove(temp_mol2)

                if mol:
                    smiles = Chem.MolToSmiles(mol)
                    molecules.append({"smiles": smiles, "mol_id": mol_id})
            except Exception:
                continue
    except Exception as e:
        print(f"Error parsing MOL2 file: {e}")
    return molecules


# ─── CSV parser ─────────────────────────────────────────────────────────────

# Common column name patterns for SMILES (including BioAssay columns)
_SMILES_COLUMN_NAMES = [
    "smiles", "SMILES", "Smiles",
    "canonical_smiles", "Canonical_SMILES",
    "PUBCHEM_EXT_DATASOURCE_SMILES",
    "PUBCHEM_OPENEYE_CAN_SMILES",
    "PUBCHEM_OPENEYE_ISO_SMILES",
    "molecule", "Molecule", "MOLECULE",
    "compound_smiles", "Compound_SMILES",
    "smi", "SMI",
    "structure", "Structure",
    "isosmiles", "isomericsmiles",
]

# Common column name patterns for molecule IDs (including BioAssay columns)
_ID_COLUMN_NAMES = [
    "PUBCHEM_CID", "CID", "cid",
    "PUBCHEM_SID", "SID", "sid",
    "id", "ID", "Id",
    "mol_id", "molecule_id", "MoleculeID",
    "name", "Name", "NAME",
    "compound_id", "CompoundID", "Compound_ID",
    "chembl_id", "ChEMBL_ID",
    "title", "Title",
    "index",
]

# BioAssay activity outcome columns
_ACTIVITY_COLUMN_NAMES = [
    "PUBCHEM_ACTIVITY_OUTCOME", "activity_outcome", "Activity_Outcome",
    "PUBCHEM_ACTIVITY_SCORE", "activity_score", "Activity_Score",
    "bioactivity_type", "standard_type", "Standard_Type",
    "pchembl_value", "pChEMBL_Value",
    "standard_value", "Standard_Value",
    "IC50", "ic50", "EC50", "ec50", "Ki", "ki", "Kd", "kd",
]


def _parse_csv(file_path: str) -> List[Dict[str, str]]:
    """
    Parse .csv files. Auto-detects the SMILES column by matching against
    common column names. Also attempts to find an ID column.
    """
    molecules = []
    try:
        import pandas as pd

        # Try common separators
        for sep in [",", "\t", ";", " "]:
            try:
                df = pd.read_csv(file_path, sep=sep, engine="python", on_bad_lines="skip")
                if len(df.columns) > 1:
                    break
            except Exception:
                continue
        else:
            df = pd.read_csv(file_path, on_bad_lines="skip")

        if df.empty:
            print("⚠️ CSV file is empty")
            return molecules

        columns = list(df.columns)

        # Find the SMILES column
        smiles_col = None
        for candidate in _SMILES_COLUMN_NAMES:
            if candidate in columns:
                smiles_col = candidate
                break
        # Fallback: case-insensitive match
        if smiles_col is None:
            col_lower = {c.lower(): c for c in columns}
            for candidate in _SMILES_COLUMN_NAMES:
                if candidate.lower() in col_lower:
                    smiles_col = col_lower[candidate.lower()]
                    break
        # Last resort: use first column
        if smiles_col is None:
            smiles_col = columns[0]
            print(f"⚠️ Could not find SMILES column, using first column: '{smiles_col}'")

        # Find an ID column
        id_col = None
        for candidate in _ID_COLUMN_NAMES:
            if candidate in columns and candidate != smiles_col:
                id_col = candidate
                break
        if id_col is None:
            col_lower = {c.lower(): c for c in columns}
            for candidate in _ID_COLUMN_NAMES:
                if candidate.lower() in col_lower and col_lower[candidate.lower()] != smiles_col:
                    id_col = col_lower[candidate.lower()]
                    break

        # Detect if this is a BioAssay CSV (has activity columns)
        activity_col = None
        for candidate in _ACTIVITY_COLUMN_NAMES:
            if candidate in columns:
                activity_col = candidate
                break
        if activity_col is None:
            col_lower = {c.lower(): c for c in columns}
            for candidate in _ACTIVITY_COLUMN_NAMES:
                if candidate.lower() in col_lower:
                    activity_col = col_lower[candidate.lower()]
                    break

        if activity_col:
            print(f"🧬 Detected BioAssay CSV format (activity column: '{activity_col}')")

        for i, row in df.iterrows():
            smiles_val = str(row[smiles_col]).strip()
            if not smiles_val or smiles_val == "nan":
                continue
            mol = Chem.MolFromSmiles(smiles_val)
            if mol:
                mol_id = str(row[id_col]).strip() if id_col and str(row[id_col]).strip() != "nan" else f"CSV-{i+1}"

                # Enrich with BioAssay activity data if available
                entry = {"smiles": smiles_val, "mol_id": mol_id}
                if activity_col:
                    activity_val = str(row[activity_col]).strip()
                    if activity_val and activity_val != "nan":
                        entry["mol_id"] = f"{mol_id} ({activity_col}: {activity_val})"
                molecules.append(entry)

    except Exception as e:
        print(f"Error parsing CSV file: {e}")
    return molecules


# ─── LCMS parser (.mzML / .mzXML) ──────────────────────────────────────────

# Common molecular formulas → SMILES lookup for drug-like compounds
_FORMULA_TO_SMILES = {
    "C8H10N4O2": ("CN1C=NC2=C1C(=O)N(C(=O)N2C)C", "Caffeine"),
    "C9H8O4": ("CC(=O)Oc1ccccc1C(=O)O", "Aspirin"),
    "C13H18O2": ("CC(C)CC1=CC=C(C=C1)C(C)C(=O)O", "Ibuprofen"),
    "C17H19NO3": ("CN1CCC23C4C1CC5=CC(=O)CCC5(C2C(=O)CC34)O", "Morphine"),
    "C16H13ClN2O": ("OC1=NC2=CC=CC=C2C(C3=CC=CC=C3Cl)=N1", "Chlorzoxazone-deriv"),
    "C10H15N": ("CC(CC1=CC=CC=C1)NC", "Methamphetamine"),
    "C20H25N3O": ("CCN(CC)C1=CC=C(C=C1)/C=N/N=C2\\C=CC(=O)C=C2", "LCMS-Compound"),
    "C21H30O5": ("CC12CCC3C(C1CCC2(C(=O)CO)O)CCC4=CC(=O)CCC34C", "Cortisol"),
}


def _parse_lcms(file_path: str) -> List[Dict[str, str]]:
    """
    Parse LCMS files (.mzML, .mzXML) by extracting compound identifiers and
    molecular formulas from the XML. Attempts to map formulas to known SMILES.
    
    This is a lightweight parser for integration purposes — for production use,
    a full MS library (e.g. pyteomics or ms_deisotope) would be more robust.
    """
    molecules = []
    try:
        import xml.etree.ElementTree as ET
        
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Handle namespace in mzML/mzXML
        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag.split("}")[0] + "}"

        compound_count = 0

        # Strategy 1: Look for <compound> or <identification> elements
        for elem in root.iter():
            tag = elem.tag.replace(ns, "")

            # mzML: Look for userParam / cvParam with molecular formula info
            if tag in ("cvParam", "userParam"):
                name = elem.get("name", "").lower()
                value = elem.get("value", "")

                if "formula" in name and value:
                    formula = value.strip()
                    if formula in _FORMULA_TO_SMILES:
                        smiles, compound_name = _FORMULA_TO_SMILES[formula]
                        compound_count += 1
                        molecules.append({
                            "smiles": smiles,
                            "mol_id": f"LCMS-{compound_name}-{compound_count}"
                        })
                    else:
                        # Try to convert formula to a simple molecule
                        smiles = _formula_to_smiles_best_effort(formula)
                        if smiles:
                            compound_count += 1
                            molecules.append({
                                "smiles": smiles,
                                "mol_id": f"LCMS-{formula}-{compound_count}"
                            })

                # Also check for SMILES directly in the data
                if "smiles" in name and value:
                    mol = Chem.MolFromSmiles(value)
                    if mol:
                        compound_count += 1
                        molecules.append({
                            "smiles": value,
                            "mol_id": f"LCMS-{compound_count}"
                        })

            # mzXML: Look for <nameValue> or <precursorMz> to extract m/z info
            if tag == "precursorMz":
                mz_text = elem.text
                if mz_text:
                    try:
                        mz = float(mz_text.strip())
                        # Map common m/z values to known compounds (approximate)
                        smiles = _mz_to_smiles_lookup(mz)
                        if smiles:
                            compound_count += 1
                            molecules.append({
                                "smiles": smiles,
                                "mol_id": f"LCMS-mz{mz:.1f}-{compound_count}"
                            })
                    except ValueError:
                        pass

        if not molecules:
            print("⚠️ LCMS file parsed but no molecular structures could be extracted.")
            print("   Tip: Ensure the file contains molecular formula or SMILES annotations.")

    except Exception as e:
        print(f"Error parsing LCMS file: {e}")
    return molecules


def _formula_to_smiles_best_effort(formula: str) -> Optional[str]:
    """
    Best-effort conversion of a molecular formula string to SMILES.
    Uses simple heuristics for small molecules.
    """
    # Simple common molecules
    simple_formulas = {
        "H2O": "O",
        "CO2": "O=C=O",
        "CH4": "C",
        "C2H6O": "CCO",       # Ethanol
        "C2H4O2": "CC(=O)O",  # Acetic acid
        "C6H12O6": "OCC(O)C(O)C(O)C(O)C=O",  # Glucose
        "C3H8O": "CCCO",      # Propanol
        "C6H6": "c1ccccc1",   # Benzene
        "C7H8": "Cc1ccccc1",  # Toluene
        "C10H8": "c1ccc2ccccc2c1",  # Naphthalene
    }
    return simple_formulas.get(formula)


def _mz_to_smiles_lookup(mz: float, tolerance: float = 0.5) -> Optional[str]:
    """
    Look up known compounds by m/z value (approximate matching).
    In production, this would use a proper MS library.
    """
    known_mz = {
        195.09: "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",  # Caffeine [M+H]+
        180.06: "OC1=CC=C(C=C1)C(=O)O",            # Salicylic acid [M+H]+
        206.12: "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",   # Ibuprofen [M+H]+
        286.14: "CN1CCC23C4C1CC5=CC(=O)CCC5(C2C(=O)CC34)O",  # Morphine [M+H]+
        152.06: "Nc1ncnc2[nH]cnc12",                # Adenine [M+H]+
        267.10: "Nc1ncnc2n(cnc12)C3OC(CO)C(O)C3O",  # Adenosine [M+H]+
    }
    for known, smiles in known_mz.items():
        if abs(mz - known) < tolerance:
            return smiles
    return None


# ─── BioAssay JSON parser (PubChem / ChEMBL) ────────────────────────────────

def _parse_bioassay_json(file_path: str) -> List[Dict[str, str]]:
    """
    Parse PubChem BioAssay JSON exports.
    Handles two main formats:
      1. PubChem concise JSON (PC_AssaySubmit / PC_AssayResults with CIDs)
      2. Flat JSON array of compounds with SMILES/CID/activity fields
    For CID-only records, looks up SMILES via PubChem PUG REST API.
    """
    import json
    molecules = []

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading BioAssay JSON: {e}")
        return molecules

    # --- Format 1: PubChem BioAssay concise JSON ---
    # Structure: {"PC_AssaySubmit": {"assay": {...}, "data": [{"sid", "outcome", "data": [...]}]}}
    if isinstance(data, dict):
        assay_data = None

        # PubChem full format
        if "PC_AssaySubmit" in data:
            assay_data = data["PC_AssaySubmit"].get("data", [])
        elif "PC_AssayResults" in data:
            assay_data = data["PC_AssayResults"]
        # Simple wrapper: {"results": [...], "compounds": [...]}
        elif "results" in data:
            assay_data = data["results"]
        elif "compounds" in data:
            assay_data = data["compounds"]
        elif "molecules" in data:
            assay_data = data["molecules"]

        if assay_data and isinstance(assay_data, list):
            cids_to_lookup = []
            sids_to_lookup = []
            for i, record in enumerate(assay_data):
                smiles = None
                mol_id = None
                activity = None

                # Try to get SMILES directly
                for key in ["smiles", "SMILES", "canonical_smiles", "PUBCHEM_OPENEYE_CAN_SMILES"]:
                    if key in record and record[key]:
                        smiles = str(record[key]).strip()
                        break

                # Get compound ID
                for key in ["cid", "CID", "PUBCHEM_CID", "sid", "SID", "PUBCHEM_SID", "id", "ID", "compound_id", "molecule_id"]:
                    if key in record and record[key]:
                        mol_id = str(record[key]).strip()
                        break

                # Get activity outcome
                for key in ["outcome", "activity_outcome", "PUBCHEM_ACTIVITY_OUTCOME",
                            "activity_score", "PUBCHEM_ACTIVITY_SCORE",
                            "pchembl_value", "standard_value", "IC50", "EC50"]:
                    if key in record and record[key] is not None:
                        activity = str(record[key]).strip()
                        break

                if not mol_id:
                    mol_id = f"BioAssay-{i+1}"

                if activity:
                    mol_id = f"{mol_id} (Activity: {activity})"

                if smiles:
                    mol = Chem.MolFromSmiles(smiles)
                    if mol:
                        molecules.append({"smiles": smiles, "mol_id": mol_id})
                else:
                    found_cid = False
                    for key in ["cid", "CID", "PUBCHEM_CID"]:
                        if key in record and record[key]:
                            try:
                                cid_num = str(int(record[key]))
                                cids_to_lookup.append((cid_num, mol_id))
                                found_cid = True
                                break
                            except (ValueError, TypeError):
                                pass
                    if not found_cid:
                        for key in ["sid", "SID", "PUBCHEM_SID"]:
                            if key in record and record[key]:
                                try:
                                    sid_num = str(int(record[key]))
                                    sids_to_lookup.append((sid_num, mol_id))
                                    break
                                except (ValueError, TypeError):
                                    pass

            # Resolve SIDs to CIDs
            if sids_to_lookup:
                sid_map = _resolve_sids_to_cids([s[0] for s in sids_to_lookup])
                for sid_num, mol_id in sids_to_lookup:
                    if sid_num in sid_map:
                        # Grab the first linked CID
                        cids_to_lookup.append((sid_map[sid_num][0], mol_id))

            # Batch lookup CIDs via PubChem PUG REST
            if cids_to_lookup:
                smiles_map = _lookup_cids_to_smiles([c[0] for c in cids_to_lookup])
                for cid_num, mol_id in cids_to_lookup:
                    if cid_num in smiles_map:
                        smiles = smiles_map[cid_num]
                        mol = Chem.MolFromSmiles(smiles)
                        if mol:
                            molecules.append({"smiles": smiles, "mol_id": mol_id})

    # --- Format 2: Flat JSON array ---
    elif isinstance(data, list):
        cids_to_lookup = []
        sids_to_lookup = []
        for i, record in enumerate(data):
            if not isinstance(record, dict):
                continue

            smiles = None
            mol_id = None
            activity = None

            for key in ["smiles", "SMILES", "canonical_smiles"]:
                if key in record and record[key]:
                    smiles = str(record[key]).strip()
                    break

            for key in ["cid", "CID", "sid", "SID", "id", "ID", "compound_id", "molecule_id", "name"]:
                if key in record and record[key]:
                    mol_id = str(record[key]).strip()
                    break

            for key in ["outcome", "activity_outcome", "activity_score",
                        "pchembl_value", "standard_value", "IC50", "EC50"]:
                if key in record and record[key] is not None:
                    activity = str(record[key]).strip()
                    break

            if not mol_id:
                mol_id = f"BioAssay-{i+1}"
            if activity:
                mol_id = f"{mol_id} (Activity: {activity})"

            if smiles:
                mol = Chem.MolFromSmiles(smiles)
                if mol:
                    molecules.append({"smiles": smiles, "mol_id": mol_id})
            else:
                found_cid = False
                for key in ["cid", "CID", "PUBCHEM_CID"]:
                    if key in record and record[key]:
                        try:
                            cid_num = str(int(record[key]))
                            cids_to_lookup.append((cid_num, mol_id))
                            found_cid = True
                            break
                        except (ValueError, TypeError):
                            pass
                if not found_cid:
                    for key in ["sid", "SID", "PUBCHEM_SID"]:
                        if key in record and record[key]:
                            try:
                                sid_num = str(int(record[key]))
                                sids_to_lookup.append((sid_num, mol_id))
                                break
                            except (ValueError, TypeError):
                                pass

        # Resolve SIDs to CIDs
        if sids_to_lookup:
            sid_map = _resolve_sids_to_cids([s[0] for s in sids_to_lookup])
            for sid_num, mol_id in sids_to_lookup:
                if sid_num in sid_map:
                    # Grab the first linked CID
                    cids_to_lookup.append((sid_map[sid_num][0], mol_id))

        if cids_to_lookup:
            smiles_map = _lookup_cids_to_smiles([c[0] for c in cids_to_lookup])
            for cid_num, mol_id in cids_to_lookup:
                if cid_num in smiles_map:
                    smiles = smiles_map[cid_num]
                    mol = Chem.MolFromSmiles(smiles)
                    if mol:
                        molecules.append({"smiles": smiles, "mol_id": mol_id})

    if molecules:
        print(f"🧬 BioAssay: extracted {len(molecules)} compounds with valid SMILES")
    else:
        print("⚠️ BioAssay JSON parsed but no compounds with SMILES were found.")
        print("   Tip: Ensure the JSON contains SMILES strings or PubChem CIDs.")

    return molecules


def _lookup_cids_to_smiles(cids: List[str], batch_size: int = 100) -> Dict[str, str]:
    """
    Batch lookup PubChem CIDs → canonical SMILES via PUG REST API.
    Returns a dict mapping CID string → SMILES string.
    """
    import requests

    smiles_map = {}
    if not cids:
        return smiles_map

    # De-duplicate
    unique_cids = list(set(cids))
    print(f"🔬 Looking up {len(unique_cids)} CIDs from PubChem...")

    for i in range(0, len(unique_cids), batch_size):
        batch = unique_cids[i:i + batch_size]
        cid_str = ",".join(batch)
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid_str}/property/CanonicalSMILES,IsomericSMILES/JSON"

        try:
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                props = resp.json().get("PropertyTable", {}).get("Properties", [])
                for prop in props:
                    cid = str(prop.get("CID", ""))
                    smiles = prop.get("CanonicalSMILES") or prop.get("IsomericSMILES") or prop.get("SMILES") or ""
                    if cid and smiles:
                        smiles_map[cid] = smiles
                print(f"   ✓ Resolved {len(props)} CIDs in batch {i // batch_size + 1}")
            else:
                print(f"   ⚠️ PubChem API returned status {resp.status_code} for batch {i // batch_size + 1}")
        except Exception as e:
            print(f"   ⚠️ PubChem lookup failed: {e}")

    return smiles_map


def _resolve_sids_to_cids(sids: List[str], batch_size: int = 100) -> Dict[str, List[str]]:
    """
    Batch lookup PubChem SIDs → CIDs via PUG REST API.
    Returns a dict mapping SID string → List[CID string].
    """
    import requests

    sid_map = {}
    if not sids:
        return sid_map

    unique_sids = list(set(sids))
    print(f"🔬 Resolving {len(unique_sids)} SIDs to CIDs from PubChem...")

    for i in range(0, len(unique_sids), batch_size):
        batch = unique_sids[i:i + batch_size]
        sid_str = ",".join(batch)
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/substance/sid/{sid_str}/cids/JSON"

        try:
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                info_list = resp.json().get("InformationList", {}).get("Information", [])
                for info in info_list:
                    sid = str(info.get("SID", ""))
                    cids = [str(c) for c in info.get("CID", []) if c]
                    if sid and cids:
                        sid_map[sid] = cids
                print(f"   ✓ Resolved {len(info_list)} SIDs in batch {i // batch_size + 1}")
            else:
                print(f"   ⚠️ PubChem API returned status {resp.status_code} for SID batch {i // batch_size + 1}")
        except Exception as e:
            print(f"   ⚠️ PubChem SID lookup failed: {e}")

    return sid_map
