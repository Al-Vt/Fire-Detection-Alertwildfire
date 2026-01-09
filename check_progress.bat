@echo off
echo ========================================
echo   PROGRESSION DU SCRAPING
echo ========================================
echo.

docker exec airflow_standalone python -c "import psycopg2, os; conn = psycopg2.connect(os.getenv('DATABASE_URL')); cur = conn.cursor(); cur.execute('SELECT COUNT(*) FROM images'); total = cur.fetchone()[0]; cur.execute('SELECT COUNT(*) FROM images WHERE status=''NEW'''); pending = cur.fetchone()[0]; cur.execute('SELECT COUNT(*) FROM images WHERE status=''PROCESSED'''); processed = cur.fetchone()[0]; cur.execute('SELECT COUNT(*) FROM images WHERE fire_detected=true'); fires = cur.fetchone()[0]; print(f'📊 Total images: {total}'); print(f'🆕 En attente: {pending}'); print(f'✅ Analysées: {processed}'); print(f'🔥 Feux détectés: {fires}'); cur.close(); conn.close()"

echo.
echo ========================================
pause
