@echo off
cls
echo ========================================================================
echo   TEST DU PIPELINE FIRE DETECTION
echo   Verifie: Scraping ^> S3 ^> Inference ^> Monitoring
echo ========================================================================
echo.

cd /d "%~dp0"

echo Quel test voulez-vous lancer ?
echo.
echo   1. Test complet (verification infrastructure uniquement)
echo   2. Test cycle scraping + inference (scrape 5 cameras + analyse)
echo   3. Test monitoring system
echo   4. Quitter
echo.

set /p choice="Votre choix (1-4): "

if "%choice%"=="1" goto test_complet
if "%choice%"=="2" goto test_scraping
if "%choice%"=="3" goto test_monitoring
if "%choice%"=="4" goto end

echo Choix invalide
pause
goto end

:test_complet
echo.
echo ========================================================================
echo   TEST COMPLET - Verification Infrastructure
echo ========================================================================
echo.
echo Ce test verifie:
echo   - Connexion S3
echo   - Connexion Neon PostgreSQL
echo   - Tables de monitoring et reentrainement
echo   - Images dans S3 et base de donnees
echo   - Modele YOLOv8
echo.
pause

python test_complete_pipeline.py
pause
goto end

:test_scraping
echo.
echo ========================================================================
echo   TEST SCRAPING + INFERENCE
echo ========================================================================
echo.
echo Ce test va:
echo   1. Scraper 5 cameras
echo   2. Uploader les images sur S3
echo   3. Lancer l'inference avec YOLOv8
echo   4. Verifier le logging dans Neon
echo.
echo ATTENTION: Cela va prendre 2-3 minutes
echo.
pause

python test_scraping_inference.py
pause
goto end

:test_monitoring
echo.
echo ========================================================================
echo   TEST MONITORING SYSTEM
echo ========================================================================
echo.
echo Ce test verifie:
echo   - Connexion Neon
echo   - Calcul des metriques
echo   - Detection d'anomalies
echo   - Generation du rapport HTML
echo.
pause

python test_monitoring.py
pause
goto end

:end
echo.
echo Appuyez sur une touche pour fermer...
pause >nul
