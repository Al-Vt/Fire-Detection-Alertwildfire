-- Script pour nettoyer les tables MLflow dans Neon PostgreSQL
-- Exécutez ce script dans la console SQL de Neon

-- Supprimer toutes les tables MLflow
DROP TABLE IF EXISTS alembic_version CASCADE;
DROP TABLE IF EXISTS experiment_tags CASCADE;
DROP TABLE IF EXISTS experiments CASCADE;
DROP TABLE IF EXISTS input_tags CASCADE;
DROP TABLE IF EXISTS inputs CASCADE;
DROP TABLE IF EXISTS latest_metrics CASCADE;
DROP TABLE IF EXISTS metric_tags CASCADE;
DROP TABLE IF EXISTS metrics CASCADE;
DROP TABLE IF EXISTS model_version_tags CASCADE;
DROP TABLE IF EXISTS model_versions CASCADE;
DROP TABLE IF EXISTS param_tags CASCADE;
DROP TABLE IF EXISTS params CASCADE;
DROP TABLE IF EXISTS registered_model_aliases CASCADE;
DROP TABLE IF EXISTS registered_model_tags CASCADE;
DROP TABLE IF EXISTS registered_models CASCADE;
DROP TABLE IF EXISTS run_tags CASCADE;
DROP TABLE IF EXISTS runs CASCADE;
DROP TABLE IF EXISTS tags CASCADE;
DROP TABLE IF EXISTS trace_info CASCADE;
DROP TABLE IF EXISTS trace_request_metadata CASCADE;
DROP TABLE IF EXISTS trace_tags CASCADE;

-- Message de confirmation
SELECT 'Toutes les tables MLflow ont été supprimées. Redémarrez le conteneur mlflow_server.' AS status;
