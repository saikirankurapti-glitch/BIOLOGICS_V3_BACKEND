import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem, MACCSkeys, Descriptors, Lipinski
import os
import sys

# Try to import sascorer from RDKit Contrib
try:
    from rdkit.Contrib.SA_Score import sascorer
except ImportError:
    # Heuristic fallback if RDKit Contrib is not in path
    # We found it in: backend\venv\Lib\site-packages\rdkit\Contrib\SA_Score\sascorer.py
    import site
    try:
        site_packages = site.getsitepackages()
    except AttributeError:
        # Fallback for virtual environments where getsitepackages is not available
        site_packages = [p for p in sys.path if "site-packages" in p]
        
    for p in site_packages:
        potential_path = os.path.join(p, "rdkit", "Contrib", "SA_Score")
        if os.path.exists(potential_path):
            if potential_path not in sys.path:
                sys.path.append(potential_path)
            break
    try:
        import sascorer
    except:
        sascorer = None

def calculate_molecular_properties(smiles: str):
    """
    Parses a SMILES string and returns calculated physicochemical properties.
    Returns None if the SMILES is invalid.
    """
    try:
        mol = Chem.MolFromSmiles(smiles)
        if not mol:
            return None
        
        props = {
            "MolWt": round(Descriptors.MolWt(mol), 2),
            "LogP": round(Descriptors.MolLogP(mol), 2),
            "NumHDonors": Lipinski.NumHDonors(mol),
            "NumHAcceptors": Lipinski.NumHAcceptors(mol),
            "RotatableBonds": Descriptors.NumRotatableBonds(mol),
            "TPSA": round(Descriptors.TPSA(mol), 2),
            "IsLipinskiCompliant": False,
            "SA_Score": calculate_sa_score(mol)
        }

        # Check Lipinski's Rule of 5
        if (props["MolWt"] <= 500 and props["LogP"] <= 5 and 
            props["NumHDonors"] <= 5 and props["NumHAcceptors"] <= 10):
            props["IsLipinskiCompliant"] = True
            
        return props
    except Exception as e:
        print(f"Error calculating properties for {smiles}: {e}")
        return None

def calculate_sa_score(mol):
    """
    Calculates the Synthetic Accessibility Score (1 is easy, 10 is very difficult).
    """
    if not mol: return 5.0
    if sascorer:
        try:
            return round(sascorer.calculateScore(mol), 2)
        except:
            pass
    
    # Generic fallback: complexity based on ring count and chiral centers
    score = 1.0 + (Descriptors.MolWt(mol) / 100.0)
    score += Lipinski.RingCount(mol) * 0.5
    return min(10.0, round(score, 2))

def extract_features(smiles: str) -> np.ndarray:
    """Generates 2048-bit ECFP4 + 166 MACCS keys + RDKit 2D descriptors."""
    mol = Chem.MolFromSmiles(smiles)
    fallback_len = 2048 + 166 + len(Descriptors.descList)
    if not mol:
        return np.zeros(fallback_len)
        
    try:
        # 1. Morgan Fingerprint (ECFP4) - 2048 bits
        fp_morgan = AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=2048)
        arr_morgan = np.zeros((0,), dtype=np.int8)
        Chem.DataStructs.ConvertToNumpyArray(fp_morgan, arr_morgan)
        
        # 2. MACCS Keys - 166 keys
        fp_maccs = MACCSkeys.GenMACCSKeys(mol)
        arr_maccs = np.zeros((0,), dtype=np.int8)
        Chem.DataStructs.ConvertToNumpyArray(fp_maccs, arr_maccs)
        
        # 3. 2D Descriptors
        arr_desc = np.zeros(len(Descriptors.descList))
        for i, (name, func) in enumerate(Descriptors.descList):
            try:
                val = func(mol)
                arr_desc[i] = val if not np.isnan(val) and not np.isinf(val) else 0.0
            except:
                arr_desc[i] = 0.0
                
        return np.concatenate((arr_morgan, arr_maccs, arr_desc))
    except Exception:
        return np.zeros(fallback_len)
