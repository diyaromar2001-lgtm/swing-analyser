@echo off
title 📈 Swing Analyser — Démarrage
color 0A

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║       📈  SWING ANALYSER  — Démarrage       ║
echo  ╚══════════════════════════════════════════════╝
echo.

:: ── Chemins ──────────────────────────────────────────────────────────────────
set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"
set "UVICORN=%BACKEND%\venv\Scripts\uvicorn.exe"
set "NPM=%ROOT%frontend\node_modules\.bin\next.cmd"

:: ── Vérifications ────────────────────────────────────────────────────────────
if not exist "%UVICORN%" (
    echo  [ERREUR] uvicorn introuvable : %UVICORN%
    echo  Lance d'abord :  cd backend ^&^& python -m venv venv ^&^& venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

if not exist "%FRONTEND%\node_modules" (
    echo  [ERREUR] node_modules manquant.
    echo  Lance d'abord :  cd frontend ^&^& npm install
    pause
    exit /b 1
)

:: ── Tuer les anciens processus sur les ports 8000 / 3000 (silencieux) ────────
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8000 "') do (
    taskkill /PID %%p /F >nul 2>&1
)
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":3000 "') do (
    taskkill /PID %%p /F >nul 2>&1
)

:: ── Backend ───────────────────────────────────────────────────────────────────
echo  [1/2] Démarrage du backend  (port 8000)...
start "🔧 Backend — FastAPI" /D "%BACKEND%" cmd /k ".\venv\Scripts\uvicorn.exe main:app --host 0.0.0.0 --port 8000 --reload"

:: Attendre que le backend réponde (max ~20 s)
echo  Attente du backend...
set /a tries=0
:wait_backend
timeout /t 2 /nobreak >nul
powershell -Command "try { $r=(Invoke-WebRequest http://localhost:8000/health -UseBasicParsing -TimeoutSec 2).StatusCode; exit $r } catch { exit 0 }" >nul 2>&1
if %ERRORLEVEL%==200 goto backend_ok
set /a tries+=1
if %tries% lss 10 goto wait_backend
echo  [AVERTISSEMENT] Backend pas encore prêt — on continue quand même.
:backend_ok
echo  [OK] Backend actif sur http://localhost:8000

:: ── Frontend ──────────────────────────────────────────────────────────────────
echo  [2/2] Démarrage du frontend (port 3000)...
start "🌐 Frontend — Next.js" /D "%FRONTEND%" cmd /k "npx next dev --turbopack"

:: Attendre que le frontend réponde
echo  Attente du frontend (compilation ~10-20 s)...
set /a tries=0
:wait_frontend
timeout /t 3 /nobreak >nul
powershell -Command "try { $r=(Invoke-WebRequest http://localhost:3000 -UseBasicParsing -TimeoutSec 2).StatusCode; exit $r } catch { exit 0 }" >nul 2>&1
if %ERRORLEVEL%==200 goto frontend_ok
set /a tries+=1
if %tries% lss 15 goto wait_frontend
echo  [AVERTISSEMENT] Frontend pas encore prêt — ouverture quand même.
:frontend_ok
echo  [OK] Frontend actif sur http://localhost:3000

:: ── Ouvrir le navigateur ──────────────────────────────────────────────────────
echo.
echo  ✅ Tout est prêt ! Ouverture du navigateur...
start "" "http://localhost:3000"

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║  Backend  → http://localhost:8000            ║
echo  ║  Frontend → http://localhost:3000            ║
echo  ║                                              ║
echo  ║  Ferme les fenêtres "Backend" et            ║
echo  ║  "Frontend" pour stopper les serveurs.       ║
echo  ╚══════════════════════════════════════════════╝
echo.
pause
