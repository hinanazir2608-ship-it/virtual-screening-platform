import os
import re
import subprocess
import logging
from typing import Dict, Any, List, Tuple, Optional

# Setup logger for module 2
logger = logging.getLogger("ProteinPrep")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class ProteinPreparationError(Exception):
    """Custom exception raised when protein preparation fails at any stage."""
    pass


def download_pdb(pdb_id: str, output_dir: str) -> str:
    """
    Downloads a PDB structure file from RCSB database.
    """
    pdb_id = pdb_id.strip().lower()
    if len(pdb_id) != 4:
        raise ProteinPreparationError(f"Invalid PDB ID format: '{pdb_id}'")

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{pdb_id}.pdb")

    # Fast path if already present
    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        logger.info(f"PDB file already exists locally: {output_path}")
        return output_path

    url = f"https://files.rcsb.org/download/{pdb_id.upper()}.pdb"
    logger.info(f"Downloading PDB structure {pdb_id.upper()} from RCSB...")

    try:
        import urllib.request
        urllib.request.urlretrieve(url, output_path)
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise ProteinPreparationError(f"Downloaded PDB file is empty for ID: {pdb_id}")
        return output_path
    except Exception as e:
        raise ProteinPreparationError(f"Failed to download PDB ID '{pdb_id}': {str(e)}")


def clean_pdb_structure(input_pdb: str, output_pdb: str, keep_water: bool = False, keep_hetero: bool = False) -> str:
    """
    Cleans a raw PDB file by removing water molecules (HOH), heterogens (HETATM), 
    and non-standard residues while preserving standard ATOM records.
    """
    if not os.path.exists(input_pdb):
        raise ProteinPreparationError(f"Input PDB file not found: {input_pdb}")

    cleaned_lines = []
    with open(input_pdb, "r", encoding="utf-8") as infile:
        for line in infile:
            record_type = line[:6].strip()

            if record_type == "ATOM":
                cleaned_lines.append(line)
            elif record_type == "HETATM":
                res_name = line[17:20].strip()
                if keep_water and res_name in ["HOH", "WAT"]:
                    cleaned_lines.append(line)
                elif keep_hetero and res_name not in ["HOH", "WAT"]:
                    cleaned_lines.append(line)
            elif record_type in ["TER", "END"]:
                cleaned_lines.append(line)

    if not cleaned_lines:
        raise ProteinPreparationError("No valid atomic structural data remained after cleaning.")

    os.makedirs(os.path.dirname(output_pdb), exist_ok=True)
    with open(output_pdb, "w", encoding="utf-8") as outfile:
        outfile.writelines(cleaned_lines)

    logger.info(f"Cleaned PDB saved to: {output_pdb}")
    return output_pdb


def run_pdb2pqr(input_pdb: str, output_pqr: str, ff: str = "AMBER", ph: float = 7.4) -> str:
    """
    Runs pdb2pqr CLI tool (or fallback wrapper) to add missing heavy atoms/hydrogens 
    and assign state at target pH.
    """
    cmd = [
        "pdb2pqr",
        f"--ff={ff}",
        f"--with-ph={ph}",
        "--whitespace",
        input_pdb,
        output_pqr
    ]

    logger.info(f"Executing PDB2PQR protonation at pH {ph}...")
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return output_pqr
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.warning(f"PDB2PQR CLI execution unavailable or failed: {e}. Falling back to OpenBabel/Reduce protonation.")
        return protonate_openbabel(input_pdb, output_pqr.replace(".pqr", "_ob.pdb"), ph=ph)


def protonate_openbabel(input_pdb: str, output_pdb: str, ph: float = 7.4) -> str:
    """
    Fallback protonation engine utilizing OpenBabel CLI (`obabel`).
    Adds hydrogens corresponding to target pH.
    """
    cmd = [
        "obabel",
        "-ipdb", input_pdb,
        "-opdb", "-O", output_pdb,
        "-p", str(ph)
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return output_pdb
    except Exception as err:
        raise ProteinPreparationError(f"OpenBabel protonation fallback failed: {err}")


def convert_pdb_to_pdbqt(input_path: str, output_pdbqt: str, preserve_charges: bool = True) -> str:
    """
    Converts a protonated PDB or PQR file to AutoDock PDBQT format using OpenBabel.
    Applies Partial Charges (Gasteiger) and rigid protein backbone defaults.
    """
    if not os.path.exists(input_path):
        raise ProteinPreparationError(f"Target structure for PDBQT conversion not found: {input_path}")

    # Deduce input extension
    in_ext = "pqr" if input_path.endswith(".pqr") else "pdb"

    cmd = [
        "obabel",
        f"-i{in_ext}", input_path,
        "-opdbqt", "-O", output_pdbqt,
        "-xr"  # Keep target as rigid receptor
    ]

    if preserve_charges and in_ext == "pqr":
        cmd.append("-un")  # Preserve charge states calculated by PDB2PQR

    try:
        logger.info(f"Converting {input_path} to PDBQT format via OpenBabel...")
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        if not os.path.exists(output_pdbqt) or os.path.getsize(output_pdbqt) == 0:
            raise ProteinPreparationError("Generated PDBQT receptor file is empty.")
        return output_pdbqt
    except Exception as e:
        raise ProteinPreparationError(f"Failed converting receptor to PDBQT: {str(e)}")


def prepare_receptor(
    receptor_source: str,
    output_dir: str,
    ph: float = 7.4,
    keep_water: bool = False,
    keep_hetero: bool = False
) -> Dict[str, Any]:
    """
    Master pipeline entry-point for Module 2.
    Processes a raw PDB ID or local PDB path and returns the clean PDBQT file.
    """
    os.makedirs(output_dir, exist_ok=True)

    # 1. Resolve source input
    if os.path.exists(receptor_source):
        raw_pdb_path = receptor_source
        base_name = os.path.splitext(os.path.basename(receptor_source))[0]
    else:
        raw_pdb_path = download_pdb(receptor_source, output_dir)
        base_name = receptor_source.lower()

    # File paths
    cleaned_pdb = os.path.join(output_dir, f"{base_name}_clean.pdb")
    protonated_pqr = os.path.join(output_dir, f"{base_name}_protonated.pqr")
    final_pdbqt = os.path.join(output_dir, f"{base_name}_receptor.pdbqt")

    # 2. Clean structure
    clean_pdb_structure(raw_pdb_path, cleaned_pdb, keep_water=keep_water, keep_hetero=keep_hetero)

    # 3. Add Hydrogens & Protonation State
    pqr_path = run_pdb2pqr(cleaned_pdb, protonated_pqr, ph=ph)

    # 4. Final conversion to PDBQT format
    convert_pdb_to_pdbqt(pqr_path, final_pdbqt)

    logger.info(f"Receptor preparation complete: {final_pdbqt}")
    
    return {
        "status": "success",
        "receptor_id": base_name,
        "clean_pdb": cleaned_pdb,
        "receptor_pdbqt": final_pdbqt
    }