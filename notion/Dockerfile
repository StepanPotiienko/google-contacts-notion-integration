# syntax=docker/dockerfile:1
FROM python:3.14-slim

WORKDIR /app

COPY notion/requirements.txt ./

RUN pip install --no-cache-dir -r ./requirements.txt

COPY .env /app/.env
COPY notion/ /app

RUN useradd user
USER user

CMD ["python3", "delete_duplicates.py"]