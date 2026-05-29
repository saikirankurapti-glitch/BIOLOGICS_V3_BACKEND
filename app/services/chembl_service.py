import httpx
from typing import Optional, Dict, Any, List

CHEMBL_API_URL = "https://www.ebi.ac.uk/chembl/api/data"

async def fetch_target_chembl_id(uniprot_id: str) -> Optional[str]:
    """Retrieve the ChEMBL Target ID mapping for a given UniProt ID."""
    try:
        url = f"{CHEMBL_API_URL}/target?target_components__accession={uniprot_id}&format=json"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                targets = data.get("targets", [])
                if targets:
                    # Return the dict ID
                    return targets[0].get("target_chembl_id")
            return None
    except Exception as e:
        print(f"Error fetching ChEMBL target: {e}")
        return None

async def fetch_known_ligands(uniprot_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Fetches known binding small molecules with bioactivity (IC50, Ki, Kd) from ChEMBL
    using the UniProt ID to find the matching ChEMBL Target and pulling activities.
    """
    chembl_target_id = await fetch_target_chembl_id(uniprot_id)
    if not chembl_target_id:
        return []
        
    try:
        # Filter for IC50/Ki/Kd activities for this target, only those physically binding
        # pchembl_value > 5 filters for reasonably strong bindings (pIC50 > 5 -> <10uM)
        url = (f"{CHEMBL_API_URL}/activity?target_chembl_id={chembl_target_id}"
               f"&pchembl_value__gte=5.0&standard_type__in=IC50,Ki,Kd"
               f"&limit={limit}&format=json")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=15)
            if response.status_code == 200:
                activities = response.json().get("activities", [])
                
                ligands = []
                for act in activities:
                    if not act.get("canonical_smiles"):
                        continue
                        
                    ligands.append({
                        "molecule_chembl_id": act.get("molecule_chembl_id"),
                        "smiles": act.get("canonical_smiles"),
                        "standard_type": act.get("standard_type"),      # IC50
                        "standard_value": act.get("standard_value"),    # 10.5
                        "standard_units": act.get("standard_units"),    # nM
                        "pchembl_value": act.get("pchembl_value"),      # 7.9 (log affinity)
                        "assay_description": act.get("assay_description", "")
                    })
                return ligands
            else:
                return []
    except Exception as e:
        print(f"Error fetching ChEMBL ligands: {e}")
        return []
