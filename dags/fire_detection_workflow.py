from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.email import send_email  # <--- On utilise l'outil officiel
from datetime import datetime, timedelta
import os
import boto3
import mlflow
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from database import DatabaseManager 
# from alertwildfire_urls_list import CAMERA_URLS

# --- CONFIGURATION ---
default_args = {
    'owner': 'axel',
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
    'start_date': datetime(2024, 1, 1),
    'catchup': False,
    'email_on_failure': False, # Tu peux mettre True si tu veux être averti quand ça plante
}

MLFLOW_TRACKING_URI = "http://mlflow:5000"

# --- TÂCHE 1 : SCRAPING (Inchangée) ---
def task_scrape_images(**context):
    print("📸 Début du scraping...")
    from scraper import AlertWildfireScraper
    
    scraper = AlertWildfireScraper()
    scraper.start()
    scraper.scrape_all()  # Toutes les 165 caméras !
    scraper.stop()
    print("✅ Scraping terminé.")

# --- TÂCHE 2 : INFÉRENCE + EMAIL + MONITORING (Améliorée) ---
def task_run_inference(**context):
    print("Debut de l'analyse IA...")

    # Import du module inference avec monitoring
    import sys
    sys.path.insert(0, '/opt/airflow')
    from model.inference import FireDetector

    db = DatabaseManager()
    images = db.get_pending_images()  # Toutes les images en attente

    if not images:
        print("Aucune image en attente.")
        return

    # Initialiser le détecteur (qui va auto-logger dans Neon)
    detector = FireDetector(model_path='/opt/airflow/model/weights/best.pt')

    s3 = boto3.client('s3')
    bucket = os.getenv("S3_BUCKET_NAME")

    for img in images:
        local_path = f"/tmp/{img['id']}.png"
        try:
            s3.download_file(bucket, img['s3_path'], local_path)

            # Prédiction avec auto-logging des métriques de monitoring
            detections = detector.predict(
                image_path=local_path,
                conf_threshold=0.4,
                image_id=img['id'],
                batch_id=img['batch_id'],
                camera_name=img['camera_name'],
                s3_path=img['s3_path']
            )

            is_fire = len(detections) > 0
            conf = detections[0]['confidence'] if detections else 0.0
            bbox = detections[0]['bbox'] if detections else []

            db.update_prediction(img['id'], is_fire, conf, bbox)

            # ENVOI ALERTE
            if is_fire and conf > 0.4:
                print(f"FEU DETECTE (ID: {img['id']}) ! Envoi mail...")

                subject = f"ALERTE INCENDIE : {img['camera_name']}"
                html_content = f"""
                <h3>FEU DETECTE PAR LE MODELE</h3>
                <p><b>Camera :</b> {img['camera_name']}</p>
                <p><b>Confiance IA :</b> {conf:.2f} ({(conf*100):.0f}%)</p>
                <p><b>ID Image :</b> {img['id']}</p>
                <p><b>Batch ID :</b> {img['batch_id']}</p>
                <hr>
                <p><i>Ceci est une alerte automatique generee par Airflow + MLflow.</i></p>
                <p><i>Prediction loggee dans Neon pour monitoring.</i></p>
                """

                send_email(to=['axel.vilamot@gmail.com'], subject=subject, html_content=html_content)
                print("Mail envoye via Airflow Backend.")

            os.remove(local_path)
        except Exception as e:
            print(f"Erreur sur l'image {img['id']}: {e}")

    db.close()
    print(f"Analyse terminee - {len(images)} images analysees et loggees dans Neon")

# --- DAG DEFINITION ---
with DAG(
    'fire_detection_pipeline',
    default_args=default_args,
    description='Pipeline de détection incendie',
    schedule_interval='*/15 * * * *',  # Toutes les 15 minutes (165 caméras)
    catchup=False
) as dag:

    scrape_task = PythonOperator(task_id='scrape_cameras', python_callable=task_scrape_images)
    inference_task = PythonOperator(task_id='analyze_images', python_callable=task_run_inference)

    scrape_task >> inference_task