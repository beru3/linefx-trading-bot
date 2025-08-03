@echo off
chcp 65001 >nul
title LINE FX Bot
cd /d "%~dp0"

echo Checking Python...
python --version
if errorlevel 1 (
    echo Python not found! Please install Python first.
    pause
    exit
)

echo Setting up virtual environment...
if not exist venv (
    python -m venv venv
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing requirements...
pip install -r requirements.txt

echo Installing Playwright...
playwright install chromium

echo Checking data loading...
python -c "import sys; sys.path.append('bot'); from data_reader import DataReaderFactory, TradeScheduleManager, load_trading_settings; import json; config = json.load(open('config/settings.json', 'r', encoding='utf-8')); trading_config = load_trading_settings('config'); reader = DataReaderFactory.create_reader(config, trading_config); manager = TradeScheduleManager(reader); success = manager.load_data(); summary = manager.get_trade_summary() if success else None; print(f'Data loaded: {summary[\"total\"]} trades') if success else print('Failed to load data') or exit(1)"

if errorlevel 1 (
    echo Data loading failed. Stopping bot execution.
    pause
    exit
)

echo Starting bot...
python bot\linefx_bot.py

pause