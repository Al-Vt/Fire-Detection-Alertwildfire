@echo off
cls
echo ========================================
echo   TEST COMPLET DU SYSTEME
echo   165 cameras - Pipeline complet
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] Verification des conteneurs...
docker ps | findstr airflow
if errorlevel 1 (
    echo [ERREUR] Airflow n'est pas lance !
    echo Lancez d'abord: docker-compose up -d
    pause
    exit /b 1
)
echo     Airflow operationnel

echo.
echo [2/3] Lancement du test manuel du DAG...
echo     (Cela va prendre 10-15 minutes)
echo.
docker exec airflow_standalone airflow dags test fire_detection_pipeline 2026-01-09

echo.
echo [3/3] Verification des resultats...
docker exec airflow_standalone python -c "import psycopg2, os; conn = psycopg2.connect(os.getenv('DATABASE_URL')); cur = conn.cursor(); cur.execute('SELECT COUNT(*) FROM images'); total = cur.fetchone()[0]; cur.execute('SELECT COUNT(*) FROM images WHERE fire_detected=true'); fires = cur.fetchone()[0]; print(f'\n📊 RESULTATS:'); print(f'   Total images: {total}'); print(f'   Feux detectes: {fires}'); cur.close(); conn.close()"

echo.
echo ========================================
echo   TEST TERMINE !
echo ========================================
echo.
echo Pour voir les details :
echo   - Interface Airflow: http://localhost:8080
echo   - Logs: docker logs airflow_standalone
echo.
pause
