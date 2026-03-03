@echo off
setlocal
cd /d "%~dp0"

set "EXIT_CODE=0"
set "PY_CMD=python"
if exist ".\.venv\Scripts\python.exe" set "PY_CMD=.\.venv\Scripts\python.exe"

echo ==========================================
echo           One-Click EXE Builder
echo ==========================================
echo [INFO] Python: %PY_CMD%
set /p EXE_NAME=Enter output EXE name (without .exe): 

if "%EXE_NAME%"=="" (
  echo [ERROR] Name cannot be empty.
  set "EXIT_CODE=1"
  goto :end
)

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

copy /Y ".\dist\main.exe" ".\dist\%EXE_NAME%.exe" >nul
if errorlevel 1 (
  echo [ERROR] Failed to create named EXE.
  set "EXIT_CODE=1"
  goto :end
)

echo [DONE] Created: .\dist\%EXE_NAME%.exe

:end
endlocal
exit /b %EXIT_CODE%
