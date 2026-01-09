# On part d'une version Python officielle
FROM python:3.10-slim

# Installation des dépendances système pour Chrome et Postgres
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Installation de Chrome (nécessaire pour Selenium)
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update && apt-get install -y google-chrome-stable

# On prépare le dossier de travail
WORKDIR /app

# Copie des requirements et installation
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du reste du code
COPY . .

# Commande de lancement (on s'assure que python tourne sans buffer pour voir les logs)
ENV PYTHONUNBUFFERED=1
CMD ["python", "main_scraper.py"]