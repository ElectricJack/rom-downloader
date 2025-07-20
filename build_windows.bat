@echo off
rem ROM Downloader - Simple Windows Build Script
rem Direct Windows build without shell script dependencies

setlocal enabledelayedexpansion

echo ROM Downloader - Simple Windows Build
echo =====================================
echo.

rem Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Please install Python 3.8+ and add to PATH.
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Python found - OK
python --version

rem Check pip
python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: pip not found. Please install pip.
    pause
    exit /b 1
)

echo pip found - OK

rem Install dependencies
echo.
echo Installing build dependencies...
python -m pip install -r requirements-build.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

rem Create dist directory
echo.
echo Preparing build environment...
if exist "dist" rmdir /s /q "dist"
mkdir "dist"

rem Check for icon
set ICON_ARG=
if exist "icon.ico" (
    set ICON_ARG=--windows-icon-from-ico=icon.ico
    echo Using icon: icon.ico
)

rem Build with Nuitka
echo.
echo Building executable with Nuitka...
echo This may take several minutes...
echo.

python -m nuitka ^
    --onefile ^
    --windows-console-mode=disable ^
    --enable-plugin=tk-inter ^
    --enable-plugin=multiprocessing ^
    --windows-product-name="ROMDownloader" ^
    --windows-company-name="ROM Downloader Project" ^
    --windows-product-version="1.0.0" ^
    --windows-file-version="1.0.0" ^
    --windows-file-description="ROM Download and Management Tool" ^
    --output-dir=dist ^
    --output-filename="ROMDownloader.exe" ^
    --include-data-dir=config=config ^
    --include-data-dir=tools=tools ^
    --include-package=src ^
    --include-package=config ^
    --include-package=gui ^
    --include-package=models ^
    --include-package=downloader ^
    --include-package=scraper ^
    --include-package=processors ^
    --include-package=filters ^
    --include-package=tools ^
    --include-package=state ^
    --include-package=network ^
    --include-package=rom_manager ^
    --include-package=utils ^
    --lto=yes ^
    --static-libpython=yes ^
    --remove-output ^
    --assume-yes-for-downloads ^
    --show-progress ^
    %ICON_ARG% ^
    main.py

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Build failed. Check the error messages above.
    echo.
    echo Common solutions:
    echo - Ensure all dependencies are installed
    echo - Check that Python and pip are up to date
    echo - Try running as Administrator
    echo - Check Windows Defender isn't blocking the build
    pause
    exit /b 1
)

rem Create release package
echo.
echo Packaging release...

set RELEASE_DIR=dist\ROMDownloader_v1.0.0_Windows
mkdir "%RELEASE_DIR%"

rem Copy executable
copy "dist\ROMDownloader.exe" "%RELEASE_DIR%\"

rem Copy data directories
if exist "config" xcopy "config" "%RELEASE_DIR%\config\" /E /I /Q
if exist "tools" xcopy "tools" "%RELEASE_DIR%\tools\" /E /I /Q

rem Copy documentation
if exist "README.md" copy "README.md" "%RELEASE_DIR%\"
if exist "CLAUDE.md" copy "CLAUDE.md" "%RELEASE_DIR%\"
if exist "BUILD.md" copy "BUILD.md" "%RELEASE_DIR%\"
if exist "requirements.txt" copy "requirements.txt" "%RELEASE_DIR%\"

rem Create launcher script
echo @echo off > "%RELEASE_DIR%\launch.bat"
echo title ROM Downloader >> "%RELEASE_DIR%\launch.bat"
echo echo Starting ROM Downloader... >> "%RELEASE_DIR%\launch.bat"
echo ROMDownloader.exe >> "%RELEASE_DIR%\launch.bat"
echo if errorlevel 1 ( >> "%RELEASE_DIR%\launch.bat"
echo     echo. >> "%RELEASE_DIR%\launch.bat"
echo     echo Application exited with error. Press any key to close. >> "%RELEASE_DIR%\launch.bat"
echo     pause ^>nul >> "%RELEASE_DIR%\launch.bat"
echo ) >> "%RELEASE_DIR%\launch.bat"

rem Create ZIP archive (if PowerShell is available)
powershell -Command "if (Test-Path 'dist\ROMDownloader_v1.0.0_Windows') { Compress-Archive -Path 'dist\ROMDownloader_v1.0.0_Windows' -DestinationPath 'dist\ROMDownloader_v1.0.0_Windows.zip' -Force; Write-Host 'ZIP archive created: ROMDownloader_v1.0.0_Windows.zip' }" 2>nul

rem Get file size
for %%A in ("dist\ROMDownloader.exe") do set FILE_SIZE=%%~zA
set /a FILE_SIZE_MB=!FILE_SIZE!/1048576

rem Cleanup
echo.
echo Cleaning up temporary files...
if exist "main.build" rmdir /s /q "main.build" 2>nul
if exist "main.dist" rmdir /s /q "main.dist" 2>nul

rem Show results
echo.
echo ========================================
echo BUILD COMPLETED SUCCESSFULLY!
echo ========================================
echo.
echo Executable: dist\ROMDownloader.exe
echo Size: !FILE_SIZE_MB! MB
echo Location: %RELEASE_DIR%
echo.
if exist "dist\ROMDownloader_v1.0.0_Windows.zip" (
    echo Archive: dist\ROMDownloader_v1.0.0_Windows.zip
    echo.
)
echo Next steps:
echo 1. Test the executable: %RELEASE_DIR%\ROMDownloader.exe
echo 2. Use the launcher: %RELEASE_DIR%\launch.bat
echo 3. Distribute the release folder to users
echo.

rem Test launch (optional)
set /p LAUNCH_TEST="Would you like to test the executable now? (y/n): "
if /i "%LAUNCH_TEST%"=="y" (
    echo.
    echo Testing executable...
    start "" "%RELEASE_DIR%\ROMDownloader.exe"
)

echo.
echo Press any key to close...
pause >nul