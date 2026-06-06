@echo off
title MPDTE College Predictor - Setup
color 0B
echo.
echo ============================================================
echo   MPDTE College Predictor ^& Analyzer - Windows Setup
echo ============================================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Download from https://python.org
    pause
    exit /b 1
)

echo [OK] Python found
echo.
echo Installing dependencies...
pip install customtkinter pdfplumber pandas reportlab openpyxl Pillow --quiet
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)

echo [OK] Dependencies installed
echo.
echo Starting MPDTE College Predictor...
echo.
python main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Application crashed. Check logs above.
    pause
)
