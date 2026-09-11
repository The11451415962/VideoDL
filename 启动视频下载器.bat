@echo off
chcp 65001 >nul
title 视频下载器
cd /d "%~dp0"

echo ============================================
echo   视频下载器 - Fluent 版启动器
echo ============================================
echo.

rem ---- 检查 Python ----
where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 未找到 Python。
    echo 请先安装 Python 3.10 或更高版本，并在安装时勾选 "Add Python to PATH"。
    echo 下载地址：https://www.python.org/downloads/
    pause
    exit /b 1
)

rem ---- 检查 PySide6，缺失则自动安装 ----
python -c "import PySide6" >nul 2>nul
if errorlevel 1 (
    echo 首次运行：正在安装 PySide6（约 200MB），请稍候...
    python -m pip install PySide6
    if errorlevel 1 (
        echo.
        echo [错误] PySide6 安装失败。
        echo 请手动打开命令行执行： pip install PySide6
        pause
        exit /b 1
    )
    echo 安装完成。
)

echo 正在启动...
echo.

rem ---- 运行程序 ----
python video_downloader_qt.py
if errorlevel 1 (
    echo.
    echo [错误] 程序运行出错，请把上面的信息发给作者。
    pause
)
