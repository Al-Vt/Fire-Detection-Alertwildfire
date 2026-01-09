# Diagrammes Mermaid - Fire Detection System

**Pour visualiser ces diagrammes :**
1. Copier le code
2. Aller sur https://mermaid.live/
3. Coller le code dans l'éditeur
4. Le diagramme s'affiche automatiquement
5. Exporter en PNG/SVG

---

## 1. Architecture Globale du Système

```mermaid
graph TB
    subgraph "Sources de Données"
        CAM[165 Caméras ALERTWildfire]
    end

    subgraph "Scraping & Stockage"
        SCRAPER[Scraper Selenium]
        S3[(AWS S3<br/>Images)]
        NEON[(Neon PostgreSQL<br/>Métadonnées)]
    end

    subgraph "Détection IA"
        YOLO[YOLOv8 Fine-tuné<br/>Precision: 77.3%<br/>Recall: 76.9%]
        INFERENCE[Inference Engine]
    end

    subgraph "Monitoring"
        LOG[Logger Automatique]
        METRICS[Calcul Métriques]
        ALERTS[Détection Anomalies]
    end

    subgraph "Réentraînement"
        ANNOT[Annotations Manuelles]
        RETRAIN[Fine-tuning YOLOv8]
        VALID[Validation & Comparaison]
        DEPLOY[Déploiement Auto]
    end

    subgraph "Orchestration"
        AIRFLOW[Apache Airflow]
        MLFLOW[MLflow Tracking]
    end

    subgraph "Notifications"
        EMAIL[Email Alertes<br/>axel.vilamot@gmail.com]
    end

    CAM -->|Screenshots| SCRAPER
    SCRAPER -->|Upload| S3
    SCRAPER -->|Métadonnées| NEON
    S3 -->|Images| INFERENCE
    NEON -->|Images en attente| INFERENCE
    INFERENCE -->|Prédiction| YOLO
    YOLO -->|Résultats| LOG
    LOG -->|Logging| NEON
    LOG -->|Si feu détecté| EMAIL
    NEON -->|Données quotidiennes| METRICS
    METRICS -->|Analyse| ALERTS
    ALERTS -->|Si dégradation| EMAIL
    ALERTS -->|Si critique| RETRAIN
    NEON -->|Images annotées| ANNOT
    ANNOT -->|Dataset| RETRAIN
    RETRAIN -->|Nouveau modèle| VALID
    VALID -->|Si amélioration >= 2%| DEPLOY
    DEPLOY -->|Nouvelle version| YOLO
    AIRFLOW -.Orchestre.-> SCRAPER
    AIRFLOW -.Orchestre.-> INFERENCE
    AIRFLOW -.Orchestre.-> METRICS
    AIRFLOW -.Orchestre.-> RETRAIN
    MLFLOW -.Track.-> RETRAIN

    style CAM fill:#e1f5ff
    style YOLO fill:#fff4e1
    style NEON fill:#e8f5e9
    style S3 fill:#e8f5e9
    style EMAIL fill:#ffebee
    style AIRFLOW fill:#f3e5f5
```

---

## 2. DAG: fire_detection_pipeline (Toutes les 15 minutes)

```mermaid
graph LR
    START([Démarrage<br/>Toutes les 15 min]) --> SCRAPE[Scrape 165 Caméras]
    SCRAPE --> S3_UPLOAD[Upload S3 +<br/>Insert PostgreSQL]
    S3_UPLOAD --> GET_PENDING[Récupérer Images<br/>status = NEW]
    GET_PENDING --> CHECK_EMPTY{Images<br/>en attente ?}
    CHECK_EMPTY -->|Non| END1([Fin])
    CHECK_EMPTY -->|Oui| LOOP_START[Pour chaque image]
    LOOP_START --> DOWNLOAD[Télécharger depuis S3]
    DOWNLOAD --> INFERENCE[Inférence YOLOv8<br/>conf >= 0.4]
    INFERENCE --> LOG[Logger dans<br/>model_predictions]
    LOG --> CHECK_FIRE{Feu<br/>détecté ?}
    CHECK_FIRE -->|Non| UPDATE_DB[Update images<br/>status = ANALYZED]
    CHECK_FIRE -->|Oui| SEND_EMAIL[📧 Envoyer Email<br/>Alerte Incendie]
    SEND_EMAIL --> UPDATE_DB
    UPDATE_DB --> CHECK_MORE{Plus<br/>d'images ?}
    CHECK_MORE -->|Oui| LOOP_START
    CHECK_MORE -->|Non| END2([Fin])

    style SCRAPE fill:#e1f5ff
    style INFERENCE fill:#fff4e1
    style SEND_EMAIL fill:#ffebee
    style LOG fill:#e8f5e9
```

