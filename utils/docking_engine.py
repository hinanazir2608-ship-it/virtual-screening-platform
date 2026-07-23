import os
import subprocess
import logging
from typing import Dict, Any, Tuple, List  # <-- Yahan Tuple aur List add karein

logger = logging.getLogger("DockingEngine")

def run_vina_docking(
    receptor_pdbqt: str,
    ligand_pdbqt: str,
    output_dir: str,
    grid_center: Tuple[float, float, float],
    grid_size: Tuple[float, float, float] = (20.0, 20.0, 20.0),
    exhaustiveness: int = 8
) -> Dict[str, Any]:
    """Executes AutoDock Vina CLI for a single ligand-receptor pair."""
    ligand_id = os.path.splitext(os.path.basename(ligand_pdbqt))[0]
    out_pdbqt = os.path.join(output_dir, f"{ligand_id}_out.pdbqt")
    log_file = os.path.join(output_dir, f"{ligand_id}_log.txt")

    cmd = [
        "vina",
        "--receptor", receptor_pdbqt,
        "--ligand", ligand_pdbqt,
        "--out", out_pdbqt,
        "--log", log_file,
        "--center_x", str(grid_center[0]),
        "--center_y", str(grid_center[1]),
        "--center_z", str(grid_center[2]),
        "--size_x", str(grid_size[0]),
        "--size_y", str(grid_size[1]),
        "--size_z", str(grid_size[2]),
        "--exhaustiveness", str(exhaustiveness)
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return {"status": "success", "ligand_id": ligand_id, "out_pdbqt": out_pdbqt, "log_file": log_file}
    except subprocess.CalledProcessError as e:
        logger.error(f"Docking failed for {ligand_id}: {e.stderr}")
        return {"status": "error", "ligand_id": ligand_id, "error": str(e.stderr)}