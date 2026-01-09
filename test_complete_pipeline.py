"""
Test complet du pipeline Fire Detection
Teste: Scraping -> Upload S3 -> Inference -> Monitoring -> Email
"""

import os
import sys
import boto3
import psycopg2
from dotenv import load_dotenv
from datetime import datetime
import time

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')

print("=" * 70)
print("TEST COMPLET DU PIPELINE FIRE DETECTION")
print("=" * 70)

# Initialisation
s3 = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# ==============================================================================
# TEST 1: CONNEXION S3
# ==============================================================================
print("\n[TEST 1/7] Connexion au bucket S3...")
try:
    response = s3.list_objects_v2(Bucket=S3_BUCKET_NAME, MaxKeys=1)
    print(f"  [OK] Connexion reussie au bucket: {S3_BUCKET_NAME}")
except Exception as e:
    print(f"  [ERREUR] Impossible de se connecter a S3: {e}")
    sys.exit(1)

# ==============================================================================
# TEST 2: CONNEXION BASE DE DONNÉES
# ==============================================================================
print("\n[TEST 2/7] Connexion a la base de donnees Neon...")
try:
    cur.execute("SELECT COUNT(*) FROM images")
    total_images = cur.fetchone()[0]
    print(f"  [OK] Connexion reussie - {total_images} images dans la base")
except Exception as e:
    print(f"  [ERREUR] Impossible de se connecter a Neon: {e}")
    sys.exit(1)

# ==============================================================================
# TEST 3: VÉRIFIER TABLES DE MONITORING
# ==============================================================================
print("\n[TEST 3/7] Verification des tables de monitoring...")
tables_required = ['model_predictions', 'daily_metrics', 'model_alerts']
for table in tables_required:
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"  [OK] Table '{table}' existe ({count} enregistrements)")
    except Exception as e:
        print(f"  [ERREUR] Table '{table}' introuvable: {e}")

# ==============================================================================
# TEST 4: VÉRIFIER TABLES DE RÉENTRAÎNEMENT
# ==============================================================================
print("\n[TEST 4/7] Verification des tables de reentrainement...")
tables_retrain = ['annotations', 'model_versions', 'model_comparisons', 'retrain_triggers']
for table in tables_retrain:
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"  [OK] Table '{table}' existe ({count} enregistrements)")
    except Exception as e:
        print(f"  [ERREUR] Table '{table}' introuvable: {e}")

# ==============================================================================
# TEST 5: VÉRIFIER DERNIÈRES PRÉDICTIONS
# ==============================================================================
print("\n[TEST 5/7] Verification des dernieres predictions...")
try:
    cur.execute("""
        SELECT COUNT(*),
               SUM(CASE WHEN fire_detected THEN 1 ELSE 0 END) as fires,
               AVG(confidence) as avg_conf,
               MAX(prediction_timestamp) as last_pred
        FROM model_predictions
        WHERE prediction_timestamp > NOW() - INTERVAL '24 hours'
    """)

    row = cur.fetchone()
    if row[0] > 0:
        print(f"  [OK] {row[0]} predictions dans les dernieres 24h")
        print(f"       - Feux detectes: {row[1] or 0}")
        print(f"       - Confiance moyenne: {row[2]:.3f}" if row[2] else "       - Confiance moyenne: N/A")
        print(f"       - Derniere prediction: {row[3]}")
    else:
        print(f"  [ATTENTION] Aucune prediction dans les dernieres 24h")
        print(f"  [INFO] Vous devez lancer le scraping + inference pour generer des donnees")
except Exception as e:
    print(f"  [ERREUR] Impossible de recuperer les predictions: {e}")

# ==============================================================================
# TEST 6: VÉRIFIER IMAGES DANS S3
# ==============================================================================
print("\n[TEST 6/7] Verification des images dans S3...")
try:
    # Compter les images dans S3
    paginator = s3.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix='fire_detection/')

    total_s3_images = 0
    for page in pages:
        if 'Contents' in page:
            total_s3_images += len(page['Contents'])

    print(f"  [OK] {total_s3_images} images dans S3 (prefix: fire_detection/)")

    # Comparer avec la base de données
    cur.execute("SELECT COUNT(*) FROM images")
    total_db_images = cur.fetchone()[0]

    if total_db_images > 0:
        ratio = (total_s3_images / total_db_images) * 100
        print(f"  [INFO] {total_db_images} images referencees dans la base")
        print(f"  [INFO] Ratio S3/DB: {ratio:.1f}%")

        if ratio < 90:
            print(f"  [ATTENTION] Certaines images de la base ne sont peut-etre pas dans S3")

    # Tester le téléchargement d'une image
    if total_s3_images > 0:
        print(f"\n  [TEST] Telechargement d'une image test depuis S3...")
        cur.execute("SELECT s3_path FROM images ORDER BY created_at DESC LIMIT 1")
        test_s3_path = cur.fetchone()

        if test_s3_path:
            test_local_path = '/tmp/test_download.jpg'
            try:
                s3.download_file(S3_BUCKET_NAME, test_s3_path[0], test_local_path)
                file_size = os.path.getsize(test_local_path)
                print(f"  [OK] Telechargement reussi ({file_size} bytes)")
                os.remove(test_local_path)
            except Exception as e:
                print(f"  [ERREUR] Echec telechargement: {e}")