---

## 3. DAG: model_monitoring_daily (Tous les jours à 9h)

```mermaid
graph TD
    START([Démarrage<br/>9h00 quotidien]) --> CALC[Calculer Métriques<br/>Jour Précédent]
    CALC --> QUERY[Requête SQL Agrégée<br/>model_predictions]
    QUERY --> SAVE[Sauvegarder dans<br/>daily_metrics]
    SAVE --> DETECT[Détecter Anomalies]
    DETECT --> CHECK_CONF{Confiance<br/>< 60% ?}
    CHECK_CONF -->|Oui| ALERT_CRIT[⚠️ Alerte CRITIQUE]
    CHECK_CONF -->|Non| CHECK_PRED{Prédictions<br/>< 50/jour ?}
    CHECK_PRED -->|Oui| ALERT_WARN[⚠️ Alerte WARNING]
    CHECK_PRED -->|Non| CHECK_TIME{Temps inference<br/>> 5s ?}
    CHECK_TIME -->|Oui| ALERT_WARN
    CHECK_TIME -->|Non| NO_ALERT[✅ Aucune Alerte]
    ALERT_CRIT --> SAVE_ALERT[Sauvegarder dans<br/>model_alerts]
    ALERT_WARN --> SAVE_ALERT
    NO_ALERT --> TRENDS[Analyser Tendances<br/>7 derniers jours]
    SAVE_ALERT --> TRENDS
    TRENDS --> REPORT[Générer Rapport HTML]
    REPORT --> EMAIL[📧 Envoyer Email<br/>Rapport Quotidien]
    EMAIL --> END([Fin])

    style ALERT_CRIT fill:#ffebee
    style ALERT_WARN fill:#fff9c4
    style NO_ALERT fill:#e8f5e9
    style EMAIL fill:#e1f5ff
```

---

## 4. DAG: model_retraining (Déclenchement manuel)

```mermaid
graph TB
    START([Démarrage<br/>Manuel ou Auto]) --> CHECK{Conditions<br/>remplies ?}
    CHECK -->|Alertes critiques<br/>+ 100 annotations| YES1[Continuer]
    CHECK -->|500+ annotations| YES1
    CHECK -->|Non| SKIP[Skip Réentraînement]
    SKIP --> END1([Fin])

    YES1 --> TRIGGER[Créer Trigger<br/>retrain_triggers]
    TRIGGER --> DOWNLOAD[Télécharger Images<br/>depuis S3]
    DOWNLOAD --> PREPARE[Préparer Dataset<br/>Train 80% / Val 20%]
    PREPARE --> LABELS[Créer Labels YOLO<br/>fichiers .txt]
    LABELS --> YAML[Générer data.yaml]
    YAML --> MLFLOW_START[🚀 Démarrer MLflow Run]
    MLFLOW_START --> TRAIN[Fine-tuning YOLOv8<br/>30 epochs]
    TRAIN --> VALIDATE[Validation sur Val Set<br/>Calculer Metrics]
    VALIDATE --> COMPARE[Comparer avec Baseline]
    COMPARE --> CHECK_IMPROVE{Amélioration<br/>>= 2% ?}
    CHECK_IMPROVE -->|Oui| BACKUP[Backup Ancien Modèle]
    CHECK_IMPROVE -->|Non| ROLLBACK[❌ Rollback<br/>Pas de déploiement]
    BACKUP --> DEPLOY[✅ Déployer Nouveau Modèle<br/>model/weights/best.pt]
    DEPLOY --> MARK[Marquer deployed=TRUE<br/>model_versions]
    MARK --> FLAG[Marquer Annotations<br/>used_for_training=TRUE]
    ROLLBACK --> CLEANUP[Nettoyer Fichiers<br/>Temporaires]
    FLAG --> CLEANUP
    CLEANUP --> REPORT[📊 Générer Rapport<br/>Résultats]
    REPORT --> EMAIL[📧 Envoyer Email<br/>Rapport Réentraînement]
    EMAIL --> END2([Fin])

    style CHECK_IMPROVE fill:#fff4e1
    style DEPLOY fill:#e8f5e9
    style ROLLBACK fill:#ffebee
    style TRAIN fill:#e1f5ff
```

---

## 5. Flux de Données - Scraping vers Inference

