@echo off
title ViralShortsEngine + Cloudflare Tunnel
cd /d "%~dp0"
echo ========================================================
echo   Starting ViralShortsEngine Studio with Cloudflare Tunnel
echo ========================================================
python run_tunnel.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Script ended or exited with error code %ERRORLEVEL%.
    pause
)
