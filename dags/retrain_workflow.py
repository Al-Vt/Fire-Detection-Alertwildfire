"""
DAG Airflow pour le reentrainement automatique du modele
Peut etre declenche manuellement ou automatiquement via alertes
"""

from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.email import send_email
from datetime import datetime, timedelta
import sys
import os

# Ajouter le chemin du projet
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from retraining.retrain_model import ModelRetrainer

# Configuration
EMAIL_TO = ['axel.vilamot@gmail.com']

def check_retrain_needed(**context):
    """
    Verifie si un reentrainement est necessaire
    Retourne le nom de la prochaine tache (branch)
    """
    retrainer = ModelRetrainer()

    try:
        should_retrain, reason, count = retrainer.check_if_retraining_needed()

        context['ti'].xcom_push(key='should_retrain', value=should_retrain)
        context['ti'].xcom_push(key='reason', value=reason)
        context['ti'].xcom_push(key='annotated_count', value=count)

        print(f"Verification: should_retrain={should_retrain}, reason={reason}, count={count}")

        if should_retrain:
            # Creer le trigger
            trigger_id = retrainer.create_retrain_trigger('automatic', reason, count)
            context['ti'].xcom_push(key='trigger_id', value=trigger_id)
            return 'prepare_dataset_task'
        else:
            return 'skip_retrain_task'

    finally:
        retrainer.close()


def prepare_dataset_task(**context):
    """Prepare le dataset pour l'entrainement"""
    print("Preparation du dataset...")

    retrainer = ModelRetrainer()

    try:
        data_yaml_path, train_count, val_count = retrainer.prepare_dataset()

        context['ti'].xcom_push(key='data_yaml_path', value=str(data_yaml_path))
        context['ti'].xcom_push(key='train_count', value=train_count)
        context['ti'].xcom_push(key='val_count', value=val_count)

        print(f"Dataset prepare: {train_count} train, {val_count} val")

    except Exception as e:
        print(f"Erreur preparation dataset: {e}")
        retrainer.cleanup()
        raise e
    finally:
        retrainer.close()


def train_model_task(**context):
    """Entraine le nouveau modele"""
    print("Demarrage de l'entrainement...")

    data_yaml_path = context['ti'].xcom_pull(key='data_yaml_path', task_ids='prepare_dataset_task')
    train_count = context['ti'].xcom_pull(key='train_count', task_ids='prepare_dataset_task')
    val_count = context['ti'].xcom_pull(key='val_count', task_ids='prepare_dataset_task')

    retrainer = ModelRetrainer()

    try:
        # Entrainement avec parametres adaptes
        train_results = retrainer.train_model(
            data_yaml_path=data_yaml_path,
            epochs=30,  # Moins d'epochs pour le fine-tuning
            batch_size=16,
            img_size=960,
            learning_rate=0.001
        )

        # Sauvegarder la version
        dataset_info = {
            'total': train_count + val_count,
            'train': train_count,
            'val': val_count
        }

        version_id = retrainer.save_model_version(train_results, dataset_info)

        # Passer les infos aux taches suivantes
        context['ti'].xcom_push(key='version_name', value=train_results['version_name'])
        context['ti'].xcom_push(key='model_path', value=train_results['model_path'])
        context['ti'].xcom_push(key='precision', value=train_results['precision'])
        context['ti'].xcom_push(key='recall', value=train_results['recall'])
        context['ti'].xcom_push(key='map50', value=train_results['map50'])

        print(f"Entrainement termine: {train_results['version_name']}")
        print(f"Precision: {train_results['precision']:.3f}, Recall: {train_results['recall']:.3f}, mAP50: {train_results['map50']:.3f}")

    except Exception as e:
        print(f"Erreur entrainement: {e}")
        retrainer.cleanup()
        raise e
    finally:
        retrainer.close()


def validate_and_compare_task(**context):
    """
    Valide le nouveau modele et compare avec baseline
    Decide du deploiement
    """
    print("Validation et comparaison avec baseline...")

    version_name = context['ti'].xcom_pull(key='version_name', task_ids='train_model_task')

    retrainer = ModelRetrainer()

    try:
        should_deploy, improvement, comparison = retrainer.compare_with_baseline(version_name)

        context['ti'].xcom_push(key='should_deploy', value=should_deploy)
        context['ti'].xcom_push(key='improvement', value=improvement)
        context['ti'].xcom_push(key='comparison', value=comparison)

        print(f"Decision: {'DEPLOYER' if should_deploy else 'ROLLBACK'}")
        print(f"Amelioration: {improvement:.1f}%")

        return 'deploy_model_task' if should_deploy else 'skip_deploy_task'

    finally:
        retrainer.close()


def deploy_model_task(**context):
    """Deploie le nouveau modele en production"""
    print("Deploiement du modele...")

    version_name = context['ti'].xcom_pull(key='version_name', task_ids='train_model_task')
    model_path = context['ti'].xcom_pull(key='model_path', task_ids='train_model_task')

    retrainer = ModelRetrainer()

    try:
        retrainer.deploy_model(version_name, model_path)
        retrainer.mark_annotations_as_used()
        print(f"Modele {version_name} deploye avec succes!")

    finally:
        retrainer.close()


