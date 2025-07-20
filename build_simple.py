#!/usr/bin/env python3
"""
Simple Python-based build script for ROM Downloader
Alternative to shell script for cross-platform building
"""

import os
import sys
import subprocess
import json
import shutil
import platform
from pathlib import Path


def log(message, level="INFO"):
    """Simple logging function"""
    colors = {
        "INFO": "\033[94m",
        "WARN": "\033[93m", 
        "ERROR": "\033[91m",
        "SUCCESS": "\033[92m"
    }
    reset = "\033[0m"
    color = colors.get(level, "")
    print(f"{color}[{level}]{reset} {message}")


def check_python_version():
    """Check if Python version is adequate"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        log(f"Python {version.major}.{version.minor} detected. Python 3.8+ required.", "ERROR")
        return False
    
    log(f"Python {version.major}.{version.minor} detected - OK", "SUCCESS")
    return True


def install_dependencies():
    """Install build dependencies"""
    log("Installing build dependencies...")
    
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", "requirements-build.txt"
        ], check=True)
        log("Dependencies installed successfully", "SUCCESS")
        return True
    except subprocess.CalledProcessError:
        log("Failed to install dependencies", "ERROR")
        return False


def load_build_config():
    """Load build configuration"""
    config_path = Path("build_config.json")
    if not config_path.exists():
        log("build_config.json not found", "ERROR")
        return None
    
    try:
        with open(config_path) as f:
            config = json.load(f)
        log("Build configuration loaded", "SUCCESS")
        return config
    except Exception as e:
        log(f"Failed to load build config: {e}", "ERROR")
        return None


def prepare_directories():
    """Prepare build directories"""
    log("Preparing directories...")
    
    # Clean and create dist directory
    dist_dir = Path("dist")
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir()
    
    log("Directories prepared", "SUCCESS")
    return dist_dir


def build_with_nuitka(config, dist_dir):
    """Build executable with Nuitka"""
    log("Building executable with Nuitka...")
    
    app_config = config["app"]
    nuitka_config = config["nuitka"]
    
    # Base Nuitka command
    cmd = [
        sys.executable, "-m", "nuitka",
        "main.py"
    ]
    
    # Add basic options
    if nuitka_config.get("onefile", True):
        cmd.append("--onefile")
    
    if nuitka_config.get("console_mode") == "disable":
        cmd.append("--windows-console-mode=disable")
    
    # Add plugins
    for plugin in nuitka_config.get("plugins", []):
        cmd.extend(["--enable-plugin", plugin])
    
    # Add package includes
    for package in nuitka_config.get("include_packages", []):
        cmd.extend(["--include-package", package])
    
    # Add data directories
    for data_dir in nuitka_config.get("include_data_dirs", []):
        cmd.extend(["--include-data-dir", f"{data_dir['source']}={data_dir['target']}"])
    
    # Windows metadata
    cmd.extend([
        "--windows-product-name", app_config["name"],
        "--windows-company-name", app_config["company"],
        "--windows-product-version", app_config["version"],
        "--windows-file-version", app_config["version"],
        "--windows-file-description", app_config["description"]
    ])
    
    # Output options
    cmd.extend([
        "--output-dir", str(dist_dir),
        "--output-filename", f"{app_config['name']}.exe"
    ])
    
    # Optimization options
    if nuitka_config.get("lto", True):
        cmd.append("--lto=yes")
    
    if nuitka_config.get("static_libpython", True):
        cmd.append("--static-libpython=yes")
    
    if nuitka_config.get("remove_output", True):
        cmd.append("--remove-output")
    
    if nuitka_config.get("show_progress", True):
        cmd.append("--show-progress")
    
    if nuitka_config.get("assume_yes_for_downloads", True):
        cmd.append("--assume-yes-for-downloads")
    
    # Cross-compilation for Windows
    if platform.system() != "Windows":
        cross_config = config.get("cross_compilation", {})
        if cross_config.get("mingw64", True):
            cmd.append("--mingw64")
    
    log(f"Running command: {' '.join(cmd)}")
    
    try:
        subprocess.run(cmd, check=True)
        log("Executable built successfully", "SUCCESS")
        return True
    except subprocess.CalledProcessError:
        log("Build failed", "ERROR")
        return False


def package_release(config, dist_dir):
    """Package the release"""
    log("Packaging release...")
    
    app_config = config["app"]
    packaging_config = config.get("packaging", {})
    
    # Create release directory
    release_name = f"{app_config['name']}_v{app_config['version']}_Windows"
    release_dir = dist_dir / release_name
    release_dir.mkdir()
    
    # Copy executable
    exe_name = f"{app_config['name']}.exe"
    shutil.copy(dist_dir / exe_name, release_dir / exe_name)
    
    # Copy data directories
    for data_dir in ["config", "tools"]:
        if Path(data_dir).exists():
            shutil.copytree(data_dir, release_dir / data_dir)
    
    # Copy additional files
    for file_name in packaging_config.get("include_files", []):
        if Path(file_name).exists():
            shutil.copy(file_name, release_dir / file_name)
    
    # Create launcher script
    launcher_content = f"""@echo off
title {app_config['name']}
echo Starting {app_config['name']}...
{exe_name}
if errorlevel 1 (
    echo.
    echo Application exited with error. Press any key to close.
    pause >nul
)
"""
    with open(release_dir / "launch.bat", "w") as f:
        f.write(launcher_content)
    
    # Create ZIP if requested
    if packaging_config.get("create_zip", True):
        zip_name = f"{release_name}.zip"
        try:
            shutil.make_archive(
                str(dist_dir / release_name), 
                'zip', 
                release_dir
            )
            log(f"Created archive: {zip_name}", "SUCCESS")
        except Exception as e:
            log(f"Failed to create ZIP: {e}", "WARN")
    
    log(f"Release packaged: {release_dir}", "SUCCESS")
    return release_dir


def verify_build(release_dir, app_name):
    """Verify the build"""
    log("Verifying build...")
    
    exe_path = release_dir / f"{app_name}.exe"
    if not exe_path.exists():
        log(f"Executable not found: {exe_path}", "ERROR")
        return False
    
    # Check file size
    size = exe_path.stat().st_size
    size_mb = size / (1024 * 1024)
    log(f"Executable size: {size_mb:.1f} MB", "INFO")
    
    if size < 1024:  # Less than 1KB is suspicious
        log("Executable seems too small", "WARN")
    
    log("Build verification completed", "SUCCESS")
    return True


def main():
    """Main build function"""
    print("=" * 50)
    print("ROM Downloader - Simple Build Script")
    print("=" * 50)
    
    # Check environment
    if not check_python_version():
        return 1
    
    # Load configuration
    config = load_build_config()
    if not config:
        return 1
    
    # Install dependencies
    if not install_dependencies():
        return 1
    
    # Prepare directories
    dist_dir = prepare_directories()
    
    # Build executable
    if not build_with_nuitka(config, dist_dir):
        return 1
    
    # Package release
    release_dir = package_release(config, dist_dir)
    
    # Verify build
    if not verify_build(release_dir, config["app"]["name"]):
        return 1
    
    print("\n" + "=" * 50)
    print("🎉 Build completed successfully!")
    print("=" * 50)
    print(f"📁 Release directory: {release_dir}")
    print(f"🚀 Executable: {config['app']['name']}.exe")
    print("\nNext steps:")
    print("1. Test the executable on a Windows machine")
    print("2. Distribute the release folder to users")
    print("3. Consider code signing for production releases")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())