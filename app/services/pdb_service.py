import requests
from typing import Optional, Dict, Any

PDB_API_URL = "https://data.rcsb.org/rest/v1/core/entry/"

def fetch_pdb_metadata(pdb_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetches logical metadata for a given PDB ID (e.g., '4INS').
    Returns a dictionary with 'title', 'classification', 'method', etc.
    """
    safe_id = pdb_id.strip().upper()
    try:
        response = requests.get(f"{PDB_API_URL}{safe_id}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            
            # Extract useful fields
            metadata = {
                "pdb_id": safe_id,
                "title": data.get("struct", {}).get("title", "Unknown Title"),
                "classification": data.get("struct_keywords", {}).get("pdbx_keywords", "Unknown Class"),
                "experiment_method": data.get("exptl", [{}])[0].get("method", "Unknown"),
                "deposition_date": data.get("rcsb_accession_info", {}).get("deposit_date", ""),
                "url": f"https://www.rcsb.org/structure/{safe_id}"
            }
            return metadata
        elif response.status_code == 404:
            print(f"PDB ID {safe_id} not found (404).")
            return {"error": "NotFound", "pdb_id": safe_id}
        else:
            print(f"PDB API returned {response.status_code} for {safe_id}")
            return None
    except Exception as e:
        print(f"Error fetching PDB data: {e}")
        return None
