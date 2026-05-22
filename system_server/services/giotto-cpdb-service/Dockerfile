FROM python:3.10-slim

WORKDIR /app/system_server

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    r-base \
    r-base-dev \
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
COPY services/giotto-cpdb-service/requirements.txt ./services/giotto-cpdb-service/requirements.txt

RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r services/giotto-cpdb-service/requirements.txt

COPY . .

RUN mkdir -p /app/outputs

ENV PORT=8080
ENV OUTPUT_DIR=/app/outputs

EXPOSE 8080

WORKDIR /app/system_server/services/giotto-cpdb-service

CMD ["python", "main.py"]

