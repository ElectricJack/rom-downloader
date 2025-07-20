# ROM Downloader - Windows PowerShell Build Script
# Native PowerShell implementation for Windows users

param(
    [string]$Mode = "build",
    [switch]$CleanOnly,
    [switch]$NoCleanup,
    [switch]$VerifyOnly,
    [switch]$Help
)

# Configuration
$AppName = "ROMDownloader"
$Version = "1.0.0"
$ProjectRoot = $PSScriptRoot
$DistDir = Join-Path $ProjectRoot "dist"
$BuildDir = Join-Path $ProjectRoot "build"

# Colors for output
function Write-ColorMessage {
    param(
        [string]$Message,
        [string]$Level = "INFO"
    )
    
    $colors = @{
        "INFO" = "Cyan"
        "WARN" = "Yellow"
        "ERROR" = "Red"
        "SUCCESS" = "Green"
    }
    
    $color = $colors[$Level]
    if ($color) {
        Write-Host "[$Level] $Message" -ForegroundColor $color
    } else {
        Write-Host "[$Level] $Message"
    }
}

function Show-Usage {
    Write-Host "ROM Downloader - PowerShell Build Script"
    Write-Host ""
    Write-Host "Usage: .\build_release.ps1 [OPTIONS]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -CleanOnly     Only clean build artifacts"
    Write-Host "  -NoCleanup     Skip cleanup after build"
    Write-Host "  -VerifyOnly    Only verify existing build"
    Write-Host "  -Help          Show this help message"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\build_release.ps1                # Basic build"
    Write-Host "  .\build_release.ps1 -CleanOnly     # Clean only"
    Write-Host "  .\build_release.ps1 -NoCleanup     # Build without cleanup"
}

function Test-Prerequisites {
    Write-ColorMessage "Checking prerequisites..." "INFO"
    
    # Check Python
    try {
        $pythonVersion = python --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-ColorMessage "Python found: $pythonVersion" "SUCCESS"
        } else {
            Write-ColorMessage "Python not found. Please install Python 3.8+ and add to PATH." "ERROR"
            return $false
        }
    } catch {
        Write-ColorMessage "Python not found. Please install Python 3.8+ and add to PATH." "ERROR"
        return $false
    }
    
    # Check pip
    try {
        $pipVersion = python -m pip --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-ColorMessage "pip found: $pipVersion" "SUCCESS"
        } else {
            Write-ColorMessage "pip not found. Please install pip." "ERROR"
            return $false
        }
    } catch {
        Write-ColorMessage "pip not found. Please install pip." "ERROR"
        return $false
    }
    
    return $true
}

function Install-Dependencies {
    Write-ColorMessage "Installing build dependencies..." "INFO"
    
    try {
        python -m pip install -r requirements-build.txt
        if ($LASTEXITCODE -eq 0) {
            Write-ColorMessage "Dependencies installed successfully" "SUCCESS"
            return $true
        } else {
            Write-ColorMessage "Failed to install dependencies" "ERROR"
            return $false
        }
    } catch {
        Write-ColorMessage "Failed to install dependencies" "ERROR"
        return $false
    }
}

