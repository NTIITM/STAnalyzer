#!/usr/bin/env python3
"""
Test script for verifying Tangram spatial imputation service
Based on service-fixer skill template
"""
import requests
import json
import time
import os
import sys
from pathlib import Path
import anndata as ad
import pandas as pd

# ===== CONFIGURATION =====
SERVICE_NAME = "spatial-imputation-tangram-service"
BASE_URL = "http://localhost:38411"
HEALTH_ENDPOINT = f"{BASE_URL}/health"
PROCESSING_ENDPOINT = f"{BASE_URL}/api/impute"
DOWNLOAD_ENDPOINT = f"{BASE_URL}/api/download"

# Test data paths
SPATIAL_DATA_PATH = "/home/common/hwluo/project/system_server/services/spatial-imputation-tangram-service/data/without/slideseq_MOp_1217.h5ad"
SINGLE_CELL_DATA_PATH = "/home/common/hwluo/project/system_server/services/spatial-imputation-tangram-service/data/without/mop_sn_tutorial.h5ad"
OUTPUT_DIR = "/home/common/hwluo/project/system_server/services/spatial-imputation-tangram-service/outputs"

# ===== TEST FUNCTIONS =====

def test_health():
    """Test health check endpoint"""
    print("=" * 60)
    print("Test 1: Health Check")
    print("=" * 60)
    try:
        response = requests.get(HEALTH_ENDPOINT, timeout=10)
        response.raise_for_status()
        data = response.json()
        print(f"✓ Health check passed")
        print(f"  Status: {data.get('status')}")
        print(f"  Bio available: {data.get('bio_available')}")
        print(f"  Tangram available: {data.get('tangram_available')}")
        print(f"  Output dir: {data.get('output_dir')}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"✗ Health check failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"  Status code: {e.response.status_code}")
            print(f"  Response: {e.response.text}")
        return False
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        return False


