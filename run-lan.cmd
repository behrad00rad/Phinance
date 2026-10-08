@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run-local.ps1" -Lan
if errorlevel 1 (
  echo.
  pause
)
