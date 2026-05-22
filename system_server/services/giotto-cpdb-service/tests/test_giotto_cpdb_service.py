import os
import sys
import tempfile

import numpy as np
import pandas as pd
import anndata as ad
from fastapi.testclient import TestClient

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from main import app  # noqa: E402


def _mock_adata() -> "ad.AnnData":
    genes = ["CXCL12", "CXCR4", "VEGFA", "KDR", "DLL4", "NOTCH1", "HGF", "MET", "EGF", "EGFR"]
    rng = np.random.default_rng(11)
    X = rng.random((50, len(genes)))
    obs = pd.DataFrame(
        {
            "giotto_group": ["A"] * 20 + ["B"] * 15 + ["C"] * 15,
        },
        index=[f"cell_{i}" for i in range(50)],
    )
    var = pd.DataFrame(index=genes)
    adata = ad.AnnData(X=X, obs=obs, var=var)
    coords = np.column_stack(
        [rng.uniform(0, 80, size=50), rng.uniform(0, 80, size=50)]
    )
    adata.obsm["spatial"] = coords
    return adata


def test_giotto_cpdb_endpoint():
    client = TestClient(app)
    adata = _mock_adata()
    with tempfile.NamedTemporaryFile(suffix=".h5ad") as handle:
        adata.write_h5ad(handle.name)
        handle.seek(0)
        response = client.post(
            "/api/giotto-cpdb",
            data={
                "file_type": "h5ad",
                "groupby": "giotto_group",
                "spatial_key": "spatial",
                "n_permutations": 20,
                "pval_threshold": 0.5
            },
            files={"file": ("mock.h5ad", handle, "application/octet-stream")},
        )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    file_id = payload["data"]["all_edges_csv"]["file_id"]
    resp = client.get(f"/api/download/{file_id}", params={"artifact": "all"})
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]


def test_healthcheck():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200

