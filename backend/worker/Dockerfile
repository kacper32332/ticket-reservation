# Budowanie: docker build -f backend/worker/Dockerfile backend
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared ./shared
COPY worker ./worker

CMD ["python", "-m", "worker.main"]
