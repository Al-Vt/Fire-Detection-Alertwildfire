# Guide des Tests - Fire Detection System

## Vue d'ensemble

Ce guide explique tous les tests disponibles pour vérifier que le système Fire Detection fonctionne correctement.

---

## Scripts de Test Disponibles

### 1. **TEST_PIPELINE.bat** (Recommandé)

**Interface interactive** pour lancer tous les tests.

**Comment utiliser :**
```bash
# Double-cliquer sur TEST_PIPELINE.bat
# Ou dans le terminal:
TEST_PIPELINE.bat
```

**Options :**
1. Test complet (vérification infrastructure)
2. Test cycle scraping + inference
3. Test monitoring system

---

### 2. **test_complete_pipeline.py**

**Test d'infrastructure complet** - Vérifie que tous les composants sont bien configurés.

**Ce qui est testé :**
- ✅ Connexion au bucket S3
- ✅ Connexion à la base Neon PostgreSQL
- ✅ Tables de monitoring (model_predictions, daily_metrics, model_alerts)
- ✅ Tables de réentraînement (annotations, model_versions, etc.)
- ✅ Présence des images dans S3
- ✅ Cohérence entre S3 et base de données
- ✅ Modèle YOLOv8 présent et valide

**Commande :**
```bash
python test_complete_pipeline.py
```

**Durée :** ~10 secondes

**Quand utiliser :** Avant de lancer le système pour la première fois, ou après une modification de configuration.

---

### 3. **test_scraping_inference.py**

**Test du cycle complet** - Scraping → S3 → Inference → Monitoring

**Ce qui est testé :**
- 📸 Scraping de 5 caméras
- ☁️ Upload des images sur S3
- 🧠 Inférence YOLOv8 sur les images
- 📊 Logging automatique dans Neon
- 🔥 Détection de feux

**Commande :**
```bash
python test_scraping_inference.py
```

**Durée :** 2-3 minutes

**Quand utiliser :** Pour tester que tout le pipeline fonctionne de bout en bout.

---

### 4. **test_monitoring.py**

**Test du système de monitoring** - Vérifie le calcul des métriques et la détection d'anomalies.

**Ce qui est testé :**
- 📊 Calcul des métriques quotidiennes
- 🚨 Détection d'anomalies
- 📈 Analyse des tendances
- 📧 Génération du rapport HTML

**Commande :**
```bash
python test_monitoring.py
```

**Durée :** ~5 secondes

**Quand utiliser :** Pour vérifier que le monitoring fonctionne (nécessite des prédictions existantes).

---

### 5. **test_email.py**

**Test d'envoi d'email** - Vérifie la configuration SMTP.

**Commande :**
```bash
python test_email.py
```

**Durée :** ~2 secondes

---

## Tests via Airflow

### Test manuel d'un DAG

Pour tester un DAG Airflow manuellement (sans attendre le schedule) :

```bash
# Test du DAG principal
docker exec airflow_standalone airflow dags test fire_detection_pipeline 2026-01-09

# Test du DAG de monitoring
docker exec airflow_standalone airflow dags test model_monitoring_daily 2026-01-09

# Test du DAG de réentraînement
docker exec airflow_standalone airflow dags test model_retraining 2026-01-09
```

---

## Séquence de Tests Recommandée

### Avant le premier lancement

1. **Test complet** : `python test_complete_pipeline.py`
   - Vérifie que tout est configuré

2. **Test email** : `python test_email.py`
   - Vérifie que les alertes peuvent être envoyées

3. **Test scraping + inference** : `python test_scraping_inference.py`
   - Vérifie que le cycle complet fonctionne

4. **Lancer le système** : `LANCER_SYSTEME.bat`
   - Le système est maintenant opérationnel

### Après quelques jours de fonctionnement

5. **Test monitoring** : `python test_monitoring.py`
   - Vérifie que les métriques sont bien calculées

---

## Vérifications Manuelles

### Vérifier les images dans S3

```bash
# Lister les images
aws s3 ls s3://fire-detection-bucket-axelvlmt/fire_detection/ --recursive

# Compter les images
aws s3 ls s3://fire-detection-bucket-axelvlmt/fire_detection/ --recursive | wc -l
```

### Vérifier la base de données

Via Python :
```python
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

# Total images
cur.execute("SELECT COUNT(*) FROM images")
print(f"Total images: {cur.fetchone()[0]}")

# Feux détectés
cur.execute("SELECT COUNT(*) FROM images WHERE fire_detected = TRUE")
print(f"Feux détectés: {cur.fetchone()[0]}")

# Prédictions loggées
cur.execute("SELECT COUNT(*) FROM model_predictions")
print(f"Prédictions loggées: {cur.fetchone()[0]}")

cur.close()
conn.close()
```

### Vérifier Airflow

1. Ouvrir http://localhost:8080
2. Identifiants : `admin` / `admin123`
3. Vérifier les DAGs :
   - `fire_detection_pipeline` : Actif, s'exécute toutes les 15 minutes
   - `model_monitoring_daily` : Actif, s'exécute tous les jours à 9h
   - `model_retraining` : Inactif (déclenchement manuel)

### Vérifier MLflow

1. Ouvrir http://localhost:5001
2. Vérifier les runs d'entraînement
3. Vérifier les modèles enregistrés

---

## Résolution de Problèmes

### Erreur : "Connexion à S3 échouée"

**Solution :**
- Vérifier les credentials dans `.env`
- Vérifier que le bucket existe : `aws s3 ls s3://fire-detection-bucket-axelvlmt/`

### Erreur : "Connexion à Neon échouée"

**Solution :**
- Vérifier `DATABASE_URL` dans `.env`
- Vérifier que la base est accessible depuis votre réseau

### Erreur : "Modèle YOLOv8 introuvable"

**Solution :**
- Le fichier doit être dans `model/weights/best.pt`
- Vérifier que le modèle a été téléchargé/copié

### Erreur : "Aucune image scrapée"

**Solutions possibles :**
- Caméras offline (normal, environ 60% de succès)
- Problème de driver Selenium (vérifier les logs)
- Timeout trop court (augmenter dans scraper.py)

---

## Logs et Débogage

### Logs Airflow

```bash
# Logs du container
docker logs airflow_standalone

# Logs d'une tâche spécifique
docker exec airflow_standalone airflow tasks logs fire_detection_pipeline scrape_cameras 2026-01-09
```

### Logs Python

Les scripts de test affichent des logs détaillés directement dans la console.

Pour plus de détails, modifier le niveau de logging :
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## Checklist de Validation

Avant de considérer le système comme opérationnel :

- [ ] Test complet réussi
- [ ] Test scraping + inference réussi (au moins 1 image analysée)
- [ ] Images présentes dans S3
- [ ] Images référencées dans la base Neon
- [ ] Prédictions loggées dans `model_predictions`
- [ ] Email de test reçu
- [ ] Airflow accessible (http://localhost:8080)
- [ ] DAG `fire_detection_pipeline` actif
- [ ] DAG `model_monitoring_daily` actif

---

## Support

Si un test échoue de manière inexpliquée :

1. Vérifier les logs détaillés
2. Vérifier `.env` (credentials)
3. Redémarrer les containers : `docker-compose restart`
4. Réexécuter `create_monitoring_tables.py` et `create_retraining_tables.py`

---

**Système testé et validé par Claude Code**
Date : 2026-01-09
