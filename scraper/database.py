import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import logging
import json

# On charge les variables d'environnement
load_dotenv()

# Récupération de l'URL Neon depuis le .env
DB_CONNECTION_STRING = os.getenv("DATABASE_URL")

class DatabaseManager:
    def __init__(self):
        # Connexion à la base de données
        try:
            self.conn = psycopg2.connect(DB_CONNECTION_STRING)
            self.conn.autocommit = True
        except Exception as e:
            logging.error(f"❌ Erreur critique connexion DB: {e}")
            raise e

    def insert_image(self, batch_id, camera_name, s3_path):
        """ Enregistre une nouvelle image (Status: NEW) """
        query = """
        INSERT INTO images (batch_id, camera_name, s3_path, status)
        VALUES (%s, %s, %s, 'NEW')
        RETURNING id;
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (batch_id, camera_name, s3_path))
                image_id = cur.fetchone()[0]
                return image_id
        except Exception as e:
            logging.error(f"Erreur insert_image: {e}")
            return None

    def get_pending_images(self, limit=10):
        """ Récupère les images en attente (Status: NEW) """
        query = """
        SELECT * FROM images 
        WHERE status = 'NEW' 
        ORDER BY captured_at ASC 
        LIMIT %s;
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (limit,))
                return cur.fetchall()
        except Exception as e:
            logging.error(f"Erreur get_pending_images: {e}")
            return []

    def update_prediction(self, image_id, fire_detected, confidence, bbox):
        """ Met à jour le résultat de l'IA (Status: PROCESSED) """
        query = """
        UPDATE images 
        SET status = 'PROCESSED', 
            fire_detected = %s, 
            confidence = %s, 
            bbox = %s
        WHERE id = %s;
        """
        try:
            # On convertit la boîte (liste) en JSON pour Postgres
            bbox_json = json.dumps(bbox)
            
            with self.conn.cursor() as cur:
                cur.execute(query, (fire_detected, confidence, bbox_json, image_id))
        except Exception as e:
            logging.error(f"Erreur update_prediction: {e}")

    def close(self):
        if self.conn:
            self.conn.close()