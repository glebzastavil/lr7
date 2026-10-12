@echo off
chcp 65001 >nul
title TrafficEditor
color 0A

echo ========================================
echo   Запуск TrafficEditor
echo ========================================
echo.

:: Проверяем Python
python --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo [ОШИБКА] Python не найден!
    echo Установите Python с https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Проверяем main.py
if not exist "main.py" (
    color 0C
    echo [ОШИБКА] Файл main.py не найден!
    echo Положите main.py в ту же папку, что и run.bat
    pause
    exit /b 1
)

:: Устанавливаем PyQt5 если нужно
python -c "import PyQt5" >nul 2>&1
if errorlevel 1 (
    echo Установка PyQt5...
    pip install PyQt5
)

echo Запуск программы...
echo.

:: Запускаем Python-скрипт
python main.py

echo.
echo Программа завершена.
pause