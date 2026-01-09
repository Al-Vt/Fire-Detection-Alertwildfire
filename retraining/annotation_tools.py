"""
Outils pour l'annotation manuelle des predictions
Permet de valider/corriger les predictions pour ameliorer le modele
"""

import psycopg2
import os
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')


class AnnotationManager:
    def __init__(self):
        self.conn = psycopg2.connect(DATABASE_URL)
        self.cur = self.conn.cursor()

    def close(self):
        """Ferme la connexion a la base de donnees"""
        self.cur.close()
        self.conn.close()

    def get_predictions_to_review(self, limit=50, fire_only=False):
        """
        Recupere les predictions qui necessitent une revision
        fire_only=True pour ne recuperer que les detections de feu
        """
        fire_filter = "AND mp.fire_detected = TRUE" if fire_only else ""

        self.cur.execute(f"""
            SELECT mp.id, mp.image_id, mp.camera_name, mp.fire_detected,
                   mp.confidence, mp.bbox, i.s3_path, mp.prediction_timestamp
            FROM model_predictions mp
            JOIN images i ON mp.image_id = i.id
            LEFT JOIN annotations a ON mp.id = a.prediction_id
            WHERE a.id IS NULL  -- Pas encore annotee
            {fire_filter}
            ORDER BY mp.prediction_timestamp DESC
            LIMIT %s
        """, (limit,))

        predictions = []
        for row in self.cur.fetchall():
            predictions.append({
                'prediction_id': row[0],
                'image_id': row[1],
                'camera_name': row[2],
                'fire_detected': row[3],
                'confidence': row[4],
                'bbox': row[5],
                's3_path': row[6],
                'timestamp': row[7]
            })

        return predictions

    def annotate_prediction(self, prediction_id, is_correct, corrected_label=None,
                          corrected_bbox=None, notes=None, annotated_by='manual'):
        """
        Annote une prediction
        - prediction_id: ID de la prediction
        - is_correct: True si la prediction est correcte, False sinon
        - corrected_label: 'fire' ou 'no_fire' si correction necessaire
        - corrected_bbox: [x, y, w, h] si bbox incorrecte
        - notes: Notes optionnelles
        """
        self.cur.execute("""
            INSERT INTO annotations
            (prediction_id, image_id, annotation_type, is_correct, corrected_label,
             corrected_bbox, notes, annotated_by)
            SELECT %s, mp.image_id,
                   CASE WHEN %s THEN 'validation' ELSE 'correction' END,
                   %s, %s, %s, %s, %s
            FROM model_predictions mp
            WHERE mp.id = %s
            RETURNING id
        """, (
            prediction_id,
            is_correct,
            is_correct,
            corrected_label,
            psycopg2.extras.Json(corrected_bbox) if corrected_bbox else None,
            notes,
            annotated_by,
            prediction_id
        ))

        self.conn.commit()
        annotation_id = self.cur.fetchone()[0]

        logging.info(f"Annotation creee: ID={annotation_id}, prediction={prediction_id}, is_correct={is_correct}")
        return annotation_id

    def batch_annotate_correct(self, prediction_ids, annotated_by='manual'):
        """Annote plusieurs predictions comme correctes en batch"""
        for pred_id in prediction_ids:
            self.annotate_prediction(pred_id, is_correct=True, annotated_by=annotated_by)

        logging.info(f"{len(prediction_ids)} predictions annotees comme correctes")

    def batch_annotate_false_positive(self, prediction_ids, annotated_by='manual'):
        """Annote plusieurs predictions comme faux positifs"""
        for pred_id in prediction_ids:
            self.annotate_prediction(
                pred_id,
                is_correct=False,
                corrected_label='no_fire',
                notes='Faux positif',
                annotated_by=annotated_by
            )

        logging.info(f"{len(prediction_ids)} predictions annotees comme faux positifs")

    def get_annotation_stats(self):
        """Recupere les statistiques d'annotation"""
        self.cur.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) as correct,
                SUM(CASE WHEN NOT is_correct THEN 1 ELSE 0 END) as incorrect,
                SUM(CASE WHEN used_for_training THEN 1 ELSE 0 END) as used_for_training,
                SUM(CASE WHEN NOT used_for_training AND is_correct IS NOT NULL THEN 1 ELSE 0 END) as ready_for_training
            FROM annotations
        """)

        row = self.cur.fetchone()

        return {
            'total': row[0],
            'correct': row[1],
            'incorrect': row[2],
            'used_for_training': row[3],
            'ready_for_training': row[4]
        }

    def export_annotations_for_training(self, output_file='annotations_export.json'):
        """Exporte les annotations non utilisees pour le reentrainement"""
        import json

        self.cur.execute("""
            SELECT a.image_id, i.s3_path, a.corrected_label, a.corrected_bbox,
                   a.is_correct, mp.fire_detected, mp.confidence, mp.bbox
            FROM annotations a
            JOIN images i ON a.image_id = i.id
            LEFT JOIN model_predictions mp ON a.prediction_id = mp.id
            WHERE a.used_for_training = FALSE
            AND a.is_correct IS NOT NULL
        """)

        annotations = []
        for row in self.cur.fetchall():
            annotations.append({
                'image_id': row[0],
                's3_path': row[1],
                'corrected_label': row[2],
                'corrected_bbox': row[3],
                'is_correct': row[4],
                'original_fire_detected': row[5],
                'original_confidence': float(row[6]) if row[6] else None,
                'original_bbox': row[7]
            })

        with open(output_file, 'w') as f:
            json.dump(annotations, f, indent=2)

        logging.info(f"{len(annotations)} annotations exportees vers {output_file}")
        return output_file


if __name__ == "__main__":
    # Test de l'annotation manager
    manager = AnnotationManager()

    # Afficher les stats
    stats = manager.get_annotation_stats()
    print("\nStatistiques d'annotation:")
    print(f"  Total: {stats['total']}")
    print(f"  Correctes: {stats['correct']}")
    print(f"  Incorrectes: {stats['incorrect']}")
    print(f"  Utilisees pour entrainement: {stats['used_for_training']}")
    print(f"  Pretes pour entrainement: {stats['ready_for_training']}")

    # Recuperer les predictions a reviewer
    predictions = manager.get_predictions_to_review(limit=10, fire_only=True)
    print(f"\n{len(predictions)} predictions a reviewer (feu detecte):")
    for p in predictions[:5]:  # Afficher les 5 premieres
        print(f"  - ID={p['prediction_id']}, Camera={p['camera_name']}, Confidence={p['confidence']:.2f}")

    manager.close()