function Initialize-BuildEnvironment {
    Write-ColorMessage "Preparing build environment..." "INFO"
    
    # Clean previous builds
    if (Test-Path $BuildDir) {
        Write-ColorMessage "Cleaning previous build directory..." "INFO"
        Remove-Item $BuildDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    
    if (Test-Path $DistDir) {
        Write-ColorMessage "Cleaning previous dist directory..." "INFO"
        Remove-Item $DistDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    
    # Create directories
    New-Item -ItemType Directory -Path $BuildDir -Force | Out-Null
    New-Item -ItemType Directory -Path $DistDir -Force | Out-Null
    
    Write-ColorMessage "Build environment prepared" "SUCCESS"
}

function Get-BuildConfig {
    $configPath = Join-Path $ProjectRoot "build_config.json"
    if (-not (Test-Path $configPath)) {
        Write-ColorMessage "build_config.json not found" "ERROR"
        return $null
    }
    
    try {
        $config = Get-Content $configPath -Raw | ConvertFrom-Json
        Write-ColorMessage "Build configuration loaded" "SUCCESS"
        return $config
    } catch {
        Write-ColorMessage "Failed to load build config: $($_.Exception.Message)" "ERROR"
        return $null
    }
}

function Build-Executable {
    param([object]$Config)
    
    Write-ColorMessage "Building executable with Nuitka..." "INFO"
    
    $appConfig = $Config.app
    $nuitkaConfig = $Config.nuitka
    
    # Build Nuitka command
    $cmd = @(
        "python", "-m", "nuitka",
        "main.py"
    )
    
    # Add basic options
    if ($nuitkaConfig.onefile) {
        $cmd += "--onefile"
    }
    
    if ($nuitkaConfig.console_mode -eq "disable") {
        $cmd += "--windows-console-mode=disable"
    }
    
    # Add plugins
    foreach ($plugin in $nuitkaConfig.plugins) {
        $cmd += "--enable-plugin=$plugin"
    }
    
    # Add package includes
    foreach ($package in $nuitkaConfig.include_packages) {
        $cmd += "--include-package=$package"
    }
    
    # Add data directories
    foreach ($dataDir in $nuitkaConfig.include_data_dirs) {
        $source = $dataDir.source
        $target = $dataDir.target
        $cmd += "--include-data-dir=$source=$target"
    }
    
    # Windows metadata
    $cmd += @(
        "--windows-product-name=$($appConfig.name)",
        "--windows-company-name=$($appConfig.company)",
        "--windows-product-version=$($appConfig.version)",
        "--windows-file-version=$($appConfig.version)",
        "--windows-file-description=$($appConfig.description)"
    )
    
    # Output options
    $cmd += @(
        "--output-dir=$DistDir",
        "--output-filename=$($appConfig.name).exe"
    )
    
    # Optimization options
    if ($nuitkaConfig.lto) {
        $cmd += "--lto=yes"
    }
    
    if ($nuitkaConfig.static_libpython) {
        $cmd += "--static-libpython=yes"
    }
    
    if ($nuitkaConfig.remove_output) {
        $cmd += "--remove-output"
    }
    
    if ($nuitkaConfig.show_progress) {
        $cmd += "--show-progress"
    }
    
    if ($nuitkaConfig.assume_yes_for_downloads) {
        $cmd += "--assume-yes-for-downloads"
    }
    
    # Check for icon
    $iconPath = Join-Path $ProjectRoot "icon.ico"
    if (Test-Path $iconPath) {
        $cmd += "--windows-icon-from-ico=$iconPath"
        Write-ColorMessage "Using icon: $iconPath" "INFO"
    }
    
    Write-ColorMessage "Running Nuitka command..." "INFO"
    Write-ColorMessage "Command: $($cmd -join ' ')" "INFO"
    
    try {
        & $cmd[0] $cmd[1..($cmd.Length-1)]
        if ($LASTEXITCODE -eq 0) {
            Write-ColorMessage "Executable built successfully" "SUCCESS"
            return $true
        } else {
            Write-ColorMessage "Build failed with exit code $LASTEXITCODE" "ERROR"
            return $false
        }
    } catch {
        Write-ColorMessage "Build failed: $($_.Exception.Message)" "ERROR"
        return $false
    }
}

function New-ReleasePackage {
    param([object]$Config)
    
    Write-ColorMessage "Packaging release..." "INFO"
    
    $appConfig = $Config.app
    $packagingConfig = $Config.packaging
    
    # Create release directory
    $releaseName = "$($appConfig.name)_v$($appConfig.version)_Windows"
    $releaseDir = Join-Path $DistDir $releaseName
    New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null
    
    # Copy executable
    $exeName = "$($appConfig.name).exe"
    $sourcePath = Join-Path $DistDir $exeName
    $targetPath = Join-Path $releaseDir $exeName
    
    if (Test-Path $sourcePath) {
        Copy-Item $sourcePath $targetPath
        Write-ColorMessage "Copied executable: $exeName" "INFO"
    } else {
        Write-ColorMessage "Executable not found: $sourcePath" "ERROR"
        return $false
    }
    
    # Copy data directories
    foreach ($dirName in @("config", "tools")) {
        $sourceDirPath = Join-Path $ProjectRoot $dirName
        if (Test-Path $sourceDirPath) {
            $targetDirPath = Join-Path $releaseDir $dirName
            Copy-Item $sourceDirPath $targetDirPath -Recurse -Force
            Write-ColorMessage "Copied directory: $dirName" "INFO"
        }
    }
    
    # Copy additional files
    if ($packagingConfig.include_files) {
        foreach ($fileName in $packagingConfig.include_files) {
            $sourceFilePath = Join-Path $ProjectRoot $fileName
            if (Test-Path $sourceFilePath) {
                $targetFilePath = Join-Path $releaseDir $fileName
                Copy-Item $sourceFilePath $targetFilePath
                Write-ColorMessage "Copied file: $fileName" "INFO"
            }
        }
    }
    
    # Create launcher script
    $launcherLines = @(
        "@echo off",
        "title $($appConfig.name)",
        "echo Starting $($appConfig.name)...",
        "$exeName",
        "if errorlevel 1 (",
        "    echo.",
        "    echo Application exited with error. Press any key to close.",
        "    pause >nul",
        ")"
    )
    
    $launcherPath = Join-Path $releaseDir "launch.bat"
    Set-Content -Path $launcherPath -Value ($launcherLines -join "`r`n")
    Write-ColorMessage "Created launcher script" "INFO"
    
    # Create ZIP archive if requested
    if ($packagingConfig.create_zip) {
        $zipName = "$releaseName.zip"
        $zipPath = Join-Path $DistDir $zipName
        
        try {
            Compress-Archive -Path $releaseDir -DestinationPath $zipPath -Force
            Write-ColorMessage "Created archive: $zipName" "SUCCESS"
        } catch {
            Write-ColorMessage "Failed to create ZIP: $($_.Exception.Message)" "WARN"
        }
    }
    
    Write-ColorMessage "Release packaged: $releaseDir" "SUCCESS"
    return $releaseDir
}

function Test-Build {
    param([string]$ReleaseDir, [string]$ExeName)
    
    Write-ColorMessage "Verifying build..." "INFO"
    
    $exePath = Join-Path $ReleaseDir $ExeName
    if (-not (Test-Path $exePath)) {
        Write-ColorMessage "Executable not found: $exePath" "ERROR"
        return $false
    }
    
    # Check file size
    $fileInfo = Get-Item $exePath
    $sizeMB = [math]::Round($fileInfo.Length / 1MB, 1)
    Write-ColorMessage "Executable size: $sizeMB MB" "INFO"
    
    if ($fileInfo.Length -lt 1024) {
        Write-ColorMessage "Executable seems too small" "WARN"
    }
    
    Write-ColorMessage "Build verification completed" "SUCCESS"
    return $true
}

function Clear-BuildArtifacts {
    Write-ColorMessage "Cleaning up build artifacts..." "INFO"
    
    # Remove Python cache
    Get-ChildItem -Path $ProjectRoot -Name "__pycache__" -Recurse -Directory | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path $ProjectRoot -Name "*.pyc" -Recurse -File | Remove-Item -Force -ErrorAction SilentlyContinue
    
    # Remove Nuitka build directories
    $nuitkaBuilds = @("main.build", "main.dist")
    foreach ($dir in $nuitkaBuilds) {
        $dirPath = Join-Path $ProjectRoot $dir
        if (Test-Path $dirPath) {
            Remove-Item $dirPath -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    
    Write-ColorMessage "Cleanup completed" "SUCCESS"
}

# Main execution
function Main {
    Write-Host "=" * 50
    Write-ColorMessage "ROM Downloader - PowerShell Build Script" "INFO"
    Write-ColorMessage "Version: $Version" "INFO"
    Write-Host "=" * 50
    
    if ($Help) {
        Show-Usage
        return 0
    }
    
    if ($CleanOnly) {
        Clear-BuildArtifacts
        return 0
    }
    
    if ($VerifyOnly) {
        $config = Get-BuildConfig
        if (-not $config) { return 1 }
        
        $releaseDir = Join-Path $DistDir "$($config.app.name)_v$($config.app.version)_Windows"
        $result = Test-Build $releaseDir "$($config.app.name).exe"
        return if ($result) { 0 } else { 1 }
    }
    
    $startTime = Get-Date
    
    # Main build process
    if (-not (Test-Prerequisites)) { return 1 }
    if (-not (Install-Dependencies)) { return 1 }
    
    Initialize-BuildEnvironment
    
    $config = Get-BuildConfig
    if (-not $config) { return 1 }
    
    if (-not (Build-Executable $config)) { return 1 }
    
    $releaseDir = New-ReleasePackage $config
    if (-not $releaseDir) { return 1 }
    
    if (-not (Test-Build $releaseDir "$($config.app.name).exe")) { return 1 }
    
    if (-not $NoCleanup) {
        Clear-BuildArtifacts
    }
    
    $endTime = Get-Date
    $duration = ($endTime - $startTime).TotalSeconds
    
    Write-ColorMessage "Build completed successfully in $([math]::Round($duration, 1))s" "SUCCESS"
    Write-ColorMessage "Release files are in: $DistDir" "INFO"
    
    Write-Host ""
    Write-Host "=" * 50
    Write-Host "🎉 ROM Downloader Windows Build Ready!" -ForegroundColor Green
    Write-Host "=" * 50
    Write-Host "📁 Location: $releaseDir" -ForegroundColor Cyan
    Write-Host "🚀 Executable: $($config.app.name).exe" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Next steps:"
    Write-Host "1. Test the executable on a Windows machine"
    Write-Host "2. Distribute the release folder to users"
    Write-Host "3. Consider code signing for production releases"
    
    return 0
}

# Handle Ctrl+C gracefully
trap {
    Write-ColorMessage "Build interrupted" "ERROR"
    Clear-BuildArtifacts
    exit 1
}

exit (Main)