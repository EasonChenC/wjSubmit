@echo off
chcp 65001 >nul
echo ======================================
echo   问卷自动化 API 服务
echo ======================================
echo.
echo 正在启动服务...
echo API文档: http://localhost:8000/docs
echo.

REM Use the custom launcher that sets event loop policy
python run_api.py

pause
