@echo off
chcp 65001 >nul
echo LINE FX Auto Trading Bot - Python Edition
echo ==========================================

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found
    echo Please install Python from: https://python.org/
    pause
    exit
)

REM Setup virtual environment
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing Python packages...
pip install -r requirements.txt

echo Installing Playwright browsers...
playwright install chromium

REM Check config file
if not exist "config\settings.json" (
    echo ERROR: settings.json not found in config folder
    pause
    exit
)

echo.
echo === Bot Features ===
echo [OK] Python + Playwright automation
echo [OK] Bot detection avoidance (enhanced)
echo [OK] Automatic screenshot capture
echo [OK] Detailed logging
echo [OK] Virtual environment isolation
echo.

REM メニュー表示
:menu
echo.
echo === メニュー ===
echo 1. データソース設定確認
echo 2. ログインテスト
echo 3. スケジュール自動取引実行
echo 4. 手動取引テスト
echo 5. ログ確認
echo 6. 終了
echo.
set /p choice="選択してください (1-6): "

if "%choice%"=="1" goto datasource
if "%choice%"=="2" goto logintest
if "%choice%"=="3" goto runbot
if "%choice%"=="4" goto manualtest
if "%choice%"=="5" goto showlog
if "%choice%"=="6" goto end
goto menu

:datasource
echo.
echo === データソース設定 ===
python -c "
import json
with open('config/settings.json', 'r', encoding='utf-8') as f:
    config = json.load(f)
ds = config.get('data_source', {})
print(f'現在のデータソース: {ds.get(\"type\", \"excel\")}')
if ds.get('type') == 'excel':
    print(f'Excelファイル: {ds.get(\"excel\", {}).get(\"file_path\", \"\")}')
elif ds.get('type') == 'csv':
    print(f'CSVファイル: {ds.get(\"csv\", {}).get(\"file_path\", \"\")}')
elif ds.get('type') == 'google_sheets':
    print(f'Google Sheets ID: {ds.get(\"google_sheets\", {}).get(\"spreadsheet_id\", \"\")}')
    print(f'シート名: {ds.get(\"google_sheets\", {}).get(\"sheet_name\", \"\")}')
"
echo.
echo データソースを変更するには config/settings.json を編集してください
echo.
pause
goto menu

:logintest
echo.
echo === ログインテスト ===
echo ログインテストを開始します...
echo Ctrl+C で停止
echo.
python tests\login_test.py
pause
goto menu

:runbot
echo.
echo === スケジュール自動取引実行 ===
echo スケジュールベースの自動取引を開始します...
echo Ctrl+C で停止
echo.
python bot\linefx_bot.py
pause
goto menu

:manualtest
echo.
echo === 手動取引テスト ===
echo 手動取引テストを開始します...
echo Ctrl+C で停止
echo.
python tests\trading_test.py
pause
goto menu

:showlog
echo.
echo === ログ確認 ===
for %%f in (logs\*.log) do (
    echo 最新ログ: %%f
    type "%%f" | more
    goto :logshown
)
echo ログファイルが見つかりません
:logshown
pause
goto menu

:end
echo Botを終了しました

echo.
echo Bot execution completed.
pause