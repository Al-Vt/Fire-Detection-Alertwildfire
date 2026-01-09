#!/usr/bin/env python3
"""
ALERTWildfire Camera Scraper - Batch Structure
Organisé par Date/Heure pour Airflow
"""
import boto3
from database import DatabaseManager
import os
import time
import logging
import argparse
import hashlib
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# =============================================================================
# CONFIGURATION
# =============================================================================

# Création d'un ID unique pour ce lancement (ex: 20260108_123000)
BATCH_ID = datetime.now().strftime("%Y%m%d_%H%M%S")

BASE_DIR = Path("alertwildfire_data")
# Les images iront dans raw/20260108_123000/
SUCCESS_DIR = BASE_DIR / "raw" / BATCH_ID 
ERROR_DIR = BASE_DIR / "errors" / BATCH_ID

DEFAULT_INTERVAL = 300 
PAGE_TIMEOUT = 45 

# Ta liste complète
CAMERA_URLS = [
    "https://www.alertwildfire.org/?currentFirecam=ca-alder-hill-1&viewMode=Grid",  # Alder Hill 1
    "https://www.alertwildfire.org/?currentFirecam=ca-alpine-meadows-ctc-1&viewMode=Grid",  # Alpine Meadows CTC 1
    "https://www.alertwildfire.org/?currentFirecam=ca-alta-peak-1&viewMode=Grid",  # Alta Peak 1
    "https://www.alertwildfire.org/?currentFirecam=id-anderson-1&viewMode=Grid",  # Anderson 1
    "https://www.alertwildfire.org/?currentFirecam=nv-angel-peak-1&viewMode=Grid",  # Angel Peak 1
    "https://www.alertwildfire.org/?currentFirecam=nv-armstrong-lookout-1&viewMode=Grid",  # Armstrong Lookout 1
    "https://www.alertwildfire.org/?currentFirecam=nv-armstrong-lookout-2&viewMode=Grid",  # Armstrong Lookout 2
    "https://www.alertwildfire.org/?currentFirecam=ca-babbitt-peak-1&viewMode=Grid",  # Babbitt Peak 1
    "https://www.alertwildfire.org/?currentFirecam=ca-bald-mtn-eldorado-1&viewMode=Grid",  # Bald Mtn ElDorado 1
    "https://www.alertwildfire.org/?currentFirecam=ca-bald-mtn-eldorado-2&viewMode=Grid",  # Bald Mtn ElDorado 2
    "https://www.alertwildfire.org/?currentFirecam=nv-bald-mtn-1&viewMode=Grid",  # Bald Mtn NV 1
    "https://www.alertwildfire.org/?currentFirecam=id-bennett-mtn-1&viewMode=Grid",  # Bennett Mtn ID 1
    "https://www.alertwildfire.org/?currentFirecam=id-big-bald-mtn-1&viewMode=Grid",  # Big Bald Mtn 1
    "https://www.alertwildfire.org/?currentFirecam=id-big-hill-1&viewMode=Grid",  # Big Hill 1
    "https://www.alertwildfire.org/?currentFirecam=nv-black-mtn-1&viewMode=Grid",  # Black Mtn NV 1
    "https://www.alertwildfire.org/?currentFirecam=ca-blackwood-canyon-1&viewMode=Grid",  # Blackwood Canyon (Temp) 1
    "https://www.alertwildfire.org/?currentFirecam=nv-brock-1&viewMode=Grid",  # Brock 1
    "https://www.alertwildfire.org/?currentFirecam=ca-buckskin-mtn-1&viewMode=Grid",  # Buckskin Mtn 1
    "https://www.alertwildfire.org/?currentFirecam=ca-bunker-hill-1&viewMode=Grid",  # Bunker Hill 1
    "https://www.alertwildfire.org/?currentFirecam=nv-calaveras-1&viewMode=Grid",  # Calaveras NV 1
    "https://www.alertwildfire.org/?currentFirecam=nv-callaghan-peak-1&viewMode=Grid",  # Callaghan Peak 1
    "https://www.alertwildfire.org/?currentFirecam=ca-carson-hill-1&viewMode=Grid",  # Carson Hill 1
    "https://www.alertwildfire.org/?currentFirecam=nv-cave-mtn-1&viewMode=Grid",  # Cave Mtn 1
    "https://www.alertwildfire.org/?currentFirecam=nv-cave-mtn-2&viewMode=Grid",  # Cave Mtn 2
    "https://www.alertwildfire.org/?currentFirecam=ca-chimney-peak-1&viewMode=Grid",  # Chimney Peak 1
    "https://www.alertwildfire.org/?currentFirecam=nv-deer-mountain-1&viewMode=Grid",  # Deer Mountain 1
    "https://www.alertwildfire.org/?currentFirecam=ca-delano-1&viewMode=Grid",  # Delano 1
    "https://www.alertwildfire.org/?currentFirecam=nv-diamond-peak-1&viewMode=Grid",  # Diamond Peak NV 1
    "https://www.alertwildfire.org/?currentFirecam=ca-dl-bliss-state-park-1&viewMode=Grid",  # DL Bliss State Park 1
    "https://www.alertwildfire.org/?currentFirecam=ca-dollar-point-1&viewMode=Grid",  # Dollar Point 1
    "https://www.alertwildfire.org/?currentFirecam=nv-dolly-varden-1&viewMode=Grid",  # Dolly Varden 1
    "https://www.alertwildfire.org/?currentFirecam=ca-eagle-peak-1&viewMode=Grid",  # Eagle Peak 1
    "https://www.alertwildfire.org/?currentFirecam=ca-edgewood-tahoe-resort-1&viewMode=Grid",  # Edgewood Tahoe Resort 1
    "https://www.alertwildfire.org/?currentFirecam=nv-elephant-1&viewMode=Grid",  # Elephant 1
    "https://www.alertwildfire.org/?currentFirecam=nv-elko-mountain-1&viewMode=Grid",  # Elko Mountain 1
    "https://www.alertwildfire.org/?currentFirecam=nv-ella-mtn-1&viewMode=Grid",  # Ella Mtn 1
    "https://www.alertwildfire.org/?currentFirecam=nv-fairview-peak-1&viewMode=Grid",  # Fairview Peak 1
    "https://www.alertwildfire.org/?currentFirecam=nv-fairview-peak-2&viewMode=Grid",  # Fairview Peak 2
    "https://www.alertwildfire.org/?currentFirecam=ca-fallen-leaf-lake-1&viewMode=Grid",  # Fallen Leaf Lake 1
    "https://www.alertwildfire.org/?currentFirecam=ca-fort-sage-1&viewMode=Grid",  # Fort Sage 1
    "https://www.alertwildfire.org/?currentFirecam=nv-fortynine-mtn-1&viewMode=Grid",  # Fortynine Mtn 1
    "https://www.alertwildfire.org/?currentFirecam=nv-fox-mtn-1&viewMode=Grid",  # Fox Mtn 1
    "https://www.alertwildfire.org/?currentFirecam=nv-genoa-peak-1&viewMode=Grid",  # Genoa Peak 1
    "https://www.alertwildfire.org/?currentFirecam=nv-gerlach-1&viewMode=Grid",  # Gerlach (Mobile) 1
    "https://www.alertwildfire.org/?currentFirecam=nv-hawkins-peak-1&viewMode=Grid",  # Hawkins Peak 1
    "https://www.alertwildfire.org/?currentFirecam=nv-hayden-peak-1&viewMode=Grid",  # Hayden Peak 1
    "https://www.alertwildfire.org/?currentFirecam=ca-heavenly-ski-area-1&viewMode=Grid",  # Heavenly Ski Area 1
    "https://www.alertwildfire.org/?currentFirecam=ca-heavenly-ski-area-2&viewMode=Grid",  # Heavenly Ski Area 2
    "https://www.alertwildfire.org/?currentFirecam=nv-highland-peak-1&viewMode=Grid",  # Highland Peak NV 1
    "https://www.alertwildfire.org/?currentFirecam=nv-hillside-1&viewMode=Grid",  # Hillside NV 1
    "https://www.alertwildfire.org/?currentFirecam=ca-homewood-ski-area-1&viewMode=Grid",  # Homewood Ski Area 1
    "https://www.alertwildfire.org/?currentFirecam=ca-homewood-ski-area-2&viewMode=Grid",  # Homewood Ski Area 2
    "https://www.alertwildfire.org/?currentFirecam=nv-jacks-peak-1&viewMode=Grid",  # Jacks Peak 1
    "https://www.alertwildfire.org/?currentFirecam=ca-kern-mtns-1&viewMode=Grid",  # Kern Mtns 1
    "https://www.alertwildfire.org/?currentFirecam=nv-knoll-mtn-1&viewMode=Grid",  # Knoll Mtn 1
    "https://www.alertwildfire.org/?currentFirecam=nv-kyle-canyon-1&viewMode=Grid",  # Kyle Canyon 1
    "https://www.alertwildfire.org/?currentFirecam=nv-lamoille-1&viewMode=Grid",  # Lamoille 1
    "https://www.alertwildfire.org/?currentFirecam=nv-lamoille-2&viewMode=Grid",  # Lamoille 2
    "https://www.alertwildfire.org/?currentFirecam=ca-leek-springs-1&viewMode=Grid",  # Leek Springs 1
    "https://www.alertwildfire.org/?currentFirecam=nv-little-valley-1&viewMode=Grid",  # Little Valley, NV 1
    "https://www.alertwildfire.org/?currentFirecam=ca-maggies-peak-1&viewMode=Grid",  # Maggies Peak 1
    "https://www.alertwildfire.org/?currentFirecam=ca-martis-peak-1&viewMode=Grid",  # Martis Peak 1
    "https://www.alertwildfire.org/?currentFirecam=nv-mcclellan-peak-1&viewMode=Grid",  # McClellan Peak NV 1
    "https://www.alertwildfire.org/?currentFirecam=nv-midas-peak-1&viewMode=Grid",  # Midas Peak 1
    "https://www.alertwildfire.org/?currentFirecam=nv-minden-1&viewMode=Grid",  # Minden 1
    "https://www.alertwildfire.org/?currentFirecam=nv-mohawk-esmeralda-1&viewMode=Grid",  # Mohawk Esmeralda 1
    "https://www.alertwildfire.org/?currentFirecam=nv-montezuma-pk-1&viewMode=Grid",  # Montezuma Pk 1
    "https://www.alertwildfire.org/?currentFirecam=nv-mt-wilson-lincoln-1&viewMode=Grid",  # Mt Wilson Lincoln 1
    "https://www.alertwildfire.org/?currentFirecam=nv-mt-charleston-1&viewMode=Grid",  # Mt. Charleston 1
    "https://www.alertwildfire.org/?currentFirecam=id-mt-cotterel-1&viewMode=Grid",  # Mt. Cotterel 1
    "https://www.alertwildfire.org/?currentFirecam=id-mt-danaher-1&viewMode=Grid",  # Mt. Danaher 1
    "https://www.alertwildfire.org/?currentFirecam=id-mt-harrison-1&viewMode=Grid",  # Mt. Harrison 1
    "https://www.alertwildfire.org/?currentFirecam=nv-mt-lewis-1&viewMode=Grid",  # Mt. Lewis 1
    "https://www.alertwildfire.org/?currentFirecam=nv-mt-lewis-2&viewMode=Grid",  # Mt. Lewis 2
    "https://www.alertwildfire.org/?currentFirecam=nv-mt-lincoln-1&viewMode=Grid",  # Mt. Lincoln 1
    "https://www.alertwildfire.org/?currentFirecam=nv-new-york-peak-1&viewMode=Grid",  # New York Peak 1
    "https://www.alertwildfire.org/?currentFirecam=nv-noaa-reno-1&viewMode=Grid",  # NOAA Reno NV 1
    "https://www.alertwildfire.org/?currentFirecam=ca-north-mokelumne-1&viewMode=Grid",  # North Mokelumne 1
    "https://www.alertwildfire.org/?currentFirecam=id-notch-butte-1&viewMode=Grid",  # Notch Butte 1
    "https://www.alertwildfire.org/?currentFirecam=nv-energy-south-reno-1&viewMode=Grid",  # NV Energy South Reno 1
    "https://www.alertwildfire.org/?currentFirecam=nv-energy-south-reno-2&viewMode=Grid",  # NV Energy South Reno 2
    "https://www.alertwildfire.org/?currentFirecam=nv-opal-mtn-1&viewMode=Grid",  # Opal Mtn 1
    "https://www.alertwildfire.org/?currentFirecam=nv-pearl-1&viewMode=Grid",  # Pearl 1
    "https://www.alertwildfire.org/?currentFirecam=nv-peavine-peak-1&viewMode=Grid",  # Peavine Peak NV 1
    "https://www.alertwildfire.org/?currentFirecam=nv-penn-peak-1&viewMode=Grid",  # Penn Peak 1
    "https://www.alertwildfire.org/?currentFirecam=nv-pilot-peak-1&viewMode=Grid",  # Pilot Peak NV 1
    "https://www.alertwildfire.org/?currentFirecam=ca-pinegrove-1&viewMode=Grid",  # Pinegrove 1
    "https://www.alertwildfire.org/?currentFirecam=nv-potosi-north-1&viewMode=Grid",  # Potosi North 1
    "https://www.alertwildfire.org/?currentFirecam=nv-potosi-north-2&viewMode=Grid",  # Potosi North 2
    "https://www.alertwildfire.org/?currentFirecam=nv-potosi-south-1&viewMode=Grid",  # Potosi South 1
    "https://www.alertwildfire.org/?currentFirecam=nv-potosi-south-2&viewMode=Grid",  # Potosi South 2
    "https://www.alertwildfire.org/?currentFirecam=ca-prospect-peak-1&viewMode=Grid",  # Prospect Peak 1
    "https://www.alertwildfire.org/?currentFirecam=ca-prospect-peak-2&viewMode=Grid",  # Prospect Peak 2
    "https://www.alertwildfire.org/?currentFirecam=nv-queen-bee-1&viewMode=Grid",  # Queen Bee 1
    "https://www.alertwildfire.org/?currentFirecam=nv-rawe-peak-1&viewMode=Grid",  # Rawe Peak NV 1
    "https://www.alertwildfire.org/?currentFirecam=nv-ridge-tahoe-1&viewMode=Grid",  # Ridge Tahoe NV 1
    "https://www.alertwildfire.org/?currentFirecam=id-rockland-1&viewMode=Grid",  # Rockland 1
    "https://www.alertwildfire.org/?currentFirecam=nv-sage-hen-1&viewMode=Grid",  # Sage Hen 1
    "https://www.alertwildfire.org/?currentFirecam=nv-sehewokii-neweneean-katete-1&viewMode=Grid",  # Sehewoki'i Newenee'an Katete 1
    "https://www.alertwildfire.org/?currentFirecam=ca-serene-lakes-1&viewMode=Grid",  # Serene Lakes 1
    "https://www.alertwildfire.org/?currentFirecam=id-shafer-butte-1&viewMode=Grid",  # Shafer Butte 1
    "https://www.alertwildfire.org/?currentFirecam=id-sheep-two-1&viewMode=Grid",  # Sheep Two 1
    "https://www.alertwildfire.org/?currentFirecam=nv-siberia-1&viewMode=Grid",  # Siberia 1
    "https://www.alertwildfire.org/?currentFirecam=ca-sierra-at-tahoe-1&viewMode=Grid",  # Sierra at Tahoe 1
    "https://www.alertwildfire.org/?currentFirecam=nv-singatse-peak-1&viewMode=Grid",  # Singatse Peak NV 1
    "https://www.alertwildfire.org/?currentFirecam=az-sky-dome-nau-1&viewMode=Grid",  # Sky Dome NAU 1
    "https://www.alertwildfire.org/?currentFirecam=nv-slide-mtn-1&viewMode=Grid",  # Slide Mtn NV 1
    "https://www.alertwildfire.org/?currentFirecam=nv-slide-mtn-2&viewMode=Grid",  # Slide Mtn NV 2
    "https://www.alertwildfire.org/?currentFirecam=nv-smith-1&viewMode=Grid",  # Smith 1
    "https://www.alertwildfire.org/?currentFirecam=nv-snow-valley-peak-1&viewMode=Grid",  # Snow Valley Peak NV 1
    "https://www.alertwildfire.org/?currentFirecam=nv-sonoma-peak-1&viewMode=Grid",  # Sonoma Peak 1
    "https://www.alertwildfire.org/?currentFirecam=nv-spruce-mtn-1&viewMode=Grid",  # Spruce Mtn 1
    "https://www.alertwildfire.org/?currentFirecam=nv-star-nevada-1&viewMode=Grid",  # Star Nevada 1
    "https://www.alertwildfire.org/?currentFirecam=nv-steamboat-1&viewMode=Grid",  # Steamboat NV 1
    "https://www.alertwildfire.org/?currentFirecam=nv-summit-lake-1&viewMode=Grid",  # Summit Lake 1
    "https://www.alertwildfire.org/?currentFirecam=nv-swales-mtn-1&viewMode=Grid",  # Swales Mtn 1
    "https://www.alertwildfire.org/?currentFirecam=ca-tahoe-donner-1&viewMode=Grid",  # Tahoe Donner 1
    "https://www.alertwildfire.org/?currentFirecam=nv-tenabo-mtn-1&viewMode=Grid",  # Tenabo Mtn 1
    "https://www.alertwildfire.org/?currentFirecam=nv-tv-hill-1&viewMode=Grid",  # TV Hill 1
    "https://www.alertwildfire.org/?currentFirecam=nv-upper-peavine-1&viewMode=Grid",  # Upper Peavine 1
    "https://www.alertwildfire.org/?currentFirecam=nv-virginia-peak-1&viewMode=Grid",  # Virginia Peak 1
    "https://www.alertwildfire.org/?currentFirecam=nv-winnemucca-mountain-1&viewMode=Grid",  # Winnemucca Mountain 1
    "https://www.alertwildfire.org/?currentFirecam=nv-yellow-pk-1&viewMode=Grid",  # Yellow Pk 1
    "https://www.alertwildfire.org/?currentFirecam=nv-zephyr-1&viewMode=Grid",  # Zephyr, NV (Big George Ventures) 1
]

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'scraper_{BATCH_ID}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# =============================================================================
# HELPERS
# =============================================================================