def test_processing(spatial_path: str, single_cell_path: str):
    """Test main processing endpoint"""
    print("\n" + "=" * 60)
    print("Test 2: Processing Endpoint")
    print("=" * 60)
    
    if not os.path.exists(spatial_path):
        print(f"✗ Spatial test data not found: {spatial_path}")
        return None
    if not os.path.exists(single_cell_path):
        print(f"✗ Single-cell test data not found: {single_cell_path}")
        return None
    
    print(f"Using spatial data: {spatial_path}")
    print(f"  File size: {os.path.getsize(spatial_path) / 1024 / 1024:.2f} MB")
    print(f"Using single-cell data: {single_cell_path}")
    print(f"  File size: {os.path.getsize(single_cell_path) / 1024 / 1024:.2f} MB")
    
    try:
        # Prepare request
        with open(spatial_path, 'rb') as f_sp, open(single_cell_path, 'rb') as f_sc:
            files = {
                'spatial_file': (os.path.basename(spatial_path), f_sp, 'application/octet-stream'),
                'single_cell_file': (os.path.basename(single_cell_path), f_sc, 'application/octet-stream')
            }
            
            # Add parameters
            data = {
                'spatial_file_type': 'auto',
                'single_cell_file_type': 'auto',
                'mode': 'cells',
                'n_epochs': '250',
                'learning_rate': '0.005',
                'lambda_dreg': '5.0',
                'top_genes': '3000',
                'seed': '1234'
            }
            
            print(f"\nSending request to: {PROCESSING_ENDPOINT}")
            print(f"Parameters: {json.dumps(data, indent=2)}")
            
            # Make request
            start_time = time.time()
            response = requests.post(
                PROCESSING_ENDPOINT,
                files=files,
                data=data,
                timeout=600  # 10 minutes timeout for processing
            )
            elapsed_time = time.time() - start_time
            
            print(f"\nResponse status: {response.status_code}")
            print(f"Processing time: {elapsed_time:.2f} seconds")
            
            if response.status_code != 200:
                print(f"✗ Processing failed")
                print(f"  Status code: {response.status_code}")
                print(f"  Response: {response.text}")
                return None
            
            result = response.json()
            print(f"✓ Processing successful")
            print(f"  Success: {result.get('success')}")
            print(f"  Message: {result.get('message')}")
            
            # Check for output files
            data_dict = result.get('data', {})
            if data_dict:
                print(f"\n  Output files:")
                for filename, file_id in data_dict.items():
                    print(f"    {filename}: {file_id}")
                return data_dict
            else:
                print("  ⚠ No output files in response")
                return None
                
    except requests.exceptions.Timeout:
        print(f"✗ Request timeout (processing took too long)")
        return None
    except requests.exceptions.RequestException as e:
        print(f"✗ Request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"  Status code: {e.response.status_code}")
            print(f"  Response: {e.response.text}")
        return None
    except Exception as e:
        print(f"✗ Processing test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_download(file_id: str, expected_type: str = None):
    """Test download endpoint"""
    print("\n" + "=" * 60)
    print(f"Test 3: Download Endpoint - {file_id}")
    print("=" * 60)
    
    try:
        response = requests.get(
            f"{DOWNLOAD_ENDPOINT}/{file_id}",
            timeout=60
        )
        
        if response.status_code != 200:
            print(f"✗ Download failed")
            print(f"  Status code: {response.status_code}")
            print(f"  Response: {response.text}")
            return False
        
        # Check if response is a file
        content_type = response.headers.get('Content-Type', '')
        content_length = response.headers.get('Content-Length', '0')
        
        print(f"✓ Download successful")
        print(f"  Content-Type: {content_type}")
        print(f"  Content-Length: {int(content_length) / 1024 / 1024:.2f} MB")
        
        return True
        
    except Exception as e:
        print(f"✗ Download test failed: {e}")
        return False


def validate_outputs(data_dict: dict):
    """Validate output files in outputs directory"""
    print("\n" + "=" * 60)
    print("Test 4: Validate Output Files")
    print("=" * 60)
    
    if not data_dict:
        print("✗ No output files to validate")
        return False
    
    all_valid = True
    
    # Expected output files (updated: imputation_stats.json removed, merged into statistics.txt)
    # Cell mode may also produce: training_scores.png, auc_validation.png, mapping_score_distribution.png
    expected_files = {
        'imputed_spatial_data.h5ad': {'type': 'h5ad', 'required': True},
        'mapping_scores.csv': {'type': 'csv', 'required': True},
        'statistics.txt': {'type': 'txt', 'required': True},
        'mapping_score_distribution.png': {'type': 'png', 'required': False},
        'imputation_qc.png': {'type': 'png', 'required': False},  # legacy alias
        'training_scores.png': {'type': 'png', 'required': False},  # cell mode only
        'auc_validation.png': {'type': 'png', 'required': False},  # cell mode only
    }
    
    for filename, file_id in data_dict.items():
        file_path = os.path.join(OUTPUT_DIR, file_id)
        
        if not os.path.exists(file_path):
            print(f"✗ File not found: {filename} ({file_id})")
            all_valid = False
            continue
        
        file_size = os.path.getsize(file_path)
        print(f"\n✓ Found: {filename}")
        print(f"  File ID: {file_id}")
        print(f"  Size: {file_size / 1024:.2f} KB")
        
        # Validate file content based on type
        if filename.endswith('.h5ad'):
            try:
                adata = ad.read_h5ad(file_path)
                print(f"  ✓ Valid h5ad file")
                print(f"    Shape: {adata.shape}")
                print(f"    Obs columns: {list(adata.obs.columns)}")
                print(f"    Var columns: {list(adata.var.columns)}")
            except Exception as e:
                print(f"  ✗ Invalid h5ad file: {e}")
                all_valid = False
                
        elif filename.endswith('.csv'):
            try:
                df = pd.read_csv(file_path)
                print(f"  ✓ Valid CSV file")
                print(f"    Shape: {df.shape}")
                print(f"    Columns: {list(df.columns)}")
                if 'mapping_score' in df.columns:
                    print(f"    Mapping score range: [{df['mapping_score'].min():.4f}, {df['mapping_score'].max():.4f}]")
                    print(f"    Mapping score mean: {df['mapping_score'].mean():.4f}")
            except Exception as e:
                print(f"  ✗ Invalid CSV file: {e}")
                all_valid = False
                
        elif filename.endswith('.json'):
            try:
                with open(file_path, 'r') as f:
                    stats = json.load(f)
                print(f"  ✓ Valid JSON file")
                print(f"    Keys: {list(stats.keys())}")
            except Exception as e:
                print(f"  ✗ Invalid JSON file: {e}")
                all_valid = False
                
        elif filename.endswith('.txt'):
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                print(f"  ✓ Valid TXT file")
                print(f"    Length: {len(content)} characters")
                print(f"    Preview (first 200 chars):\n{content[:200]}...")
            except Exception as e:
                print(f"  ✗ Invalid TXT file: {e}")
                all_valid = False
                
        elif filename.endswith('.png'):
            print(f"  ✓ PNG file (visualization)")
    
    return all_valid


def main():
    """Main test function"""
    print("\n" + "=" * 60)
    print(f"Service Fix Verification Test: {SERVICE_NAME}")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print(f"Output Directory: {OUTPUT_DIR}")
    print()
    
    # Check if test data exists
    if not os.path.exists(SPATIAL_DATA_PATH):
        print(f"⚠ Spatial test data not found: {SPATIAL_DATA_PATH}")
        print("   Skipping processing test")
        spatial_path = None
    else:
        spatial_path = SPATIAL_DATA_PATH
    
    if not os.path.exists(SINGLE_CELL_DATA_PATH):
        print(f"⚠ Single-cell test data not found: {SINGLE_CELL_DATA_PATH}")
        print("   Skipping processing test")
        single_cell_path = None
    else:
        single_cell_path = SINGLE_CELL_DATA_PATH
    
    # Run tests
    results = []
    
    # Test 1: Health check
    results.append(("Health Check", test_health()))
    
    # Test 2: Processing (if data provided)
    data_dict = None
    if spatial_path and single_cell_path:
        data_dict = test_processing(spatial_path, single_cell_path)
        if data_dict:
            results.append(("Processing", True))
            
            # Test 3: Download (test one file)
            if 'imputed_spatial_data.h5ad' in data_dict:
                download_ok = test_download(data_dict['imputed_spatial_data.h5ad'])
                results.append(("Download", download_ok))
            
            # Test 4: Validate outputs
            validate_ok = validate_outputs(data_dict)
            results.append(("Output Validation", validate_ok))
        else:
            results.append(("Processing", False))
    else:
        print("\n⚠ Skipping processing test - test data not available")
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("✅ All tests passed! Service fix verified.")
        sys.exit(0)
    else:
        print("❌ Some tests failed. Service may still have issues.")
        sys.exit(1)


if __name__ == "__main__":
    main()