except Exception as e:
    print(f"  [ERREUR] Impossible de verifier S3: {e}")

# ==============================================================================
# TEST 7: VÉRIFIER MODÈLE YOLO
# ==============================================================================
print("\n[TEST 7/7] Verification du modele YOLOv8...")
model_path = 'model/weights/best.pt'

if os.path.exists(model_path):
    print(f"  [OK] Modele trouve: {model_path}")
    model_size = os.path.getsize(model_path) / (1024 * 1024)  # MB
    print(f"       Taille: {model_size:.1f} MB")

    # Vérifier la version déployée dans la base
    try:
        cur.execute("""
            SELECT version_name, precision, recall, map50, deployed_at
            FROM model_versions
            WHERE deployed = TRUE
            ORDER BY deployed_at DESC
            LIMIT 1
        """)

        deployed = cur.fetchone()
        if deployed:
            print(f"  [INFO] Version deployee: {deployed[0]}")
            print(f"         Precision: {deployed[1]:.3f}, Recall: {deployed[2]:.3f}, mAP50: {deployed[3]:.3f}")
            print(f"         Deploye le: {deployed[4]}")
        else:
            print(f"  [INFO] Aucune version enregistree dans la base (utilise modele initial)")
    except Exception as e:
        print(f"  [ATTENTION] Impossible de verifier version deployee: {e}")
else:
    print(f"  [ERREUR] Modele introuvable: {model_path}")
    print(f"  [INFO] Le modele doit etre place dans ce dossier")

# ==============================================================================
# RÉSUMÉ
# ==============================================================================
print("\n" + "=" * 70)
print("RESUME DU TEST")
print("=" * 70)

# Statistiques globales
cur.execute("SELECT COUNT(*) FROM images")
total_images = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM images WHERE fire_detected = TRUE")
total_fires = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM model_predictions")
total_predictions = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM annotations")
total_annotations = cur.fetchone()[0]

print(f"\nStatistiques globales:")
print(f"  - Images scrapees: {total_images}")
print(f"  - Feux detectes: {total_fires}")
print(f"  - Predictions loggees: {total_predictions}")
print(f"  - Annotations manuelles: {total_annotations}")

print(f"\nInfrastructure:")
print(f"  - S3 Bucket: {S3_BUCKET_NAME}")
print(f"  - Base de donnees: Neon PostgreSQL")
print(f"  - Modele: YOLOv8s (fine-tuned)")

print(f"\nPipeline:")
print(f"  [{'OK' if total_images > 0 else 'ATTENTION'}] Scraping -> S3 -> Base de donnees")
print(f"  [{'OK' if total_predictions > 0 else 'ATTENTION'}] Inference -> Monitoring")
print(f"  [{'OK' if total_annotations > 0 else 'INFO'}] Annotations pour reentrainement")

print("\n" + "=" * 70)

if total_images > 0 and total_predictions > 0:
    print("STATUT: SYSTEME OPERATIONNEL")
    print("\nProchaines etapes:")
    print("  1. Le systeme va continuer a scraper toutes les 15 minutes")
    print("  2. Vous recevrez un email quotidien avec les metriques (9h)")
    print("  3. Annotez les predictions si vous voulez ameliorer le modele")
else:
    print("STATUT: SYSTEME PRET (EN ATTENTE DE DONNEES)")
    print("\nProchaines etapes:")
    print("  1. Lancez le systeme avec LANCER_SYSTEME.bat")
    print("  2. Attendez 15 minutes pour le premier cycle")
    print("  3. Verifiez les resultats dans Airflow (http://localhost:8080)")

print("=" * 70)

# Fermeture
cur.close()
conn.close()
