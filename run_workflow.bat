@echo off
TITLE ETAFlow - Complete MLOps Workflow Demo
COLOR 0A

echo ===============================================================================
echo        ZOMATO ETAFLOW - END-TO-END MLOPS WORKFLOW DEMO EXECUTION
echo ===============================================================================
echo.

IF NOT EXIST ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found at .venv. Please run setup first.
    pause
    exit /b 1
)

echo [INFO] Running master MLOps pipeline...
echo.

.\.venv\Scripts\python.exe scripts\run_full_mlops_workflow.py

echo.
echo ===============================================================================
echo [SUCCESS] Workflow execution complete!
echo To open the web application, run: start.bat
echo ===============================================================================
echo.
pause

