FROM python:3.10-slim

# On met à jour les noms des paquets pour Debian récent
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libgthread-2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY inference.py .
COPY weights/ ./weights/

ENV PYTHONUNBUFFERED=1

CMD ["python", "inference.py"]