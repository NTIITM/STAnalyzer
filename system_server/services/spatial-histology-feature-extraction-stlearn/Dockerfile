FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PORT=53903 \
    OUTPUT_DIR=/app/outputs

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/outputs

EXPOSE 53903

CMD ["python", "main.py"]