```mermaid
sequenceDiagram
    participant C as Caméras
    participant S as Scraper
    participant S3 as AWS S3
    participant DB as PostgreSQL
    participant I as Inference
    participant Y as YOLOv8
    participant E as Email

    Note over C,S: Toutes les 15 minutes
    C->>S: Screenshots (165 caméras)
    S->>S: Traitement Selenium
    S->>S3: Upload PNG
    S3-->>S: OK (s3_path)
    S->>DB: INSERT images<br/>(batch_id, camera_name, s3_path)
    DB-->>S: image_id

    Note over DB,I: Dès que scraping terminé
    I->>DB: SELECT * FROM images<br/>WHERE status='NEW'
    DB-->>I: Liste images
    loop Pour chaque image
        I->>S3: download_file(s3_path)
        S3-->>I: Image PNG
        I->>Y: predict(image)
        Y-->>I: detections + confidence
        I->>DB: INSERT model_predictions<br/>(logging monitoring)
        I->>DB: UPDATE images<br/>SET fire_detected, confidence
        alt Feu détecté
            I->>E: send_email(alerte)
            E-->>I: Email envoyé
        end
    end
```

---

## 6. Flux de Monitoring Quotidien

```mermaid
sequenceDiagram
    participant A as Airflow (9h)
    participant M as ModelMonitor
    participant DB as PostgreSQL
    participant E as Email

    Note over A,M: Tous les jours à 9h00
    A->>M: calculate_daily_metrics()
    M->>DB: SELECT agrégé<br/>FROM model_predictions<br/>WHERE date=YESTERDAY
    DB-->>M: Données brutes
    M->>M: Calculer stats<br/>(avg_conf, total_pred, etc.)
    M->>DB: INSERT daily_metrics

    M->>M: detect_anomalies()
    alt Confiance < 60%
        M->>DB: INSERT model_alerts<br/>(severity=CRITICAL)
        Note over M: Peut déclencher réentraînement
    else Prédictions < 50
        M->>DB: INSERT model_alerts<br/>(severity=WARNING)
    end

    M->>DB: SELECT daily_metrics<br/>7 derniers jours
    DB-->>M: Historique
    M->>M: get_trend_analysis()
    M->>M: generate_report(HTML)
    M->>E: send_email(rapport)
    E-->>A: Email envoyé
```

---

## 7. Flux de Réentraînement

```mermaid
sequenceDiagram
    participant A as Airflow
    participant R as ModelRetrainer
    participant DB as PostgreSQL
    participant S3 as AWS S3
    participant Y as YOLOv8
    participant ML as MLflow

    A->>R: check_if_retraining_needed()
    R->>DB: SELECT COUNT(*) FROM model_alerts<br/>WHERE severity='critical'
    DB-->>R: critical_count
    R->>DB: SELECT COUNT(*) FROM annotations<br/>WHERE used_for_training=FALSE
    DB-->>R: annotated_count

    alt Conditions OK (100+ annotations)
        R->>DB: INSERT retrain_triggers
        R->>DB: SELECT annotations + images
        DB-->>R: Dataset (images + labels)

        loop Pour chaque annotation
            R->>S3: download_file(s3_path)
            S3-->>R: Image
            R->>R: Créer fichier .txt (YOLO format)
        end

        R->>R: Générer data.yaml
        R->>ML: start_run()
        ML-->>R: run_id
        R->>Y: model.train(data.yaml, epochs=30)
        Y-->>R: Nouveau modèle + metrics
        R->>ML: log_params() + log_metrics()
        R->>DB: INSERT model_versions

        R->>DB: SELECT baseline FROM model_versions<br/>WHERE deployed=TRUE
        DB-->>R: baseline_metrics
        R->>R: compare(new_metrics, baseline_metrics)

        alt Amélioration >= 2%
            R->>R: Backup ancien modèle
            R->>R: Copier nouveau modèle vers production
            R->>DB: UPDATE model_versions<br/>SET deployed=TRUE
            R->>DB: UPDATE annotations<br/>SET used_for_training=TRUE
            Note over R: ✅ Déploiement réussi
        else Amélioration < 2%
            Note over R: ❌ Rollback - Modèle non déployé
        end

        R->>A: send_report_email()
    else Conditions non remplies
        Note over R: Skip réentraînement
    end
```

---

## 8. Architecture des Tables PostgreSQL

