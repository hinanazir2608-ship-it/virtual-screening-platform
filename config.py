import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

# Ensure required directories exist
for path in [DATA_DIR, OUTPUT_DIR]:
    os.makedirs(path, exist_ok=True)

# Default Configs
DEFAULT_VINA_CONFIG = {
    "cpu": 4,
    "exhaustiveness": 8,
    "num_modes": 9,
    "energy_range": 3
}