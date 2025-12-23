@echo off
echo 🚀 Запуск API сервера...
echo 📦 Установка зависимостей...

REM Создание виртуального окружения (опционально)
python -m venv venv 2>nul
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

REM Установка зависимостей
pip install -r requirements.txt

echo ✅ Зависимости установлены
echo 🌐 Запуск сервера на http://0.0.0.0:5000
echo 📡 Endpoints:
echo    - GET /api/test - тест сервера
echo    - GET /api/test-db - тест БД
echo    - GET /api/region/<код> - данные региона
echo    - GET /api/regions - список регионов

python api_server.py
pause