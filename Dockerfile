FROM python:3.9-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY ./requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY ./backend /app/backend

CMD ["uvicorn", "main:app", "--app-dir", "backend/booking-api", "--host", "0.0.0.0", "--port", "8000"]