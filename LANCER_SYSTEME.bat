@echo off
cls
echo ========================================
echo   SYSTEME DE DETECTION D'INCENDIES
echo   Lancement automatique
echo ========================================
echo.

cd /d "%~dp0"

echo [1/4] Verification de Docker Desktop...
docker ps >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Docker Desktop n'est pas lance !
    echo Veuillez demarrer Docker Desktop puis relancer ce script.
    pause
    exit /b 1
)
echo     ✓ Docker operationnel

echo.
echo [2/4] Demarrage des conteneurs...
docker-compose up -d
if errorlevel 1 (
    echo [ERREUR] Echec du demarrage
    pause
    exit /b 1
)
echo     ✓ Conteneurs demarres

echo.
echo [3/4] Attente initialisation (30 secondes)...
timeout /t 30 /nobreak >nul
echo     ✓ Initialisation terminee

echo.
echo [4/4] Verification des services...
docker ps
echo.

echo ========================================
echo   SYSTEME OPERATIONNEL !
echo ========================================
echo.
echo Interfaces disponibles :
echo   - Airflow : http://localhost:8080
echo   - MLflow  : http://localhost:5000
echo.
echo Identifiants Airflow :
echo   Username : admin
echo   Password : admin123
echo.
echo Prochaines etapes :
echo   1. Ouvrir http://localhost:8080
echo   2. Se connecter avec admin/admin123
echo   3. Activer le DAG "fire_detection_pipeline"
echo   4. Le systeme tournera automatiquement toutes les 10 min
echo.
echo Les alertes seront envoyees a : axel.vilamot@gmail.com
echo.
echo ========================================
echo Appuyez sur une touche pour ouvrir Airflow...
pause >nul

start http://localhost:8080

echo.
echo Pour arreter le systeme : docker-compose down
echo.
pause
