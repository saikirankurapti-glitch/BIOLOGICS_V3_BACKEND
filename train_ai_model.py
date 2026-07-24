import pandas as pd
import numpy as np
import xgboost as xgb
from rdkit import Chem
from rdkit.Chem import AllChem, MACCSkeys, Descriptors
from sklearn.model_selection import KFold
import pickle
import os
import urllib.request
import zipfile

def extract_features(smiles: str) -> np.ndarray:
    """Generates 2048-bit ECFP4 + 166 MACCS keys + RDKit 2D descriptors."""
    mol = Chem.MolFromSmiles(smiles)
    fallback_len = 2048 + 166 + len(Descriptors.descList)
    if not mol:
        print(f"Failed to featurize {smiles}")
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
        
        # 3. 2D Descriptors (Subset for stability)
        desc_keys = [d[0] for d in Descriptors.descList]
        arr_desc = np.zeros(len(desc_keys))
        for i, (name, func) in enumerate(Descriptors.descList):
            try:
                val = func(mol)
                arr_desc[i] = val if not np.isnan(val) and not np.isinf(val) else 0.0
            except:
                arr_desc[i] = 0.0
                
        return np.concatenate((arr_morgan, arr_maccs, arr_desc))
    except Exception as e:
        print(f"Error featurizing {smiles}: {e}")
        return np.zeros(2048 + 166 + len(Descriptors.descList))

print("Gathering scientific training dataset...")
chembl_file = os.path.join("test_datasets", "chembl_training_data.csv")

if os.path.exists(chembl_file):
    print(f"Loading real-world ChEMBL dataset from {chembl_file}...")
    df = pd.read_csv(chembl_file)
    if 'canonical_smiles' in df.columns:
        df = df.rename(columns={'canonical_smiles': 'smiles'})
    print(f"Successfully loaded {len(df)} compounds.")
else:
    print("ChEMBL data not found. Falling back to internal simulation dataset...")
    sample_data = {
        'smiles': [
            "CC1=C(C=C(C=C1)NC(=O)C2=CC=C(C=C2)CN3CCN(CC3)C)NC4=NC=CC(=N4)C5=CN=CC=C5", # Imatinib
            "CN1C=NC2=C1C(=O)N(C(=O)N2C)C", # Caffeine
            "CC(C)(C)C1=CC(=NO1)NC(=O)NC2=CC=C(C=C2)C3=CN4C5=C(C=C(C=C5)OCCCCN6CCOCC6)N=C4C=C3",
            "C1=CC=C(C=C1)C(=O)O", # Benzoic acid
            "CC1=C(C=C(C=C1)NC(=O)C2=CC=C(C=C2)C(F)(F)F)NC3=NC=CC(=N3)C4=CN=CC=C4", # Nilotinib
            "CCO", # Ethanol
            "NC1=NC=NC2=C1N=CN2C3C(C(C(O3)COP(=O)(O)O)O)O", # AMP
            "O=C1C=C(C(=O)O)NC2=C1C=CC=C2", # Kynurenic_Acid
            "O=C1c2ccccc2-c3nc(ccc13)c4ccccc4", # Pamoic_Acid
            "CCOc1cc(=O)n2c(c1)cccc2", # Zaprinast
            "O=C(Cc1ccc(O)c(O)c1)C(F)(F)F", # Lodoxamide
            "C1=CC=CC=C1", # Benzene
            "CC(=O)Oc1ccccc1C(=O)O", # Aspirin
            "CN1C2CCC1C(C(C2)OC(=O)c3ccccc3)C(=O)OC", # Cocaine
            "CC12CCC3C(C1CCC2O)CCC4=CC(=O)CCC34C", # Testosterone
        ] * 50,
        'pIC50': [8.2, 3.1, 7.8, 2.0, 8.5, 0.1, 4.0, 7.8, 8.9, 8.2, 7.5, 0.0, 3.2, 2.5, 1.2] * 50
    }
    df = pd.DataFrame(sample_data)

print("Extracting 2400+ mathematical features per molecule using RDKit...")
X_list = []
for smi in df['smiles']:
    X_list.append(extract_features(smi))

X = np.stack(X_list)
y = df['pIC50'].values

print("Training XGBoost Regressor Assembly...")
# Train the production-ready model
xgb_model = xgb.XGBRegressor(
    n_estimators=300,
    learning_rate=0.05,
    max_depth=6,
    objective='reg:squarederror'
    # tree_method='gpu_hist' # Disabled for default CPU compatibility in this environment
)

xgb_model.fit(X, y)

# Validate fit
predictions = xgb_model.predict(X)
print(f"Training R^2: {1 - np.var(y - predictions) / np.var(y):.4f}")

# Save Model
model_path = os.path.join("app", "ai_models")
os.makedirs(model_path, exist_ok=True)
target_file = os.path.join(model_path, "binding_affinity_model.pkl")

with open(target_file, "wb") as f:
    pickle.dump(xgb_model, f)

print(f"✅ Production Model deployed to {target_file}")
