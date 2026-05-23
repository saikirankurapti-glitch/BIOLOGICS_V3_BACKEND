import httpx
import re
from typing import Optional, Dict, Any, List

UNIPROT_API_URL = "https://rest.uniprot.org/uniprotkb/"

async def fetch_uniprot_data(uniprot_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetches protein sequence and metadata from UniProt.
    If a gene name (e.g., EGFR) is provided instead of an ID (e.g., P00533),
    it automatically resolves the top reviewed Human accession.
    """
    safe_id = uniprot_id.strip().upper()
    try:
        async with httpx.AsyncClient() as client:
            
            # 1. Resolve Gene Name to UniProt ID if necessary
            # A typical UniProt ID is 6 or 10 alphanumeric characters (e.g. P00533)
            # Gene names are usually shorter letters/numbers like EGFR, TP53
            is_uniprot_format = re.match(r'^[O,P,Q][0-9][A-Z,0-9]{3}[0-9]|[A-N,R-Z][0-9]([A-Z][A-Z,0-9]{2}[0-9]){1,2}$', safe_id)
            
            if not is_uniprot_format:
                # Search for human reviewed sequence with this gene name
                search_url = f"https://rest.uniprot.org/uniprotkb/search?query=(gene:{safe_id}) AND (reviewed:true) AND (organism_id:9606)&size=1"
                search_res = await client.get(search_url, timeout=10)
                if search_res.status_code == 200 and search_res.json().get('results'):
                    safe_id = search_res.json()['results'][0]['primaryAccession']
                    print(f"Resolved Gene name '{uniprot_id}' to UniProt ID: {safe_id}")
                else:
                    print(f"Failed to resolve gene name {safe_id} to a UniProt ID.")
                    return None

            # 2. Fetch Core Data
            response = await client.get(f"{UNIPROT_API_URL}{safe_id}.json", timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                # Extract logical data
                name = data.get("proteinDescription", {}).get("recommendedName", {}).get("fullName", {}).get("value", safe_id)
                sequence = data.get("sequence", {}).get("value", "")
                gene_name = data.get("genes", [{}])[0].get("geneName", {}).get("value", "")
                
                # Extract PDB cross-references if available
                pdb_ids = []
                for db in data.get("uniProtKBCrossReferences", []):
                    if db["database"] == "PDB":
                        pdb_ids.append(db["id"])
                
                return {
                    "uniprot_id": safe_id,
                    "name": name,
                    "gene_name": gene_name,
                    "sequence": sequence,
                    "pdb_ids": list(set(pdb_ids)),
                    "organism": data.get("organism", {}).get("scientificName", "")
                }
            else:
                print(f"UniProt returned {response.status_code} for {safe_id}")
                return None
    except Exception as e:
        print(f"Error fetching UniProt data: {e}")
        return None
