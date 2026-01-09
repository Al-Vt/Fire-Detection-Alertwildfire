@echo off
echo ========================================
echo RECUPERATION DES IDENTIFIANTS AIRFLOW
echo ========================================
echo.
docker exec airflow_standalone bash -c "cat /root/airflow/standalone_admin_password.txt"
echo.
echo ========================================
echo Username: admin
echo Password: ^(voir ci-dessus^)
echo URL: http://localhost:8080
echo ========================================
pause