```mermaid
erDiagram
    images ||--o{ model_predictions : "has many"
    images ||--o{ annotations : "has many"
    model_predictions ||--o| annotations : "can have one"

    images {
        int id PK
        varchar batch_id
        varchar camera_name
        text s3_path
        varchar status
        boolean fire_detected
        float confidence
        jsonb bbox
        timestamp captured_at
        timestamp created_at
    }

    model_predictions {
        int id PK
        int image_id FK
        varchar batch_id
        varchar camera_name
        boolean fire_detected
        float confidence
        jsonb bbox
        float inference_time_ms
        int image_size_bytes
        text s3_path
        timestamp prediction_timestamp
    }

    daily_metrics {
        int id PK
        date metric_date UK
        int total_predictions
        int fire_detections
        float avg_confidence
        float min_confidence
        float max_confidence
        float std_confidence
        float avg_inference_time_ms
        int unique_cameras
    }

    model_alerts {
        int id PK
        varchar alert_type
        text alert_message
        varchar severity
        float metric_value
        float threshold_value
        boolean resolved
        timestamp created_at
    }

    annotations {
        int id PK
        int image_id FK
        int prediction_id FK
        varchar annotation_type
        boolean is_correct
        varchar corrected_label
        jsonb corrected_bbox
        text notes
        boolean used_for_training
        timestamp annotated_at
    }

    model_versions {
        int id PK
        varchar version_name UK
        varchar mlflow_run_id
        float precision
        float recall
        float map50
        float map50_95
        boolean deployed
        timestamp deployed_at
        timestamp training_completed_at
    }

    model_comparisons {
        int id PK
        varchar old_version
        varchar new_version
        float old_precision
        float new_precision
        float old_recall
        float new_recall
        float old_map50
        float new_map50
        float improvement_percent
        varchar decision
    }

    retrain_triggers {
        int id PK
        varchar trigger_type
        text trigger_reason
        int annotated_images_count
        varchar status
        varchar model_version_created
        timestamp triggered_at
    }
```

---

## 9. Timeline d'Exécution Quotidienne

```mermaid
gantt
    title Exécution Quotidienne du Système Fire Detection
    dateFormat HH:mm
    axisFormat %H:%M

    section Scraping (24/7)
    Cycle 1 (165 cams)     :00:00, 15m
    Inference Cycle 1      :00:15, 5m
    Cycle 2 (165 cams)     :00:15, 15m
    Inference Cycle 2      :00:30, 5m
    Cycle 3 (165 cams)     :00:30, 15m
    Inference Cycle 3      :00:45, 5m
    Cycle 4 (165 cams)     :00:45, 15m
    ...                    :01:00, 1m

    section Monitoring
    Calcul Métriques J-1   :09:00, 5m
    Détection Anomalies    :09:05, 2m
    Envoi Email Rapport    :09:07, 1m

    section Réentraînement
    Check Conditions       :crit, 10:00, 5m
    Préparation Dataset    :10:05, 30m
    Fine-tuning (30 epochs):10:35, 120m
    Validation             :12:35, 10m
    Déploiement            :12:45, 5m
```

---

## 10. États et Transitions - Images

```mermaid
stateDiagram-v2
    [*] --> NEW : Image scrapée
    NEW --> ANALYZED : Inference complétée
    ANALYZED --> ANNOTATED : Annotation manuelle
    ANNOTATED --> USED_FOR_TRAINING : Réentraînement
    USED_FOR_TRAINING --> [*]

    state NEW {
        [*] --> EnAttente : Dans S3 + PostgreSQL
        EnAttente --> PrêtePourInference : status='NEW'
    }

    state ANALYZED {
        [*] --> AvecFeu : fire_detected=TRUE
        [*] --> SansFeu : fire_detected=FALSE
        AvecFeu --> AlerteEnvoyée : Email envoyé
        AvecFeu --> LoggéMonitoring : Dans model_predictions
        SansFeu --> LoggéMonitoring
    }

    state ANNOTATED {
        [*] --> Correcte : is_correct=TRUE
        [*] --> FauxPositif : is_correct=FALSE + corrected_label='no_fire'
        [*] --> BboxCorrigée : is_correct=FALSE + corrected_bbox
    }
```

---

## 11. Décisions - Réentraînement

