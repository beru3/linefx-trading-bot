@echo off
chcp 65001 >nul
title LINE FX Bot - Test Trading
cd /d "%~dp0"

echo ==============================================
echo LINE FX Bot - USDJPY Long Test
echo ==============================================
echo.
echo Test Schedule:
echo Entry:  15:15:00 USD/JPY Long 1000 (Prep: 15:14:30)
echo Exit:   15:16:00 Position Close (Prep: 15:15:30) - 60 seconds holding
echo.
echo Current time: 
powershell -command "Get-Date -Format 'yyyy-MM-dd HH:mm:ss'"
echo.
echo Starting in 5 seconds...
timeout /t 5 /nobreak > nul

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Starting scheduled trading bot...
python bot\linefx_bot.py trading

echo.
echo Trading test completed!
pause