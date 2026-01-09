#!/usr/bin/env python3
"""
Script pour réinitialiser les tables MLflow dans Neon PostgreSQL
"""
import psycopg2
import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

print("🔄 Connexion à Neon PostgreSQL...")
conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
cursor = conn.cursor()

print("🗑️  Suppression des tables MLflow existantes...")

tables_to_drop = [
    "alembic_version",
    "experiment_tags",
    "experiments",
    "input_tags",
    "inputs",
    "latest_metrics",
    "metric_tags",
    "metrics",
    "model_version_tags",
    "model_versions",
    "param_tags",
    "params",
    "registered_model_aliases",
    "registered_model_tags",
    "registered_models",
    "run_tags",
    "runs",
    "tags",
    "trace_info",
    "trace_request_metadata",
    "trace_tags"
]

for table in tables_to_drop:
    try:
        cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
        print(f"  ✅ Supprimé: {table}")
    except Exception as e:
        print(f"  ⚠️  {table}: {e}")

print("\n✅ Nettoyage terminé ! MLflow va recréer les tables au prochain démarrage.")
print("   Exécutez: docker-compose restart mlflow")

cursor.close()
conn.close()
