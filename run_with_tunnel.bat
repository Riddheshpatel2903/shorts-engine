@echo off
title ViralShortsEngine Pro Studio + Cloudflare Live Tunnel
cd /d "%~dp0"

echo ======================================================================
echo   Starting ViralShortsEngine Studio + Cloudflare Live Tunnel
echo ======================================================================
echo.
echo [1/3] Starting Local Streamlit Studio Server on http://localhost:8501...
start "Streamlit Studio Server" cmd /c "python -m streamlit run ui.py --server.port 8501 --server.address 127.0.0.1"

echo [2/3] Waiting 4 seconds for server to initialize...
timeout /t 4 /nobreak >nul

echo.
echo [✓] Opening your local browser to http://localhost:8501...
start http://localhost:8501

echo.
echo [3/3] Connecting Cloudflare Secure Tunnel for worldwide access...
echo ======================================================================
echo   Your PUBLIC LIVE URL will appear below:
echo   (If Cloudflare has a network delay, your local studio is still open!)
echo ======================================================================
echo.

cloudflared.exe tunnel --url http://127.0.0.1:8501

echo.
echo [!] Cloudflare tunnel closed or disconnected.
echo [✓] Your local studio is still running at http://localhost:8501!
echo.
pause
