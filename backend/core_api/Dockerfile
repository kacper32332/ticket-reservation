# Budowanie: docker build -f backend/core_api/Dockerfile backend
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared ./shared
COPY core_api ./core_api

EXPOSE 8000
CMD ["uvicorn", "core_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
