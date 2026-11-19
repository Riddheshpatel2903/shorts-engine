@echo off
title ViralShortsEngine Pro Studio
cd /d "%~dp0"
echo ========================================================
echo   Launching ViralShortsEngine Pro Studio Dashboard
echo ========================================================
python -m streamlit run ui.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Streamlit exited or failed to start.
    pause
)
