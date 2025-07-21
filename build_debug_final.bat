@echo off
rem Final debug build with complete module inclusion

echo Building debug ROM Downloader with complete module inclusion...

if exist "dist\main.build" rmdir /s /q "dist\main.build"
if exist "dist\main.dist" rmdir /s /q "dist\main.dist"

python -m nuitka ^
    --standalone ^
    --windows-console-mode=attach ^
    --enable-plugin=tk-inter ^
    --output-dir=dist ^
    --output-filename=ROMDownloader_debug.exe ^
    --include-data-dir=config=config ^
    --include-data-dir=tools=tools ^
    --follow-imports ^
    --include-module=src ^
    --include-module=src.config ^
    --include-module=src.config.enhanced_config_manager ^
    --include-module=src.gui ^
    --include-module=src.gui.game_library_gui ^
    --include-module=src.models ^
    --include-module=src.downloader ^
    --include-module=src.scraper ^
    --include-module=src.processors ^
    --include-module=src.filters ^
    --include-module=src.tools ^
    --include-module=src.tools.base ^
    --include-module=src.state ^
    --include-module=src.network ^
    --include-module=src.rom_manager ^
    --include-module=src.utils ^
    --include-module=src.utils.dirs ^
    --windows-product-name="ROMDownloader" ^
    --windows-file-description="ROM Download Tool" ^
    --windows-product-version="1.0.0" ^
    --windows-file-version="1.0.0" ^
    --assume-yes-for-downloads ^
    --show-progress ^
    main.py

if %errorlevel% neq 0 (
    echo Build failed!
    pause
    exit /b 1
)

echo.
echo Testing debug executable...
if exist "dist\main.dist\ROMDownloader_debug.exe" (
    echo Build successful!
    echo.
    echo Running debug version...
    "dist\main.dist\ROMDownloader_debug.exe"
) else (
    echo ERROR: Debug executable not found!
)

pause