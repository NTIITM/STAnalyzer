#!/usr/bin/env python3
"""
Test script for verifying spatial-clustering-graphst service fixes
"""
import requests
import json
import time
import os
import sys
from pathlib import Path

# ===== CONFIGURATION =====
SERVICE_NAME = "spatial-clustering-graphst"
BASE_URL = "http://localhost:46725"
HEALTH_ENDPOINT = f"{BASE_URL}/health"
PROCESSING_ENDPOINT = f"{BASE_URL}/api/graphst-cluster"
DOWNLOAD_ENDPOINT = f"{BASE_URL}/api/download"

# Test data path (update or pass as command line argument)
TEST_DATA_PATH = "/home/common/hwluo/project/Data/ST/151507_hvg.h5ad"

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
        print(f"  Response: {json.dumps(data, indent=2)}")
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


def test_processing(test_data_path: str):
    """Test main processing endpoint"""
    print("\n" + "=" * 60)
    print("Test 2: Processing Endpoint")
    print("=" * 60)
    
    if not test_data_path or not os.path.exists(test_data_path):
        print(f"✗ Test data not found: {test_data_path}")
        return False
    
    print(f"Using test data: {test_data_path}")
    print(f"File size: {os.path.getsize(test_data_path) / 1024 / 1024:.2f} MB")
    
    try:
        # Prepare request
        with open(test_data_path, 'rb') as f:
            files = {'file': (os.path.basename(test_data_path), f, 'application/octet-stream')}
            
            # Add parameters based on service_config.json
            data = {
                'resolution': '1.0',
                'algorithm': 'leiden',
                'random_state': '41',
                'epochs': '600',
                'neighborhoods': '6',
            }
            
            print(f"\nSending request to: {PROCESSING_ENDPOINT}")
            print(f"Parameters: {json.dumps(data, indent=2)}")
            
            # Make request
            print("\n⏳ Processing (this may take several minutes)...")
            start_time = time.time()
            response = requests.post(
                PROCESSING_ENDPOINT,
                files=files,
                data=data,
                timeout=1800  # 30 minutes timeout for processing
            )
            elapsed_time = time.time() - start_time
            
            print(f"\nResponse status: {response.status_code}")
            print(f"Processing time: {elapsed_time:.2f} seconds ({elapsed_time/60:.2f} minutes)")
            
            if response.status_code != 200:
                print(f"✗ Processing failed")
                print(f"  Status code: {response.status_code}")
                print(f"  Response: {response.text}")
                return False
            
            result = response.json()
            print(f"✓ Processing successful")
            print(f"  Response: {json.dumps(result, indent=2)}")
            
            # Check for output files in data dict
            if 'data' in result and isinstance(result['data'], dict):
                data_dict = result['data']
                print(f"\n  Output files:")
                for filename, file_id in data_dict.items():
                    print(f"    {filename}: {file_id}")
                # Return first file ID for download test
                if data_dict:
                    first_file_id = list(data_dict.values())[0]
                    return first_file_id
            else:
                print("  ⚠ No output files in response")
                return True
                
    except requests.exceptions.Timeout:
        print(f"✗ Request timeout (processing took too long)")
        return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"  Status code: {e.response.status_code}")
            print(f"  Response: {e.response.text}")
        return False
    except Exception as e:
        print(f"✗ Processing test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_download(file_id: str):
    """Test download endpoint"""
    if not file_id:
        print("\n" + "=" * 60)
        print("Test 3: Download Endpoint (skipped - no file ID)")
        print("=" * 60)
        return True
    
    print("\n" + "=" * 60)
    print("Test 3: Download Endpoint")
    print("=" * 60)
    
    try:
        # Note: The endpoint uses path parameter, not query parameter
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
        print(f"  File ID: {file_id}")
        print(f"  Content-Type: {content_type}")
        print(f"  Content-Length: {content_length} bytes ({int(content_length)/1024/1024:.2f} MB)")
        
        return True
        
    except Exception as e:
        print(f"✗ Download test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test function"""
    print("\n" + "=" * 60)
    print(f"Service Fix Verification Test: {SERVICE_NAME}")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print()
    
    # Get test data path
    test_data_path = TEST_DATA_PATH
    if len(sys.argv) > 1:
        test_data_path = sys.argv[1]
    
    if not test_data_path:
        print("⚠ No test data provided")
        print("Usage: python test_service_fix.py <test_data_path>")
        print("Or set TEST_DATA_PATH in the script")
        print()
        # Still test health check
        health_ok = test_health()
        sys.exit(0 if health_ok else 1)
    
    # Run tests
    results = []
    
    # Test 1: Health check
    results.append(("Health Check", test_health()))
    
    # Test 2: Processing (if data provided)
    if test_data_path:
        file_id = test_processing(test_data_path)
        if isinstance(file_id, str):
            results.append(("Processing", True))
            # Test 3: Download
            results.append(("Download", test_download(file_id)))
        else:
            results.append(("Processing", file_id))
    
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




























