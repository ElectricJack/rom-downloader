@echo off
rem ROM Downloader - Windows Release Build Script
rem Wrapper for build_release.sh using Git Bash or WSL

setlocal enabledelayedexpansion

echo ROM Downloader Windows Build Script
echo ===================================

rem Check for Git Bash
where bash >nul 2>&1
if %errorlevel% == 0 (
    echo Using Git Bash...
    bash build_release.sh %*
    goto :end
)

rem Check for WSL
where wsl >nul 2>&1
if %errorlevel% == 0 (
    echo Using WSL...
    wsl bash build_release.sh %*
    goto :end
)

rem Try direct execution with MSYS2/Cygwin
if exist "C:\msys64\usr\bin\bash.exe" (
    echo Using MSYS2...
    C:\msys64\usr\bin\bash.exe build_release.sh %*
    goto :end
)

rem Fallback to PowerShell with basic Nuitka build
echo No bash environment found. Attempting basic Nuitka build...
echo This requires Python and Nuitka to be installed.
echo.

rem Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Please install Python 3.11+ and add to PATH.
    pause
    exit /b 1
)

rem Check pip
python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: pip not found. Please install pip.
    pause
    exit /b 1
)

rem Install dependencies
echo Installing dependencies...
python -m pip install nuitka>=1.8.0
python -m pip install -r requirements.txt

rem Create dist directory
if not exist "dist" mkdir dist

rem Basic Nuitka build
echo Building executable...
python -m nuitka ^
    --onefile ^
    --windows-console-mode=disable ^
    --enable-plugin=tk-inter ^
    --enable-plugin=multiprocessing ^
    --windows-product-name="ROMDownloader" ^
    --windows-company-name="ROM Downloader" ^
    --windows-product-version="1.0.0" ^
    --windows-file-version="1.0.0" ^
    --windows-file-description="ROM Download and Management Tool" ^
    --output-dir=dist ^
    --output-filename="ROMDownloader.exe" ^
    --include-data-dir=config=config ^
    --include-data-dir=tools=tools ^
    --include-package=src ^
    --lto=yes ^
    --static-libpython=yes ^
    --remove-output ^
    --assume-yes-for-downloads ^
    --show-progress ^
    main.py

if %errorlevel% == 0 (
    echo.
    echo ================================
    echo Build completed successfully!
    echo ================================
    echo Executable: dist\ROMDownloader.exe
    echo.
) else (
    echo.
    echo Build failed. Check the error messages above.
    pause
    exit /b 1
)

:end
echo.
pause