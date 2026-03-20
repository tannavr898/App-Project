@echo off
echo ========================================
echo Student Wellness Dashboard - Setup
echo ========================================
echo.

echo Installing Python dependencies...
pip install -r requirements.txt

echo.
echo ========================================
echo Setup completed!
echo ========================================
echo.
echo To start the dashboard, run:
echo   streamlit run app.py
echo.
echo The dashboard will open at: http://localhost:8501
echo.
