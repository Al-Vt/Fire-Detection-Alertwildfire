import os
import logging
import time
from ultralytics import YOLO
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Charger les variables d'environnement
load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

class FireDetector:
    def __init__(self, model_path='weights/best.pt'):
        self.model_path = model_path
        logging.info(f"Chargement du modèle depuis {self.model_path}...")
        
        try:
            # Chargement du modèle YOLO entraîné
            self.model = YOLO(self.model_path)
            logging.info("Modèle chargé avec succès.")
        except Exception as e:
            logging.error(f"Erreur lors du chargement du modèle : {e}")
            raise e

    def predict(self, image_path, conf_threshold=0.4, image_id=None, batch_id=None, camera_name=None, s3_path=None):
        """
        Détecte le feu dans une image donnée.
        Retourne une liste de détections ou une liste vide.
        Log automatiquement les prédictions dans Neon PostgreSQL pour monitoring.
        """
        logging.info(f"Analyse de l'image : {image_path}")

        # Mesurer le temps d'inférence
        start_time = time.time()

        # Inférence (imgsz=960 car c'est ce que tu as utilisé pour l'entraînement)
        results = self.model.predict(source=image_path, conf=conf_threshold, imgsz=960, save=False)

        inference_time_ms = (time.time() - start_time) * 1000

        detections = []
        fire_detected = False
        max_confidence = 0.0
        best_bbox = None

        for result in results:
            # result.boxes contient les boîtes de détection
            for box in result.boxes:
                # Récupération des infos
                cls_id = int(box.cls[0])
                confidence = float(box.conf[0])
                coords = box.xywhn[0].tolist() # Coordonnées normalisées (x, y, w, h)

                # On ne garde que la classe 'fire' (normalement 0 selon ton data.yaml)
                if cls_id == 0:
                    fire_detected = True
                    if confidence > max_confidence:
                        max_confidence = confidence
                        best_bbox = coords

                    detections.append({
                        "class": "fire",
                        "confidence": confidence,
                        "bbox": coords
                    })

        # Logger la prédiction dans la base de données pour monitoring
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

        if detections:
            logging.warning(f"FEU DETECTE ! ({len(detections)} foyers)")
        else:
            logging.info("Aucune anomalie detectee.")

        return detections

    def _log_prediction(self, image_id, batch_id, camera_name, s3_path, fire_detected, confidence, bbox, inference_time_ms, image_size_bytes):
        """Log la prédiction dans Neon PostgreSQL pour monitoring"""
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

# --- Test rapide si on lance le script directement ---
if __name__ == "__main__":
    # Pour tester, assure-toi d'avoir une image test.jpg dans le dossier
    detector = FireDetector()
    
    # Exemple fictif pour tester le chargement
    # detector.predict("test.jpg")
    # TEST : Si une image test.jpg existe, on essaie de la prédire
    test_image = "test.jpg"
    if os.path.exists(test_image):
        print(f"--- Lancement du test sur {test_image} ---")
        detector.predict(test_image)
    else:
        print(f"⚠️ Image {test_image} introuvable. Placez une image dans le dossier pour tester la prédiction.")