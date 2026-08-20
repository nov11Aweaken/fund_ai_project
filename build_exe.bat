@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "EXIT_CODE=0"
set "PY_EXE="
set "PY_ARGS="
set "EXE_PREFIX=基你太美"
set "BUILD_TOOLS_DIR=%CD%\.build_tools"
set "BUILD_VENV=%CD%\.build_tools\venv"
set "BUILD_PYTHON=%CD%\.build_tools\venv\Scripts\python.exe"

REM Prefer a healthy project virtual environment, then a system Python.
if exist ".\.venv\Scripts\python.exe" (
  ".\.venv\Scripts\python.exe" --version >nul 2>nul
  if not errorlevel 1 (
    set "PY_EXE=%CD%\.venv\Scripts\python.exe"
  ) else (
    echo [WARN] .venv is unavailable and will be skipped.
  )
)

if not defined PY_EXE (
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3 --version >nul 2>nul
    if not errorlevel 1 (
      set "PY_EXE=py"
      set "PY_ARGS=-3"
    )
  )
)

if not defined PY_EXE (
  where python >nul 2>nul
  if not errorlevel 1 (
    python --version >nul 2>nul
    if not errorlevel 1 set "PY_EXE=python"
  )
)

REM If Windows has no working Python, let uv create an isolated build environment.
if not defined PY_EXE (
  where uv >nul 2>nul
  if errorlevel 1 (
    echo [ERROR] No working Python was found, and uv is not installed.
    echo [INFO] Install Python 3.12 or uv, then run this script again.
    set "EXIT_CODE=1"
    goto :end
  )

  set "UV_CACHE_DIR=!BUILD_TOOLS_DIR!\uv-cache"
  set "UV_PYTHON_INSTALL_DIR=!BUILD_TOOLS_DIR!\python"
  set "UV_LINK_MODE=copy"

  if exist "!BUILD_PYTHON!" (
    "!BUILD_PYTHON!" --version >nul 2>nul
    if not errorlevel 1 (
      "!BUILD_PYTHON!" -m pip --version >nul 2>nul
      if not errorlevel 1 set "PY_EXE=!BUILD_PYTHON!"
    )
  )

  if not defined PY_EXE (
    echo [INFO] No working Python found. Creating an isolated Python 3.12 build environment with uv...
    uv venv --python 3.12 --seed --clear "!BUILD_VENV!"
    if errorlevel 1 (
      echo [ERROR] Failed to create the isolated build environment.
      set "EXIT_CODE=1"
      goto :end
    )
    set "PY_EXE=!BUILD_PYTHON!"
  )
)

echo ==========================================
echo           One-Click EXE Builder
echo ==========================================
echo [INFO] Python: !PY_EXE! !PY_ARGS!

REM Get current date in YYYYMMDD format
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "DATE_STR=%%i"
if not defined DATE_STR set "DATE_STR=unknown_date"

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

"%PY_EXE%" %PY_ARGS% -m pip --version >nul 2>nul
if errorlevel 1 (
  echo [INFO] Initializing pip...
  "%PY_EXE%" %PY_ARGS% -m ensurepip --upgrade
  if errorlevel 1 (
    echo [ERROR] Failed to initialize pip.
    set "EXIT_CODE=1"
    goto :end
  )
)

"%PY_EXE%" %PY_ARGS% -c "import akshare, certifi, flet, matplotlib, mplfinance, pandas, pyecharts, requests" >nul 2>nul
if errorlevel 1 (
  echo [INFO] Installing project dependencies...
  "%PY_EXE%" %PY_ARGS% -m pip install -r .\requirements.txt
  if errorlevel 1 (
    echo [ERROR] Failed to install requirements.
    set "EXIT_CODE=1"
    goto :end
  )
)

"%PY_EXE%" %PY_ARGS% -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
  echo [INFO] Installing PyInstaller...
  "%PY_EXE%" %PY_ARGS% -m pip install pyinstaller
  if errorlevel 1 (
    echo [ERROR] Failed to install PyInstaller.
    set "EXIT_CODE=1"
    goto :end
  )
)

REM Clean up running executables only after the build environment is ready.
echo [INFO] Checking for running processes...
tasklist | find /i "main.exe" >nul 2>nul
if not errorlevel 1 (
  echo [INFO] Found running main.exe, terminating...
  taskkill /IM main.exe /F >nul 2>nul
  timeout /t 1 /nobreak >nul
)
echo [INFO] Building with PyInstaller...
"%PY_EXE%" %PY_ARGS% -m PyInstaller --clean .\main.spec
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
