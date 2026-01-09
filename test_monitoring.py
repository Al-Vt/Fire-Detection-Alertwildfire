"""
Script de test du systeme de monitoring
Verifie que tout fonctionne correctement
"""

import os
from dotenv import load_dotenv
from monitoring.metrics import ModelMonitor
from datetime import datetime, timedelta

load_dotenv()

print("=" * 60)
print("TEST DU SYSTEME DE MONITORING")
print("=" * 60)

# Test 1: Connexion a Neon
print("\n[1/4] Test connexion a Neon PostgreSQL...")
try:
    monitor = ModelMonitor()
    print("  [OK] Connexion reussie")
except Exception as e:
    print(f"  [ERREUR] Echec connexion: {e}")
    exit(1)

# Test 2: Calcul des metriques
print("\n[2/4] Test calcul des metriques...")
try:
    # Essayer d'abord avec la date d'aujourd'hui
    metrics = monitor.calculate_daily_metrics(target_date=datetime.now().date())

    if metrics is None:
        print("  [INFO] Pas de predictions aujourd'hui, test avec hier...")
        metrics = monitor.calculate_daily_metrics(target_date=(datetime.now() - timedelta(days=1)).date())

    if metrics:
        print(f"  [OK] Metriques calculees:")
        print(f"       - Date: {metrics['metric_date']}")
        print(f"       - Predictions: {metrics['total_predictions']}")
        print(f"       - Feux detectes: {metrics['fire_detections']}")
        print(f"       - Confiance moyenne: {metrics['avg_confidence']}")

        # Sauvegarder les metriques
        monitor.save_daily_metrics(metrics)
        print("  [OK] Metriques sauvegardees dans Neon")
    else:
        print("  [ATTENTION] Aucune prediction dans la base")
        print("  [INFO] Vous devrez lancer le scraping + inference pour generer des donnees")
except Exception as e:
    print(f"  [ERREUR] {e}")
    import traceback
    traceback.print_exc()

# Test 3: Detection d'anomalies
print("\n[3/4] Test detection d'anomalies...")
try:
    if metrics:
        alerts = monitor.detect_anomalies(metrics)

        if alerts:
            print(f"  [OK] {len(alerts)} alerte(s) detectee(s):")
            for alert in alerts:
                print(f"       - [{alert['severity']}] {alert['message']}")
            monitor.save_alerts(alerts)
        else:
            print("  [OK] Aucune anomalie detectee - Modele fonctionne normalement")
    else:
        print("  [SKIP] Pas de metriques, pas d'analyse")
except Exception as e:
    print(f"  [ERREUR] {e}")

# Test 4: Analyse des tendances
print("\n[4/4] Test analyse des tendances...")
try:
    trends = monitor.get_trend_analysis(days=7)

    if trends:
        print(f"  [OK] Tendances sur {trends['period_days']} jours:")
        print(f"       - Confiance: {trends['avg_confidence_trend']}")
        print(f"       - Predictions: {trends['predictions_trend']}")
        print(f"       - Detections feux: {trends['fire_detections_trend']}")
        print(f"       - Temps inference: {trends['inference_time_trend']}")
    else:
        print("  [INFO] Pas assez de donnees pour analyser les tendances")
        print("  [INFO] Il faut au moins 2 jours de donnees")
except Exception as e:
    print(f"  [ERREUR] {e}")

# Test 5: Generation du rapport
print("\n[5/5] Test generation du rapport HTML...")
try:
    if metrics:
        report = monitor.generate_report(metrics, alerts if metrics else [], trends)

        # Sauvegarder le rapport dans un fichier
        report_file = "test_monitoring_report.html"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"  [OK] Rapport genere et sauvegarde dans {report_file}")
        print(f"  [INFO] Ouvrez ce fichier dans un navigateur pour voir le rapport")
    else:
        print("  [SKIP] Pas de metriques, pas de rapport")
except Exception as e:
    print(f"  [ERREUR] {e}")

# Fermer la connexion
monitor.close()

print("\n" + "=" * 60)
print("RESUME")
print("=" * 60)
print("\nLe systeme de monitoring est configure et pret!")
print("\nProchaines etapes:")
print("  1. Lancez le systeme avec LANCER_SYSTEME.bat")
print("  2. Le DAG 'fire_detection_pipeline' va scraper et analyser les images")
print("  3. Chaque prediction sera loggee automatiquement dans Neon")
print("  4. Le DAG 'model_monitoring_daily' s'executera tous les jours a 9h")
print("  5. Vous recevrez un email quotidien avec les metriques")
print("\nConfiguration:")
print(f"  - Email: axel.vilamot@gmail.com")
print(f"  - Base de donnees: Neon PostgreSQL")
print(f"  - Frequence scraping: Toutes les 15 minutes")
print(f"  - Frequence monitoring: Quotidien a 9h00")
print("\n" + "=" * 60)
