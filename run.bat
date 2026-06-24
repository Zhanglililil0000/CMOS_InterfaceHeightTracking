@echo off
chcp 65001 >nul

set "CONDA_ENV=C:\ProgramData\anaconda3\envs\py310"
set "PATH=%CONDA_ENV%;%CONDA_ENV%\Scripts;%CONDA_ENV%\Library\bin;%PATH%"

cd /d "%~dp0src"

echo ============================================
echo   CMOS 高度控制 - 后端服务启动
echo ============================================
echo.

echo [1/2] 检查依赖...
pip install -r "%~dp0requirements.txt" -q
if %errorlevel% neq 0 (
    echo 依赖安装失败，请检查Python环境和网络连接
    pause
    exit /b 1
)
echo 依赖检查完成
echo.

echo [2/2] 启动服务...
echo 服务地址: http://localhost:8082
echo 按 Ctrl+C 停止服务
echo ============================================
echo.

python server.py

pause
