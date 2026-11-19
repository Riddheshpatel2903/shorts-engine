@echo off
title ViralShortsEngine Pro Studio (Local)
cd /d "%~dp0"

echo ======================================================================
echo   Launching ViralShortsEngine Pro Studio (Local Machine)
echo ======================================================================
echo.
echo [1/2] Opening your browser to http://localhost:8501...
timeout /t 2 /nobreak >nul
start http://localhost:8501

echo [2/2] Starting Streamlit Studio Engine...
echo ======================================================================
echo   Press Ctrl+C in this window at any time to stop the studio.
echo ======================================================================
echo.

python -m streamlit run ui.py --server.port 8501 --server.address 127.0.0.1

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Streamlit exited with error code %ERRORLEVEL%.
    pause
)