```mermaid
flowchart TD
    START([Vérification Conditions]) --> CHECK_ALERTS{Alertes<br/>critiques ?}
    CHECK_ALERTS -->|Oui| CHECK_ANNOT{>= 100<br/>annotations ?}
    CHECK_ALERTS -->|Non| CHECK_QUOTA{>= 500<br/>annotations ?}

    CHECK_ANNOT -->|Oui| RETRAIN[🚀 Déclencher<br/>Réentraînement]
    CHECK_ANNOT -->|Non| WAIT1[⏳ Attendre Plus<br/>d'Annotations]

    CHECK_QUOTA -->|Oui| RETRAIN
    CHECK_QUOTA -->|Non| WAIT2[⏳ Conditions<br/>Non Remplies]

    RETRAIN --> TRAIN[Fine-tuning YOLOv8]
    TRAIN --> VALIDATE[Validation]
    VALIDATE --> COMPARE{Amélioration<br/>>= 2% ?}

    COMPARE -->|Oui| DEPLOY[✅ Déployer<br/>Nouveau Modèle]
    COMPARE -->|Non| ROLLBACK[❌ Rollback<br/>Garder Ancien]

    DEPLOY --> UPDATE[Marquer deployed=TRUE]
    ROLLBACK --> KEEP[Garder deployed actuel]

    UPDATE --> EMAIL_SUCCESS[📧 Email:<br/>Déploiement Réussi]
    KEEP --> EMAIL_ROLLBACK[📧 Email:<br/>Pas de Déploiement]

    WAIT1 --> END([Fin])
    WAIT2 --> END
    EMAIL_SUCCESS --> END
    EMAIL_ROLLBACK --> END

    style RETRAIN fill:#e1f5ff
    style DEPLOY fill:#e8f5e9
    style ROLLBACK fill:#ffebee
    style COMPARE fill:#fff4e1
```

---

## 12. Infrastructure Docker

```mermaid
graph TB
    subgraph "Docker Compose"
        subgraph "Container: airflow_standalone"
            AIRFLOW_WEB[Airflow Webserver<br/>Port 8080]
            AIRFLOW_SCHED[Airflow Scheduler]
            AIRFLOW_EXEC[Airflow Executor<br/>Sequential]
            VOL_DAGS[Volume: ./dags]
            VOL_SCRAPER[Volume: ./scraper]
            VOL_MODEL[Volume: ./model]
            VOL_MONITOR[Volume: ./monitoring]
            VOL_RETRAIN[Volume: ./retraining]
        end

        subgraph "Container: mlflow_server"
            MLFLOW_UI[MLflow UI<br/>Port 5001]
            MLFLOW_BACKEND[Backend Store<br/>PostgreSQL]
        end
    end

    subgraph "Services Externes"
        NEON[(Neon PostgreSQL<br/>Cloud)]
        S3[(AWS S3<br/>Bucket)]
        SMTP[Gmail SMTP<br/>Email]
        CAMERAS[165 Caméras<br/>ALERTWildfire]
    end

    AIRFLOW_WEB --> AIRFLOW_SCHED
    AIRFLOW_SCHED --> AIRFLOW_EXEC
    AIRFLOW_EXEC --> VOL_DAGS
    AIRFLOW_EXEC --> VOL_SCRAPER
    AIRFLOW_EXEC --> VOL_MODEL
    AIRFLOW_EXEC --> VOL_MONITOR
    AIRFLOW_EXEC --> VOL_RETRAIN

    MLFLOW_UI --> MLFLOW_BACKEND
    MLFLOW_BACKEND --> NEON

    AIRFLOW_EXEC -->|Scraping| CAMERAS
    AIRFLOW_EXEC -->|Upload| S3
    AIRFLOW_EXEC -->|Metadata| NEON
    AIRFLOW_EXEC -->|Email| SMTP

    style NEON fill:#e8f5e9
    style S3 fill:#e8f5e9
    style SMTP fill:#ffebee
    style CAMERAS fill:#e1f5ff
```

---

## Instructions d'Utilisation

### Pour visualiser sur Mermaid Live :

1. Copier un bloc de code (avec les ` ` `mermaid ... ` ` `)
2. Aller sur **https://mermaid.live/**
3. Coller le code dans l'éditeur de gauche
4. Le diagramme s'affiche automatiquement à droite
5. Cliquer sur "Actions" → "Export PNG" ou "Export SVG"

### Pour intégrer dans un README.md :

Les blocs sont déjà au bon format ! Copiez-collez directement dans votre README.md et GitHub/GitLab les afficheront automatiquement.

### Pour intégrer dans une présentation :

1. Exporter en PNG/SVG depuis Mermaid Live
2. Insérer les images dans PowerPoint/Google Slides

---

**12 diagrammes créés :**
1. Architecture globale
2. DAG fire_detection_pipeline
3. DAG model_monitoring_daily
4. DAG model_retraining
5. Flux scraping → inference (sequence)
6. Flux monitoring (sequence)
7. Flux réentraînement (sequence)
8. Architecture base de données (ERD)
9. Timeline quotidienne (Gantt)
10. États des images (state)
11. Décisions réentraînement (flowchart)
12. Infrastructure Docker

**Tous prêts à être visualisés sur https://mermaid.live/ !**
