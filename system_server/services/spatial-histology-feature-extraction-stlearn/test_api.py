import os
import requests
import time

SERVICE_URL = "http://localhost:53903/api/histology-feature-extraction"

def test_service(h5ad_path):
    print(f"Testing stLearn service with file: {h5ad_path}")
    
    with open(h5ad_path, 'rb') as f:
        files = {
            'file': (os.path.basename(h5ad_path), f, 'application/octet-stream')
        }
        data = {
            'file_type': 'h5ad',
            'use_gpu': 'true',
            'cnn_base': 'resnet50',
            'n_components': 10,  # low components for fast test
            'physical_distance': 1.0
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
            assert "sme_normalized_data.h5ad" in result["data"]
            assert "morphology_PCA_plot.png" in result["data"]
        else:
            print("Failed:", response.text)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
        test_service(test_file)
    else:
        print("Usage: python test_api.py <path_to_h5ad>")
