@echo off
cd /d "%~dp0"
echo Vergadervoorbereiding wordt gestart...
echo.

REM Controleer of Python beschikbaar is
python --version >nul 2>&1
if errorlevel 1 (
    echo FOUT: Python is niet gevonden. Installeer Python via https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Installeer packages als dat nog niet gedaan is
pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo Benodigde packages worden geïnstalleerd...
    pip install -r requirements.txt
)

echo App wordt geopend in je browser...
streamlit run app.py --server.headless false
pause
