@echo off
title ViralShortsEngine Pro Studio + Cloudflare Live Tunnel
cd /d "%~dp0"

echo ======================================================================
echo   Starting ViralShortsEngine Studio + Cloudflare Live Tunnel
echo ======================================================================
echo.
echo [1/3] Starting Local Streamlit Studio Server on port 8501...
start "Streamlit Studio Server" /min cmd /c "python -m streamlit run ui.py --server.port 8501 --server.address 127.0.0.1 --server.headless true"

echo [2/3] Waiting 4 seconds for server to initialize...
timeout /t 4 /nobreak >nul

echo [3/3] Connecting Cloudflare Secure Tunnel...
echo.
echo ======================================================================
echo   Your LIVE Public URL will be displayed below:
echo   (Keep this window OPEN while using your app!)
echo ======================================================================
echo.

cloudflared.exe tunnel --url http://127.0.0.1:8501

echo.
echo Stopping Streamlit server...
taskkill /F /FI "WINDOWTITLE eq Streamlit Studio Server*" >nul 2>&1
echo Done.
pause
