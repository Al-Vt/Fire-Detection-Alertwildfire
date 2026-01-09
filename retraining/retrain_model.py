"""
Module de reentrainement automatique du modele YOLOv8
Gere le telechargement des donnees, preparation du dataset, entrainement et validation
"""

import os
import shutil
import json
import boto3
import psycopg2
import mlflow
import yaml
from datetime import datetime
from ultralytics import YOLO
from pathlib import Path
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
MLFLOW_TRACKING_URI = os.getenv('MLFLOW_TRACKING_URI', 'http://localhost:5000')


class ModelRetrainer:
    def __init__(self, base_model_path='model/weights/best.pt'):
        self.base_model_path = base_model_path
        self.conn = psycopg2.connect(DATABASE_URL)
        self.cur = self.conn.cursor()
        self.s3 = boto3.client('s3')

        # Repertoires de travail
        self.work_dir = Path('retraining_workspace')
        self.dataset_dir = self.work_dir / 'dataset'
        self.images_dir = self.dataset_dir / 'images'
        self.labels_dir = self.dataset_dir / 'labels'
        self.train_dir = self.images_dir / 'train'
        self.val_dir = self.images_dir / 'val'
        self.train_labels_dir = self.labels_dir / 'train'
        self.val_labels_dir = self.labels_dir / 'val'

        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

    def close(self):
        """Ferme la connexion a la base de donnees"""
        self.cur.close()
        self.conn.close()

    def check_if_retraining_needed(self):
        """
        Verifie si un reentrainement est necessaire
        Retourne (should_retrain, reason, annotated_count)
        """
        # Verifier s'il y a des alertes critiques recentes
        self.cur.execute("""
            SELECT COUNT(*) FROM model_alerts
            WHERE severity = 'critical'
            AND created_at > NOW() - INTERVAL '7 days'
            AND resolved = FALSE
        """)
        critical_alerts = self.cur.fetchone()[0]

        # Compter les images annotees non utilisees pour entrainement
        self.cur.execute("""
            SELECT COUNT(*) FROM annotations
            WHERE used_for_training = FALSE
            AND is_correct IS NOT NULL
        """)
        annotated_count = self.cur.fetchone()[0]

        # Conditions de declenchement
        if critical_alerts > 0 and annotated_count >= 100:
            return True, f"{critical_alerts} alerte(s) critique(s) detectee(s)", annotated_count
        elif annotated_count >= 760320:
            return True, f"{annotated_count} nouvelles images annotees disponibles", annotated_count
        else:
            return False, f"Pas assez d'images annotees ({annotated_count}/100 minimum)", annotated_count

    def create_retrain_trigger(self, trigger_type, reason, annotated_count):
        """Cree un trigger de reentrainement dans la base"""
        self.cur.execute("""
            INSERT INTO retrain_triggers
            (trigger_type, trigger_reason, annotated_images_count, status)
            VALUES (%s, %s, %s, 'pending')
            RETURNING id
        """, (trigger_type, reason, annotated_count))
        self.conn.commit()
        trigger_id = self.cur.fetchone()[0]
        logging.info(f"Trigger de reentrainement cree: ID={trigger_id}")
        return trigger_id

    def prepare_dataset(self):
        """
        Prepare le dataset pour l'entrainement
        Telecharge images depuis S3 et cree les labels YOLO
        """
        logging.info("Preparation du dataset...")

        # Creer les repertoires
        for dir_path in [self.train_dir, self.val_dir, self.train_labels_dir, self.val_labels_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        # Recuperer toutes les annotations non utilisees
        self.cur.execute("""
            SELECT a.id, a.image_id, a.corrected_label, a.corrected_bbox,
                   a.is_correct, i.s3_path, i.camera_name,
                   mp.fire_detected, mp.confidence, mp.bbox
            FROM annotations a
            JOIN images i ON a.image_id = i.id
            LEFT JOIN model_predictions mp ON a.prediction_id = mp.id
            WHERE a.used_for_training = FALSE
            AND a.is_correct IS NOT NULL
            ORDER BY a.annotated_at
        """)

        annotations = self.cur.fetchall()
        total = len(annotations)

        if total < 100:
            raise Exception(f"Pas assez d'annotations ({total}/100 minimum)")

        logging.info(f"Preparation de {total} images annotees...")

        # Split train/val (80/20)
        split_idx = int(total * 0.8)

        for idx, annot in enumerate(annotations):
            annot_id, image_id, corrected_label, corrected_bbox, is_correct, s3_path, camera_name, fire_detected, confidence, bbox = annot

            # Determiner si train ou val
            is_train = idx < split_idx
            img_dir = self.train_dir if is_train else self.val_dir
            lbl_dir = self.train_labels_dir if is_train else self.val_labels_dir

            # Telecharger l'image depuis S3
            image_filename = f"img_{image_id}.jpg"
            local_image_path = img_dir / image_filename

            try:
                self.s3.download_file(S3_BUCKET_NAME, s3_path, str(local_image_path))
            except Exception as e:
                logging.error(f"Erreur telechargement image {image_id}: {e}")
                continue

            # Creer le fichier label YOLO
            label_filename = f"img_{image_id}.txt"
            local_label_path = lbl_dir / label_filename

            # Utiliser la bbox corrigee si disponible, sinon celle predite
            final_bbox = corrected_bbox if corrected_bbox else bbox

            # Ecrire le label au format YOLO
            if final_bbox and (is_correct or corrected_label == 'fire'):
                with open(local_label_path, 'w') as f:
                    # Format YOLO: class_id x_center y_center width height (normalized)
                    class_id = 0  # fire
                    if isinstance(final_bbox, dict):
                        x, y, w, h = final_bbox.get('x', 0), final_bbox.get('y', 0), final_bbox.get('w', 0), final_bbox.get('h', 0)
                    else:
                        x, y, w, h = final_bbox[0], final_bbox[1], final_bbox[2], final_bbox[3]
                    f.write(f"{class_id} {x} {y} {w} {h}\n")
            else:
                # Pas de feu ou faux positif -> fichier label vide
                local_label_path.touch()

        # Creer le fichier data.yaml
        data_yaml = {
            'path': str(self.dataset_dir.absolute()),
            'train': 'images/train',
            'val': 'images/val',
            'nc': 1,
            'names': ['fire']
        }

        data_yaml_path = self.dataset_dir / 'data.yaml'
        with open(data_yaml_path, 'w') as f:
            yaml.dump(data_yaml, f)

        logging.info(f"Dataset prepare: {split_idx} train, {total - split_idx} val")
        return data_yaml_path, split_idx, total - split_idx

    def train_model(self, data_yaml_path, epochs=50, batch_size=16, img_size=960, learning_rate=0.001):
        """
        Entraine le modele YOLOv8 avec fine-tuning
        """
        logging.info("Demarrage de l'entrainement...")

        version_name = f"fire_model_v{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Demarrer MLflow run
        with mlflow.start_run(run_name=version_name) as run:
            mlflow_run_id = run.info.run_id

            # Logger les hyperparametres
            mlflow.log_param("base_model", self.base_model_path)
            mlflow.log_param("epochs", epochs)
            mlflow.log_param("batch_size", batch_size)
            mlflow.log_param("img_size", img_size)
            mlflow.log_param("learning_rate", learning_rate)

            # Charger le modele de base
            model = YOLO(self.base_model_path)

            # Entrainer
            training_start = datetime.now()

            results = model.train(
                data=str(data_yaml_path),
                epochs=epochs,
                batch=batch_size,
                imgsz=img_size,
                lr0=learning_rate,
                project=str(self.work_dir / 'runs'),
                name=version_name,
                exist_ok=True,
                verbose=True
            )

            training_end = datetime.now()
            training_duration = (training_end - training_start).total_seconds() / 60

            # Valider le modele
            val_results = model.val()

            # Extraire les metriques
            precision = float(val_results.box.p.mean()) if hasattr(val_results.box, 'p') else 0.0
            recall = float(val_results.box.r.mean()) if hasattr(val_results.box, 'r') else 0.0
            map50 = float(val_results.box.map50) if hasattr(val_results.box, 'map50') else 0.0
            map50_95 = float(val_results.box.map) if hasattr(val_results.box, 'map') else 0.0

            # Logger les metriques dans MLflow
            mlflow.log_metric("precision", precision)
            mlflow.log_metric("recall", recall)
            mlflow.log_metric("map50", map50)
            mlflow.log_metric("map50_95", map50_95)

            # Sauvegarder le modele dans MLflow
            model_path = self.work_dir / 'runs' / version_name / 'weights' / 'best.pt'
            mlflow.log_artifact(str(model_path))

            logging.info(f"Entrainement termine - Precision: {precision:.3f}, Recall: {recall:.3f}, mAP50: {map50:.3f}")

            return {
                'version_name': version_name,
                'mlflow_run_id': mlflow_run_id,
                'model_path': str(model_path),
                'precision': precision,
                'recall': recall,
                'map50': map50,
                'map50_95': map50_95,
                'training_duration': training_duration,
                'training_start': training_start,
                'training_end': training_end
            }

    def save_model_version(self, train_results, dataset_info):
        """Sauvegarde la nouvelle version du modele dans la base"""
        self.cur.execute("""
            INSERT INTO model_versions
            (version_name, mlflow_run_id, base_model_version, training_started_at,
             training_completed_at, training_duration_minutes, dataset_size, train_split,
             val_split, precision, recall, map50, map50_95, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'completed')
            RETURNING id
        """, (
            train_results['version_name'],
            train_results['mlflow_run_id'],
            self.base_model_path,
            train_results['training_start'],
            train_results['training_end'],
            train_results['training_duration'],
            dataset_info['total'],
            dataset_info['train'],
            dataset_info['val'],
            train_results['precision'],
            train_results['recall'],
            train_results['map50'],
            train_results['map50_95']
        ))
        self.conn.commit()
        version_id = self.cur.fetchone()[0]
        logging.info(f"Version sauvegardee: {train_results['version_name']} (ID={version_id})")
        return version_id

    def compare_with_baseline(self, new_version_name):
        """
        Compare la nouvelle version avec la version actuellement deployee
        Retourne (should_deploy, improvement_percent, comparison_details)
        """
        # Recuperer la version actuellement deployee
        self.cur.execute("""
            SELECT version_name, precision, recall, map50
            FROM model_versions
            WHERE deployed = TRUE
            ORDER BY deployed_at DESC
            LIMIT 1
        """)

        baseline = self.cur.fetchone()

        if not baseline:
            logging.info("Pas de baseline deployee, deploiement automatique")
            return True, 100.0, "Premiere version"

        baseline_name, baseline_precision, baseline_recall, baseline_map50 = baseline

        # Recuperer les metriques de la nouvelle version
        self.cur.execute("""
            SELECT precision, recall, map50
            FROM model_versions
            WHERE version_name = %s
        """, (new_version_name,))

        new_metrics = self.cur.fetchone()
        new_precision, new_recall, new_map50 = new_metrics

        # Calculer l'amelioration
        improvement = ((new_map50 - baseline_map50) / baseline_map50 * 100) if baseline_map50 > 0 else 0

        # Decision: deployer si amelioration >= 2% ou si precision/recall s'ameliorent
        should_deploy = improvement >= 2.0 or (new_precision > baseline_precision and new_recall > baseline_recall)

        # Sauvegarder la comparaison
        self.cur.execute("""
            INSERT INTO model_comparisons
            (old_version, new_version, old_precision, new_precision, old_recall,
             new_recall, old_map50, new_map50, improvement_percent, decision, decision_reason)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            baseline_name,
            new_version_name,
            baseline_precision,
            new_precision,
            baseline_recall,
            new_recall,
            baseline_map50,
            new_map50,
            improvement,
            'deploy' if should_deploy else 'rollback',
            f"Amelioration: {improvement:.1f}%" if should_deploy else "Pas assez d'amelioration"
        ))
        self.conn.commit()

        logging.info(f"Comparaison: Baseline {baseline_name} (mAP50={baseline_map50:.3f}) vs {new_version_name} (mAP50={new_map50:.3f})")
        logging.info(f"Amelioration: {improvement:.1f}% - Decision: {'DEPLOYER' if should_deploy else 'ROLLBACK'}")

        return should_deploy, improvement, {
            'baseline_name': baseline_name,
            'baseline_map50': baseline_map50,
            'new_map50': new_map50
        }

    def deploy_model(self, version_name, model_path):
        """
        Deploie la nouvelle version du modele en production
        """
        logging.info(f"Deploiement de {version_name}...")

        # Copier le modele vers le repertoire de production
        production_model_path = Path(self.base_model_path)
        production_model_path.parent.mkdir(parents=True, exist_ok=True)

        # Backup de l'ancien modele
        if production_model_path.exists():
            backup_path = production_model_path.parent / f"best_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pt"
            shutil.copy(production_model_path, backup_path)
            logging.info(f"Backup de l'ancien modele: {backup_path}")

        # Copier le nouveau modele
        shutil.copy(model_path, production_model_path)

        # Marquer comme deploye dans la base
        self.cur.execute("""
            UPDATE model_versions
            SET deployed = FALSE
            WHERE deployed = TRUE
        """)

        self.cur.execute("""
            UPDATE model_versions
            SET deployed = TRUE, deployed_at = NOW()
            WHERE version_name = %s
        """, (version_name,))

        self.conn.commit()

        logging.info(f"Modele {version_name} deploye avec succes!")

    def mark_annotations_as_used(self):
        """Marque toutes les annotations utilisees pour l'entrainement"""
        self.cur.execute("""
            UPDATE annotations
            SET used_for_training = TRUE
            WHERE used_for_training = FALSE
            AND is_correct IS NOT NULL
        """)
        self.conn.commit()
        logging.info("Annotations marquees comme utilisees")

    def cleanup(self):
        """Nettoie les fichiers temporaires"""
        if self.work_dir.exists():
            shutil.rmtree(self.work_dir)
            logging.info("Fichiers temporaires nettoyes")


if __name__ == "__main__":
    # Test du retrainer
    retrainer = ModelRetrainer()

    # Verifier si reentrainement necessaire
    should_retrain, reason, count = retrainer.check_if_retraining_needed()

    if should_retrain:
        print(f"Reentrainement necessaire: {reason}")
        print(f"{count} images annotees disponibles")
    else:
        print(f"Pas de reentrainement necessaire: {reason}")

    retrainer.close()
