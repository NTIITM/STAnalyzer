import os
import requests
import time

SERVICE_URL = "http://localhost:53901/api/neighborhood-enrichment"
# Find a sample h5ad file in the user's workspace
# I will use /home/common/hwluo/project/textMSA/Xenium_V1_Human_Lung_Cancer_Addon_FFPE_outs.h5ad 
# or similar accessible one. Actually I need to know if such a file with discrete labels exists.

def test_service(h5ad_path, cluster_key="leiden"):
    print(f"Testing service with file: {h5ad_path}")
    
    with open(h5ad_path, 'rb') as f:
        files = {
            'file': (os.path.basename(h5ad_path), f, 'application/octet-stream')
        }
        data = {
            'file_type': 'h5ad',
            'spatial_key': 'spatial',
            'cluster_key': cluster_key,
            'n_neighbors': 6,
            'n_perms': 100, # fast test
        }
        
        start = time.time()
        print("Sending request to:", SERVICE_URL)
        response = requests.post(SERVICE_URL, files=files, data=data)
        elapsed = time.time() - start
        
        print(f"Response status: {response.status_code}")
        print(f"Time taken: {elapsed:.2f} seconds")
        
        if response.status_code == 200:
            result = response.json()
            print("Success:", result)
            
            # Verify we received the expected files
            assert "neighborhood_enrichment_zscores.csv" in result["data"]
            assert "neighborhood_enrichment_heatmap.png" in result["data"]
        else:
            print("Failed:", response.text)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
        cluster_key = sys.argv[2] if len(sys.argv) > 2 else "leiden"
        test_service(test_file, cluster_key)
    else:
        print("Usage: python test_api.py <path_to_h5ad> [cluster_key]")
