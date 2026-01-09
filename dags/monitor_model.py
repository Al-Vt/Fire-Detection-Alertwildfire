"""
DAG Airflow pour le monitoring quotidien du modèle de détection de feu
Calcule les métriques, détecte les anomalies et envoie un rapport email
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.email import send_email
from datetime import datetime, timedelta
import sys
import os

# Ajouter le chemin du projet pour importer les modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monitoring.metrics import ModelMonitor

# Configuration email
EMAIL_TO = ['axel.vilamot@gmail.com']

def calculate_and_save_metrics(**context):
    """
    Calcule les métriques quotidiennes et les sauvegarde
    """
    monitor = ModelMonitor()

    try:
        # Calculer les métriques d'hier
        metrics = monitor.calculate_daily_metrics()

        if metrics is None:
            print("Aucune prediction hier, pas de metriques a calculer")
            context['ti'].xcom_push(key='metrics', value=None)
            return

        # Sauvegarder les métriques
        monitor.save_daily_metrics(metrics)

        # Passer les métriques au contexte pour la prochaine tâche
        context['ti'].xcom_push(key='metrics', value=metrics)

        print(f"Metriques calculees et sauvegardees: {metrics}")

    finally:
        monitor.close()


def detect_and_alert(**context):
    """
    Détecte les anomalies dans les métriques et crée des alertes
    """
    # Récupérer les métriques de la tâche précédente
    metrics = context['ti'].xcom_pull(key='metrics', task_ids='calculate_metrics')

    if metrics is None:
        print("Pas de metriques, pas d'analyse d'anomalies")
        context['ti'].xcom_push(key='alerts', value=[])
        return

    monitor = ModelMonitor()

    try:
        # Détecter les anomalies
        alerts = monitor.detect_anomalies(metrics)

        if alerts:
            print(f"ALERTE: {len(alerts)} anomalie(s) detectee(s)")
            for alert in alerts:
                print(f"  - {alert['message']}")

            # Sauvegarder les alertes
            monitor.save_alerts(alerts)
        else:
            print("Aucune anomalie detectee - Modele fonctionne normalement")

        # Passer les alertes au contexte
        context['ti'].xcom_push(key='alerts', value=alerts)

    finally:
        monitor.close()


def generate_and_send_report(**context):
    """
    Génère un rapport HTML et l'envoie par email
    """
    # Récupérer métriques et alertes
    metrics = context['ti'].xcom_pull(key='metrics', task_ids='calculate_metrics')
    alerts = context['ti'].xcom_pull(key='alerts', task_ids='detect_anomalies')

    if metrics is None:
        print("Pas de metriques, pas de rapport a envoyer")
        return

    monitor = ModelMonitor()

    try:
        # Analyse des tendances
        trends = monitor.get_trend_analysis(days=7)

        # Générer le rapport HTML
        html_report = monitor.generate_report(metrics, alerts, trends)

        # Préparer le sujet de l'email
        if alerts:
            critical_alerts = [a for a in alerts if a['severity'] == 'critical']
            if critical_alerts:
                subject = f"[CRITIQUE] Alerte Monitoring Modele - {metrics['metric_date']}"
            else:
                subject = f"[ATTENTION] Alerte Monitoring Modele - {metrics['metric_date']}"
        else:
            subject = f"[OK] Rapport Monitoring Modele - {metrics['metric_date']}"

        # Envoyer l'email
        send_email(
            to=EMAIL_TO,
            subject=subject,
            html_content=html_report
        )

        print(f"Rapport envoye a {EMAIL_TO}")

        # Marquer comme envoyé dans la base
        monitor.cur.execute("""
            UPDATE daily_metrics
            SET alert_sent = TRUE
            WHERE metric_date = %s
        """, (metrics['metric_date'],))
        monitor.conn.commit()

    finally:
        monitor.close()


# Définition du DAG
default_args = {
    'owner': 'fire_detection',
    'depends_on_past': False,
    'email': EMAIL_TO,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'model_monitoring_daily',
    default_args=default_args,
    description='Monitoring quotidien du modele de detection de feu',
    schedule_interval='0 9 * * *',  # Tous les jours à 9h00 du matin
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['monitoring', 'model', 'fire_detection'],
) as dag:

    # Tâche 1: Calculer les métriques quotidiennes
    calculate_metrics_task = PythonOperator(
        task_id='calculate_metrics',
        python_callable=calculate_and_save_metrics,
        provide_context=True,
    )

    # Tâche 2: Détecter les anomalies
    detect_anomalies_task = PythonOperator(
        task_id='detect_anomalies',
        python_callable=detect_and_alert,
        provide_context=True,
    )

    # Tâche 3: Générer et envoyer le rapport
    send_report_task = PythonOperator(
        task_id='send_report',
        python_callable=generate_and_send_report,
        provide_context=True,
    )

    # Définir l'ordre d'exécution
    calculate_metrics_task >> detect_anomalies_task >> send_report_task
