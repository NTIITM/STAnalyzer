FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# Set working directory
WORKDIR /app

# Install Python 3.10 and system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3.10-dev \
    python3-pip \
    gcc \
    g++ \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create symbolic links (override existing pip/python links to avoid build failures)
RUN ln -sf /usr/bin/python3.10 /usr/bin/python && \
    ln -sf /usr/bin/pip3 /usr/bin/pip

# Copy dependency file
COPY requirements.txt .

# Install Python dependencies
# Install PyTorch (CUDA 11.8 version)
RUN pip install --no-cache-dir torch==2.0.1 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Install other dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy GraphST directory and install (must be before copying application code)
COPY GraphST /app/GraphST

# Fix GraphST package structure issues
# setup.py has packages = ["GraphST"] which only installs inner package, but we need outer package structure to support from GraphST.GraphST import GraphST
# Modify setup.py to use find_packages() to automatically discover all packages
RUN sed -i 's/packages = \["GraphST"\]/packages = find_packages()/g' /app/GraphST/setup.py

# Fix outer __init__.py to import from inner GraphST subpackage
RUN cat > /app/GraphST/__init__.py << 'EOF'
#!/usr/bin/env python
"""
# Author: Yahui Long
# File Name: __init__.py
# Description: Fixed to import from inner GraphST package
"""

__author__ = "Yahui Long"
__email__ = "long_yahui@immunol.a-star.edu.sg"

# Import from inner GraphST package
from GraphST.GraphST.utils import clustering
from GraphST.GraphST.preprocess import preprocess_adj, preprocess, construct_interaction, construct_interaction_KNN, add_contrastive_label, get_feature, permutation, fix_seed, filter_with_overlap_gene
EOF

# Install GraphST in editable mode
RUN cd /app/GraphST && pip install --no-cache-dir -e .

# Add GraphST directory to PYTHONPATH to ensure imports work correctly
# This allows from GraphST.GraphST import GraphST to work properly
ENV PYTHONPATH=/app/GraphST

# Copy application code
COPY . .

# Fix outer __init__.py again (because COPY . . may have overwritten the previous fix)
RUN cat > /app/GraphST/__init__.py << 'EOF'
#!/usr/bin/env python
"""
# Author: Yahui Long
# File Name: __init__.py
# Description: Fixed to import from inner GraphST package
"""

__author__ = "Yahui Long"
__email__ = "long_yahui@immunol.a-star.edu.sg"

# Import from inner GraphST package
from GraphST.GraphST.utils import clustering
from GraphST.GraphST.preprocess import preprocess_adj, preprocess, construct_interaction, construct_interaction_KNN, add_contrastive_label, get_feature, permutation, fix_seed, filter_with_overlap_gene
EOF

# Create output directory
RUN mkdir -p /app/outputs

# Expose port
EXPOSE 8080

# Set environment variables
ENV PORT=8080
ENV OUTPUT_DIR=/app/outputs

# Start command
CMD ["python", "main.py"]


