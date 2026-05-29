from rdkit import Chem
from rdkit.Chem import Descriptors, Lipinski

def calculate_preformulation_properties(smiles: str):
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return None
    
    mw = round(Descriptors.MolWt(mol), 2)
    logp = round(Descriptors.MolLogP(mol), 2)
    tpsa = round(Descriptors.TPSA(mol), 2)
    hbd = Lipinski.NumHDonors(mol)
    hba = Lipinski.NumHAcceptors(mol)
    rb = Lipinski.NumRotatableBonds(mol)
    
    # Solubility Prediction (Basic heuristic rules)
    # Rule of thumb: High logP -> Low solubility
    if logp < 0:
        solubility = "High"
    elif logp < 3:
        solubility = "Moderate"
    elif logp < 5:
        solubility = "Low"
    else:
        solubility = "Very Low"
        
    # Lipinski Violations
    violations = 0
    if mw > 500: violations += 1
    if logp > 5: violations += 1
    if hbd > 5: violations += 1
    if hba > 10: violations += 1
    
    # Veber Rules
    veber_violations = 0
    if rb > 10: veber_violations += 1
    if tpsa > 140: veber_violations += 1
    
    stability_risks = []
    if tpsa > 120: 
        stability_risks.append("Potential hygroscopicity risk due to high TPSA")
    if rb > 10: 
        stability_risks.append("High conformational flexibility risk")
    if mw > 600:
        stability_risks.append("Aggregation risk due to high molecular weight")
    
    # Recommended Excipients
    excipients = ["histidine buffer"]
    if solubility in ["Low", "Very Low"]:
        excipients.extend(["polysorbate 80", "PEG"])
    
    if "hygroscopicity" in "".join(stability_risks):
        excipients.append("sucrose")
    else:
        excipients.append("trehalose")
        
    return {
        "molecular_weight": mw,
        "logp": logp,
        "tpsa": tpsa,
        "h_bond_donors": hbd,
        "h_bond_acceptors": hba,
        "rotatable_bonds": rb,
        "solubility_prediction": solubility,
        "stability_risk": stability_risks,
        "recommended_excipients": excipients,
        "lipinski_violations": violations,
        "veber_violations": veber_violations,
        "drug_likeness_status": "Pass" if violations <= 1 and veber_violations == 0 else "Alert"
    }

def design_formulation_logic(pre_data: dict, route: str):
    solubility = pre_data.get("solubility_prediction", "Moderate")
    
    design = {
        "formulation_type": "Injectable Solution" if route == "injection" else "Solid Oral Dosage",
        "drug_concentration": "10 mg/mL" if route == "injection" else "100 mg",
        "buffer": "Histidine (10mM)" if route == "injection" else "Phosphate Buffer",
        "stabilizer": "Trehalose (5%)" if "hygroscopicity" not in "".join(pre_data.get("stability_risk", [])) else "Sucrose (5%)",
        "surfactant": "Polysorbate 80 (0.02%)" if solubility in ["Low", "Very Low"] else "None",
        "recommended_ph": 6.0 if route == "injection" else 7.2
    }
    return design
