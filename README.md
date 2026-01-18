# Fire Detection System - Surveillance Automatisée d'Incendies Forestiers

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10-blue.svg)
![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-00FFFF.svg)
![Airflow](https://img.shields.io/badge/Airflow-2.8.0-017CEE.svg)
![MLflow](https://img.shields.io/badge/MLflow-2.10.0-0194E2.svg)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

**Système intelligent de détection précoce d'incendies forestiers par analyse d'images de caméras de surveillance en temps réel**

[Démo](#démonstration) • [Installation](#installation-rapide) • [Documentation](#documentation) • [Architecture](#architecture)

</div>

---

## Table des matières

- [À propos](#à-propos)
- [Fonctionnalités](#fonctionnalités)
- [Architecture](#architecture)
- [Technologies](#technologies)
- [Installation](#installation-rapide)
- [Configuration](#configuration)
- [Utilisation](#utilisation)
- [Performance](#performance-du-modèle)
- [Résultats](#résultats)
- [Roadmap](#roadmap)
- [Contribution](#contribution)
- [Auteur](#auteur)
- [License](#license)

---

## À propos

Ce projet implémente un **système automatisé de détection d'incendies forestiers** utilisant l'intelligence artificielle pour analyser en temps réel les flux de 165 caméras de surveillance du réseau [ALERTWildfire](https://www.alertwildfire.org/).

Le modèle YOLOv8 a été fine-tuné pour détecter uniquement la fumée dans les images de caméras, car elle représente le signal précoce d’un incendie, permettant d’alerter avant l’apparition des flammes.

### Le problème

Les incendies de forêt se propagent rapidement et causent des dégâts catastrophiques. Une détection précoce, même de quelques minutes, peut :
- Permettre une intervention plus rapide des pompiers
- Sauver des vies et des propriétés
- Limiter les dégâts écologiques
- Réduire les coûts de lutte contre les incendies

### La solution

Un pipeline MLOps complet qui :
1. **Scrape** automatiquement 165 caméras de surveillance (toutes les 15 min)
2. **Analyse** chaque image avec un modèle YOLOv8 fine-tuné (précision 77%)
3. **Alerte** instantanément par email en cas de détection de feu
4. **Stocke** toutes les données pour analyse historique (S3 + PostgreSQL)

---

## Fonctionnalités

### Scraping Automatisé
-  **165 caméras** du réseau ALERTWildfire (USA)
-  **Couverture géographique** : Californie, Nevada, Idaho, Oregon, Arizona
-  **Fréquence** : Cycle complet toutes les 15 minutes
-  **Stockage** : AWS S3 + PostgreSQL
-  **Résilience** : Gestion automatique des erreurs (caméras offline, timeouts)

### Intelligence Artificielle
-  **Modèle** : YOLOv8 Nano (optimisé vitesse/précision)
-  **Dataset** : 33,636 images (Pyro-SDIS)
-  **Fine-tuning** : 50 époques avec augmentation de données
-  Dégèle de la tête et du coup
-  **Performance** : 77.3% précision, 76.9% rappel, 83.3% mAP50
-  **Inférence** : ~30ms/image (CPU) ou ~3ms/image (GPU)

### Alertes en Temps Réel
-  **Email automatique** dès détection (confiance > 40%)
-  **Contenu riche** : nom caméra, confiance IA, timestamp
-  **Multi-destinataires** : support de listes de distribution
-  **Latence** : < 15 minutes entre feu et alerte

### Orchestration MLOps
-  **Airflow** : Orchestration des workflows
-  **MLflow** : Versioning et tracking des modèles
-  **Docker** : Environnement reproductible
-  **PostgreSQL** : Base de données robuste (Neon)
-  **S3** : Stockage scalable des images

---

## Architecture

### Vue d'ensemble

```

                  ALERTWildfire.org                          
              (165 caméras USA)                              

                        Selenium WebDriver
                       ↓
        
           Scraper (Airflow DAG)      
           - Toutes les 15 minutes    
           - Batch: 165 caméras       
        
                       
         
         ↓                            ↓
              
       AWS S3               PostgreSQL (Neon)
       Images                 Métadonnées    
     (~1MB/img)               + Prédictions  
              
                                     
         
                        YOLOv8 Inference
                       ↓
        
           FireDetector (YOLOv8)      
           - Résolution: 960×960      
           - Confiance > 40%          
        
                       
            
            ↓                     ↓
          
      Update DB          Email Alert  
     fire_detected       Gmail SMTP   
          
```

### Pipeline Airflow

```python
scrape_cameras (8-10 min)
     Scrape 165 caméras
     Upload S3
     Insert PostgreSQL (status: NEW)
           ↓
analyze_images (2-3 min)
     Download S3
     YOLOv8 inference
     Update DB (fire_detected, confidence, bbox)
     Send email if confidence > 0.4
```

**Fréquence** : Toutes les 15 minutes (96 cycles/jour)
**Couverture** : ~15,840 images analysées quotidiennement

---

## Technologies

### Backend & Orchestration
- **Python 3.10** - Langage principal
- **Apache Airflow 2.8.0** - Orchestration des workflows
- **MLflow 2.10.0** - Tracking et versioning des modèles
- **PostgreSQL (Neon)** - Base de données cloud
- **Docker & Docker Compose** - Containerisation

### Machine Learning
- **Ultralytics YOLOv8** - Modèle de détection d'objets
- **PyTorch 2.5.1** - Framework deep learning
- **OpenCV** - Traitement d'images
- **Torchvision** - Augmentation de données

### Scraping & Storage
- **Selenium + WebDriver** - Web scraping automatisé
- **Boto3** - SDK AWS pour S3
- **psycopg2** - Connecteur PostgreSQL

### Monitoring
- **MLflow UI** - Visualisation des expériences
- **Airflow UI** - Monitoring des DAGs

---

## Installation Rapide

### Prérequis

- **Docker Desktop** installé et démarré
- **Git** pour cloner le repo
- **8GB RAM minimum** (recommandé: 16GB)
- **Comptes** : AWS (S3), Neon (PostgreSQL), Gmail (SMTP)

### Étape 1 : Cloner le projet

```bash
git clone https://github.com/votre-username/fire-detection-system.git
cd fire-detection-system
```

### Étape 2 : Configuration

Créez un fichier `.env` à la racine :

```bash
# AWS S3
AWS_ACCESS_KEY_ID=votre_access_key
AWS_SECRET_ACCESS_KEY=votre_secret_key
AWS_REGION=eu-west-3
S3_BUCKET_NAME=votre-bucket-name

# PostgreSQL (Neon)
DATABASE_URL=postgresql://user:password@host.neon.tech/dbname?sslmode=require

# Airflow SMTP (Gmail)
AIRFLOW__SMTP__SMTP_HOST=smtp.gmail.com
AIRFLOW__SMTP__SMTP_PORT=587
AIRFLOW__SMTP__SMTP_USER=votre.email@gmail.com
AIRFLOW__SMTP__SMTP_PASSWORD=votre_app_password
AIRFLOW__SMTP__SMTP_MAIL_FROM=votre.email@gmail.com
```

> ** Important** : Utilisez un [App Password Gmail](https://myaccount.google.com/apppasswords), pas votre mot de passe principal.

### Étape 3 : Créer la table PostgreSQL

Connectez-vous à votre console Neon et exécutez :

```sql
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

CREATE INDEX idx_images_status ON images(status);
CREATE INDEX idx_images_batch_id ON images(batch_id);
CREATE INDEX idx_images_captured_at ON images(captured_at);
```

### Étape 4 : Lancer le système

**Windows :**
```bash
LANCER_SYSTEME.bat
```

**Linux/Mac :**
```bash
docker-compose up -d
```

### Étape 5 : Activer le pipeline

1. Ouvrez **http://localhost:8080**
2. Login : `admin` / `admin123`
3. Activez le DAG `fire_detection_pipeline`
4. Cliquez sur  "Trigger DAG" pour un test immédiat

 **C'est tout ! Le système tourne maintenant en continu.**

---

## Configuration

### Personnalisation du pipeline

#### Changer l'email de destination

**Fichier :** `dags/fire_detection_workflow.py` (ligne 87)

```python
send_email(to=['votre.email@example.com'], subject=subject, html_content=html_content)
```

#### Modifier la fréquence

**Fichier :** `dags/fire_detection_workflow.py` (ligne 101)

```python
schedule_interval='*/15 * * * *',  # Toutes les 15 minutes

# Exemples :
# */10 * * * *  → Toutes les 10 minutes
# */30 * * * *  → Toutes les 30 minutes
# 0 * * * *     → Toutes les heures
```

#### Ajuster le seuil de confiance

**Fichier :** `dags/fire_detection_workflow.py` (ligne 73)

```python
if is_fire and conf > 0.4:  # 40% minimum (actuel)
if is_fire and conf > 0.5:  # 50% (plus strict)
if is_fire and conf > 0.3:  # 30% (plus sensible)
```

---

## Utilisation

### Interfaces web

| Service | URL | Credentials | Description |
|---------|-----|-------------|-------------|
| **Airflow** | http://localhost:8080 | admin / admin123 | Orchestration, logs, monitoring |
| **MLflow** | http://localhost:5000 | - | Tracking modèles, expériences |

### Scripts utiles

```bash
# Lancer le système
docker-compose up -d

# Voir les logs en temps réel
docker logs -f airflow_standalone

# Tester le scraping manuellement (10 caméras)
docker exec airflow_standalone bash -c "cd /opt/airflow/dags && python scraper.py --cameras 10"

# Vérifier la progression
check_progress.bat  # Windows

# Arrêter le système
docker-compose down

# Redémarrer un service
docker-compose restart airflow
```

---

## Performance du Modèle

### Dataset

- **Source** : [Pyro-SDIS](https://huggingface.co/datasets/pyronear/pyro-sdis) (Pyronear)
- **Train** : 26,908 images
- **Validation** : 6,728 images
- **Total** : 33,636 images annotées
- **Classes** : 1 (fire)
- **Format** : YOLO (bounding boxes normalisées)

### Métriques

| Métrique | Valeur | Description |
|----------|--------|-------------|
| **Précision** | 77.3% | Taux de vrais positifs parmi les détections |
| **Rappel** | 76.9% | Taux de feux effectivement détectés |
| **mAP50** | 83.3% | Précision moyenne à IoU 0.5 |
| **mAP50-95** | 54.6% | Précision moyenne IoU 0.5-0.95 |
| **F1-Score** | 77.1% | Moyenne harmonique précision/rappel |

### Temps d'inférence

| Plateforme | Temps/image | Images/seconde |
|------------|-------------|----------------|
| CPU (Intel i7) | ~30ms | ~33 fps |
| GPU (RTX 3060) | ~3ms | ~333 fps |

### Architecture du modèle

```yaml
Modèle: YOLOv8n (Nano - optimisé vitesse)
Résolution: 960×960 pixels
Poids: 6.2 MB (last.pt)
Paramètres: 3.2M
FLOPS: 8.7G

Fine-tuning:
  - Epochs: 50
  - Batch size: 32
  - Learning rate: 0.001 (initial), 0.0001 (fine-tuning)
  - Optimizer: AdamW
  - Augmentation: HSV, Flip, Mosaic, Erasing
```

---

## Résultats

### Couverture quotidienne

- **Caméras surveillées** : 165
- **Cycles par jour** : 96 (toutes les 15 min)
- **Images analysées/jour** : ~15,840
- **Images analysées/mois** : ~475,200
- **Latence alerte** : < 15 minutes

### Coûts estimés

| Service | Coût mensuel (estimation) |
|---------|---------------------------|
| AWS S3 (500GB) | ~$11.50 |
| Neon PostgreSQL (Free tier) | $0 |
| Gmail SMTP | $0 |
| **Total** | **~$11.50/mois** |

### Impact potentiel

Avec une détection 15 minutes plus rapide :
-  Surface brûlée réduite de ~30-50%
-  Coûts de lutte réduits de ~40%
-  Risques pour populations réduits significativement

---

## Roadmap

### Version 1.0 (Actuelle)
- [x] Scraping automatisé 165 caméras
- [x] Modèle YOLOv8 fine-tuné
- [x] Alertes email temps réel
- [x] Stockage S3 + PostgreSQL
- [x] Pipeline Airflow opérationnel
- [x] Documentation complète

### Version 2.0 (En cours)
- [ ] Dashboard temps réel (Grafana)
- [ ] Notifications multi-canaux (SMS, Slack, Discord)
- [ ] API REST pour intégrations tierces
- [ ] Détection de fumée en plus des flammes
- [ ] Classification intensité du feu (faible/moyen/fort)

### Version 3.0 (Planifiée)
- [ ] Modèle YOLOv8m/l pour meilleure précision
- [ ] Prédiction de propagation du feu (ML)
- [ ] Intégration données météo
- [ ] Application mobile iOS/Android
- [ ] Système d'alertes géolocalisées

---

## Contribution

Les contributions sont les bienvenues ! Voici comment participer :

### Processus

1. **Fork** le projet
2. **Créez** une branche feature (`git checkout -b feature/AmazingFeature`)
3. **Committez** vos changements (`git commit -m 'Add AmazingFeature'`)
4. **Pushez** vers la branche (`git push origin feature/AmazingFeature`)
5. **Ouvrez** une Pull Request

### Guidelines

-  Code Python formaté avec `black`
-  Tests unitaires pour nouvelles features
-  Documentation mise à jour
-  Commits descriptifs (conventional commits)
-  Pas de credentials hardcodés

---

## ‍ Auteur

**Axel Vilamot**

-  Email: [axel.vilamot@gmail.com](mailto:axel.vilamot@gmail.com)
-  Formation: Jedha Bootcamp Data Science
-  Projet: Système de détection d'incendies forestiers

---

## License

Ce projet est sous licence **MIT** - voir le fichier LICENSE pour plus de détails.

---

## Remerciements

- **ALERTWildfire** - Réseau de caméras de surveillance
- **Pyronear** - Dataset Pyro-SDIS
- **Ultralytics** - Framework YOLOv8
- **Apache Airflow** - Orchestration
- **Jedha Bootcamp** - Formation Data Science

---

## Documentation Complémentaire

-  [Guide de démarrage complet](GUIDE_DEMARRAGE.md)
-  [Guide utilisateur simplifié](README_SIMPLE.md)
-  [Configuration finale détaillée](CONFIGURATION_FINALE.md)

---

## Avertissements

- Ce système est un **outil d'aide à la décision**, pas un remplacement des systèmes officiels de détection d'incendies
- Toujours **vérifier visuellement** les alertes avant intervention
- **Ne pas se fier uniquement** à ce système pour la sécurité
- Les performances peuvent varier selon conditions météo, qualité des caméras, etc.

---

## Support

Besoin d'aide ? Plusieurs options :

1.  Consultez la [documentation](#-documentation-complémentaire)
2.  Discussions et questions
3.  Email : [axel.vilamot@gmail.com](mailto:axel.vilamot@gmail.com)

---

<div align="center">

** Si ce projet vous a été utile, n'hésitez pas à lui donner une étoile ! **

Made by Axel Vilamot

</div>
