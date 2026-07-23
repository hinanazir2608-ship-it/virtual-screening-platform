import os
import gc
import logging
import subprocess
from typing import Generator, Dict, Any, List

logger = logging.getLogger("LigandPrep")

def parse_sdf_molecules(sdf_path: str) -> Generator[str, None, None]:
    """Memory-efficient streaming generator to split heavy multi-compound SDF files."""
    current_mol = []
    with open(sdf_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            current_mol.append(line)
            if line.startswith("$$$$"):
                yield "".join(current_mol)
                current_mol = []
    if current_mol:
        yield "".join(current_mol)

def convert_sdf_block_to_pdbqt(sdf_block: str, mol_id: str, output_dir: str) -> str:
    """Converts a single SDF molecule block into 3D PDBQT using OpenBabel CLI."""
    temp_sdf = os.path.join(output_dir, f"{mol_id}_temp.sdf")
    output_pdbqt = os.path.join(output_dir, f"{mol_id}.pdbqt")

    with open(temp_sdf, "w", encoding="utf-8") as f:
        f.write(sdf_block)

    cmd = [
        "obabel", "-isdf", temp_sdf,
        "-opdbqt", "-O", output_pdbqt,
        "--gen3d", "-p", "7.4"
    ]
    
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return output_pdbqt
    except Exception as e:
        logger.error(f"Failed to prepare ligand {mol_id}: {e}")
        return None
    finally:
        if os.path.exists(temp_sdf):
            os.remove(temp_sdf)

def process_ligand_batch(sdf_file: str, output_dir: str, batch_size: int = 500) -> List[str]:
    """Batched generator wrapper to process large database libraries safely without RAM leaks."""
    os.makedirs(output_dir, exist_ok=True)
    prepared_files = []
    count = 0

    for idx, mol_block in enumerate(parse_sdf_molecules(sdf_file)):
        mol_id = f"LIG_{idx+1:05d}"
        pdbqt_file = convert_sdf_block_to_pdbqt(mol_block, mol_id, output_dir)
        if pdbqt_file:
            prepared_files.append(pdbqt_file)
        
        count += 1
        if count % batch_size == 0:
            gc.collect()  # Explicit Garbage Collection call

    gc.collect()
    return prepared_files