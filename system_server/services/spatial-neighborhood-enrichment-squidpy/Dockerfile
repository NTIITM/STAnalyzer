FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PORT=53901 \
    OUTPUT_DIR=/app/outputs

WORKDIR /app

RUN apt-get update && apt-get install -y gcc g++ && rm -rf /var/lib/apt/lists/*

# Install in batches with retries so each layer is cached independently
RUN pip install --no-cache-dir --timeout 600 "fastapi==0.110.0" "uvicorn==0.29.0" "python-multipart==0.0.9"
RUN pip install --no-cache-dir --timeout 600 "numpy==1.24.4" "pandas==2.2.1"
RUN pip install --no-cache-dir --timeout 600 "anndata==0.10.6"
RUN pip install --no-cache-dir --timeout 600 "scipy==1.13.0" "matplotlib==3.8.3" "seaborn==0.13.2"
RUN pip install --no-cache-dir --timeout 600 "scikit-learn==1.3.2"
RUN pip install --no-cache-dir --timeout 600 "scikit-image==0.19.3"
RUN pip install --no-cache-dir --timeout 600 "scanpy==1.9.8"
# Install dask pinned version BEFORE squidpy to avoid spatialdata pulling newer dask
RUN pip install --no-cache-dir --timeout 600 "dask[dataframe]==2023.3.0"
RUN pip install --no-cache-dir --timeout 600 "squidpy==1.3.1"

COPY . .

RUN mkdir -p /app/outputs

EXPOSE 53901

CMD ["python", "main.py"]
