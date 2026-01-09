"""
Script pour supprimer les tables de reentrainement si elles existent
"""

import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

def drop_retraining_tables():
    """Supprime les tables de reentrainement"""

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS retrain_triggers CASCADE;")
    cur.execute("DROP TABLE IF EXISTS model_comparisons CASCADE;")
    cur.execute("DROP TABLE IF EXISTS model_versions CASCADE;")
    cur.execute("DROP TABLE IF EXISTS annotations CASCADE;")

    conn.commit()
    cur.close()
    conn.close()

    print("[OK] Tables supprimees")

if __name__ == "__main__":
    drop_retraining_tables()
