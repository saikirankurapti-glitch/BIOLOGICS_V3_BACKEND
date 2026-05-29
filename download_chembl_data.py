import pandas as pd
import numpy as np
import os
from chembl_webresource_client.new_client import new_client

def fetch_chembl_data(target_name="GPR35", output_csv="chembl_training_data.csv"):
    print(f"Searching ChEMBL for target: {target_name}...")
    target = new_client.target
    target_query = target.search(target_name)
    targets = pd.DataFrame.from_dict(target_query)
    
    if targets.empty:
        print("No targets found.")
        return
    
    # Select the first target
    target_chembl_id = targets.iloc[0]['target_chembl_id']
    print(f"Found Target: {target_chembl_id} ({targets.iloc[0].get('pref_name', 'Unknown')})")
    
    # Fetch Activities
    print("Fetching IC50 and EC50 activities. This might take a few minutes...")
    activity = new_client.activity
    res_ic50 = activity.filter(target_chembl_id=target_chembl_id, standard_type="IC50")
    res_ec50 = activity.filter(target_chembl_id=target_chembl_id, standard_type="EC50")
    
    activities = list(res_ic50) + list(res_ec50)
    
    if not activities:
        print("No activities found.")
        return
        
    df = pd.DataFrame(activities)
    print(f"Downloaded {len(df)} activity records.")
    
    # We need pChEMBL value or standard value
    df = df[df.standard_value.notna()]
    df = df[df.canonical_smiles.notna()]
    
    # Convert standard_value to numeric
    # Assuming nM units for IC50/EC50
    df['standard_value'] = pd.to_numeric(df['standard_value'], errors='coerce')
    df = df.dropna(subset=['standard_value', 'canonical_smiles'])
    
    # Calculate pIC50 if pchembl_value is missing
    def calculate_pic50(row):
        if pd.notna(row.get('pchembl_value')):
            return float(row['pchembl_value'])
        # Convert nM to M and take negative log
        val_molar = row['standard_value'] * 1e-9
        if val_molar > 0:
            return -np.log10(val_molar)
        return 0.0

    df['pIC50'] = df.apply(calculate_pic50, axis=1)
    
    # Keep only relevant columns
    df_clean = df[['canonical_smiles', 'molecule_chembl_id', 'pIC50', 'standard_type']]
    
    # Remove duplicates
    df_clean = df_clean.drop_duplicates(subset=['canonical_smiles'])
    
    print(f"Cleaned dataset contains {len(df_clean)} molecules.")
    
    output_path = os.path.join("test_datasets", output_csv)
    df_clean.to_csv(output_path, index=False)
    print(f"✅ Saved ChEMBL data to {output_path}")

if __name__ == "__main__":
    fetch_chembl_data()
