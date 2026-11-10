# Budowanie: docker build -f backend/booking_api/Dockerfile backend
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared ./shared
COPY booking_api ./booking_api

EXPOSE 8000
CMD ["uvicorn", "booking_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
