FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --use-deprecated=legacy-resolver -r requirements.txt

COPY . .

ENV PORT=8080 \
    OUTPUT_DIR=/app/outputs

EXPOSE 8080

RUN mkdir -p /app/outputs

CMD ["python", "main.py"]

