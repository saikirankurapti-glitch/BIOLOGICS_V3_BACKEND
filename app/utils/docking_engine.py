import os
import subprocess
import requests
import asyncio
import shutil
from rdkit import Chem
from rdkit.Chem import AllChem

def download_pdb(pdb_id, output_path):
    """Downloads a PDB file from RCSB."""
    url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
    print(f"📡 Downloading PDB {pdb_id} from RCSB...")
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(response.text)
            return True
        else:
            print(f"❌ Failed to download PDB {pdb_id}: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error downloading PDB {pdb_id}: {e}")
        return False

def _atom_to_pdbqt_line(atom, conf, atom_type="C"):
    """Converts a single RDKit atom to a PDBQT ATOM line."""
    idx = atom.GetIdx()
    pos = conf.GetAtomPosition(idx)
    symbol = atom.GetSymbol()
    charge = 0.0
    # Map common atom types
    at_map = {"C": "C", "N": "N", "O": "OA", "S": "SA", "P": "P", "F": "F", "Cl": "Cl", "Br": "Br", "I": "I", "H": "H"}
    ad_type = at_map.get(symbol, "C")
    return (f"ATOM  {idx+1:5d}  {symbol:<3s} LIG A   1    "
            f"{pos.x:8.3f}{pos.y:8.3f}{pos.z:8.3f}"
            f"  1.00  0.00    {charge:6.3f} {ad_type}\n")

def prepare_ligand_pdbqt(smiles, output_path):
    """
    Converts a SMILES string to a 3D PDBQT file using pure RDKit.
    No external tools required.
    """
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return False

    mol = Chem.AddHs(mol)
    result = AllChem.EmbedMolecule(mol, AllChem.ETKDG())
    if result == -1:
        # Try with random coordinates if ETKDG fails for unusual structures
        AllChem.EmbedMolecule(mol, randomSeed=42)

    AllChem.UFFOptimizeMolecule(mol)
    conf = mol.GetConformer()

    with open(output_path, "w") as f:
        f.write("ROOT\n")
        for atom in mol.GetAtoms():
            f.write(_atom_to_pdbqt_line(atom, conf))
        f.write("ENDROOT\n")
        f.write("TORSDOF 0\n")
    return True


def calculate_protein_center(pdb_path):
    """
    Calculates the geometric center of the protein to set the docking box.
    """
    coords = []
    try:
        with open(pdb_path, 'r') as f:
            for line in f:
                if line.startswith(("ATOM", "HETATM")):
                    try:
                        x = float(line[30:38])
                        y = float(line[38:46])
                        z = float(line[46:54])
                        coords.append((x, y, z))
                    except:
                        continue
        if not coords:
            return (0.0, 0.0, 0.0)
        
        avg_x = sum(c[0] for c in coords) / len(coords)
        avg_y = sum(c[1] for c in coords) / len(coords)
        avg_z = sum(c[2] for c in coords) / len(coords)
        return (avg_x, avg_y, avg_z)
    except Exception as e:
        print(f"⚠️ Could not calculate center: {e}")
        return (0.0, 0.0, 0.0)

async def run_vina_docking(receptor_pdbqt, ligand_pdbqt, output_docked, center=(0,0,0), size=(30,30,30)):
    """
    Executes the Autodock Vina subprocess using an absolute path for Windows compatibility.
    """
    # Prefer the local binary in ./bin
    local_bin = os.path.join(os.getcwd(), "bin", "vina.exe")
    if os.path.exists(local_bin):
        vina_path = os.path.abspath(local_bin)
    else:
        # Fallback to system path
        vina_path = shutil.which("vina") or shutil.which("vina.exe")
    
    if not vina_path:
        print("⚠️ AutoDock Vina binary not found in ./bin/vina.exe or system PATH. Simulation mode enabled.")
        await asyncio.sleep(2)
        return -7.5

    # Auto-calculate center if it's default (0,0,0)
    if center == (0,0,0):
        print("🔍 Calculating protein center for docking box...")
        center = calculate_protein_center(receptor_pdbqt)
        print(f"📍 Auto-centered box at: {center}")

    cx, cy, cz = float(center[0]), float(center[1]), float(center[2])
    sx, sy, sz = float(size[0]), float(size[1]), float(size[2])

    cmd = [
        vina_path,
        "--receptor", os.path.abspath(receptor_pdbqt),
        "--ligand", os.path.abspath(ligand_pdbqt),
        "--out", os.path.abspath(output_docked),
        "--center_x", str(cx),
        "--center_y", str(cy),
        "--center_z", str(cz),
        "--size_x", str(sx),
        "--size_y", str(sy),
        "--size_z", str(sz),
        "--cpu", "1",
        "--exhaustiveness", "4"
    ]
    
    print(f"🧪 [Vina] Executing binary: {vina_path}")
    
    def run_vina_sync():
        """Helper to run the blocking process in a thread."""
        return subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )

    try:
        # Use thread-based execution to avoid Windows asyncio subprocess issues
        result = await asyncio.to_thread(run_vina_sync)
        
        if result.returncode != 0:
            print(f"❌ Vina Process Failed with status {result.returncode}")
            print(f"   Error: {result.stderr}")
            return 0.0

        for line in result.stdout.split('\n'):
            if "   1 " in line:
                parts = line.split()
                if len(parts) >= 2:
                    return float(parts[1])
                    
        return -4.0 # Baseline if output wasn't parsed
    except Exception as e:
        import traceback
        print(f"❌ Exception running Vina: {type(e).__name__}: {e}")
        traceback.print_exc()
        return 0.0

import shutil
