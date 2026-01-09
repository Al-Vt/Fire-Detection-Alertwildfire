# Système Fire Detection - Vue d'Ensemble Complète

**Date :** 2026-01-09
**Version :** 2.0 (avec Monitoring + Réentraînement)

---

## Architecture Globale

```
┌─────────────────────────────────────────────────────────────────────┐
│                     AIRFLOW ORCHESTRATION                            │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  DAG: fire_detection_pipeline (Toutes les 15 minutes)         │ │
│  │  1. Scraping 165 caméras → S3 → PostgreSQL                    │ │
│  │  2. Inference YOLOv8 → Détection feux                         │ │
│  │  3. Email si feu détecté → axel.vilamot@gmail.com             │ │
│  │  4. Logging automatique → Neon (monitoring)                   │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  DAG: model_monitoring_daily (Tous les jours à 9h)            │ │
│  │  1. Calcul métriques quotidiennes                             │ │
│  │  2. Détection anomalies (confiance, temps inference)          │ │
│  │  3. Analyse tendances (7 jours)                               │ │
│  │  4. Email rapport → axel.vilamot@gmail.com                    │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  DAG: model_retraining (Déclenchement manuel)                 │ │
│  │  1. Vérification quota annotations (min 100)                  │ │
│  │  2. Préparation dataset (S3 → YOLO format)                    │ │
│  │  3. Fine-tuning YOLOv8 (30 epochs)                            │ │
│  │  4. Validation + Comparaison baseline                         │ │
│  │  5. Déploiement auto si amélioration ≥ 2%                     │ │
│  │  6. Email rapport réentraînement                              │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                         STOCKAGE                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │   AWS S3         │  │  Neon PostgreSQL │  │     MLflow       │  │
│  │  - Images        │  │  - Metadata      │  │  - Runs          │  │
│  │  - Screenshots   │  │  - Predictions   │  │  - Metrics       │  │
│  │                  │  │  - Monitoring    │  │  - Models        │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Composants du Système

### 1. Scraping (scraper/)
- **Fichier principal :** `scraper/scraper.py`
- **Sources :** 165 caméras ALERTWildfire.org
- **Technologie :** Selenium WebDriver (screenshots)
- **Fréquence :** Toutes les 15 minutes
- **Output :** Images → S3 + Métadonnées → Neon

### 2. Détection (model/)
- **Modèle :** YOLOv8s fine-tuné sur Pyro-SDIS (33,636 images)
- **Performances :** Precision 77.3%, Recall 76.9%, mAP50 77.1%
- **Fichier :** `model/inference.py`
- **Logging :** Automatique dans `model_predictions` (Neon)

### 3. Monitoring (monitoring/)
- **Fichier principal :** `monitoring/metrics.py`
- **Métriques :** Confiance moyenne, temps inference, détections
- **Alertes :** Confiance < 60%, Temps > 5s, Détections < 50/jour
- **Rapport :** Email quotidien à 9h avec tendances 7 jours

### 4. Réentraînement (retraining/)
- **Fichier principal :** `retraining/retrain_model.py`
- **Trigger :** Manuel OU (Alertes critiques + 100 annotations)
- **Process :** Dataset prep → Fine-tuning → Validation → Deploy
- **Sécurité :** Deploy UNIQUEMENT si amélioration ≥ 2%

### 5. Orchestration (dags/)
- **fire_detection_workflow.py :** Pipeline principal (15 min)
- **monitor_model.py :** Monitoring quotidien (9h)
- **retrain_workflow.py :** Réentraînement (manuel)

---

## Base de Données (Neon PostgreSQL)

### Tables Principales

**images**
- Métadonnées des images scrapées
- Lien vers S3 (s3_path)
- Status, fire_detected, confidence, bbox

**model_predictions** (Monitoring)
- Log de CHAQUE prédiction
- Confidence, inference_time_ms, bbox
- Utilisé pour calcul métriques quotidiennes

**daily_metrics** (Monitoring)
- Agrégation quotidienne
- avg_confidence, total_predictions, fire_detections
- Utilisé pour détection tendances

**model_alerts** (Monitoring)
- Alertes de dégradation
- Type, severity, threshold_value
- Resolved status

**annotations** (Réentraînement)
- Validation manuelle des prédictions
- Corrections (label, bbox)
- Used_for_training flag

**model_versions** (Réentraînement)
- Historique complet des versions
- Metrics (precision, recall, mAP50)
- Deployed status

**model_comparisons** (Réentraînement)
- Comparaisons entre versions
- Amélioration en pourcentage
- Décision deploy/rollback

---

## Workflow Typique

### Jour 1 : Lancement
1. Lancer système : `LANCER_SYSTEME.bat`
2. Vérifier Airflow : http://localhost:8080
3. Premier cycle après 15 minutes

### Jour 2-7 : Accumulation de données
- Scraping automatique toutes les 15 minutes
- ~165 images/cycle (succès ~60%)
- Logging automatique dans Neon
- Emails d'alerte si feu détecté

### Jour 8 : Premier rapport monitoring
- Email à 9h avec métriques de la semaine
- Tendances de performance
- Alertes si dégradation détectée

### Semaine 2-4 : Annotation (optionnel)
- Utiliser `retraining/annotation_tools.py`
- Valider/corriger les prédictions
- Objectif : 100+ annotations

### Mois 2+ : Réentraînement (si nécessaire)
- Déclencher manuellement dans Airflow
- Ou automatique si alertes critiques + 100 annotations
- Validation et déploiement automatique

---

## Configuration Actuelle

### Scraping
- **Caméras :** 165 (toutes scrapées par cycle)
- **Fréquence :** Toutes les 15 minutes
- **Taux de succès :** ~60% (caméras offline normales)

### Détection
- **Seuil confiance :** 0.4
- **Image size :** 960x960
- **Email alerte :** axel.vilamot@gmail.com

### Monitoring
- **Fréquence :** Quotidien à 9h
- **Seuils :**
  - Confiance min : 60%
  - Temps max : 5000ms
  - Prédictions min : 50/jour

### Réentraînement
- **Déclenchement :** Manuel (ou auto si critiques)
- **Dataset min :** 100 images annotées
- **Split :** 80% train / 20% val
- **Epochs :** 30 (fine-tuning)
- **Deploy :** Si amélioration ≥ 2%

---

## Scripts de Test

1. **TEST_PIPELINE.bat** : Menu interactif
2. **test_complete_pipeline.py** : Vérif infrastructure
3. **test_scraping_inference.py** : Test cycle complet
4. **test_monitoring.py** : Test monitoring system

Voir [GUIDE_TESTS.md](GUIDE_TESTS.md) pour détails.

---

## Scripts Utilitaires

### Lancement
- `LANCER_SYSTEME.bat` : Démarrer Docker + Airflow + MLflow
- `LANCER_TEST_COMPLET.bat` : Test manuel du DAG
- `check_progress.bat` : Vérifier progression

### Configuration
- `create_monitoring_tables.py` : Créer tables monitoring
- `create_retraining_tables.py` : Créer tables réentraînement
- `drop_retraining_tables.py` : Supprimer tables (reset)

### Annotation
- `retraining/annotation_tools.py` : Annoter prédictions
- `retraining/version_manager.py` : Gérer versions modèle

---

## Emails Automatiques

### 1. Alerte Incendie (temps réel)
**Trigger :** Feu détecté (confidence > 0.4)
**À :** axel.vilamot@gmail.com
**Contenu :**
- Nom caméra
- Confiance IA
- ID image
- Lien S3 (optionnel)

### 2. Rapport Monitoring Quotidien (9h)
**Trigger :** Tous les jours à 9h
**À :** axel.vilamot@gmail.com
**Contenu :**
- Métriques jour précédent
- Alertes détectées
- Tendances 7 jours
- Status système

### 3. Rapport Réentraînement
**Trigger :** Fin du réentraînement
**À :** axel.vilamot@gmail.com
**Contenu :**
- Nouvelles métriques modèle
- Comparaison baseline
- Décision deploy/rollback
- Amélioration en %

---

## Fichiers Critiques (NE PAS MODIFIER)

### Configuration
- `.env` : **CRITIQUE** - Tous les credentials
- `docker-compose.yml` : Configuration containers
- `model/weights/best.pt` : Modèle YOLOv8 production

### Code Principal
- `dags/fire_detection_workflow.py` : Pipeline principal
- `model/inference.py` : Détection + logging
- `scraper/scraper.py` : Scraping caméras
- `monitoring/metrics.py` : Calcul métriques
- `retraining/retrain_model.py` : Réentraînement

---

## Prochaines Améliorations Possibles

1. **Dashboard temps réel** (Grafana + Prometheus)
2. **API REST** pour déclenchement manuel
3. **Interface web** pour annotation
4. **Alertes SMS** (Twilio)
5. **Détection multi-classes** (fumée, flammes, véhicules)
6. **Géolocalisation** des caméras sur carte
7. **Historique vidéo** (timelapse avant/après détection)

---

## Maintenance

### Quotidienne
- Vérifier email monitoring (9h)
- Vérifier alertes incendie

### Hebdomadaire
- Vérifier espace S3 (quota)
- Vérifier logs Airflow
- Annoter quelques prédictions

### Mensuelle
- Analyser métriques de performance
- Décider si réentraînement nécessaire
- Nettoyer anciennes images S3 (optionnel)

---

## Support et Logs

### Logs Airflow
```bash
docker logs airflow_standalone
docker exec airflow_standalone airflow tasks logs <dag> <task> <date>
```

### Logs MLflow
```bash
docker logs mlflow_server
```

### Base de données
```python
import psycopg2
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
# Requêtes SQL...
```

---

## Sécurité

### Credentials (dans .env)
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY
- DATABASE_URL (Neon)
- SMTP_PASSWORD

### Fichiers protégés (.gitignore)
- `.env`
- `logs/`
- `mlruns/`
- `*.pt` (modèles)
- Fichiers temporaires

---

## Performance Attendue

### Scraping
- **Input :** 165 caméras
- **Success rate :** ~60% (98 images)
- **Durée :** 3-5 minutes
- **Stockage :** ~2-3 MB/image

### Inference
- **Vitesse :** ~200-500ms/image
- **Précision :** 77.3%
- **Rappel :** 76.9%
- **Faux positifs :** ~5-10%

### Monitoring
- **Overhead :** <1% (logging minimal)
- **Rapport :** <5s génération
- **Email :** <2s envoi

---

**Système développé avec Claude Code**
**Contact :** axel.vilamot@gmail.com
**Repository :** https://github.com/AxelVlmt/fire-detection

---

## Commandes de Démarrage Rapide

```bash
# Lancer le système
LANCER_SYSTEME.bat

# Tester le pipeline
TEST_PIPELINE.bat

# Vérifier progression
check_progress.bat

# Accéder aux interfaces
# Airflow: http://localhost:8080 (admin/admin123)
# MLflow: http://localhost:5001
```

**Le système est maintenant prêt à détecter les incendies 24/7 !**
