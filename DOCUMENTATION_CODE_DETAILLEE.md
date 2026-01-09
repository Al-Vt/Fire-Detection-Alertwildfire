# Documentation Code Détaillée - Fire Detection System

**Projet :** Système de Détection d'Incendies Automatisé
**Auteur :** Axel Vilamot
**Date :** 2026-01-09
**Technologies :** Python, YOLOv8, Airflow, MLflow, PostgreSQL, AWS S3

---

# Table des Matières

1. [Architecture Globale](#architecture-globale)
2. [Scraping (scraper/)](#scraping)
3. [Détection IA (model/)](#detection-ia)
4. [Monitoring (monitoring/)](#monitoring)
5. [Réentraînement (retraining/)](#reentrainement)
6. [Orchestration Airflow (dags/)](#orchestration-airflow)
7. [Scripts Utilitaires](#scripts-utilitaires)
8. [Configuration](#configuration)

---

# Architecture Globale

## Vue d'ensemble du système

Le système Fire Detection est composé de 6 modules principaux :

1. **Scraping** : Capture d'images depuis 165 caméras
2. **Stockage** : S3 (images) + PostgreSQL (métadonnées)
3. **Détection** : YOLOv8 fine-tuné pour détecter le feu
4. **Monitoring** : Suivi des performances du modèle
5. **Réentraînement** : Amélioration automatique du modèle
6. **Orchestration** : Airflow pour automatiser tout le pipeline

## Flux de données

```
Caméras → Scraper → S3 + PostgreSQL → YOLOv8 → Détection
                                                     ↓
                                        Email Alerte + Monitoring
                                                     ↓
                                        Métriques Quotidiennes
                                                     ↓
                            Si dégradation → Réentraînement Automatique
```

---

# Scraping

## scraper/scraper.py

**Objectif :** Capturer des screenshots des caméras de surveillance forestière et les stocker dans S3.

### Imports et Configuration

```python
import os
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import boto3
from database import DatabaseManager
```

**Explication :**
- `selenium` : Pilotage automatique du navigateur Chrome
- `boto3` : Client AWS pour upload S3
- `database` : Gestion PostgreSQL (Neon)

### Classe AlertWildfireScraper

```python
class AlertWildfireScraper:
    def __init__(self):
        self.db = DatabaseManager()
        self.s3_client = boto3.client('s3')
        self.bucket_name = os.getenv('S3_BUCKET_NAME')
        self.driver = None
        self.batch_id = None
```

**Explication :**
- Initialise la connexion à la base de données
- Configure le client S3 avec les credentials du .env
- Prépare le driver Selenium (sera créé dans start())

### Méthode start()

```python
def start(self):
    """Démarre le navigateur Chrome en mode headless"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Pas d'interface graphique
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')

    self.driver = webdriver.Chrome(options=chrome_options)
    self.batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
```

**Explication :**
- `--headless` : Exécution sans fenêtre (serveur)
- `--no-sandbox` : Nécessaire pour Docker
- `--window-size` : Taille du screenshot (HD)
- `batch_id` : Identifiant unique pour ce cycle de scraping

### Méthode scrape_camera()

```python
def scrape_camera(self, url, camera_name):
    """
    Scrape une caméra individuelle

    Args:
        url: URL de la caméra
        camera_name: Nom extrait de l'URL

    Returns:
        bool: True si succès, False sinon
    """
    try:
        # 1. Naviguer vers l'URL
        self.driver.get(url)

        # 2. Attendre que l'image soit chargée (max 10s)
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, 'img'))
        )

        time.sleep(2)  # Attendre stabilisation complète

        # 3. Prendre le screenshot
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"fire_detection/{self.batch_id}/{camera_name}_{timestamp}.png"

        screenshot = self.driver.get_screenshot_as_png()

        # 4. Upload vers S3
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=filename,
            Body=screenshot,
            ContentType='image/png'
        )

        # 5. Enregistrer dans PostgreSQL
        self.db.insert_image(
            batch_id=self.batch_id,
            camera_name=camera_name,
            s3_path=filename,
            status='NEW'
        )

        return True

    except Exception as e:
        print(f"Erreur scraping {camera_name}: {e}")
        return False
```

**Explication détaillée :**

1. **Navigation** : Selenium ouvre l'URL de la caméra
2. **Attente intelligente** : WebDriverWait attend que les images soient chargées (évite screenshots vides)
3. **Screenshot** : Capture l'écran entier en PNG
4. **Upload S3** : Stocke l'image dans le bucket avec un chemin structuré
5. **Base de données** : Enregistre les métadonnées (path S3, camera, batch)

**Gestion d'erreurs :**
- Timeout si caméra offline (normal, ~40% des caméras)
- Exception capturée pour ne pas bloquer le cycle complet

### Méthode scrape_all()

```python
def scrape_all(self, max_cameras=None):
    """
    Scrape toutes les caméras (ou un nombre limité)

    Args:
        max_cameras: Nombre max de caméras (None = toutes)

    Returns:
        str: batch_id du cycle
    """
    success_count = 0
    fail_count = 0

    cameras_to_scrape = self.CAMERA_URLS[:max_cameras] if max_cameras else self.CAMERA_URLS

    for url in cameras_to_scrape:
        # Extraire le nom de la caméra depuis l'URL
        camera_name = url.split('currentFirecam=')[1].split('&')[0]

        if self.scrape_camera(url, camera_name):
            success_count += 1
        else:
            fail_count += 1

        time.sleep(1)  # Délai entre chaque caméra (politesse)

    print(f"Scraping terminé: {success_count} succès, {fail_count} échecs")
    return self.batch_id
```

**Explication :**
- Itère sur la liste des 165 URLs
- Extrait le nom de la caméra depuis l'URL (ex: `ca-lassen-1`)
- Compte les succès/échecs
- Délai de 1s entre caméras (éviter surcharge serveur)

**Taux de succès attendu :** 60% (normal, caméras parfois offline)

---

## scraper/database.py

**Objectif :** Gérer toutes les interactions avec PostgreSQL (Neon).

### Classe DatabaseManager

```python
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

class DatabaseManager:
    def __init__(self):
        """Initialise la connexion à Neon PostgreSQL"""
        self.conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        self.cur = self.conn.cursor()
```

**Explication :**
- Charge `DATABASE_URL` depuis .env
- Crée une connexion persistante
- Curseur pour exécuter les requêtes SQL

### Méthode insert_image()

```python
def insert_image(self, batch_id, camera_name, s3_path, status='NEW'):
    """
    Insère une nouvelle image dans la base

    Args:
        batch_id: ID du cycle de scraping
        camera_name: Nom de la caméra
        s3_path: Chemin dans S3
        status: Statut initial (NEW/ANALYZED)
    """
    self.cur.execute("""
        INSERT INTO images
        (batch_id, camera_name, s3_path, status, captured_at)
        VALUES (%s, %s, %s, %s, NOW())
        RETURNING id
    """, (batch_id, camera_name, s3_path, status))

    self.conn.commit()
    return self.cur.fetchone()[0]  # Retourne l'ID généré
```

**Explication :**
- Requête SQL INSERT avec paramètres sécurisés (évite SQL injection)
- `NOW()` : Timestamp automatique
- `RETURNING id` : Récupère l'ID auto-incrémenté
- `commit()` : Valide la transaction

### Méthode get_pending_images()

```python
def get_pending_images(self, limit=None):
    """
    Récupère les images en attente d'analyse

    Args:
        limit: Nombre max d'images (None = toutes)

    Returns:
        list: Liste de dictionnaires avec les infos images
    """
    query = """
        SELECT id, batch_id, camera_name, s3_path
        FROM images
        WHERE status = 'NEW'
        ORDER BY created_at ASC
    """

    if limit:
        query += f" LIMIT {limit}"

    self.cur.execute(query)

    images = []
    for row in self.cur.fetchall():
        images.append({
            'id': row[0],
            'batch_id': row[1],
            'camera_name': row[2],
            's3_path': row[3]
        })

    return images
```

**Explication :**
- Filtre sur `status = 'NEW'` (non analysées)
- Trie par date de création (FIFO)
- Convertit les résultats en dictionnaires (plus facile à manipuler)

### Méthode update_prediction()

```python
def update_prediction(self, image_id, fire_detected, confidence, bbox):
    """
    Met à jour les résultats de prédiction

    Args:
        image_id: ID de l'image
        fire_detected: True/False
        confidence: Confiance du modèle (0-1)
        bbox: Bounding box [x, y, w, h]
    """
    self.cur.execute("""
        UPDATE images
        SET
            fire_detected = %s,
            confidence = %s,
            bbox = %s,
            status = 'ANALYZED',
            updated_at = NOW()
        WHERE id = %s
    """, (fire_detected, confidence, psycopg2.extras.Json(bbox), image_id))

    self.conn.commit()
```

**Explication :**
- Met à jour plusieurs colonnes en une requête
- `psycopg2.extras.Json(bbox)` : Stocke le tableau comme JSONB
- Change le status à 'ANALYZED' pour ne pas retraiter

---

# Détection IA

## model/inference.py

**Objectif :** Charger le modèle YOLOv8 et effectuer les prédictions avec logging automatique.

### Imports et Configuration

```python
import os
import logging
import time
from ultralytics import YOLO
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')
```

**Explication :**
- `ultralytics` : Bibliothèque officielle YOLOv8
- Logging configuré pour tracer toutes les opérations
- Connexion à Neon pour le monitoring

### Classe FireDetector

```python
class FireDetector:
    def __init__(self, model_path='weights/best.pt'):
        """
        Initialise le détecteur de feu

        Args:
            model_path: Chemin vers le modèle YOLOv8 fine-tuné
        """
        self.model_path = model_path
        logging.info(f"Chargement du modèle depuis {self.model_path}...")

        try:
            self.model = YOLO(self.model_path)
            logging.info("Modèle chargé avec succès.")
        except Exception as e:
            logging.error(f"Erreur lors du chargement du modèle : {e}")
            raise e
```

**Explication :**
- Charge le modèle YOLOv8 personnalisé (fine-tuné sur Pyro-SDIS)
- Gestion d'erreur si le fichier .pt est manquant
- Log toutes les étapes pour débogage

### Méthode predict()

```python
def predict(self, image_path, conf_threshold=0.4, image_id=None,
            batch_id=None, camera_name=None, s3_path=None):
    """
    Détecte le feu dans une image

    Args:
        image_path: Chemin local de l'image
        conf_threshold: Seuil de confiance minimum (défaut 0.4)
        image_id, batch_id, camera_name, s3_path: Métadonnées pour monitoring

    Returns:
        list: Liste des détections [{'class': 'fire', 'confidence': 0.85, 'bbox': [x,y,w,h]}]
    """
    logging.info(f"Analyse de l'image : {image_path}")

    # 1. MESURER LE TEMPS D'INFÉRENCE
    start_time = time.time()

    # 2. INFÉRENCE YOLO
    results = self.model.predict(
        source=image_path,
        conf=conf_threshold,  # Seuil de confiance
        imgsz=960,            # Taille image (même que l'entraînement)
        save=False            # Ne pas sauvegarder les résultats
    )

    inference_time_ms = (time.time() - start_time) * 1000

    # 3. PARSER LES RÉSULTATS
    detections = []
    fire_detected = False
    max_confidence = 0.0
    best_bbox = None

    for result in results:
        for box in result.boxes:
            cls_id = int(box.cls[0])        # ID de la classe
            confidence = float(box.conf[0])  # Confiance
            coords = box.xywhn[0].tolist()  # Coordonnées normalisées

            # Classe 0 = fire (selon data.yaml)
            if cls_id == 0:
                fire_detected = True

                if confidence > max_confidence:
                    max_confidence = confidence
                    best_bbox = coords

                detections.append({
                    "class": "fire",
                    "confidence": confidence,
                    "bbox": coords  # [x_center, y_center, width, height]
                })

    # 4. LOGGER DANS NEON (MONITORING)
    self._log_prediction(
        image_id=image_id,
        batch_id=batch_id,
        camera_name=camera_name,
        s3_path=s3_path,
        fire_detected=fire_detected,
        confidence=max_confidence if fire_detected else None,
        bbox=best_bbox,
        inference_time_ms=inference_time_ms,
        image_size_bytes=os.path.getsize(image_path) if os.path.exists(image_path) else None
    )

    # 5. LOG RÉSULTAT
    if detections:
        logging.warning(f"FEU DETECTE ! ({len(detections)} foyers)")
    else:
        logging.info("Aucune anomalie detectee.")

    return detections
```

**Explication détaillée :**

**Étape 1 : Mesure du temps**
- `start_time` : Timestamp avant inférence
- Utilisé pour détecter si le modèle ralentit (monitoring)

**Étape 2 : Inférence YOLOv8**
- `conf=0.4` : Ne garde que les détections avec confiance ≥ 40%
- `imgsz=960` : Même taille que l'entraînement (important!)
- `save=False` : Ne sauvegarde pas les images annotées (gain de performance)

**Étape 3 : Parsing**
- `result.boxes` : Liste des boîtes détectées
- `box.cls[0]` : Classe (0 = fire, selon data.yaml)
- `box.conf[0]` : Confiance (0-1)
- `box.xywhn[0]` : Coordonnées normalisées (0-1)
  - x, y : Centre de la boîte
  - w, h : Largeur, hauteur

**Étape 4 : Logging monitoring**
- Sauvegarde CHAQUE prédiction dans `model_predictions`
- Permet de calculer les métriques quotidiennes
- Détecte les dégradations du modèle

**Étape 5 : Log console**
- WARNING si feu (facile à repérer dans les logs)
- INFO si rien (pas d'alerte)

### Méthode _log_prediction()

```python
def _log_prediction(self, image_id, batch_id, camera_name, s3_path,
                    fire_detected, confidence, bbox, inference_time_ms, image_size_bytes):
    """
    Log la prédiction dans Neon PostgreSQL pour monitoring

    Cette fonction est CRITIQUE pour le système de monitoring.
    Elle enregistre chaque prédiction pour calculer les métriques quotidiennes.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO model_predictions
            (image_id, batch_id, camera_name, fire_detected, confidence, bbox,
             inference_time_ms, image_size_bytes, s3_path, prediction_timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            image_id,
            batch_id,
            camera_name,
            fire_detected,
            confidence,
            None if bbox is None else psycopg2.extras.Json(bbox),
            inference_time_ms,
            image_size_bytes,
            s3_path,
            datetime.now()
        ))

        conn.commit()
        cur.close()
        conn.close()

        logging.info(f"Prediction loggee dans Neon (fire_detected={fire_detected}, confidence={confidence})")

    except Exception as e:
        logging.error(f"Erreur lors du logging de la prediction: {e}")
        # Ne pas lever d'exception pour ne pas bloquer le pipeline
```

**Explication :**
- Connexion séparée (robustesse si problème réseau)
- Sauvegarde TOUTES les infos de prédiction
- JSONB pour la bbox (flexible, requêtable)
- Exception capturée : le logging ne doit pas bloquer le pipeline principal

**Données stockées :**
- `image_id` : Lien avec la table images
- `fire_detected` : Boolean (feu oui/non)
- `confidence` : 0-1 (NULL si pas de feu)
- `bbox` : Coordonnées de la boîte
- `inference_time_ms` : Performance du modèle
- `image_size_bytes` : Taille de l'image (détecte images corrompues)

---

# Monitoring

## monitoring/metrics.py

**Objectif :** Calculer les métriques quotidiennes et détecter les dégradations du modèle.

### Configuration des Seuils

```python
# Seuils d'alerte pour détecter les dégradations
THRESHOLDS = {
    'min_avg_confidence': 0.60,      # Confiance moyenne minimum acceptable
    'max_avg_confidence': 0.95,      # Confiance moyenne maximum (possible overfitting)
    'min_daily_predictions': 50,     # Minimum de prédictions attendues par jour
    'max_inference_time_ms': 5000,   # Temps maximum d'inférence acceptable (5s)
}
```

**Explication :**
- `min_avg_confidence` : Si la confiance moyenne baisse < 60%, le modèle dégrade
- `max_avg_confidence` : Si > 95%, possible overfitting (le modèle est trop sûr)
- `min_daily_predictions` : Si < 50, problème de scraping
- `max_inference_time_ms` : Si > 5s, problème de performance

### Classe ModelMonitor

```python
class ModelMonitor:
    def __init__(self):
        """Initialise le monitor du modèle"""
        self.conn = psycopg2.connect(DATABASE_URL)
        self.cur = self.conn.cursor()
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
```

### Méthode calculate_daily_metrics()

```python
def calculate_daily_metrics(self, target_date=None):
    """
    Calcule les métriques quotidiennes

    Args:
        target_date: Date cible (défaut: hier)

    Returns:
        dict: Métriques agrégées
    """
    if target_date is None:
        target_date = (datetime.now() - timedelta(days=1)).date()

    logging.info(f"Calcul des metriques pour {target_date}")

    # REQUÊTE SQL AGRÉGÉE
    self.cur.execute("""
        SELECT
            COUNT(*) as total_predictions,
            SUM(CASE WHEN fire_detected = TRUE THEN 1 ELSE 0 END) as fire_detections,
            AVG(CASE WHEN fire_detected = TRUE THEN confidence ELSE NULL END) as avg_confidence,
            MIN(CASE WHEN fire_detected = TRUE THEN confidence ELSE NULL END) as min_confidence,
            MAX(CASE WHEN fire_detected = TRUE THEN confidence ELSE NULL END) as max_confidence,
            STDDEV(CASE WHEN fire_detected = TRUE THEN confidence ELSE NULL END) as std_confidence,
            AVG(inference_time_ms) as avg_inference_time_ms,
            COUNT(DISTINCT camera_name) as unique_cameras
        FROM model_predictions
        WHERE DATE(prediction_timestamp) = %s
    """, (target_date,))

    result = self.cur.fetchone()

    if result[0] == 0:
        logging.warning(f"Aucune prediction pour {target_date}")
        return None

    # FORMATER LES RÉSULTATS
    metrics = {
        'metric_date': target_date,
        'total_predictions': result[0],
        'fire_detections': result[1] or 0,
        'avg_confidence': float(result[2]) if result[2] else None,
        'min_confidence': float(result[3]) if result[3] else None,
        'max_confidence': float(result[4]) if result[4] else None,
        'std_confidence': float(result[5]) if result[5] else None,
        'avg_inference_time_ms': float(result[6]) if result[6] else None,
        'unique_cameras': result[7]
    }

    logging.info(f"Metriques calculees: {metrics}")
    return metrics
```

**Explication SQL :**

1. **COUNT(*)** : Total de prédictions
2. **SUM(CASE...)** : Compte seulement les feux détectés
3. **AVG(CASE...)** : Confiance moyenne UNIQUEMENT sur les détections (ignore les "pas de feu")
4. **STDDEV** : Écart-type (dispersion des confidences)
5. **AVG(inference_time_ms)** : Temps moyen d'inférence
6. **COUNT(DISTINCT camera_name)** : Nombre de caméras uniques

**Pourquoi CASE WHEN ?**
- On ne veut calculer la confiance moyenne QUE sur les détections de feu
- Si on inclut les "pas de feu" (confidence = NULL), ça fausse les stats

### Méthode detect_anomalies()

```python
def detect_anomalies(self, metrics):
    """
    Détecte les anomalies dans les métriques

    Args:
        metrics: Dictionnaire des métriques quotidiennes

    Returns:
        list: Liste des alertes détectées
    """
    if metrics is None:
        return []

    alerts = []

    # ALERTE 1: Confiance moyenne trop basse
    if metrics['avg_confidence'] and metrics['avg_confidence'] < THRESHOLDS['min_avg_confidence']:
        alerts.append({
            'type': 'low_confidence',
            'message': f"Confiance moyenne trop basse: {metrics['avg_confidence']:.2f} < {THRESHOLDS['min_avg_confidence']}",
            'severity': 'critical',  # CRITIQUE = nécessite réentraînement
            'value': metrics['avg_confidence'],
            'threshold': THRESHOLDS['min_avg_confidence']
        })

    # ALERTE 2: Confiance moyenne trop élevée (overfitting)
    if metrics['avg_confidence'] and metrics['avg_confidence'] > THRESHOLDS['max_avg_confidence']:
        alerts.append({
            'type': 'high_confidence',
            'message': f"Confiance moyenne anormalement elevee (possible overfitting): {metrics['avg_confidence']:.2f} > {THRESHOLDS['max_avg_confidence']}",
            'severity': 'warning',
            'value': metrics['avg_confidence'],
            'threshold': THRESHOLDS['max_avg_confidence']
        })

    # ALERTE 3: Nombre de prédictions trop bas
    if metrics['total_predictions'] < THRESHOLDS['min_daily_predictions']:
        alerts.append({
            'type': 'low_predictions',
            'message': f"Nombre de predictions trop bas: {metrics['total_predictions']} < {THRESHOLDS['min_daily_predictions']}",
            'severity': 'warning',
            'value': metrics['total_predictions'],
            'threshold': THRESHOLDS['min_daily_predictions']
        })

    # ALERTE 4: Temps d'inférence trop long
    if metrics['avg_inference_time_ms'] and metrics['avg_inference_time_ms'] > THRESHOLDS['max_inference_time_ms']:
        alerts.append({
            'type': 'slow_inference',
            'message': f"Temps d'inference trop long: {metrics['avg_inference_time_ms']:.0f}ms > {THRESHOLDS['max_inference_time_ms']}ms",
            'severity': 'warning',
            'value': metrics['avg_inference_time_ms'],
            'threshold': THRESHOLDS['max_inference_time_ms']
        })

    return alerts
```

**Explication :**
- Vérifie chaque métrique contre les seuils
- Crée une alerte pour chaque seuil dépassé
- `severity` : 'critical' ou 'warning'
  - **critical** : Déclenche potentiellement le réentraînement
  - **warning** : Informe mais n'agit pas automatiquement

### Méthode get_trend_analysis()

```python
def get_trend_analysis(self, days=7):
    """
    Analyse les tendances sur les N derniers jours

    Args:
        days: Nombre de jours à analyser

    Returns:
        dict: Tendances (increasing/decreasing/stable)
    """
    self.cur.execute("""
        SELECT
            metric_date,
            avg_confidence,
            total_predictions,
            fire_detections,
            avg_inference_time_ms
        FROM daily_metrics
        WHERE metric_date >= CURRENT_DATE - INTERVAL '%s days'
        ORDER BY metric_date DESC
    """, (days,))

    results = self.cur.fetchall()

    if len(results) < 2:
        return None  # Pas assez de données

    trends = {
        'period_days': days,
        'avg_confidence_trend': self._calculate_trend([r[1] for r in results if r[1]]),
        'predictions_trend': self._calculate_trend([r[2] for r in results]),
        'fire_detections_trend': self._calculate_trend([r[3] for r in results]),
        'inference_time_trend': self._calculate_trend([r[4] for r in results if r[4]])
    }

    return trends

def _calculate_trend(self, values):
    """
    Calcule la tendance (hausse/baisse/stable)

    Méthode: Compare la moyenne de la première moitié avec la deuxième moitié
    """
    if len(values) < 2:
        return 'insufficient_data'

    first_half = sum(values[:len(values)//2]) / (len(values)//2)
    second_half = sum(values[len(values)//2:]) / (len(values) - len(values)//2)

    diff_percent = ((second_half - first_half) / first_half * 100) if first_half > 0 else 0

    if diff_percent > 10:
        return 'increasing'  # Hausse > 10%
    elif diff_percent < -10:
        return 'decreasing'  # Baisse > 10%
    else:
        return 'stable'      # Variation < 10%
```

**Explication de l'analyse de tendance :**

**Méthode simple mais efficace :**
1. Récupère les 7 derniers jours
2. Divise en 2 moitiés (3.5 premiers jours vs 3.5 derniers jours)
3. Compare les moyennes
4. Si différence > 10% → Tendance claire

**Exemple :**
- Jours 1-3 : confiance moyenne = 0.70
- Jours 4-7 : confiance moyenne = 0.60
- Différence : -14% → **decreasing** → ALERTE!

### Méthode generate_report()

```python
def generate_report(self, metrics, alerts, trends):
    """
    Génère un rapport HTML pour email

    Args:
        metrics: Métriques quotidiennes
        alerts: Liste des alertes
        trends: Tendances 7 jours

    Returns:
        str: HTML du rapport
    """
    if metrics is None:
        return "<p>Aucune donnee disponible pour generer un rapport.</p>"

    status_emoji = "🔴" if alerts else "🟢"

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif;">
        <h2>{status_emoji} Rapport de Monitoring du Modele - {metrics['metric_date']}</h2>

        <h3>Metriques Quotidiennes</h3>
        <table border="1" cellpadding="8" style="border-collapse: collapse;">
            <tr><td><b>Total predictions</b></td><td>{metrics['total_predictions']}</td></tr>
            <tr><td><b>Feux detectes</b></td><td>{metrics['fire_detections']}</td></tr>
            <tr><td><b>Cameras uniques</b></td><td>{metrics['unique_cameras']}</td></tr>
            <tr style="background-color: {'#ffcccc' if metrics['avg_confidence'] and metrics['avg_confidence'] < THRESHOLDS['min_avg_confidence'] else '#ccffcc'}">
                <td><b>Confiance moyenne</b></td>
                <td>{metrics['avg_confidence']:.2f if metrics['avg_confidence'] else 'N/A'}</td>
            </tr>
            <tr><td><b>Confiance min/max</b></td><td>{metrics['min_confidence']:.2f if metrics['min_confidence'] else 'N/A'} / {metrics['max_confidence']:.2f if metrics['max_confidence'] else 'N/A'}</td></tr>
            <tr><td><b>Temps inference moyen</b></td><td>{metrics['avg_inference_time_ms']:.0f}ms</td></tr>
        </table>
    """

    # ALERTES
    if alerts:
        html += "<h3 style='color: red;'>Alertes Detectees</h3><ul>"
        for alert in alerts:
            color = 'red' if alert['severity'] == 'critical' else 'orange'
            html += f"<li style='color: {color};'><b>{alert['type']}</b>: {alert['message']}</li>"
        html += "</ul>"
    else:
        html += "<p style='color: green;'><b>Aucune alerte - Modele fonctionne normalement</b></p>"

    # TENDANCES
    if trends:
        html += "<h3>Tendances (7 derniers jours)</h3><ul>"
        html += f"<li>Confiance: {trends['avg_confidence_trend']}</li>"
        html += f"<li>Predictions: {trends['predictions_trend']}</li>"
        html += f"<li>Detections feux: {trends['fire_detections_trend']}</li>"
        html += f"<li>Temps inference: {trends['inference_time_trend']}</li>"
        html += "</ul>"

    html += """
        <hr>
        <p style="color: gray; font-size: 12px;">
        Rapport genere automatiquement par le systeme de monitoring Fire Detection.
        </p>
    </body>
    </html>
    """

    return html
```

**Explication du rapport HTML :**

1. **Emoji de statut** : 🟢 si OK, 🔴 si alertes
2. **Tableau de métriques** : Mise en forme professionnelle
3. **Code couleur** :
   - Rouge si confiance trop basse (< 60%)
   - Vert sinon
4. **Section alertes** : Liste détaillée si problèmes
5. **Tendances** : Affiche l'évolution sur 7 jours

**Ce rapport est envoyé par email tous les jours à 9h !**

---

# Réentraînement

## retraining/retrain_model.py

**Objectif :** Réentraîner automatiquement le modèle YOLOv8 avec de nouvelles images annotées.

### Classe ModelRetrainer

```python
class ModelRetrainer:
    def __init__(self, base_model_path='model/weights/best.pt'):
        """
        Initialise le système de réentraînement

        Args:
            base_model_path: Chemin vers le modèle actuel (sera utilisé comme base)
        """
        self.base_model_path = base_model_path
        self.conn = psycopg2.connect(DATABASE_URL)
        self.cur = self.conn.cursor()
        self.s3 = boto3.client('s3')

        # Repertoires de travail
        self.work_dir = Path('retraining_workspace')
        self.dataset_dir = self.work_dir / 'dataset'
        self.images_dir = self.dataset_dir / 'images'
        self.labels_dir = self.dataset_dir / 'labels'
        self.train_dir = self.images_dir / 'train'
        self.val_dir = self.images_dir / 'val'
        self.train_labels_dir = self.labels_dir / 'train'
        self.val_labels_dir = self.labels_dir / 'val'

        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
```

**Explication de l'architecture des dossiers :**

```
retraining_workspace/
├── dataset/
│   ├── images/
│   │   ├── train/  (80% des images)
│   │   └── val/    (20% des images)
│   ├── labels/
│   │   ├── train/  (fichiers .txt YOLO)
│   │   └── val/
│   └── data.yaml   (config YOLOv8)
└── runs/           (résultats d'entraînement)
```

**Format YOLO pour les labels :**
Chaque image `img_123.jpg` a un fichier `img_123.txt` :
```
0 0.5 0.5 0.2 0.3
```
- `0` : Classe (0 = fire)
- `0.5 0.5` : Centre de la boîte (x, y) normalisé (0-1)
- `0.2 0.3` : Largeur, hauteur normalisées (0-1)

### Méthode check_if_retraining_needed()

```python
def check_if_retraining_needed(self):
    """
    Vérifie si un réentraînement est nécessaire

    Critères:
    1. Alertes critiques récentes (7 jours) + 100 annotations
    2. OU 500+ annotations disponibles

    Returns:
        tuple: (should_retrain, reason, annotated_count)
    """
    # Vérifier s'il y a des alertes critiques récentes
    self.cur.execute("""
        SELECT COUNT(*) FROM model_alerts
        WHERE severity = 'critical'
        AND created_at > NOW() - INTERVAL '7 days'
        AND resolved = FALSE
    """)
    critical_alerts = self.cur.fetchone()[0]

    # Compter les images annotées non utilisées
    self.cur.execute("""
        SELECT COUNT(*) FROM annotations
        WHERE used_for_training = FALSE
        AND is_correct IS NOT NULL
    """)
    annotated_count = self.cur.fetchone()[0]

    # DÉCISION
    if critical_alerts > 0 and annotated_count >= 100:
        return True, f"{critical_alerts} alerte(s) critique(s) detectee(s)", annotated_count
    elif annotated_count >= 500:
        return True, f"{annotated_count} nouvelles images annotees disponibles", annotated_count
    else:
        return False, f"Pas assez d'images annotees ({annotated_count}/100 minimum)", annotated_count
```

**Explication de la logique :**

**Cas 1 : Réentraînement urgent**
- Alertes critiques (confiance < 60%)
- ET au moins 100 images annotées
- → Le modèle dégrade, on réentraîne immédiatement

**Cas 2 : Réentraînement préventif**
- 500+ images annotées disponibles
- → On améliore proactivement le modèle

**Cas 3 : Pas de réentraînement**
- Pas d'alertes critiques
- ET moins de 100 annotations
- → On attend plus de données

### Méthode prepare_dataset()

```python
def prepare_dataset(self):
    """
    Prépare le dataset pour l'entraînement
    1. Télécharge images depuis S3
    2. Crée les fichiers labels YOLO
    3. Split train/val (80/20)

    Returns:
        tuple: (data_yaml_path, train_count, val_count)
    """
    logging.info("Preparation du dataset...")

    # 1. CRÉER LES RÉPERTOIRES
    for dir_path in [self.train_dir, self.val_dir, self.train_labels_dir, self.val_labels_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)

    # 2. RÉCUPÉRER LES ANNOTATIONS
    self.cur.execute("""
        SELECT a.id, a.image_id, a.corrected_label, a.corrected_bbox,
               a.is_correct, i.s3_path, i.camera_name,
               mp.fire_detected, mp.confidence, mp.bbox
        FROM annotations a
        JOIN images i ON a.image_id = i.id
        LEFT JOIN model_predictions mp ON a.prediction_id = mp.id
        WHERE a.used_for_training = FALSE
        AND a.is_correct IS NOT NULL
        ORDER BY a.annotated_at
    """)

    annotations = self.cur.fetchall()
    total = len(annotations)

    if total < 100:
        raise Exception(f"Pas assez d'annotations ({total}/100 minimum)")

    logging.info(f"Preparation de {total} images annotees...")

    # 3. SPLIT TRAIN/VAL (80/20)
    split_idx = int(total * 0.8)

    # 4. TRAITER CHAQUE ANNOTATION
    for idx, annot in enumerate(annotations):
        (annot_id, image_id, corrected_label, corrected_bbox, is_correct,
         s3_path, camera_name, fire_detected, confidence, bbox) = annot

        # Déterminer si train ou val
        is_train = idx < split_idx
        img_dir = self.train_dir if is_train else self.val_dir
        lbl_dir = self.train_labels_dir if is_train else self.val_labels_dir

        # 5. TÉLÉCHARGER L'IMAGE DEPUIS S3
        image_filename = f"img_{image_id}.jpg"
        local_image_path = img_dir / image_filename

        try:
            self.s3.download_file(S3_BUCKET_NAME, s3_path, str(local_image_path))
        except Exception as e:
            logging.error(f"Erreur telechargement image {image_id}: {e}")
            continue

        # 6. CRÉER LE FICHIER LABEL YOLO
        label_filename = f"img_{image_id}.txt"
        local_label_path = lbl_dir / label_filename

        # Utiliser la bbox corrigée si disponible, sinon celle prédite
        final_bbox = corrected_bbox if corrected_bbox else bbox

        # 7. ÉCRIRE LE LABEL
        if final_bbox and (is_correct or corrected_label == 'fire'):
            with open(local_label_path, 'w') as f:
                class_id = 0  # fire
                if isinstance(final_bbox, dict):
                    x, y, w, h = final_bbox.get('x', 0), final_bbox.get('y', 0), final_bbox.get('w', 0), final_bbox.get('h', 0)
                else:
                    x, y, w, h = final_bbox[0], final_bbox[1], final_bbox[2], final_bbox[3]
                f.write(f"{class_id} {x} {y} {w} {h}\n")
        else:
            # Pas de feu ou faux positif → fichier label vide
            local_label_path.touch()

    # 8. CRÉER LE FICHIER data.yaml
    data_yaml = {
        'path': str(self.dataset_dir.absolute()),
        'train': 'images/train',
        'val': 'images/val',
        'nc': 1,  # Nombre de classes
        'names': ['fire']  # Noms des classes
    }

    data_yaml_path = self.dataset_dir / 'data.yaml'
    with open(data_yaml_path, 'w') as f:
        yaml.dump(data_yaml, f)

    logging.info(f"Dataset prepare: {split_idx} train, {total - split_idx} val")
    return data_yaml_path, split_idx, total - split_idx
```

**Explication détaillée :**

**Étape 2 : Requête SQL complexe**
- `JOIN` : Récupère les infos depuis 3 tables
  - `annotations` : Corrections manuelles
  - `images` : Métadonnées et S3 path
  - `model_predictions` : Prédictions originales
- `WHERE used_for_training = FALSE` : Uniquement les nouvelles annotations
- `AND is_correct IS NOT NULL` : Annotations validées (pas en attente)

**Étape 3 : Split 80/20**
- 80% pour l'entraînement (le modèle apprend)
- 20% pour la validation (mesurer la performance)
- Important : PAS de mélange aléatoire ici (ordre chronologique)

**Étape 6-7 : Logique des labels**
- Si annotation corrigée → Utiliser la bbox corrigée
- Sinon → Utiliser la bbox originale du modèle
- Si faux positif → Fichier vide (indique "pas de feu")

**Étape 8 : data.yaml**
- Fichier de configuration requis par YOLOv8
- Indique où sont les données et combien de classes

### Méthode train_model()

```python
def train_model(self, data_yaml_path, epochs=50, batch_size=16, img_size=960, learning_rate=0.001):
    """
    Entraîne le modèle YOLOv8 avec fine-tuning

    Args:
        data_yaml_path: Chemin vers data.yaml
        epochs: Nombre d'époques (défaut 50)
        batch_size: Taille des batchs (défaut 16)
        img_size: Taille des images (défaut 960)
        learning_rate: Taux d'apprentissage (défaut 0.001)

    Returns:
        dict: Résultats d'entraînement (metrics, paths, etc.)
    """
    logging.info("Demarrage de l'entrainement...")

    version_name = f"fire_model_v{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # DÉMARRER MLFLOW RUN
    with mlflow.start_run(run_name=version_name) as run:
        mlflow_run_id = run.info.run_id

        # Logger les hyperparamètres
        mlflow.log_param("base_model", self.base_model_path)
        mlflow.log_param("epochs", epochs)
        mlflow.log_param("batch_size", batch_size)
        mlflow.log_param("img_size", img_size)
        mlflow.log_param("learning_rate", learning_rate)

        # 1. CHARGER LE MODÈLE DE BASE
        model = YOLO(self.base_model_path)

        # 2. ENTRAÎNER
        training_start = datetime.now()

        results = model.train(
            data=str(data_yaml_path),
            epochs=epochs,
            batch=batch_size,
            imgsz=img_size,
            lr0=learning_rate,
            project=str(self.work_dir / 'runs'),
            name=version_name,
            exist_ok=True,
            verbose=True
        )

        training_end = datetime.now()
        training_duration = (training_end - training_start).total_seconds() / 60

        # 3. VALIDER LE MODÈLE
        val_results = model.val()

        # 4. EXTRAIRE LES MÉTRIQUES
        precision = float(val_results.box.p.mean()) if hasattr(val_results.box, 'p') else 0.0
        recall = float(val_results.box.r.mean()) if hasattr(val_results.box, 'r') else 0.0
        map50 = float(val_results.box.map50) if hasattr(val_results.box, 'map50') else 0.0
        map50_95 = float(val_results.box.map) if hasattr(val_results.box, 'map') else 0.0

        # 5. LOGGER DANS MLFLOW
        mlflow.log_metric("precision", precision)
        mlflow.log_metric("recall", recall)
        mlflow.log_metric("map50", map50)
        mlflow.log_metric("map50_95", map50_95)

        # 6. SAUVEGARDER LE MODÈLE
        model_path = self.work_dir / 'runs' / version_name / 'weights' / 'best.pt'
        mlflow.log_artifact(str(model_path))

        logging.info(f"Entrainement termine - Precision: {precision:.3f}, Recall: {recall:.3f}, mAP50: {map50:.3f}")

        return {
            'version_name': version_name,
            'mlflow_run_id': mlflow_run_id,
            'model_path': str(model_path),
            'precision': precision,
            'recall': recall,
            'map50': map50,
            'map50_95': map50_95,
            'training_duration': training_duration,
            'training_start': training_start,
            'training_end': training_end
        }
```

**Explication détaillée :**

**1. MLflow Run**
- Crée un "run" pour tracker cet entraînement
- Tous les paramètres et métriques seront associés à ce run
- Visible dans l'interface MLflow (http://localhost:5001)

**2. Fine-tuning**
- On part du modèle actuel (base_model_path)
- Le modèle a déjà été entraîné sur Pyro-SDIS
- On l'affine avec les nouvelles données annotées

**3. Paramètres d'entraînement**
- `epochs=30` : Moins que l'entraînement initial (50) car c'est du fine-tuning
- `batch_size=16` : Nombre d'images par batch
- `img_size=960` : DOIT être identique à l'entraînement initial
- `lr0=0.001` : Learning rate (taux d'apprentissage)

**4. Métriques**
- **Precision** : Sur 100 détections "feu", combien sont vraies?
- **Recall** : Sur 100 vrais feux, combien sont détectés?
- **mAP50** : Mean Average Precision (IoU≥0.5)
- **mAP50-95** : mAP moyen sur plusieurs IoU

**Exemple :**
- Precision = 0.85 → 85% des détections sont correctes (15% faux positifs)
- Recall = 0.75 → On détecte 75% des feux réels (25% manqués)

### Méthode compare_with_baseline()

```python
def compare_with_baseline(self, new_version_name):
    """
    Compare la nouvelle version avec la version actuellement déployée

    Args:
        new_version_name: Nom de la nouvelle version

    Returns:
        tuple: (should_deploy, improvement_percent, comparison_details)
    """
    # 1. RÉCUPÉRER LA VERSION ACTUELLEMENT DÉPLOYÉE
    self.cur.execute("""
        SELECT version_name, precision, recall, map50
        FROM model_versions
        WHERE deployed = TRUE
        ORDER BY deployed_at DESC
        LIMIT 1
    """)

    baseline = self.cur.fetchone()

    if not baseline:
        logging.info("Pas de baseline deployee, deploiement automatique")
        return True, 100.0, "Premiere version"

    baseline_name, baseline_precision, baseline_recall, baseline_map50 = baseline

    # 2. RÉCUPÉRER LES MÉTRIQUES DE LA NOUVELLE VERSION
    self.cur.execute("""
        SELECT precision, recall, map50
        FROM model_versions
        WHERE version_name = %s
    """, (new_version_name,))

    new_metrics = self.cur.fetchone()
    new_precision, new_recall, new_map50 = new_metrics

    # 3. CALCULER L'AMÉLIORATION
    improvement = ((new_map50 - baseline_map50) / baseline_map50 * 100) if baseline_map50 > 0 else 0

    # 4. DÉCISION: DÉPLOYER SI AMÉLIORATION ≥ 2%
    should_deploy = improvement >= 2.0 or (new_precision > baseline_precision and new_recall > baseline_recall)

    # 5. SAUVEGARDER LA COMPARAISON
    self.cur.execute("""
        INSERT INTO model_comparisons
        (old_version, new_version, old_precision, new_precision, old_recall,
         new_recall, old_map50, new_map50, improvement_percent, decision, decision_reason)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        baseline_name,
        new_version_name,
        baseline_precision,
        new_precision,
        baseline_recall,
        new_recall,
        baseline_map50,
        new_map50,
        improvement,
        'deploy' if should_deploy else 'rollback',
        f"Amelioration: {improvement:.1f}%" if should_deploy else "Pas assez d'amelioration"
    ))
    self.conn.commit()

    logging.info(f"Comparaison: Baseline {baseline_name} (mAP50={baseline_map50:.3f}) vs {new_version_name} (mAP50={new_map50:.3f})")
    logging.info(f"Amelioration: {improvement:.1f}% - Decision: {'DEPLOYER' if should_deploy else 'ROLLBACK'}")

    return should_deploy, improvement, {
        'baseline_name': baseline_name,
        'baseline_map50': baseline_map50,
        'new_map50': new_map50
    }
```

**Explication de la logique de décision :**

**Critère principal : mAP50**
- C'est la métrique la plus fiable pour YOLO
- Combine précision ET rappel
- Si amélioration ≥ 2% → DÉPLOYER

**Critère secondaire : Précision ET Rappel**
- Si les DEUX s'améliorent → DÉPLOYER
- Même si mAP50 < 2%

**Exemple de décision :**

**Cas 1 : Déploiement**
```
Baseline: mAP50 = 0.77
Nouvelle: mAP50 = 0.79
Amélioration: +2.6% → DÉPLOYER ✅
```

**Cas 2 : Rollback**
```
Baseline: mAP50 = 0.77
Nouvelle: mAP50 = 0.771
Amélioration: +0.1% → ROLLBACK ❌ (pas assez)
```

**Cas 3 : Déploiement (critère secondaire)**
```
Baseline: Precision=0.77, Recall=0.76
Nouvelle: Precision=0.78, Recall=0.77
Les deux s'améliorent → DÉPLOYER ✅
```

**Pourquoi seuil à 2% ?**
- Évite les déploiements pour variations mineures
- 2% = Amélioration significative et mesurable
- Réduit les risques de régression

### Méthode deploy_model()

```python
def deploy_model(self, version_name, model_path):
    """
    Déploie la nouvelle version du modèle en production

    Args:
        version_name: Nom de la version à déployer
        model_path: Chemin vers le fichier .pt
    """
    logging.info(f"Deploiement de {version_name}...")

    production_model_path = Path(self.base_model_path)
    production_model_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. BACKUP DE L'ANCIEN MODÈLE
    if production_model_path.exists():
        backup_path = production_model_path.parent / f"best_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pt"
        shutil.copy(production_model_path, backup_path)
        logging.info(f"Backup de l'ancien modele: {backup_path}")

    # 2. COPIER LE NOUVEAU MODÈLE
    shutil.copy(model_path, production_model_path)

    # 3. MARQUER COMME DÉPLOYÉ DANS LA BASE
    # D'abord, démarquer l'ancien
    self.cur.execute("""
        UPDATE model_versions
        SET deployed = FALSE
        WHERE deployed = TRUE
    """)

    # Puis marquer le nouveau
    self.cur.execute("""
        UPDATE model_versions
        SET deployed = TRUE, deployed_at = NOW()
        WHERE version_name = %s
    """, (version_name,))

    self.conn.commit()

    logging.info(f"Modele {version_name} deploye avec succes!")
```

**Explication du process de déploiement :**

**Étape 1 : Backup**
- Copie l'ancien modèle avec timestamp
- Permet un rollback manuel si problème
- Exemple : `best_backup_20260109_143022.pt`

**Étape 2 : Remplacement**
- Copie le nouveau modèle vers `model/weights/best.pt`
- À partir de maintenant, c'est CE modèle qui sera utilisé

**Étape 3 : Base de données**
- Démarque toutes les anciennes versions
- Marque la nouvelle comme déployée
- Historique complet conservé

**IMPORTANT :**
- Le déploiement est **immédiat**
- Prochaine inférence = nouveau modèle
- Pas besoin de redémarrer Airflow

---

## retraining/annotation_tools.py

**Objectif :** Outils pour annoter manuellement les prédictions.

### Classe AnnotationManager

```python
class AnnotationManager:
    def __init__(self):
        """Initialise le gestionnaire d'annotations"""
        self.conn = psycopg2.connect(DATABASE_URL)
        self.cur = self.conn.cursor()
```

### Méthode get_predictions_to_review()

```python
def get_predictions_to_review(self, limit=50, fire_only=False):
    """
    Récupère les prédictions qui nécessitent une révision

    Args:
        limit: Nombre max de prédictions
        fire_only: True pour ne récupérer que les détections de feu

    Returns:
        list: Liste de prédictions à reviewer
    """
    fire_filter = "AND mp.fire_detected = TRUE" if fire_only else ""

    self.cur.execute(f"""
        SELECT mp.id, mp.image_id, mp.camera_name, mp.fire_detected,
               mp.confidence, mp.bbox, i.s3_path, mp.prediction_timestamp
        FROM model_predictions mp
        JOIN images i ON mp.image_id = i.id
        LEFT JOIN annotations a ON mp.id = a.prediction_id
        WHERE a.id IS NULL  -- Pas encore annotée
        {fire_filter}
        ORDER BY mp.prediction_timestamp DESC
        LIMIT %s
    """, (limit,))

    predictions = []
    for row in self.cur.fetchall():
        predictions.append({
            'prediction_id': row[0],
            'image_id': row[1],
            'camera_name': row[2],
            'fire_detected': row[3],
            'confidence': row[4],
            'bbox': row[5],
            's3_path': row[6],
            'timestamp': row[7]
        })

    return predictions
```

**Explication :**
- `LEFT JOIN annotations` : Récupère aussi les prédictions sans annotation
- `WHERE a.id IS NULL` : Filtre les non-annotées
- `fire_only` : Utile pour se concentrer sur les faux positifs

### Méthode annotate_prediction()

```python
def annotate_prediction(self, prediction_id, is_correct, corrected_label=None,
                      corrected_bbox=None, notes=None, annotated_by='manual'):
    """
    Annote une prédiction

    Args:
        prediction_id: ID de la prédiction
        is_correct: True si la prédiction est correcte, False sinon
        corrected_label: 'fire' ou 'no_fire' si correction nécessaire
        corrected_bbox: [x, y, w, h] si bbox incorrecte
        notes: Notes optionnelles
        annotated_by: Qui a annoté (défaut: 'manual')

    Returns:
        int: ID de l'annotation créée
    """
    self.cur.execute("""
        INSERT INTO annotations
        (prediction_id, image_id, annotation_type, is_correct, corrected_label,
         corrected_bbox, notes, annotated_by)
        SELECT %s, mp.image_id,
               CASE WHEN %s THEN 'validation' ELSE 'correction' END,
               %s, %s, %s, %s, %s
        FROM model_predictions mp
        WHERE mp.id = %s
        RETURNING id
    """, (
        prediction_id,
        is_correct,
        is_correct,
        corrected_label,
        psycopg2.extras.Json(corrected_bbox) if corrected_bbox else None,
        notes,
        annotated_by,
        prediction_id
    ))

    self.conn.commit()
    annotation_id = self.cur.fetchone()[0]

    logging.info(f"Annotation creee: ID={annotation_id}, prediction={prediction_id}, is_correct={is_correct}")
    return annotation_id
```

**Explication :**
- `annotation_type` : 'validation' si correct, 'correction' sinon
- `corrected_label` : Uniquement si prédiction incorrecte
- `corrected_bbox` : Uniquement si bbox mal placée

**Exemples d'usage :**

**Cas 1 : Prédiction correcte**
```python
annotate_prediction(123, is_correct=True)
# Le modèle a bien détecté un feu
```

**Cas 2 : Faux positif**
```python
annotate_prediction(456, is_correct=False, corrected_label='no_fire', notes='Reflet soleil')
# Le modèle a détecté un feu mais c'était un reflet
```

**Cas 3 : Bounding box incorrecte**
```python
annotate_prediction(789, is_correct=False, corrected_bbox=[0.6, 0.4, 0.2, 0.3], notes='Bbox trop petite')
# Le modèle a détecté le feu mais la boîte n'encadre pas bien les flammes
```

### Méthode get_annotation_stats()

```python
def get_annotation_stats(self):
    """
    Récupère les statistiques d'annotation

    Returns:
        dict: Statistiques complètes
    """
    self.cur.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) as correct,
            SUM(CASE WHEN NOT is_correct THEN 1 ELSE 0 END) as incorrect,
            SUM(CASE WHEN used_for_training THEN 1 ELSE 0 END) as used_for_training,
            SUM(CASE WHEN NOT used_for_training AND is_correct IS NOT NULL THEN 1 ELSE 0 END) as ready_for_training
        FROM annotations
    """)

    row = self.cur.fetchone()

    return {
        'total': row[0],
        'correct': row[1],
        'incorrect': row[2],
        'used_for_training': row[3],
        'ready_for_training': row[4]  # Annotations validées mais pas encore utilisées
    }
```

**Explication :**
- `ready_for_training` : Annotations prêtes pour le réentraînement
- Quand ce nombre atteint 100 → On peut réentraîner

---

# Orchestration Airflow

## dags/fire_detection_workflow.py

**Objectif :** DAG principal qui orchestre scraping → inference → alertes.

### Configuration du DAG

```python
default_args = {
    'owner': 'axel',
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
    'start_date': datetime(2024, 1, 1),
    'catchup': False,  # Ne pas rattraper les exécutions manquées
    'email_on_failure': False,
}

with DAG(
    'fire_detection_pipeline',
    default_args=default_args,
    description='Pipeline de détection incendie',
    schedule_interval='*/15 * * * *',  # Toutes les 15 minutes
    catchup=False
) as dag:
```

**Explication :**
- `owner` : Propriétaire du DAG
- `retries=1` : Réessaie 1 fois si échec
- `retry_delay` : Attend 1 minute avant de réessayer
- `catchup=False` : **IMPORTANT** - Ne pas rattraper le passé
- `schedule_interval='*/15 * * * *'` : Expression cron pour "toutes les 15 minutes"

**Format cron :**
```
*/15 * * * *
 │   │ │ │ │
 │   │ │ │ └─── Jour de la semaine (0-6, 0=dimanche)
 │   │ │ └───── Mois (1-12)
 │   │ └─────── Jour du mois (1-31)
 │   └───────── Heure (0-23)
 └─────────────Minute (0-59)

*/15 = Toutes les 15 minutes
```

### Tâche 1 : Scraping

```python
def task_scrape_images(**context):
    """
    Tâche 1: Scraper les caméras

    Steps:
    1. Initialise le scraper
    2. Démarre le navigateur Chrome
    3. Scrape toutes les 165 caméras
    4. Upload sur S3 + Enregistre dans Neon
    5. Ferme le navigateur
    """
    print("Début du scraping...")
    from scraper import AlertWildfireScraper

    scraper = AlertWildfireScraper()
    scraper.start()
    scraper.scrape_all()  # Toutes les 165 caméras
    scraper.stop()
    print("Scraping terminé.")
```

**Explication :**
- Fonction Python appelée par Airflow
- `**context` : Airflow passe des infos contextuelles (date d'exécution, etc.)
- Import local : `from scraper import...` (évite import au niveau module)

### Tâche 2 : Inférence + Email

```python
def task_run_inference(**context):
    """
    Tâche 2: Analyser les images + Envoyer alertes

    Steps:
    1. Récupère les images en attente (status='NEW')
    2. Pour chaque image:
       a. Télécharge depuis S3
       b. Inférence YOLOv8 (avec logging monitoring auto)
       c. Si feu détecté → Email d'alerte
       d. Met à jour la base
    """
    print("Début de l'analyse IA...")

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
            # 1. TÉLÉCHARGER DEPUIS S3
            s3.download_file(bucket, img['s3_path'], local_path)

            # 2. PRÉDICTION AVEC AUTO-LOGGING
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

            # 3. METTRE À JOUR LA BASE
            db.update_prediction(img['id'], is_fire, conf, bbox)

            # 4. ENVOYER EMAIL SI FEU DÉTECTÉ
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
                <p><i>Ceci est une alerte automatique générée par Airflow + MLflow.</i></p>
                <p><i>Prédiction loggée dans Neon pour monitoring.</i></p>
                """

                send_email(to=['axel.vilamot@gmail.com'], subject=subject, html_content=html_content)
                print("Mail envoyé via Airflow Backend.")

            os.remove(local_path)

        except Exception as e:
            print(f"Erreur sur l'image {img['id']}: {e}")

    db.close()
    print(f"Analyse terminée - {len(images)} images analysées et loggées dans Neon")
```

**Explication détaillée :**

**Path dans Docker**
- `/opt/airflow` : Répertoire racine dans le container
- Équivalent à votre dossier local `Fire_detection/`

**Boucle sur les images**
- Traite TOUTES les images en attente
- Si 100 images → 100 inférences
- Durée totale ≈ 50 secondes (500ms/image)

**Email d'alerte**
- `send_email()` : Fonction Airflow intégrée
- Utilise la config SMTP du .env
- Email HTML formaté

**Gestion mémoire**
- `os.remove(local_path)` : Supprime l'image temporaire
- Évite de saturer `/tmp` dans le container

### Définition du DAG

```python
with DAG(...) as dag:
    scrape_task = PythonOperator(
        task_id='scrape_cameras',
        python_callable=task_scrape_images
    )

    inference_task = PythonOperator(
        task_id='analyze_images',
        python_callable=task_run_inference
    )

    # DÉFINIR L'ORDRE D'EXÉCUTION
    scrape_task >> inference_task  # Scraping PUIS inference
```

**Explication de l'opérateur >>**
- Définit les dépendances entre tâches
- `scrape_task >> inference_task` = "scrape AVANT inference"
- Airflow attend que scrape_task termine avant de lancer inference_task

**Visualisation dans Airflow :**
```
[scrape_cameras] → [analyze_images]
```

---

## dags/monitor_model.py

**Objectif :** DAG pour le monitoring quotidien du modèle.

### Configuration

```python
with DAG(
    'model_monitoring_daily',
    default_args=default_args,
    description='Monitoring quotidien du modele de detection de feu',
    schedule_interval='0 9 * * *',  # Tous les jours à 9h00 du matin
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['monitoring', 'model', 'fire_detection'],
) as dag:
```

**Explication :**
- `schedule_interval='0 9 * * *'` : Cron pour "9h tous les jours"
- `tags` : Pour filtrer dans l'interface Airflow

### Tâche 1 : Calculer les métriques

```python
def calculate_and_save_metrics(**context):
    """
    Calcule les métriques quotidiennes et les sauvegarde
    """
    monitor = ModelMonitor()

    try:
        # Calculer les métriques d'hier
        metrics = monitor.calculate_daily_metrics()

        if metrics is None:
            print("Aucune prediction hier, pas de metriques a calculer")
            context['ti'].xcom_push(key='metrics', value=None)
            return

        # Sauvegarder les métriques
        monitor.save_daily_metrics(metrics)

        # Passer les métriques au contexte pour la prochaine tâche
        context['ti'].xcom_push(key='metrics', value=metrics)

        print(f"Metriques calculees et sauvegardees: {metrics}")

    finally:
        monitor.close()
```

**Explication de XCom :**
- `xcom_push` : Passe des données entre tâches Airflow
- `context['ti']` : TaskInstance (instance de la tâche)
- Les métriques seront récupérées par la tâche suivante avec `xcom_pull`

### Tâche 2 : Détecter les anomalies

```python
def detect_and_alert(**context):
    """
    Détecte les anomalies dans les métriques et crée des alertes
    """
    # Récupérer les métriques de la tâche précédente
    metrics = context['ti'].xcom_pull(key='metrics', task_ids='calculate_metrics')

    if metrics is None:
        print("Pas de metriques, pas d'analyse d'anomalies")
        context['ti'].xcom_push(key='alerts', value=[])
        return

    monitor = ModelMonitor()

    try:
        # Détecter les anomalies
        alerts = monitor.detect_anomalies(metrics)

        if alerts:
            print(f"ALERTE: {len(alerts)} anomalie(s) detectee(s)")
            for alert in alerts:
                print(f"  - {alert['message']}")

            # Sauvegarder les alertes
            monitor.save_alerts(alerts)
        else:
            print("Aucune anomalie detectee - Modele fonctionne normalement")

        # Passer les alertes au contexte
        context['ti'].xcom_push(key='alerts', value=alerts)

    finally:
        monitor.close()
```

**Explication :**
- Récupère les métriques avec `xcom_pull`
- Détecte les anomalies
- Sauvegarde dans `model_alerts`
- Passe les alertes à la tâche suivante

### Tâche 3 : Envoyer le rapport

```python
def generate_and_send_report(**context):
    """
    Génère un rapport HTML et l'envoie par email
    """
    metrics = context['ti'].xcom_pull(key='metrics', task_ids='calculate_metrics')
    alerts = context['ti'].xcom_pull(key='alerts', task_ids='detect_anomalies')

    if metrics is None:
        print("Pas de metriques, pas de rapport a envoyer")
        return

    monitor = ModelMonitor()

    try:
        # Analyse des tendances
        trends = monitor.get_trend_analysis(days=7)

        # Générer le rapport HTML
        html_report = monitor.generate_report(metrics, alerts, trends)

        # Préparer le sujet de l'email
        if alerts:
            critical_alerts = [a for a in alerts if a['severity'] == 'critical']
            if critical_alerts:
                subject = f"[CRITIQUE] Alerte Monitoring Modele - {metrics['metric_date']}"
            else:
                subject = f"[ATTENTION] Alerte Monitoring Modele - {metrics['metric_date']}"
        else:
            subject = f"[OK] Rapport Monitoring Modele - {metrics['metric_date']}"

        # Envoyer l'email
        send_email(
            to=['axel.vilamot@gmail.com'],
            subject=subject,
            html_content=html_report
        )

        print(f"Rapport envoye a axel.vilamot@gmail.com")

    finally:
        monitor.close()
```

**Explication :**
- Récupère métriques ET alertes
- Calcule les tendances
- Génère HTML
- Adapte le sujet selon la gravité
- Envoie l'email

### Ordre d'exécution

```python
calculate_metrics_task >> detect_anomalies_task >> send_report_task
```

**Visualisation :**
```
[calculate_metrics] → [detect_anomalies] → [send_report]
```

---

## dags/retrain_workflow.py

**Objectif :** DAG pour le réentraînement automatique (déclenchement manuel).

### Configuration

```python
with DAG(
    'model_retraining',
    default_args=default_args,
    description='Reentrainement automatique du modele de detection de feu',
    schedule_interval=None,  # Déclenchement manuel uniquement
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['retraining', 'model', 'fire_detection'],
) as dag:
```

**Explication :**
- `schedule_interval=None` : **PAS d'exécution automatique**
- Doit être déclenché manuellement depuis l'interface Airflow
- Ou déclenché programmatiquement si alertes critiques

### Tâche 1 : Vérifier si réentraînement nécessaire

```python
def check_retrain_needed(**context):
    """
    Vérifie si un réentraînement est nécessaire
    Retourne le nom de la prochaine tâche (branch)
    """
    retrainer = ModelRetrainer()

    try:
        should_retrain, reason, count = retrainer.check_if_retraining_needed()

        context['ti'].xcom_push(key='should_retrain', value=should_retrain)
        context['ti'].xcom_push(key='reason', value=reason)
        context['ti'].xcom_push(key='annotated_count', value=count)

        print(f"Verification: should_retrain={should_retrain}, reason={reason}, count={count}")

        if should_retrain:
            # Créer le trigger
            trigger_id = retrainer.create_retrain_trigger('automatic', reason, count)
            context['ti'].xcom_push(key='trigger_id', value=trigger_id)
            return 'prepare_dataset_task'  # Passe à l'étape suivante
        else:
            return 'skip_retrain_task'  # Skip tout le pipeline

    finally:
        retrainer.close()
```

**Explication de BranchPythonOperator :**
- Permet de **choisir dynamiquement** la prochaine tâche
- Si pas assez d'annotations → Skip tout
- Si conditions OK → Continue le pipeline

### Workflow complet

```python
# Tâche de branchement
check_retrain = BranchPythonOperator(
    task_id='check_retrain_needed',
    python_callable=check_retrain_needed,
    provide_context=True,
)

# Chemin 1: Réentraînement
prepare_dataset = PythonOperator(task_id='prepare_dataset_task', ...)
train_model = PythonOperator(task_id='train_model_task', ...)
validate_and_compare = BranchPythonOperator(task_id='validate_and_compare', ...)
deploy_model = PythonOperator(task_id='deploy_model_task', ...)

# Chemin 2: Skip
skip_retrain = EmptyOperator(task_id='skip_retrain_task')

# Flux d'exécution
check_retrain >> [prepare_dataset, skip_retrain]
prepare_dataset >> train_model >> validate_and_compare
validate_and_compare >> [deploy_model, skip_deploy]
[deploy_model, skip_deploy, skip_retrain] >> cleanup >> send_report
```

**Visualisation :**

```
                    ┌──> skip_retrain ──┐
                    │                    │
check_retrain ──────┤                    ├──> cleanup ──> send_report
                    │                    │
                    └──> prepare_dataset ──> train_model ──> validate ──┬──> deploy ──┘
                                                                         └──> skip_deploy ──┘
```

**Explication du flux :**

1. **check_retrain_needed** : Point de décision
   - Si conditions OK → prepare_dataset
   - Sinon → skip_retrain → cleanup → email "rien à faire"

2. **prepare_dataset** : Télécharge images + crée labels YOLO

3. **train_model** : Fine-tuning YOLOv8

4. **validate_and_compare** : Nouveau point de décision
   - Si amélioration ≥ 2% → deploy_model
   - Sinon → skip_deploy

5. **cleanup** : Nettoie fichiers temporaires (toujours exécuté)

6. **send_report** : Email avec résultats (toujours exécuté)

**trigger_rule='all_done'**
- Par défaut, Airflow exécute une tâche seulement si les parents ont réussi
- `all_done` : Exécute même si parents ont échoué
- Important pour cleanup et send_report (doivent toujours s'exécuter)

---

# Scripts Utilitaires

## create_monitoring_tables.py

**Objectif :** Créer les tables nécessaires au monitoring (à exécuter une seule fois).

```python
def create_monitoring_tables():
    """Crée les tables nécessaires pour le monitoring du modèle"""

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Table pour logger chaque prédiction individuelle
    cur.execute("""
        CREATE TABLE IF NOT EXISTS model_predictions (
            id SERIAL PRIMARY KEY,
            image_id INTEGER REFERENCES images(id),
            batch_id VARCHAR(50),
            camera_name VARCHAR(100),
            prediction_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fire_detected BOOLEAN,
            confidence FLOAT,
            bbox JSONB,
            model_version VARCHAR(50) DEFAULT 'yolov8s-v1',
            inference_time_ms FLOAT,
            image_size_bytes INTEGER,
            s3_path TEXT
        );
    """)

    # Autres tables (daily_metrics, model_alerts)...

    conn.commit()
    cur.close()
    conn.close()
```

**Explication :**
- `CREATE TABLE IF NOT EXISTS` : Ne crée que si n'existe pas
- `SERIAL PRIMARY KEY` : ID auto-incrémenté
- `REFERENCES images(id)` : Clé étrangère vers la table images
- `JSONB` : Format JSON binaire (plus rapide que JSON)

## create_retraining_tables.py

**Objectif :** Créer les tables pour le réentraînement.

```python
def create_retraining_tables():
    """Crée les tables nécessaires pour le réentraînement"""

    # Table annotations
    cur.execute("""
        CREATE TABLE IF NOT EXISTS annotations (
            id SERIAL PRIMARY KEY,
            image_id INTEGER REFERENCES images(id),
            prediction_id INTEGER REFERENCES model_predictions(id),
            annotated_by VARCHAR(100) DEFAULT 'system',
            annotation_type VARCHAR(50) NOT NULL,
            is_correct BOOLEAN,
            corrected_label VARCHAR(50),
            corrected_bbox JSONB,
            confidence_score FLOAT,
            notes TEXT,
            annotated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            used_for_training BOOLEAN DEFAULT FALSE
        );
    """)

    # Table model_versions
    cur.execute("""
        CREATE TABLE IF NOT EXISTS model_versions (
            id SERIAL PRIMARY KEY,
            version_name VARCHAR(100) UNIQUE NOT NULL,
            mlflow_run_id VARCHAR(100),
            precision FLOAT,
            recall FLOAT,
            map50 FLOAT,
            deployed BOOLEAN DEFAULT FALSE,
            deployed_at TIMESTAMP,
            ...
        );
    """)
```

---

# Configuration

## .env

**CRITIQUE - Ne JAMAIS commit ce fichier !**

```bash
# AWS S3
AWS_ACCESS_KEY_ID=VOTRE_ACCESS_KEY_ICI
AWS_SECRET_ACCESS_KEY=VOTRE_SECRET_KEY_ICI
S3_BUCKET_NAME=votre-bucket-name

# PostgreSQL (Neon)
DATABASE_URL=postgresql://user:password@host/database?sslmode=require

# Email (Gmail SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=axel.vilamot@gmail.com
SMTP_PASSWORD=qsxvcjcgxgndgfse

# MLflow
MLFLOW_TRACKING_URI=http://mlflow:5000
```

**Explication :**
- Variables d'environnement chargées par `python-dotenv`
- Accessible via `os.getenv('AWS_ACCESS_KEY_ID')`
- **IMPORTANT** : Ce fichier contient des secrets → `.gitignore`

## docker-compose.yml

```yaml
version: '3.8'

services:
  airflow_standalone:
    image: apache/airflow:2.8.0
    container_name: airflow_standalone
    environment:
      - AIRFLOW__CORE__LOAD_EXAMPLES=False
      - AIRFLOW__CORE__EXECUTOR=SequentialExecutor
      - DATABASE_URL=${DATABASE_URL}
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
    volumes:
      - ./dags:/opt/airflow/dags
      - ./scraper:/opt/airflow/scraper
      - ./model:/opt/airflow/model
      - ./monitoring:/opt/airflow/monitoring
      - ./retraining:/opt/airflow/retraining
    ports:
      - "8080:8080"
    command: >
      bash -c "
        airflow db init &&
        airflow users create --username admin --password admin123 --firstname Admin --lastname User --role Admin --email admin@example.com &&
        airflow standalone
      "

  mlflow_server:
    image: python:3.10
    container_name: mlflow_server
    environment:
      - MLFLOW_BACKEND_STORE_URI=${DATABASE_URL}
    ports:
      - "5001:5000"
    command: >
      bash -c "
        pip install mlflow psycopg2-binary &&
        mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri ${DATABASE_URL}
      "
```

**Explication :**

**Service airflow_standalone**
- `image: apache/airflow:2.8.0` : Version stable d'Airflow
- `volumes` : Monte les dossiers locaux dans le container
  - `./dags` → `/opt/airflow/dags` (DAGs visibles par Airflow)
- `ports: "8080:8080"` : Expose Airflow sur http://localhost:8080
- `command` : Commandes exécutées au démarrage
  - `airflow db init` : Initialise la base
  - `airflow users create` : Crée l'utilisateur admin
  - `airflow standalone` : Lance Airflow en mode standalone

**Service mlflow_server**
- `image: python:3.10` : Image Python de base
- `MLFLOW_BACKEND_STORE_URI` : Stocke les runs dans Neon
- `ports: "5001:5000"` : Expose MLflow sur http://localhost:5001
- `command` : Installe MLflow et le lance

---

# Annexes

## Métriques YOLOv8

### Precision
**Définition :** Sur toutes les détections "feu", combien sont vraies?

**Formule :**
```
Precision = TP / (TP + FP)
```

**Exemple :**
- Le modèle détecte 100 feux
- 85 sont de vrais feux (True Positives)
- 15 sont des faux positifs (False Positives)
- **Precision = 85 / (85 + 15) = 0.85 (85%)**

**Interprétation :**
- Precision = 100% : Jamais de faux positifs (mais peut manquer des feux)
- Precision = 50% : La moitié des détections sont des faux positifs

### Recall (Rappel)
**Définition :** Sur tous les vrais feux, combien sont détectés?

**Formule :**
```
Recall = TP / (TP + FN)
```

**Exemple :**
- Il y a 100 vrais feux dans le dataset
- Le modèle en détecte 75 (True Positives)
- 25 ne sont pas détectés (False Negatives)
- **Recall = 75 / (75 + 25) = 0.75 (75%)**

**Interprétation :**
- Recall = 100% : Tous les feux sont détectés (mais beaucoup de faux positifs possibles)
- Recall = 50% : La moitié des feux ne sont pas détectés

### mAP50 (mean Average Precision at IoU=0.5)
**Définition :** Précision moyenne en considérant qu'une détection est correcte si l'IoU ≥ 0.5

**IoU (Intersection over Union) :**
```
IoU = Aire(Intersection) / Aire(Union)
```

**Exemple :**
- Bounding box prédite : [x=0.5, y=0.5, w=0.2, h=0.3]
- Bounding box vraie : [x=0.55, y=0.52, w=0.18, h=0.28]
- Si les boîtes se chevauchent à 60% → IoU = 0.6 → **Détection correcte** (≥ 0.5)

**Interprétation :**
- mAP50 = 0.77 : Le modèle a 77% de précision moyenne
- C'est la métrique la plus importante pour YOLO

### F1-Score
**Définition :** Moyenne harmonique de Precision et Recall

**Formule :**
```
F1 = 2 * (Precision * Recall) / (Precision + Recall)
```

**Exemple :**
- Precision = 0.85
- Recall = 0.75
- **F1 = 2 * (0.85 * 0.75) / (0.85 + 0.75) = 0.797**

**Interprétation :**
- F1 = 1.0 : Perfection (Precision = Recall = 100%)
- F1 équilibre Precision et Recall

---

## Formats de Données

### Format YOLO (labels)
```
0 0.5 0.5 0.2 0.3
│  │   │   │   │
│  │   │   │   └─ Hauteur normalisée (0-1)
│  │   │   └───── Largeur normalisée (0-1)
│  │   └───────── Y centre (0-1)
│  └───────────── X centre (0-1)
└──────────────── Classe (0=fire)
```

**Normalisation :**
- `x = x_pixel / largeur_image`
- `y = y_pixel / hauteur_image`
- `w = largeur_bbox / largeur_image`
- `h = hauteur_bbox / hauteur_image`

### Format JSONB (PostgreSQL)
```json
{
  "x": 0.5,
  "y": 0.5,
  "w": 0.2,
  "h": 0.3
}
```

**Avantages :**
- Requêtable en SQL
- Flexible (peut ajouter des champs)
- Indexable

---

## Commandes Utiles

### Docker
```bash
# Lancer le système
docker-compose up -d

# Arrêter
docker-compose down

# Voir les logs
docker logs airflow_standalone
docker logs mlflow_server

# Redémarrer un service
docker-compose restart airflow_standalone

# Entrer dans un container
docker exec -it airflow_standalone bash
```

### Airflow (dans le container)
```bash
# Lister les DAGs
airflow dags list

# Tester un DAG manuellement
airflow dags test fire_detection_pipeline 2026-01-09

# Voir les logs d'une tâche
airflow tasks logs fire_detection_pipeline scrape_cameras 2026-01-09

# Créer un utilisateur
airflow users create --username admin --password admin123 --role Admin
```

### PostgreSQL (Neon)
```bash
# Se connecter (depuis Python)
import psycopg2
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

# Requête exemple
cur.execute("SELECT COUNT(*) FROM images")
print(cur.fetchone()[0])
```

### AWS S3
```bash
# Lister les images
aws s3 ls s3://fire-detection-bucket-axelvlmt/fire_detection/ --recursive

# Télécharger une image
aws s3 cp s3://fire-detection-bucket-axelvlmt/fire_detection/batch_xxx/img.png ./

# Compter les images
aws s3 ls s3://fire-detection-bucket-axelvlmt/fire_detection/ --recursive | wc -l
```

---

## Glossaire

**Airflow** : Outil d'orchestration de workflows
**DAG** : Directed Acyclic Graph (graphe de tâches)
**MLflow** : Plateforme de tracking d'expériences ML
**YOLOv8** : Modèle de détection d'objets en temps réel
**Fine-tuning** : Réentraînement d'un modèle pré-entraîné
**Inference** : Faire une prédiction avec un modèle
**IoU** : Intersection over Union (métrique de chevauchement)
**mAP** : mean Average Precision (métrique de performance)
**Precision** : Proportion de vraies détections parmi toutes les détections
**Recall** : Proportion de détections parmi tous les vrais positifs
**Neon** : Service PostgreSQL cloud
**S3** : Service de stockage objet AWS
**Selenium** : Outil d'automatisation de navigateur
**Batch** : Cycle de scraping (toutes les 15 minutes)

---

**FIN DE LA DOCUMENTATION**

**Pour convertir en PDF :**
1. Ouvrir ce fichier avec Visual Studio Code
2. Installer l'extension "Markdown PDF"
3. Clic droit → "Markdown PDF: Export (pdf)"

**Ou utiliser Pandoc :**
```bash
pandoc DOCUMENTATION_CODE_DETAILLEE.md -o DOCUMENTATION_CODE_DETAILLEE.pdf --pdf-engine=xelatex
```

---

**Projet développé avec Claude Code**
**Contact :** axel.vilamot@gmail.com
**Date :** 2026-01-09