def cleanup_task(**context):
    """Nettoie les fichiers temporaires"""
    print("Nettoyage des fichiers temporaires...")

    retrainer = ModelRetrainer()
    retrainer.cleanup()
    retrainer.close()


def send_report_task(**context):
    """Envoie un rapport email avec les resultats"""
    print("Envoi du rapport...")

    should_retrain = context['ti'].xcom_pull(key='should_retrain', task_ids='check_retrain_needed')

    if not should_retrain:
        print("Pas de reentrainement, pas de rapport a envoyer")
        return

    version_name = context['ti'].xcom_pull(key='version_name', task_ids='train_model_task')
    precision = context['ti'].xcom_pull(key='precision', task_ids='train_model_task')
    recall = context['ti'].xcom_pull(key='recall', task_ids='train_model_task')
    map50 = context['ti'].xcom_pull(key='map50', task_ids='train_model_task')
    should_deploy = context['ti'].xcom_pull(key='should_deploy', task_ids='validate_and_compare')
    improvement = context['ti'].xcom_pull(key='improvement', task_ids='validate_and_compare')

    if should_deploy:
        subject = f"[SUCCESS] Nouveau modele deploye - {version_name}"
        status_color = "green"
        status_message = f"Le nouveau modele a ete deploye avec succes (amelioration: {improvement:.1f}%)"
    else:
        subject = f"[INFO] Reentrainement termine - Pas de deploiement"
        status_color = "orange"
        status_message = f"Le nouveau modele n'a pas ete deploye (amelioration insuffisante: {improvement:.1f}%)"

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif;">
        <h2 style="color: {status_color};">Rapport de Reentrainement - {version_name}</h2>

        <h3>Statut</h3>
        <p style="color: {status_color};"><b>{status_message}</b></p>

        <h3>Metriques du Nouveau Modele</h3>
        <table border="1" cellpadding="8" style="border-collapse: collapse;">
            <tr><td><b>Precision</b></td><td>{precision:.3f}</td></tr>
            <tr><td><b>Recall</b></td><td>{recall:.3f}</td></tr>
            <tr><td><b>mAP50</b></td><td>{map50:.3f}</td></tr>
            <tr><td><b>Amelioration</b></td><td>{improvement:.1f}%</td></tr>
        </table>

        <h3>Actions Requises</h3>
        <ul>
            {'<li>Le modele a ete deploye automatiquement</li>' if should_deploy else '<li>Le modele n\'a pas ete deploye (performances insuffisantes)</li>'}
            <li>Verifier les performances sur les prochaines predictions</li>
            <li>Continuer a annoter les predictions pour ameliorer le modele</li>
        </ul>

        <hr>
        <p style="color: gray; font-size: 12px;">
        Rapport genere automatiquement par le systeme de reentrainement Fire Detection.
        </p>
    </body>
    </html>
    """

    send_email(to=EMAIL_TO, subject=subject, html_content=html_content)
    print("Rapport envoye")


# Definition du DAG
default_args = {
    'owner': 'fire_detection',
    'depends_on_past': False,
    'email': EMAIL_TO,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'model_retraining',
    default_args=default_args,
    description='Reentrainement automatique du modele de detection de feu',
    schedule_interval=None,  # Declenchement manuel uniquement
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['retraining', 'model', 'fire_detection'],
) as dag:

    # Etape 1: Verifier si reentrainement necessaire
    check_retrain = BranchPythonOperator(
        task_id='check_retrain_needed',
        python_callable=check_retrain_needed,
        provide_context=True,
    )

    # Etape 2a: Preparer le dataset
    prepare_dataset = PythonOperator(
        task_id='prepare_dataset_task',
        python_callable=prepare_dataset_task,
        provide_context=True,
    )

    # Etape 2b: Skip si pas necessaire
    skip_retrain = EmptyOperator(
        task_id='skip_retrain_task',
    )

    # Etape 3: Entrainer le modele
    train_model = PythonOperator(
        task_id='train_model_task',
        python_callable=train_model_task,
        provide_context=True,
    )

    # Etape 4: Valider et comparer
    validate_and_compare = BranchPythonOperator(
        task_id='validate_and_compare',
        python_callable=validate_and_compare_task,
        provide_context=True,
    )

    # Etape 5a: Deployer
    deploy_model = PythonOperator(
        task_id='deploy_model_task',
        python_callable=deploy_model_task,
        provide_context=True,
    )

    # Etape 5b: Skip deploiement
    skip_deploy = EmptyOperator(
        task_id='skip_deploy_task',
    )

    # Etape 6: Nettoyer
    cleanup = PythonOperator(
        task_id='cleanup_task',
        python_callable=cleanup_task,
        provide_context=True,
        trigger_rule='all_done',
    )

    # Etape 7: Envoyer rapport
    send_report = PythonOperator(
        task_id='send_report',
        python_callable=send_report_task,
        provide_context=True,
        trigger_rule='all_done',
    )

    # Flux d'execution
    check_retrain >> [prepare_dataset, skip_retrain]
    prepare_dataset >> train_model >> validate_and_compare
    validate_and_compare >> [deploy_model, skip_deploy]
    [deploy_model, skip_deploy, skip_retrain] >> cleanup >> send_report
