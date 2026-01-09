"""
Script pour creer les tables necessaires au systeme de reentrainement
Executer une seule fois pour initialiser les tables
"""

import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

def create_retraining_tables():
    """Cree les tables necessaires pour le reentrainement du modele"""

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Table pour les annotations manuelles (validation des predictions)
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

    # Table pour tracker les reentrainements
    cur.execute("""
        CREATE TABLE IF NOT EXISTS model_versions (
            id SERIAL PRIMARY KEY,
            version_name VARCHAR(100) UNIQUE NOT NULL,
            mlflow_run_id VARCHAR(100),
            mlflow_model_uri TEXT,
            base_model_version VARCHAR(100),
            training_started_at TIMESTAMP,
            training_completed_at TIMESTAMP,
            training_duration_minutes FLOAT,
            dataset_size INTEGER,
            train_split INTEGER,
            val_split INTEGER,
            epochs INTEGER,
            batch_size INTEGER,
            learning_rate FLOAT,
            precision FLOAT,
            recall FLOAT,
            map50 FLOAT,
            map50_95 FLOAT,
            status VARCHAR(50) DEFAULT 'training',
            deployed BOOLEAN DEFAULT FALSE,
            deployed_at TIMESTAMP,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Table pour comparer les performances avant/apres
    cur.execute("""
        CREATE TABLE IF NOT EXISTS model_comparisons (
            id SERIAL PRIMARY KEY,
            old_version VARCHAR(100),
            new_version VARCHAR(100),
            comparison_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            test_set_size INTEGER,
            old_precision FLOAT,
            new_precision FLOAT,
            old_recall FLOAT,
            new_recall FLOAT,
            old_map50 FLOAT,
            new_map50 FLOAT,
            improvement_percent FLOAT,
            decision VARCHAR(50),
            decision_reason TEXT
        );
    """)

    # Table pour les triggers de reentrainement
    cur.execute("""
        CREATE TABLE IF NOT EXISTS retrain_triggers (
            id SERIAL PRIMARY KEY,
            trigger_type VARCHAR(50) NOT NULL,
            trigger_reason TEXT,
            triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            triggered_by VARCHAR(100) DEFAULT 'system',
            annotated_images_count INTEGER,
            status VARCHAR(50) DEFAULT 'pending',
            model_version_created VARCHAR(100),
            completed_at TIMESTAMP
        );
    """)

    # Index pour performances
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_annotations_image_id
        ON annotations(image_id);
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_annotations_used_training
        ON annotations(used_for_training);
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_model_versions_status
        ON model_versions(status);
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_model_versions_deployed
        ON model_versions(deployed);
    """)

    conn.commit()
    cur.close()
    conn.close()

    print("[OK] Tables de reentrainement creees avec succes dans Neon PostgreSQL !")
    print("   - annotations : Validation manuelle des predictions")
    print("   - model_versions : Historique des versions du modele")
    print("   - model_comparisons : Comparaisons de performances")
    print("   - retrain_triggers : Declencheurs de reentrainement")

if __name__ == "__main__":
    create_retraining_tables()
