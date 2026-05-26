@echo off
REM Mobilgene Config Studio — double-click friendly launcher
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-dev.ps1"
if errorlevel 1 pause
REM 서버 종료 후 창 유지
