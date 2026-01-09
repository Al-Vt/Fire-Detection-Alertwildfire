import time
import os
import logging
import uuid
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# Selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# AWS & DB
import boto3
from dotenv import load_dotenv
from database import DatabaseManager  # Notre fichier database.py
from alertwildfire_urls_list import ALERTWILDFIRE_URLS  # Ta liste d'URLs

# Configuration Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

# Config AWS S3
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "eu-west-3")
BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

# ID unique pour ce lancement (pour grouper les images)
BATCH_ID = datetime.now().strftime("%Y%m%d_%H%M%S")

class S3Uploader:
    def __init__(self):
        try:
            self.s3 = boto3.client(
                's3',
                aws_access_key_id=AWS_ACCESS_KEY,
                aws_secret_access_key=AWS_SECRET_KEY,
                region_name=AWS_REGION
            )
        except Exception as e:
            logger.error(f"❌ Erreur connexion S3: {e}")
            self.s3 = None

    def upload_image_bytes(self, image_bytes, filename):
        if not self.s3: return None
        try:
            # On range par date: raw/2026-01-08/cam1.png
            date_folder = datetime.now().strftime("%Y-%m-%d")
            s3_path = f"raw/{date_folder}/{filename}"
            
            self.s3.put_object(Bucket=BUCKET_NAME, Key=s3_path, Body=image_bytes)
            logger.info(f"✅ Upload S3 réussi : {s3_path}")
            return s3_path
        except Exception as e:
            logger.error(f"❌ Erreur Upload S3: {e}")
            return None

class AlertWildfireScraper:
    def __init__(self):
        self.driver = None
        self.uploader = S3Uploader()
        try:
            self.db = DatabaseManager()
            logger.info("✅ Connecté à la DB Neon.")
        except Exception as e:
            logger.error("⚠️ Impossible de se connecter à la DB. Mode dégradé.")
            self.db = None
    
    def setup_driver(self):
        chrome_options = Options()
        # Options indispensables pour Docker
        chrome_options.add_argument("--headless=new") 
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)

    def get_camera_name(self, url):
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        # On essaie de trouver le nom dans l'URL, sinon un nom par défaut
        name = params.get('camera', ['unknown'])[0]
        if name == 'unknown':
             # Fallback sur un hash si l'url est bizarre
             name = f"cam_{uuid.uuid4().hex[:8]}"
        return name

    def scrape_camera(self, url):
        camera_name = self.get_camera_name(url)
        logger.info(f"📸 Traitement : {camera_name}")
        
        try:
            self.driver.get(url)
            # Attente intelligente de l'image
            wait = WebDriverWait(self.driver, 15)
            # On cherche l'image principale (le sélecteur peut varier selon le site)
            # Ici on prend un sélecteur générique souvent utilisé ou le body pour un screenshot global
            time.sleep(5) # Petite pause pour le chargement complet (simple et efficace)
            
            # On prend le screenshot
            img_data = self.driver.get_screenshot_as_png()
            filename = f"{camera_name}_{uuid.uuid4().hex[:6]}.png"
            
            # 1. Upload S3
            s3_path = self.uploader.upload_image_bytes(img_data, filename)
            
            # 2. Insert DB
            if s3_path and self.db:
                self.db.insert_image(BATCH_ID, camera_name, s3_path)

        except Exception as e:
            logger.error(f"❌ Échec capture {camera_name}: {e}")

    def run(self):
        self.setup_driver()
        try:
            # On prend les 5 premières caméras pour tester
            for url in ALERTWILDFIRE_URLS[:5]: 
                self.scrape_camera(url)
        finally:
            self.driver.quit()
            if self.db: self.db.close()

if __name__ == "__main__":
    logger.info("--- Démarrage du Scraper (Docker) ---")
    while True:
        scraper = AlertWildfireScraper()
        scraper.run()
        logger.info("Pause de 5 minutes...")
        time.sleep(300) # Pause de 5 min avant de recommencer