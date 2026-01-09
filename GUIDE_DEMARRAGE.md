# 🔥 Guide de démarrage - Système de détection d'incendies

## 🚀 Démarrage rapide

### 1. Lancer tous les services

```bash
cd "c:\Users\axelv\Documents\Jedha\Projet\Projet_Fire_dection\Fire_detection"
docker-compose up -d
```

**Attendez 30 secondes** pour que tout démarre.

---

### 2. Vérifier que tout est opérationnel

```bash
docker ps
```

Vous devez voir :
- ✅ **airflow_standalone** - Status: Up
- ✅ **mlflow_server** - Status: Up

---

### 3. Accéder à l'interface Airflow

**URL :** http://localhost:8080

**Identifiants :**
- **Username :** `admin`
- **Password :** `admin123`

---

### 4. Activer le pipeline de détection

1. Connectez-vous à http://localhost:8080
2. Trouvez le DAG nommé **`fire_detection_pipeline`**
3. Cliquez sur le bouton **ON/OFF** (toggle) pour l'activer
4. Le pipeline va maintenant s'exécuter **automatiquement toutes les 10 minutes**

---

## 📊 Que fait le système ?

### Workflow automatique (toutes les 10 minutes)

```
┌──────────────────────────┐
│  1. SCRAPING             │
│  - 5 caméras aléatoires  │
│  - Upload sur S3         │
│  - Enregistrement en BDD │
└────────────┬─────────────┘
             │
             ↓
┌──────────────────────────┐
│  2. ANALYSE IA           │
│  - Téléchargement S3     │
│  - YOLOv8 inference      │
│  - Mise à jour BDD       │
└────────────┬─────────────┘
             │
             ↓ (si feu > 40%)
┌──────────────────────────┐
│  3. ALERTE EMAIL 🚨      │
│  - Destination:          │
│    axel.vilamot@gmail.com│
└──────────────────────────┘
```

---

## 🔍 Surveiller le système

### Interface Airflow (http://localhost:8080)

- **DAGs** : Visualiser le pipeline
- **Graph View** : Voir les tâches (scraping → inférence)
- **Logs** : Déboguer en cas de problème
- **Code** : Voir le code du DAG

### Interface MLflow (http://localhost:5000)

- **Experiments** : Historique des runs
- **Models** : Versions du modèle YOLOv8
- **Artifacts** : Fichiers liés aux expériences

---

## 🛠️ Commandes utiles

### Voir les logs en temps réel

```bash
# Logs Airflow
docker logs -f airflow_standalone

# Logs MLflow
docker logs -f mlflow_server
```

### Arrêter le système

```bash
docker-compose down
```

### Redémarrer un service

```bash
# Redémarrer Airflow
docker-compose restart airflow

# Redémarrer MLflow
docker-compose restart mlflow
```

### Tester le scraping manuellement

```bash
docker exec airflow_standalone bash -c "cd /opt/airflow/dags && python scraper.py --cameras 3"
```

### Vérifier les images sur S3

```bash
docker exec airflow_standalone python -c "import boto3, os; s3 = boto3.client('s3'); bucket = os.getenv('S3_BUCKET_NAME'); result = s3.list_objects_v2(Bucket=bucket, Prefix='raw/', MaxKeys=20); [print(obj['Key']) for obj in result.get('Contents', [])]"
```

### Vérifier les images en base de données

```bash
docker exec airflow_standalone python -c "import psycopg2, os; conn = psycopg2.connect(os.getenv('DATABASE_URL')); cur = conn.cursor(); cur.execute('SELECT id, camera_name, status, fire_detected, confidence FROM images ORDER BY captured_at DESC LIMIT 10'); [print(f'ID:{r[0]} | {r[1]} | {r[2]} | Fire:{r[3]} | Conf:{r[4]}') for r in cur.fetchall()]; cur.close(); conn.close()"
```

---

## 📧 Configuration email

### Email de destination

Par défaut, les alertes sont envoyées à : **axel.vilamot@gmail.com**

Pour changer l'adresse, modifiez le fichier :
```
dags/fire_detection_workflow.py
```

Ligne 87 :
```python
send_email(to=['VOTRE_EMAIL@example.com'], subject=subject, html_content=html_content)
```

### Configuration SMTP (Gmail)

Les paramètres SMTP sont définis dans `.env` :
```
AIRFLOW__SMTP__SMTP_HOST=smtp.gmail.com
AIRFLOW__SMTP__SMTP_PORT=587
AIRFLOW__SMTP__SMTP_USER=axel.vilamot@gmail.com
AIRFLOW__SMTP__SMTP_PASSWORD=qsxvcjcgxgndgfse
```

