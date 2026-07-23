import os
import re
import json
import pandas as pd
from typing import List, Dict, Any

AFFINITY_REGEX = re.compile(r"^\s*1\s+(-?\d+\.\d+)", re.MULTILINE)

def parse_affinity_from_log(log_path: str) -> float | None:
    """Parses top binding affinity (mode 1) from an AutoDock Vina log file."""
    if not os.path.exists(log_path):
        return None
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()
        match = AFFINITY_REGEX.search(content)
        return float(match.group(1)) if match else None
    except Exception:
        return None

def scan_and_rank_results(logs_dir: str, summary_json_path: str = None) -> List[Dict[str, Any]]:
    """
    Scans logs/summary for docking results and ranks them by affinity (kcal/mol).
    """
    results = []

    # Fast-path: check if docking_summary.json exists
    if summary_json_path and os.path.exists(summary_json_path):
        try:
            with open(summary_json_path, "r", encoding="utf-8") as f:
                summary_data = json.load(f)
                for item in summary_data:
                    results.append({
                        "compound_id": item.get("compound_id"),
                        "affinity": float(item.get("affinity", 0.0)),
                        "log_file": item.get("log_file", ""),
                        "out_pdbqt": item.get("out_pdbqt", "")
                    })
        except Exception:
            results = []

    # Fallback: scan directory for *_log.txt
    if not results and os.path.exists(logs_dir):
        for file in os.listdir(logs_dir):
            if file.endswith("_log.txt"):
                cid = file.replace("_log.txt", "")
                filepath = os.path.join(logs_dir, file)
                aff = parse_affinity_from_log(filepath)
                if aff is not None:
                    results.append({
                        "compound_id": cid,
                        "affinity": aff,
                        "log_file": filepath,
                        "out_pdbqt": filepath.replace("_log.txt", "_out.pdbqt")
                    })

    # Sort ascending (more negative = stronger binding)
    results.sort(key=lambda x: x["affinity"])
    return results

def write_results_json(results: List[Dict[str, Any]], output_path: str) -> None:
    """Writes results to JSON."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

def write_results_csv(results: List[Dict[str, Any]], output_path: str) -> None:
    """Writes results to downloadable CSV."""
    df = pd.DataFrame(results)
    df.to_csv(output_path, index=False)