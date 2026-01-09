"""
Gestionnaire de versions du modele
Permet de lister, deployer et rollback les versions
"""

import psycopg2
import os
import shutil
from pathlib import Path
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')


class ModelVersionManager:
    def __init__(self, production_model_path='model/weights/best.pt'):
        self.production_model_path = Path(production_model_path)
        self.conn = psycopg2.connect(DATABASE_URL)
        self.cur = self.conn.cursor()

    def close(self):
        """Ferme la connexion a la base de donnees"""
        self.cur.close()
        self.conn.close()

    def list_versions(self, limit=10):
        """Liste les versions du modele"""
        self.cur.execute("""
            SELECT version_name, precision, recall, map50, map50_95,
                   deployed, deployed_at, training_completed_at, status
            FROM model_versions
            ORDER BY training_completed_at DESC
            LIMIT %s
        """, (limit,))

        versions = []
        for row in self.cur.fetchall():
            versions.append({
                'version_name': row[0],
                'precision': float(row[1]) if row[1] else None,
                'recall': float(row[2]) if row[2] else None,
                'map50': float(row[3]) if row[3] else None,
                'map50_95': float(row[4]) if row[4] else None,
                'deployed': row[5],
                'deployed_at': row[6],
                'training_completed_at': row[7],
                'status': row[8]
            })

        return versions

    def get_current_version(self):
        """Recupere la version actuellement deployee"""
        self.cur.execute("""
            SELECT version_name, precision, recall, map50, deployed_at
            FROM model_versions
            WHERE deployed = TRUE
            ORDER BY deployed_at DESC
            LIMIT 1
        """)

        row = self.cur.fetchone()
        if not row:
            return None

        return {
            'version_name': row[0],
            'precision': float(row[1]) if row[1] else None,
            'recall': float(row[2]) if row[2] else None,
            'map50': float(row[3]) if row[3] else None,
            'deployed_at': row[4]
        }

    def get_version_details(self, version_name):
        """Recupere les details d'une version specifique"""
        self.cur.execute("""
            SELECT version_name, mlflow_run_id, mlflow_model_uri, base_model_version,
                   training_started_at, training_completed_at, training_duration_minutes,
                   dataset_size, train_split, val_split, epochs, batch_size, learning_rate,
                   precision, recall, map50, map50_95, status, deployed, deployed_at, notes
            FROM model_versions
            WHERE version_name = %s
        """, (version_name,))

        row = self.cur.fetchone()
        if not row:
            return None

        return {
            'version_name': row[0],
            'mlflow_run_id': row[1],
            'mlflow_model_uri': row[2],
            'base_model_version': row[3],
            'training_started_at': row[4],
            'training_completed_at': row[5],
            'training_duration_minutes': float(row[6]) if row[6] else None,
            'dataset_size': row[7],
            'train_split': row[8],
            'val_split': row[9],
            'epochs': row[10],
            'batch_size': row[11],
            'learning_rate': float(row[12]) if row[12] else None,
            'precision': float(row[13]) if row[13] else None,
            'recall': float(row[14]) if row[14] else None,
            'map50': float(row[15]) if row[15] else None,
            'map50_95': float(row[16]) if row[16] else None,
            'status': row[17],
            'deployed': row[18],
            'deployed_at': row[19],
            'notes': row[20]
        }

    def deploy_version(self, version_name, model_path):
        """
        Deploie une version specifique
        model_path: Chemin vers le fichier .pt de cette version
        """
        logging.info(f"Deploiement de la version {version_name}...")

        # Verifier que la version existe
        version = self.get_version_details(version_name)
        if not version:
            raise Exception(f"Version {version_name} introuvable")

        # Backup de l'ancien modele
        if self.production_model_path.exists():
            backup_path = self.production_model_path.parent / f"backup_{version_name}.pt"
            shutil.copy(self.production_model_path, backup_path)
            logging.info(f"Backup cree: {backup_path}")

        # Copier le nouveau modele
        self.production_model_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(model_path, self.production_model_path)

        # Mettre a jour la base de donnees
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

        logging.info(f"Version {version_name} deployee avec succes")

    def rollback_to_version(self, version_name):
        """
        Rollback vers une version precedente
        Attention: Le fichier .pt doit etre disponible (backup ou MLflow)
        """
        logging.info(f"Rollback vers la version {version_name}...")

        version = self.get_version_details(version_name)
        if not version:
            raise Exception(f"Version {version_name} introuvable")

        # Chercher le backup
        backup_path = self.production_model_path.parent / f"backup_{version_name}.pt"

        if not backup_path.exists():
            raise Exception(f"Backup introuvable pour {version_name}. Utilisez MLflow pour recuperer le modele.")

        # Deployer le backup
        self.deploy_version(version_name, backup_path)

        logging.info(f"Rollback vers {version_name} termine")

    def compare_versions(self, version1, version2):
        """Compare deux versions du modele"""
        v1 = self.get_version_details(version1)
        v2 = self.get_version_details(version2)

        if not v1 or not v2:
            raise Exception("Une ou plusieurs versions introuvables")

        comparison = {
            'version1': version1,
            'version2': version2,
            'precision_diff': v2['precision'] - v1['precision'] if v1['precision'] and v2['precision'] else None,
            'recall_diff': v2['recall'] - v1['recall'] if v1['recall'] and v2['recall'] else None,
            'map50_diff': v2['map50'] - v1['map50'] if v1['map50'] and v2['map50'] else None,
            'v1_metrics': {
                'precision': v1['precision'],
                'recall': v1['recall'],
                'map50': v1['map50']
            },
            'v2_metrics': {
                'precision': v2['precision'],
                'recall': v2['recall'],
                'map50': v2['map50']
            }
        }

        return comparison

    def get_version_history(self, limit=20):
        """Recupere l'historique complet des versions"""
        self.cur.execute("""
            SELECT version_name, precision, recall, map50, deployed, deployed_at,
                   training_completed_at
            FROM model_versions
            ORDER BY training_completed_at DESC
            LIMIT %s
        """, (limit,))

        history = []
        for row in self.cur.fetchall():
            history.append({
                'version_name': row[0],
                'precision': float(row[1]) if row[1] else None,
                'recall': float(row[2]) if row[2] else None,
                'map50': float(row[3]) if row[3] else None,
                'deployed': row[4],
                'deployed_at': row[5],
                'training_completed_at': row[6]
            })

        return history

    def print_version_summary(self, version):
        """Affiche un resume d'une version"""
        print(f"\nVersion: {version['version_name']}")
        print(f"  Precision: {version['precision']:.3f}" if version['precision'] else "  Precision: N/A")
        print(f"  Recall: {version['recall']:.3f}" if version['recall'] else "  Recall: N/A")
        print(f"  mAP50: {version['map50']:.3f}" if version['map50'] else "  mAP50: N/A")
        print(f"  Deployed: {'Oui' if version['deployed'] else 'Non'}")
        if version['deployed_at']:
            print(f"  Deployed at: {version['deployed_at']}")


if __name__ == "__main__":
    # Test du version manager
    manager = ModelVersionManager()

    print("\n=== GESTIONNAIRE DE VERSIONS DU MODELE ===\n")

    # Version actuelle
    current = manager.get_current_version()
    if current:
        print("Version actuellement deployee:")
        manager.print_version_summary(current)
    else:
        print("Aucune version deployee")

    # Historique
    print("\n\nHistorique des versions:")
    versions = manager.list_versions(limit=10)
    for v in versions:
        status = "[DEPLOYED]" if v['deployed'] else ""
        print(f"  - {v['version_name']} {status}")
        if v['map50']:
            print(f"    mAP50: {v['map50']:.3f}, Precision: {v['precision']:.3f}, Recall: {v['recall']:.3f}")

    manager.close()
