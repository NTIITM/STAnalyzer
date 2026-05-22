import json
import time
from pathlib import Path
from fastapi.testclient import TestClient
from main import app

base = Path(__file__).parent
sp = base / "sample_data/spatial_sample.h5ad"
sc = base / "sample_data/sc_reference_sample.h5ad"

if not sp.exists() or not sc.exists():
    raise SystemExit("sample data missing")

client = TestClient(app)

start = time.time()
with sp.open("rb") as f_sp, sc.open("rb") as f_sc:
    response = client.post(
        "/api/deconvolve",
        data={
            "spatial_file_type": "h5ad",
            "single_cell_file_type": "h5ad",
            "cell_type_col": "cell_type",
            "N_cells_per_location": "30",
            "detection_alpha": "200",
            "max_epochs_ref": "50",
            "max_epochs_spatial": "80",
            "use_gpu": "true",
        },
        files={
            "spatial_file": (sp.name, f_sp, "application/octet-stream"),
            "single_cell_file": (sc.name, f_sc, "application/octet-stream"),
        },
    )

elapsed = time.time() - start
print("status", response.status_code)
try:
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))
except Exception:
    print(response.text)
print(f"elapsed_sec {elapsed:.1f}")