⚠️ **Important** : Le mot de passe doit être un **"App Password"** Gmail (pas votre mot de passe principal).

Créer un App Password : https://myaccount.google.com/apppasswords

---

## 🐛 Résolution de problèmes

### Le DAG n'apparaît pas dans Airflow

```bash
# Vérifier les erreurs de syntaxe
docker exec airflow_standalone python -m py_compile /opt/airflow/dags/fire_detection_workflow.py

# Recharger les DAGs
docker-compose restart airflow
```

### Les emails ne sont pas reçus

1. Vérifiez les spams
2. Vérifiez que le App Password est correct dans `.env`
3. Testez l'envoi :
```bash
docker exec airflow_standalone bash -c "cat > /tmp/test_mail.py << 'EOF'
from airflow.utils.email import send_email
send_email(to=['axel.vilamot@gmail.com'], subject='Test', html_content='<p>Test</p>')
print('Email envoyé')
EOF
python /tmp/test_mail.py"
```

### MLflow ne démarre pas

```bash
# Voir les logs
docker logs mlflow_server --tail 50

# Si problème de BDD, recréer les tables
docker exec airflow_standalone python -c "import psycopg2, os; conn = psycopg2.connect(os.getenv('DATABASE_URL')); conn.autocommit = True; cur = conn.cursor(); tables = ['experiments', 'runs', 'metrics', 'params', 'tags', 'alembic_version']; [cur.execute(f'DROP TABLE IF EXISTS {t} CASCADE') for t in tables]; print('Tables supprimées'); cur.close(); conn.close()"

docker-compose restart mlflow
```

### Airflow ne démarre pas

```bash
# Réinitialiser la base de données
docker exec airflow_standalone airflow db reset --yes

# Recréer l'utilisateur
docker exec airflow_standalone airflow users create --username admin --password admin123 --firstname Axel --lastname Vilamot --role Admin --email axel.vilamot@gmail.com
```

---

## 📊 Architecture du système

```
┌─────────────────────────────────────────────┐
│           ALERTWildfire.org                 │
│         (165 caméras USA)                   │
└──────────────────┬──────────────────────────┘
                   │ Selenium WebDriver
                   ↓
        ┌──────────────────────┐
        │   Scraper (Airflow)  │
        │   - Toutes les 10min │
        │   - 5 caméras/batch  │
        └──────────┬───────────┘
                   │
         ┌─────────┴──────────┐
         ↓                    ↓
    ┌─────────┐        ┌──────────────┐
    │ AWS S3  │        │  Neon Postgres│
    │ Images  │        │  Métadonnées  │
    └─────────┘        └──────────────┘
         │                    │
         └─────────┬──────────┘
                   │ YOLOv8
                   ↓
        ┌──────────────────────┐
        │  FireDetector Model  │
        │  - Confiance > 40%   │
        └──────────┬───────────┘
                   │
            ┌──────┴──────┐
            ↓             ↓
    ┌──────────────┐  ┌─────────────┐
    │ Update DB    │  │ Email Alert │
    │ fire_detected│  │ Gmail SMTP  │
    └──────────────┘  └─────────────┘
```

---

## 🎯 Prochaines étapes

### Améliorer la couverture

Actuellement, le système scrape **5 caméras par cycle** (10 minutes).

Pour augmenter à **10 caméras** :
```python
# dags/fire_detection_workflow.py ligne 32
scraper.scrape_all(max_cameras=10)
```

### Changer la fréquence

Actuellement : **toutes les 10 minutes** (`*/10 * * * *`)

Pour changer à **toutes les 5 minutes** :
```python
# dags/fire_detection_workflow.py ligne 102
schedule_interval='*/5 * * * *',
```

### Ajuster le seuil de confiance

Actuellement : **40%** (ligne 73 du DAG)

Pour augmenter à **50%** :
```python
if is_fire and conf > 0.5:  # au lieu de 0.4
```

---

## 🔐 Sécurité

**⚠️ SÉCURITÉ** : Protection de vos credentials

1. Allez sur AWS IAM Console
2. Créez une nouvelle clé d'accès
3. Ajoutez-la à votre fichier `.env`
4. Ne commitez JAMAIS le fichier `.env`
5. Redémarrez : `docker-compose restart`

---

## 📞 Support

En cas de problème, vérifiez :
1. Les logs Airflow : `docker logs airflow_standalone`
2. Les logs MLflow : `docker logs mlflow_server`
3. La connexion S3 (credentials dans `.env`)
4. La connexion PostgreSQL Neon (URL dans `.env`)

---

**🚀 Système opérationnel ! Bon monitoring ! 🔥**
