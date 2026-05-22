#!/bin/bash
set -e

# This shell script validates that all newly integrated spatial services function seamlessly.
# Remember to ensure the docker containers have fully completed their initial builds 
# via `docker-compose logs -f` respectively before triggering this script!

H5AD_TEST_FILE="/home/common/hwluo/project/textMSA/textmsa/sample_data/Xenium_V1_Human_Lung_Cancer_Addon_FFPE_outs.h5ad"

echo "====================================================="
echo "1. Testing Spatial Neighborhood Enrichment (Squidpy)"
echo "====================================================="
cd /home/common/hwluo/project/system_server/services/spatial-neighborhood-enrichment-squidpy
python test_api.py $H5AD_TEST_FILE "region" || echo "Note: If connection refused, ensure docker container 'spatial-squidpy-enrichment' is running on port 53901."

echo ""
echo "====================================================="
echo "2. Testing Spatial Point Pattern Analysis (Ripley's)"
echo "====================================================="
cd /home/common/hwluo/project/system_server/services/spatial-point-pattern-analysis
python test_api.py $H5AD_TEST_FILE "region" || echo "Note: If connection refused, ensure docker container 'spatial-point-pattern-analysis' is running on port 53902."

echo ""
echo "====================================================="
echo "3. Testing Histology Feature Extraction (stLearn)"
echo "====================================================="
cd /home/common/hwluo/project/system_server/services/spatial-histology-feature-extraction-stlearn
python test_api.py $H5AD_TEST_FILE || echo "Note: If connection refused, ensure docker container 'spatial-histology-feature-extraction' is running on port 53903."

echo "====================================================="
echo "Validation Routine Exhausted."
echo "====================================================="
