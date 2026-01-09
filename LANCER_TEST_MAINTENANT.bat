@echo off
cls
echo ========================================
echo   TEST IMMEDIAT - 165 CAMERAS
echo   Pipeline complet avec analyse IA
echo ========================================
echo.
echo Ce test va :
echo   1. Scraper 165 cameras (~10 min)
echo   2. Analyser avec YOLOv8 (~2 min)
echo   3. Envoyer des emails si feu detecte
echo.
echo Duree totale estimee : 12-15 minutes
echo.
pause

cd /d "%~dp0"

echo.
echo [1/2] Lancement du scraping + analyse...
echo.
docker exec airflow_standalone bash -c "cd /opt/airflow/dags && python scraper.py && echo '✅ Scraping termine, lancement analyse...' && python -c \"
from fire_detection_workflow import task_run_inference
task_run_inference()
print('✅ Analyse terminee !')
\""

echo.
echo [2/2] Affichage des resultats...
echo.
docker exec airflow_standalone python -c "
import psycopg2, os
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

cur.execute('SELECT COUNT(*) FROM images')
total = cur.fetchone()[0]

cur.execute('SELECT COUNT(*) FROM images WHERE status=''NEW''')
pending = cur.fetchone()[0]

cur.execute('SELECT COUNT(*) FROM images WHERE status=''PROCESSED''')
processed = cur.fetchone()[0]

cur.execute('SELECT COUNT(*) FROM images WHERE fire_detected=true')
fires = cur.fetchone()[0]

print('========================================')
print('         RESULTATS DU TEST')
print('========================================')
print(f'')
print(f'📊 Total images en BDD : {total}')
print(f'🆕 En attente analyse  : {pending}')
print(f'✅ Deja analysees      : {processed}')
print(f'🔥 FEUX DETECTES      : {fires}')
print(f'')
print('========================================')

if fires > 0:
    print(f'')
    print(f'⚠️  {fires} INCENDIE(S) DETECTE(S) !')
    print(f'    Verifiez vos emails : axel.vilamot@gmail.com')
    print(f'')
    cur.execute('SELECT camera_name, confidence FROM images WHERE fire_detected=true ORDER BY confidence DESC LIMIT 5')
    print('🔝 Top 5 detections :')
    for row in cur.fetchall():
        print(f'   - {row[0]} : {row[1]*100:.0f}%% de confiance')

cur.close()
conn.close()
"

echo.
echo ========================================
echo   TEST TERMINE !
echo ========================================
echo.
echo Pour voir plus de details :
echo   - Interface Airflow: http://localhost:8080
echo   - MLflow: http://localhost:5000
echo.
pause
