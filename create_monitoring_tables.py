"""
Script pour créer les tables de monitoring dans Neon PostgreSQL
Exécuter une seule fois pour initialiser les tables
"""

import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

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

    # Table pour métriques agrégées quotidiennes
    cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_metrics (
            id SERIAL PRIMARY KEY,
            metric_date DATE UNIQUE NOT NULL,
            total_predictions INTEGER DEFAULT 0,
            fire_detections INTEGER DEFAULT 0,
            avg_confidence FLOAT,
            min_confidence FLOAT,
            max_confidence FLOAT,
            std_confidence FLOAT,
            avg_inference_time_ms FLOAT,
            unique_cameras INTEGER,
            alert_sent BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Table pour alertes de dégradation
    cur.execute("""
        CREATE TABLE IF NOT EXISTS model_alerts (
            id SERIAL PRIMARY KEY,
            alert_type VARCHAR(50) NOT NULL,
            alert_message TEXT,
            severity VARCHAR(20) DEFAULT 'warning',
            metric_value FLOAT,
            threshold_value FLOAT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved BOOLEAN DEFAULT FALSE,
            resolved_at TIMESTAMP
        );
    """)

    # Index pour performances
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_predictions_timestamp
        ON model_predictions(prediction_timestamp);
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_predictions_confidence
        ON model_predictions(confidence);
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_predictions_fire_detected
        ON model_predictions(fire_detected);
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_daily_metrics_date
        ON daily_metrics(metric_date);
    """)

    conn.commit()
    cur.close()
    conn.close()

    print("[OK] Tables de monitoring creees avec succes dans Neon PostgreSQL !")
    print("   - model_predictions : Log de chaque prediction")
    print("   - daily_metrics : Metriques agregees quotidiennes")
    print("   - model_alerts : Alertes de degradation")

if __name__ == "__main__":
    create_monitoring_tables()
