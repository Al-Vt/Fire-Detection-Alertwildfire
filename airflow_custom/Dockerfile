# On part de l'image officielle Airflow
FROM apache/airflow:2.8.0-python3.10

USER root

# 1. Installation des outils système (Chrome pour Selenium + Libs pour OpenCV)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 2. Installation de Chrome (Scraper)
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update && apt-get install -y google-chrome-stable

USER airflow

# 3. Installation de PyTorch CPU (SEUL, sur l'index spécifique)
RUN pip install --no-cache-dir "torch==2.5.1" "torchvision==0.20.1" --index-url https://download.pytorch.org/whl/cpu

# 4. Installation des autres librairies (sur l'index standard PyPI)
RUN pip install --no-cache-dir \
    "numpy<2.0.0" \
    "pyarrow==14.0.1" \
    "ultralytics==8.1.0" \
    "boto3" \
    "psycopg2-binary" \
    "selenium" \
    "webdriver-manager" \
    "mlflow" \
    "python-dotenv"