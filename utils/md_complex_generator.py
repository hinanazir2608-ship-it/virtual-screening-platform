import os

def create_complex_pdb(receptor_pdbqt: str, ligand_pdbqt: str, output_complex_pdb: str) -> bool:
    """
    Combines receptor PDBQT and top-mode docked ligand PDBQT into a single combined PDB complex.
    """
    try:
        lines = []
        # Parse Receptor ATOMs
        with open(receptor_pdbqt, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith(("ATOM", "HETATM")):
                    lines.append(line[:66] + "\n")
        
        lines.append("TER\n")

        # Parse top docked ligand pose (Mode 1)
        in_model_1 = False
        with open(ligand_pdbqt, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MODEL 1"):
                    in_model_1 = True
                    continue
                elif line.startswith("ENDMDL"):
                    break
                
                if in_model_1 and line.startswith(("ATOM", "HETATM")):
                    lines.append(line[:66] + "\n")

        lines.append("END\n")

        with open(output_complex_pdb, "w", encoding="utf-8") as f:
            f.writelines(lines)
            
        return True
    except Exception as e:
        print(f"Error merging complex: {e}")
        return False