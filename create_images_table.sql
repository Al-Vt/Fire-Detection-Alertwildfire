-- Script pour créer la table images dans Neon PostgreSQL
-- Exécutez ce script dans la console SQL de Neon ou via Python

CREATE TABLE IF NOT EXISTS images (
    id SERIAL PRIMARY KEY,
    batch_id VARCHAR(50) NOT NULL,
    camera_name VARCHAR(100) NOT NULL,
    s3_path TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'NEW',
    fire_detected BOOLEAN DEFAULT FALSE,
    confidence FLOAT DEFAULT NULL,
    bbox JSONB DEFAULT NULL,
    captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index pour optimiser les requêtes
CREATE INDEX IF NOT EXISTS idx_images_status ON images(status);
CREATE INDEX IF NOT EXISTS idx_images_batch_id ON images(batch_id);
CREATE INDEX IF NOT EXISTS idx_images_captured_at ON images(captured_at);

-- Confirmation
SELECT 'Table images créée avec succès!' AS status;
