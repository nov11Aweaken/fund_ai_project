@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "EXIT_CODE=0"
set "PY_CMD=python"
set "EXE_PREFIX=基你太美"
if exist ".\.venv\Scripts\python.exe" set "PY_CMD=.\.venv\Scripts\python.exe"

echo ==========================================
echo           One-Click EXE Builder
echo ==========================================
echo [INFO] Python: %PY_CMD%

REM Clean up running main.exe processes to avoid file lock issues
echo [INFO] Checking for running processes...
tasklist | find /i "main.exe" >nul 2>nul
if not errorlevel 1 (
  echo [INFO] Found running main.exe, terminating...
  taskkill /IM main.exe /F >nul 2>nul
  timeout /t 1 /nobreak >nul
)

REM Get current date in YYYYMMDD format
REM Supports both English and localized date formats
for /f "tokens=1-4 delims=/- " %%a in ('wmic os get LocalDateTime ^| find "20"') do (
  set "DATE_STR=%%a"
)
if not "!DATE_STR!"=="" set "DATE_STR=!DATE_STR:~0,8!"

if "!DATE_STR!"=="" (
  REM Fallback to alternative method
  for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (
    set "mm=%%a"
    set "dd=%%b"
    set "yyyy=%%c"
  )
  set "DATE_STR=!yyyy!!mm!!dd!"
)

echo.
echo ==========================================
echo FILE NAME FORMAT: !EXE_PREFIX!_!DATE_STR!_[YOUR_INPUT].exe
echo ==========================================
echo.
set /p USER_INPUT=Enter the suffix for EXE name (no .exe needed):

if "!USER_INPUT!"=="" (
  echo [ERROR] The suffix cannot be empty.
  set "EXIT_CODE=1"
  goto :end
)

set "RAW_USER_INPUT=!USER_INPUT!"
for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $value = $env:RAW_USER_INPUT; $invalid = [System.IO.Path]::GetInvalidFileNameChars(); $pattern = '[' + [Regex]::Escape((-join $invalid)) + ']'; $safe = [Regex]::Replace($value, $pattern, '_').Trim(); Write-Output $safe"`) do (
  set "SAFE_USER_INPUT=%%i"
)

if "!SAFE_USER_INPUT!"=="" (
  echo [ERROR] The suffix cannot be empty after removing invalid file name characters.
  set "EXIT_CODE=1"
  goto :end
)

set "EXE_NAME=!EXE_PREFIX!_!DATE_STR!_!SAFE_USER_INPUT!"

where python >nul 2>nul
if errorlevel 1 (
  if not exist "%PY_CMD%" (
    echo [ERROR] Python was not found.
    set "EXIT_CODE=1"
    goto :end
  )
)

%PY_CMD% -c "import flet" >nul 2>nul
if errorlevel 1 (
  echo [INFO] Installing project dependencies...
  %PY_CMD% -m pip install -r .\requirements.txt
  if errorlevel 1 (
    echo [ERROR] Failed to install requirements.
    set "EXIT_CODE=1"
    goto :end
  )
)

%PY_CMD% -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
  echo [INFO] Installing PyInstaller...
  %PY_CMD% -m pip install pyinstaller
  if errorlevel 1 (
    echo [ERROR] Failed to install PyInstaller.
    set "EXIT_CODE=1"
    goto :end
  )
)

echo [INFO] Building with PyInstaller...
%PY_CMD% -m PyInstaller --clean .\main.spec
if errorlevel 1 (
  echo [ERROR] Build failed. Check logs above.
  set "EXIT_CODE=1"
  goto :end
)

if not exist ".\dist\main.exe" (
  echo [ERROR] dist\main.exe was not generated.
  set "EXIT_CODE=1"
  goto :end
)

copy /Y ".\dist\main.exe" ".\dist\!EXE_NAME!.exe" >nul
if errorlevel 1 (
  echo [ERROR] 文件复制失败。
  set "EXIT_CODE=1"
  goto :end
)

echo.
echo ==========================================
echo [✓ 完成] 生成文件: .\dist\!EXE_NAME!.exe
echo ==========================================
echo.

:end
endlocal
exit /b %EXIT_CODE%
