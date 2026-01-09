@echo off
cls
echo ========================================
echo   BACKUP COMPLET DU SYSTEME
echo ========================================
echo.

cd /d "%~dp0"

set BACKUP_DIR=backup_%date:~-4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set BACKUP_DIR=%BACKUP_DIR: =0%

echo Creation du dossier de backup: %BACKUP_DIR%
mkdir "%BACKUP_DIR%" 2>nul

echo.
echo [1/4] Backup des fichiers de configuration...
xcopy /E /I /Y "dags" "%BACKUP_DIR%\dags"
copy /Y ".env" "%BACKUP_DIR%\"
copy /Y "docker-compose.yml" "%BACKUP_DIR%\"
copy /Y "*.md" "%BACKUP_DIR%\"
copy /Y "*.bat" "%BACKUP_DIR%\"
echo     ✓ Fichiers sauvegardes

echo.
echo [2/4] Export de la base de donnees PostgreSQL...
docker exec airflow_standalone python -c "import psycopg2, os, json; conn = psycopg2.connect(os.getenv('DATABASE_URL')); cur = conn.cursor(); cur.execute('SELECT * FROM images'); rows = cur.fetchall(); data = [dict(zip([desc[0] for desc in cur.description], row)) for row in rows]; import json; print(json.dumps(data, default=str))" > "%BACKUP_DIR%\database_images.json"
echo     ✓ BDD exportee

echo.
echo [3/4] Liste des images S3...
docker exec airflow_standalone python -c "import boto3, os, json; s3 = boto3.client('s3'); result = s3.list_objects_v2(Bucket=os.getenv('S3_BUCKET_NAME'), Prefix='raw/', MaxKeys=1000); files = [obj['Key'] for obj in result.get('Contents', [])]; print(json.dumps(files))" > "%BACKUP_DIR%\s3_files.json"
echo     ✓ Liste S3 exportee

echo.
echo [4/4] Logs Docker...
docker logs airflow_standalone > "%BACKUP_DIR%\airflow_logs.txt" 2>&1
docker logs mlflow_server > "%BACKUP_DIR%\mlflow_logs.txt" 2>&1
echo     ✓ Logs sauvegardes

echo.
echo ========================================
echo   BACKUP TERMINE !
echo ========================================
echo.
echo Dossier de backup : %BACKUP_DIR%
echo.
echo Contenu :
dir /B "%BACKUP_DIR%"
echo.
echo Pour restaurer :
echo   1. Copiez le contenu de %BACKUP_DIR%\dags\ vers dags\
echo   2. Copiez .env et docker-compose.yml
echo   3. Relancez : docker-compose up -d
echo.
pause
