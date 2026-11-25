@echo off
REM Double-clic pour lancer le tableau de bord (Windows).
REM La premiere fois, ce script installe tout ce qu'il faut (quelques minutes), puis ouvre l'application.
cd /d "%~dp0"

where py >nul 2>nul && (set PYTHON=py) || (set PYTHON=python)
%PYTHON% --version >nul 2>nul
if errorlevel 1 (
    echo Python n'est pas installe. Telechargez-le sur https://www.python.org/downloads/
    echo et cochez "Add Python to PATH" pendant l'installation, puis relancez ce fichier.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Premiere installation, patientez...
    %PYTHON% -m venv .venv
    if errorlevel 1 ( echo Echec de la creation de l'environnement. & pause & exit /b 1 )
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 ( echo Echec de l'installation des paquets. & pause & exit /b 1 )
)

echo Lancement de l'application : elle s'ouvre dans votre navigateur.
echo Pour l'arreter, fermez cette fenetre.
".venv\Scripts\python.exe" -m streamlit run app.py
pause