def get_camera_name_from_url(url: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    if 'currentFirecam' in params:
        return params['currentFirecam'][0]
    return "unknown_camera"

def setup_driver() -> webdriver.Chrome:
    chrome_options = Options()
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(PAGE_TIMEOUT)
    return driver

class AlertWildfireScraper:
    
    def __init__(self):
        # Création du dossier spécifique à CE run (pour backup local optionnel)
        SUCCESS_DIR.mkdir(parents=True, exist_ok=True)
        ERROR_DIR.mkdir(parents=True, exist_ok=True)
        
        self.driver = None
        self.last_hashes = {} 
        self.stats = {'total': 0, 'success': 0, 'failed': 0}
        
        # ✅ AJOUT S3 et DB
        self.s3 = boto3.client('s3')
        self.bucket = os.getenv("S3_BUCKET_NAME")
        self.db = DatabaseManager()
    
    def start(self):
        logger.info(f"Démarrage Batch {BATCH_ID}...")
        self.driver = setup_driver()
    
    def stop(self):
        if self.driver:
            self.driver.quit()
        # ✅ Fermer la DB
        if self.db:
            self.db.close()
    
    def scrape_camera(self, url: str) -> bool:
        camera_name = get_camera_name_from_url(url)
        self.stats['total'] += 1
        
        try:
            logger.info(f"Traitement: {camera_name}")
            self.driver.get(url)
            wait = WebDriverWait(self.driver, 20)
            
            # --- TENTATIVE DE CAPTURE ---
            try:
                target_img = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "img.firecam-image")))
                wait.until(lambda d: target_img.get_attribute("src") and len(target_img.get_attribute("src")) > 10)
                time.sleep(2)
            except Exception:
                logger.warning(f"Fallback conteneur pour {camera_name}")
                target_img = self.driver.find_element(By.CSS_SELECTOR, ".ui-layout-center, #firecam-view")

            # ✅ SAUVEGARDE LOCALE (pour debug)
            filename = f"{camera_name}.png"
            filepath = SUCCESS_DIR / filename
            target_img.screenshot(str(filepath))
            
            # ✅ UPLOAD S3
            s3_path = f"raw/{BATCH_ID}/{filename}"
            with open(filepath, 'rb') as f:
                self.s3.put_object(
                    Bucket=self.bucket,
                    Key=s3_path,
                    Body=f.read()
                )
            
            # ✅ INSERT DATABASE
            self.db.insert_image(BATCH_ID, camera_name, s3_path)
            
            logger.info(f"✅ Sauvegardé: S3={s3_path}, Local={filepath}")
            self.stats['success'] += 1
            return True

        except Exception as e:
            logger.error(f"❌ ÉCHEC {camera_name}: {e}")
            self.stats['failed'] += 1
            
            try:
                error_path = ERROR_DIR / f"{camera_name}_ERROR.png"
                self.driver.save_screenshot(str(error_path))
            except: 
                pass
            return False

    def scrape_all(self, max_cameras: int = None):
        urls = CAMERA_URLS[:max_cameras] if max_cameras else CAMERA_URLS
        logger.info(f"Lancement du batch sur {len(urls)} caméras...")
        for url in urls:
            self.scrape_camera(url)
            time.sleep(1)

# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--continuous', '-c', action='store_true')
    parser.add_argument('--cameras', '-n', type=int, default=None)
    
    args = parser.parse_args()
    
    scraper = AlertWildfireScraper()
    
    try:
        scraper.start()
        
        if args.continuous:
            logger.warning("Mode continu activé : attention, tout ira dans le même dossier de batch.")
            while True:
                scraper.scrape_all(args.cameras)
                time.sleep(DEFAULT_INTERVAL)
        else:
            # MODE STANDARD POUR AIRFLOW (One Shot)
            scraper.scrape_all(args.cameras)
            
    finally:
        scraper.stop()
        logger.info(f"Fin du Batch {BATCH_ID}. Résumé: {scraper.stats}")

if __name__ == "__main__":
    main()