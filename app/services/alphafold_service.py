import httpx
from typing import Optional, Dict, Any

ALPHAFOLD_API_URL = "https://alphafold.ebi.ac.uk/api/prediction/"

async def fetch_alphafold_metadata(uniprot_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetches AlphaFold predicted 3D structure metadata using UniProt ID.
    Returns download URLs for the PDB/CIF structure.
    """
    safe_id = uniprot_id.strip().upper()
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{ALPHAFOLD_API_URL}{safe_id}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if not data:
                    return None
                    
                entry = data[0] if isinstance(data, list) else data
                return {
                    "uniprotAccession": entry.get("uniprotAccession"),
                    "entryId": entry.get("entryId"),
                    "pdbUrl": entry.get("pdbUrl"),
                    "cifUrl": entry.get("cifUrl"),
                    "modelCreationDate": entry.get("modelCreationDate"),
                    "source": "AlphaFold DB"
                }
            elif response.status_code == 404:
                return None
            else:
                print(f"AlphaFold API returned {response.status_code} for {safe_id}")
                return None
    except Exception as e:
        print(f"Error fetching AlphaFold data: {e}")
        return None
