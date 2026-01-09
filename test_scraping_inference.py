"""
Test rapide du cycle Scraping -> S3 -> Inference
Scrape 5 cameras et verifie que tout le pipeline fonctionne
"""

import os
import sys
import boto3
import psycopg2
from dotenv import load_dotenv
from datetime import datetime
import time

# Ajouter le path pour importer les modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scraper.scraper import AlertWildfireScraper
from model.inference import FireDetector
from scraper.database import DatabaseManager

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')

print("=" * 70)
print("TEST RAPIDE: SCRAPING -> S3 -> INFERENCE -> MONITORING")
print("=" * 70)
print(f"\nDate: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Test avec 5 cameras")
print("=" * 70)

# ==============================================================================
# ÉTAPE 1: SCRAPING
# ==============================================================================
print("\n[ETAPE 1/5] Scraping de 5 cameras...")
print("  Demarrage du scraper...")

scraper = AlertWildfireScraper()
scraper.start()

try:
    batch_id = scraper.scrape_all(max_cameras=5)
    print(f"  [OK] Scraping termine - Batch ID: {batch_id}")
except Exception as e:
    print(f"  [ERREUR] Echec du scraping: {e}")
    scraper.stop()
    sys.exit(1)
finally:
    scraper.stop()

time.sleep(2)  # Attendre que tout soit bien enregistre

# ==============================================================================
# ÉTAPE 2: VÉRIFIER UPLOAD S3
# ==============================================================================
print("\n[ETAPE 2/5] Verification de l'upload S3...")

s3 = boto3.client('s3')
db = DatabaseManager()

try:
    # Recuperer les images de ce batch
    images = db.cur.execute("""
        SELECT id, s3_path, camera_name
        FROM images
        WHERE batch_id = %s
    """, (batch_id,))
    images = db.cur.fetchall()

    print(f"  [INFO] {len(images)} images dans la base pour ce batch")

    # Verifier que les images existent dans S3
    s3_ok = 0
    s3_fail = 0

    for img_id, s3_path, camera_name in images:
        try:
            s3.head_object(Bucket=S3_BUCKET_NAME, Key=s3_path)
            s3_ok += 1
        except:
            s3_fail += 1
            print(f"  [ATTENTION] Image manquante dans S3: {s3_path}")

    print(f"  [OK] {s3_ok}/{len(images)} images presentes dans S3")

    if s3_fail > 0:
        print(f"  [ATTENTION] {s3_fail} images manquantes dans S3")

except Exception as e:
    print(f"  [ERREUR] Impossible de verifier S3: {e}")
    db.close()
    sys.exit(1)

# ==============================================================================
# ÉTAPE 3: INFERENCE
# ==============================================================================
print("\n[ETAPE 3/5] Lancement de l'inference...")

detector = FireDetector(model_path='model/weights/best.pt')

# Recuperer les images en attente (status = NEW)
pending_images = db.get_pending_images()
print(f"  [INFO] {len(pending_images)} images en attente d'analyse")

if len(pending_images) == 0:
    print(f"  [ATTENTION] Aucune image en attente (deja analysees?)")
    db.close()
    sys.exit(0)

fires_detected = 0
inference_errors = 0

for img in pending_images[:5]:  # Analyser max 5 images
    local_path = f"/tmp/test_{img['id']}.jpg"

    try:
        # Telecharger depuis S3
        s3.download_file(S3_BUCKET_NAME, img['s3_path'], local_path)

        # Inference avec logging automatique dans Neon
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
        bbox = detections[0]['bbox'] if detections else None

        # Mettre a jour la table images
        db.update_prediction(img['id'], is_fire, conf, bbox)

        if is_fire:
            fires_detected += 1
            print(f"  [FEU DETECTE] Camera: {img['camera_name']}, Confiance: {conf:.2f}")
        else:
            print(f"  [OK] Camera: {img['camera_name']}, Pas de feu")

        # Nettoyer
        if os.path.exists(local_path):
            os.remove(local_path)

    except Exception as e:
        print(f"  [ERREUR] Echec inference image {img['id']}: {e}")
        inference_errors += 1

print(f"\n  [RESULTAT] {fires_detected} feu(x) detecte(s) sur {len(pending_images[:5])} images")

if inference_errors > 0:
    print(f"  [ATTENTION] {inference_errors} erreur(s) d'inference")

# ==============================================================================
# ÉTAPE 4: VÉRIFIER LOGGING MONITORING
# ==============================================================================
print("\n[ETAPE 4/5] Verification du logging de monitoring...")

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

try:
    # Verifier que les predictions ont bien ete loggees
    cur.execute("""
        SELECT COUNT(*)
        FROM model_predictions mp
        JOIN images i ON mp.image_id = i.id
        WHERE i.batch_id = %s
    """, (batch_id,))

    logged_predictions = cur.fetchone()[0]
    print(f"  [OK] {logged_predictions} predictions loggees dans model_predictions")

    # Afficher quelques stats
    cur.execute("""
        SELECT
            AVG(confidence) as avg_conf,
            AVG(inference_time_ms) as avg_time,
            MAX(confidence) as max_conf
        FROM model_predictions mp
        JOIN images i ON mp.image_id = i.id
        WHERE i.batch_id = %s
        AND mp.fire_detected = TRUE
    """, (batch_id,))

    stats = cur.fetchone()
    if stats[0]:
        print(f"  [STATS] Confiance moyenne: {stats[0]:.3f}")
        print(f"  [STATS] Temps inference moyen: {stats[1]:.0f}ms")
        print(f"  [STATS] Confiance max: {stats[2]:.3f}")
    else:
        print(f"  [INFO] Pas de feu detecte, pas de stats de confiance")

except Exception as e:
    print(f"  [ERREUR] Impossible de verifier le logging: {e}")
finally:
    cur.close()
    conn.close()

# ==============================================================================
# ÉTAPE 5: RÉSUMÉ
# ==============================================================================
print("\n[ETAPE 5/5] Résumé du test")
print("=" * 70)

success = (
    len(images) > 0 and
    s3_ok > 0 and
    logged_predictions > 0 and
    inference_errors == 0
)

if success:
    print("\n  STATUS: TEST REUSSI")
    print("\n  Le pipeline complet fonctionne correctement:")
    print(f"    Scraping: {len(images)} images capturees")
    print(f"    S3 Upload: {s3_ok} images uploadees")
    print(f"    Inference: {logged_predictions} predictions")
    print(f"    Monitoring: Logging automatique actif")
    print(f"    Feux detectes: {fires_detected}")
else:
    print("\n  STATUS: ATTENTION - PROBLEMES DETECTES")

    if len(images) == 0:
        print("    - Aucune image scrapee")
    if s3_ok == 0:
        print("    - Aucune image dans S3")
    if logged_predictions == 0:
        print("    - Aucune prediction loggee")
    if inference_errors > 0:
        print(f"    - {inference_errors} erreurs d'inference")

print("\n" + "=" * 70)
print("PROCHAINES ETAPES:")
print("  1. Si le test est OK: Lancez le systeme complet (LANCER_SYSTEME.bat)")
print("  2. Verifiez Airflow: http://localhost:8080")
print("  3. Le DAG 'fire_detection_pipeline' scrappe toutes les 15 minutes")
print("  4. Le DAG 'model_monitoring_daily' envoie un rapport quotidien a 9h")
print("=" * 70)

# Fermeture
db.close()
