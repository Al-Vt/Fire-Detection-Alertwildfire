"""
Module de calcul des métriques de monitoring du modèle
Analyse les prédictions quotidiennes et détecte les dégradations
"""

import psycopg2
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

# Seuils d'alerte pour détecter les dégradations
THRESHOLDS = {
    'min_avg_confidence': 0.60,  # Confiance moyenne minimum acceptable
    'max_avg_confidence': 0.95,  # Confiance moyenne maximum (possible overfitting)
    'min_daily_predictions': 50,  # Minimum de prédictions attendues par jour
    'max_inference_time_ms': 5000,  # Temps maximum d'inférence acceptable (5s)
}


class ModelMonitor:
    def __init__(self):
        self.conn = psycopg2.connect(DATABASE_URL)
        self.cur = self.conn.cursor()

    def close(self):
        """Ferme la connexion à la base de données"""
        self.cur.close()
        self.conn.close()

    def calculate_daily_metrics(self, target_date=None):
        """
        Calcule les métriques quotidiennes pour une date donnée
        Si target_date est None, utilise la date d'hier
        """
        if target_date is None:
            target_date = (datetime.now() - timedelta(days=1)).date()

        logging.info(f"Calcul des metriques pour {target_date}")

        # Récupérer toutes les prédictions du jour
        self.cur.execute("""
            SELECT
                COUNT(*) as total_predictions,
                SUM(CASE WHEN fire_detected = TRUE THEN 1 ELSE 0 END) as fire_detections,
                AVG(CASE WHEN fire_detected = TRUE THEN confidence ELSE NULL END) as avg_confidence,
                MIN(CASE WHEN fire_detected = TRUE THEN confidence ELSE NULL END) as min_confidence,
                MAX(CASE WHEN fire_detected = TRUE THEN confidence ELSE NULL END) as max_confidence,
                STDDEV(CASE WHEN fire_detected = TRUE THEN confidence ELSE NULL END) as std_confidence,
                AVG(inference_time_ms) as avg_inference_time_ms,
                COUNT(DISTINCT camera_name) as unique_cameras
            FROM model_predictions
            WHERE DATE(prediction_timestamp) = %s
        """, (target_date,))

        result = self.cur.fetchone()

        if result[0] == 0:
            logging.warning(f"Aucune prediction pour {target_date}")
            return None

        metrics = {
            'metric_date': target_date,
            'total_predictions': result[0],
            'fire_detections': result[1] or 0,
            'avg_confidence': float(result[2]) if result[2] else None,
            'min_confidence': float(result[3]) if result[3] else None,
            'max_confidence': float(result[4]) if result[4] else None,
            'std_confidence': float(result[5]) if result[5] else None,
            'avg_inference_time_ms': float(result[6]) if result[6] else None,
            'unique_cameras': result[7]
        }

        logging.info(f"Metriques calculees: {metrics}")
        return metrics

    def save_daily_metrics(self, metrics):
        """Sauvegarde les métriques quotidiennes dans la table daily_metrics"""
        if metrics is None:
            return

        self.cur.execute("""
            INSERT INTO daily_metrics
            (metric_date, total_predictions, fire_detections, avg_confidence,
             min_confidence, max_confidence, std_confidence, avg_inference_time_ms, unique_cameras)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (metric_date) DO UPDATE SET
                total_predictions = EXCLUDED.total_predictions,
                fire_detections = EXCLUDED.fire_detections,
                avg_confidence = EXCLUDED.avg_confidence,
                min_confidence = EXCLUDED.min_confidence,
                max_confidence = EXCLUDED.max_confidence,
                std_confidence = EXCLUDED.std_confidence,
                avg_inference_time_ms = EXCLUDED.avg_inference_time_ms,
                unique_cameras = EXCLUDED.unique_cameras
        """, (
            metrics['metric_date'],
            metrics['total_predictions'],
            metrics['fire_detections'],
            metrics['avg_confidence'],
            metrics['min_confidence'],
            metrics['max_confidence'],
            metrics['std_confidence'],
            metrics['avg_inference_time_ms'],
            metrics['unique_cameras']
        ))

        self.conn.commit()
        logging.info(f"Metriques sauvegardees pour {metrics['metric_date']}")

    def detect_anomalies(self, metrics):
        """
        Détecte les anomalies dans les métriques et crée des alertes
        Retourne la liste des alertes détectées
        """
        if metrics is None:
            return []

        alerts = []

        # Vérifier confiance moyenne trop basse
        if metrics['avg_confidence'] and metrics['avg_confidence'] < THRESHOLDS['min_avg_confidence']:
            alerts.append({
                'type': 'low_confidence',
                'message': f"Confiance moyenne trop basse: {metrics['avg_confidence']:.2f} < {THRESHOLDS['min_avg_confidence']}",
                'severity': 'critical',
                'value': metrics['avg_confidence'],
                'threshold': THRESHOLDS['min_avg_confidence']
            })

        # Vérifier confiance moyenne trop élevée (possible overfitting)
        if metrics['avg_confidence'] and metrics['avg_confidence'] > THRESHOLDS['max_avg_confidence']:
            alerts.append({
                'type': 'high_confidence',
                'message': f"Confiance moyenne anormalement elevee (possible overfitting): {metrics['avg_confidence']:.2f} > {THRESHOLDS['max_avg_confidence']}",
                'severity': 'warning',
                'value': metrics['avg_confidence'],
                'threshold': THRESHOLDS['max_avg_confidence']
            })

        # Vérifier nombre de prédictions trop bas
        if metrics['total_predictions'] < THRESHOLDS['min_daily_predictions']:
            alerts.append({
                'type': 'low_predictions',
                'message': f"Nombre de predictions trop bas: {metrics['total_predictions']} < {THRESHOLDS['min_daily_predictions']}",
                'severity': 'warning',
                'value': metrics['total_predictions'],
                'threshold': THRESHOLDS['min_daily_predictions']
            })

        # Vérifier temps d'inférence trop long
        if metrics['avg_inference_time_ms'] and metrics['avg_inference_time_ms'] > THRESHOLDS['max_inference_time_ms']:
            alerts.append({
                'type': 'slow_inference',
                'message': f"Temps d'inference trop long: {metrics['avg_inference_time_ms']:.0f}ms > {THRESHOLDS['max_inference_time_ms']}ms",
                'severity': 'warning',
                'value': metrics['avg_inference_time_ms'],
                'threshold': THRESHOLDS['max_inference_time_ms']
            })

        return alerts

    def save_alerts(self, alerts):
        """Sauvegarde les alertes dans la table model_alerts"""
        for alert in alerts:
            self.cur.execute("""
                INSERT INTO model_alerts
                (alert_type, alert_message, severity, metric_value, threshold_value)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                alert['type'],
                alert['message'],
                alert['severity'],
                alert['value'],
                alert['threshold']
            ))

        self.conn.commit()
        logging.info(f"{len(alerts)} alerte(s) sauvegardee(s)")

    def get_trend_analysis(self, days=7):
        """
        Analyse les tendances sur les N derniers jours
        Retourne un dictionnaire avec les tendances
        """
        self.cur.execute("""
            SELECT
                metric_date,
                avg_confidence,
                total_predictions,
                fire_detections,
                avg_inference_time_ms
            FROM daily_metrics
            WHERE metric_date >= CURRENT_DATE - INTERVAL '%s days'
            ORDER BY metric_date DESC
        """, (days,))

        results = self.cur.fetchall()

        if len(results) < 2:
            return None

        trends = {
            'period_days': days,
            'avg_confidence_trend': self._calculate_trend([r[1] for r in results if r[1]]),
            'predictions_trend': self._calculate_trend([r[2] for r in results]),
            'fire_detections_trend': self._calculate_trend([r[3] for r in results]),
            'inference_time_trend': self._calculate_trend([r[4] for r in results if r[4]])
        }

        return trends

    def _calculate_trend(self, values):
        """
        Calcule la tendance (hausse/baisse/stable) d'une série de valeurs
        """
        if len(values) < 2:
            return 'insufficient_data'

        first_half = sum(values[:len(values)//2]) / (len(values)//2)
        second_half = sum(values[len(values)//2:]) / (len(values) - len(values)//2)

        diff_percent = ((second_half - first_half) / first_half * 100) if first_half > 0 else 0

        if diff_percent > 10:
            return 'increasing'
        elif diff_percent < -10:
            return 'decreasing'
        else:
            return 'stable'

    def generate_report(self, metrics, alerts, trends):
        """
        Génère un rapport HTML pour email
        """
        if metrics is None:
            return "<p>Aucune donnee disponible pour generer un rapport.</p>"

        status_emoji = "🔴" if alerts else "🟢"

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2>{status_emoji} Rapport de Monitoring du Modele - {metrics['metric_date']}</h2>

            <h3>Metriques Quotidiennes</h3>
            <table border="1" cellpadding="8" style="border-collapse: collapse;">
                <tr><td><b>Total predictions</b></td><td>{metrics['total_predictions']}</td></tr>
                <tr><td><b>Feux detectes</b></td><td>{metrics['fire_detections']}</td></tr>
                <tr><td><b>Cameras uniques</b></td><td>{metrics['unique_cameras']}</td></tr>
                <tr style="background-color: {'#ffcccc' if metrics['avg_confidence'] and metrics['avg_confidence'] < THRESHOLDS['min_avg_confidence'] else '#ccffcc'}">
                    <td><b>Confiance moyenne</b></td>
                    <td>{metrics['avg_confidence']:.2f if metrics['avg_confidence'] else 'N/A'}</td>
                </tr>
                <tr><td><b>Confiance min/max</b></td><td>{metrics['min_confidence']:.2f if metrics['min_confidence'] else 'N/A'} / {metrics['max_confidence']:.2f if metrics['max_confidence'] else 'N/A'}</td></tr>
                <tr><td><b>Temps inference moyen</b></td><td>{metrics['avg_inference_time_ms']:.0f}ms</td></tr>
            </table>
        """

        # Alertes
        if alerts:
            html += "<h3 style='color: red;'>Alertes Detectees</h3><ul>"
            for alert in alerts:
                color = 'red' if alert['severity'] == 'critical' else 'orange'
                html += f"<li style='color: {color};'><b>{alert['type']}</b>: {alert['message']}</li>"
            html += "</ul>"
        else:
            html += "<p style='color: green;'><b>Aucune alerte - Modele fonctionne normalement</b></p>"

        # Tendances
        if trends:
            html += "<h3>Tendances (7 derniers jours)</h3><ul>"
            html += f"<li>Confiance: {trends['avg_confidence_trend']}</li>"
            html += f"<li>Predictions: {trends['predictions_trend']}</li>"
            html += f"<li>Detections feux: {trends['fire_detections_trend']}</li>"
            html += f"<li>Temps inference: {trends['inference_time_trend']}</li>"
            html += "</ul>"

        html += """
            <hr>
            <p style="color: gray; font-size: 12px;">
            Rapport genere automatiquement par le systeme de monitoring Fire Detection.
            </p>
        </body>
        </html>
        """

        return html


if __name__ == "__main__":
    # Test du monitoring
    monitor = ModelMonitor()

    # Calculer métriques d'hier
    metrics = monitor.calculate_daily_metrics()

    if metrics:
        # Sauvegarder
        monitor.save_daily_metrics(metrics)

        # Détecter anomalies
        alerts = monitor.detect_anomalies(metrics)

        # Sauvegarder alertes
        if alerts:
            monitor.save_alerts(alerts)

        # Analyse tendances
        trends = monitor.get_trend_analysis(days=7)

        # Générer rapport
        report = monitor.generate_report(metrics, alerts, trends)
        print(report)

    monitor.close()
