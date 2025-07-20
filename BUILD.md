# ROM Downloader - Build Instructions

This document explains how to build ROM Downloader into a standalone Windows executable using Nuitka.

## Quick Start

### Option 1: Shell Script (Recommended)
```bash
# Linux/WSL/Git Bash
./build_release.sh

# Windows Command Prompt
build_release.bat
```

### Option 2: Python Script (Cross-platform)
```bash
python build_simple.py
```

## Prerequisites

### System Requirements
- **Python 3.8+** (Python 3.11+ recommended)
- **pip** package manager
- **Git** (for version control)
- **7-Zip or zip** (for creating archives)

### Platform-Specific Requirements

#### Windows
- **Visual Studio Build Tools** or **MinGW-w64** for compilation
- **Git Bash** (recommended) or **WSL** for shell script execution

#### Linux/WSL
- **MinGW-w64** for cross-compilation to Windows
- **Wine** (optional, for testing Windows executables)

```bash
# Ubuntu/Debian
sudo apt-get install mingw-w64 wine

# Fedora/RHEL
sudo dnf install mingw64-gcc wine

# Arch Linux
sudo pacman -S mingw-w64-gcc wine
```

#### macOS
- **Xcode Command Line Tools**
- **MinGW-w64** via Homebrew for cross-compilation

```bash
brew install mingw-w64
```

## Build Methods

### Method 1: Advanced Shell Script

The `build_release.sh` script provides the most comprehensive build process with full customization options.

#### Features
- Automatic dependency installation
- Cross-platform compilation
- Optimized executable generation
- Release packaging with ZIP archives
- Build verification
- Comprehensive logging

#### Usage
```bash
# Basic build
./build_release.sh

# Clean previous builds only
./build_release.sh --clean-only

# Build without cleanup
./build_release.sh --no-cleanup

# Verify existing build
./build_release.sh --verify-only

# Help
./build_release.sh --help
```

#### Environment Variables
```bash
# Set custom Nuitka cache directory
export NUITKA_CACHE_DIR="/tmp/nuitka_cache"

# Set number of build jobs
export BUILD_JOBS=8

# Custom Python command
export PYTHON_CMD="python3.11"
```

### Method 2: Windows Batch Script

The `build_release.bat` script provides Windows-native build support.

#### Features
- Automatic detection of Bash environments (Git Bash, WSL, MSYS2)
- Fallback to native Windows PowerShell/CMD execution
- Simplified Nuitka command execution

#### Usage
```cmd
# Run from Windows Command Prompt
build_release.bat

# With arguments (passed to shell script if available)
build_release.bat --no-cleanup
```

### Method 3: Python Build Script

The `build_simple.py` script provides a pure Python build solution.

#### Features
- Cross-platform Python execution
- JSON-based configuration
- Simplified build process
- Suitable for CI/CD integration

#### Usage
```bash
# Basic build
python build_simple.py

# With specific Python version
python3.11 build_simple.py
```

### Method 4: Manual Nuitka Build

For advanced users who want full control over the build process.

```bash
# Install dependencies
pip install -r requirements-build.txt

# Basic Nuitka command
python -m nuitka \
    --onefile \
    --windows-console-mode=disable \
    --enable-plugin=tk-inter \
    --enable-plugin=multiprocessing \
    --windows-product-name="ROMDownloader" \
    --windows-company-name="ROM Downloader" \
    --windows-product-version="1.0.0" \
    --output-dir=dist \
    --output-filename="ROMDownloader.exe" \
    --include-data-dir=config=config \
    --include-data-dir=tools=tools \
    --include-package=src \
    --lto=yes \
    --static-libpython=yes \
    --remove-output \
    --assume-yes-for-downloads \
    --show-progress \
    main.py
```

## Configuration

### Build Configuration File

The `build_config.json` file contains all build settings:

```json
{
  "app": {
    "name": "ROMDownloader",
    "version": "1.0.0",
    "description": "ROM Download and Management Tool"
  },
  "nuitka": {
    "onefile": true,
    "console_mode": "disable",
    "plugins": ["tk-inter", "multiprocessing"]
  }
}
```

### Customizing the Build

#### Changing App Information
Edit the `app` section in `build_config.json`:
```json
{
  "app": {
    "name": "MyROMDownloader",
    "version": "2.0.0",
    "description": "Custom ROM Tool"
  }
}
```

#### Adding Custom Icons
1. Place your `icon.ico` file in the project root
2. The build script will automatically detect and use it
3. For manual builds, add: `--windows-icon-from-ico=icon.ico`

#### Including Additional Files
Modify the `include_data_dirs` in `build_config.json`:
```json
{
  "nuitka": {
    "include_data_dirs": [
      {"source": "config", "target": "config"},
      {"source": "tools", "target": "tools"},
      {"source": "docs", "target": "docs"}
    ]
  }
}
```

## Output Structure

After a successful build, you'll find:

```
dist/
├── ROMDownloader_v1.0.0_Windows/
│   ├── ROMDownloader.exe          # Main executable
│   ├── config/                    # Configuration files
│   ├── tools/                     # External tools
│   ├── README.md                  # Documentation
│   ├── CLAUDE.md                  # Project instructions
│   ├── requirements.txt           # Dependencies reference
│   └── launch.bat                 # Launcher script
└── ROMDownloader_v1.0.0_Windows.zip  # Distribution archive
```

## Troubleshooting

### Common Issues

#### Python Not Found
```bash
# Linux/macOS
which python3
export PATH="/usr/local/bin:$PATH"

# Windows
where python
# Add Python to PATH in System Environment Variables
```

#### Nuitka Installation Failed
```bash
# Update pip first
python -m pip install --upgrade pip

# Install with specific version
python -m pip install "nuitka>=1.8.0"

# Clear pip cache if needed
python -m pip cache purge
```

#### MinGW-w64 Not Found (Linux/macOS)
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install gcc-mingw-w64

# macOS
brew install mingw-w64
```

#### Permission Denied
```bash
# Make scripts executable
chmod +x build_release.sh build_simple.py

# Windows: Run as Administrator if needed
```

#### Build Memory Issues
```bash
# Reduce parallel jobs
export BUILD_JOBS=2

# Clear Nuitka cache
rm -rf ~/.nuitka
```

#### Missing Dependencies
```bash
# Install all build dependencies
pip install -r requirements-build.txt

# Force reinstall
pip install -r requirements-build.txt --force-reinstall
```

### Debugging Build Issues

#### Verbose Output
```bash
# Shell script with debug mode
DEBUG=1 ./build_release.sh

# Nuitka with verbose output
python -m nuitka --verbose main.py
```

#### Testing Cross-Compilation
```bash
# Test Windows executable on Linux with Wine
wine dist/ROMDownloader.exe --help
```

#### Checking Dependencies
```bash
# List installed packages
pip list

# Check specific package
python -c "import nuitka; print(nuitka.__version__)"
```

## Performance Optimization

### Build Speed
- Use `--jobs=N` to set parallel compilation jobs
- Enable `--lto=yes` for Link Time Optimization
- Use `--static-libpython=yes` to reduce startup time

### Executable Size
- Use `--onefile` for single executable (slower startup)
- Use `--standalone` for directory distribution (faster startup)
- Add `--remove-output` to clean temporary files

### Runtime Performance
- Enable all optimization flags in `build_config.json`
- Use Python 3.11+ for best performance
- Consider profile-guided optimization for critical paths

## CI/CD Integration

### GitHub Actions Example
```yaml
name: Build Windows Release

on:
  push:
    tags: ['v*']

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    - name: Install dependencies
      run: |
        sudo apt-get install mingw-w64
        pip install -r requirements-build.txt
    - name: Build executable
      run: ./build_release.sh
    - name: Upload artifacts
      uses: actions/upload-artifact@v3
      with:
        name: windows-release
        path: dist/*.zip
```

## Code Signing (Optional)

For production releases, consider code signing:

```bash
# Using signtool.exe (Windows)
signtool sign /f certificate.pfx /p password ROMDownloader.exe

# Using osslsigncode (Linux/macOS)
osslsigncode sign -certs certificate.crt -key private.key -in ROMDownloader.exe -out ROMDownloader-signed.exe
```

## Advanced Configuration

### Custom Nuitka Options
Create a `.nuitka` config file for project-specific settings:

```ini
[nuitka]
onefile = true
static-libpython = yes
lto = yes
plugin-enable = tk-inter,multiprocessing
windows-console-mode = disable
```

### Build Profiles
Create different build configurations for different use cases:

```bash
# Development build (faster, with debug symbols)
./build_release.sh --profile=dev

# Release build (optimized, stripped)
./build_release.sh --profile=release

# Portable build (standalone directory)
./build_release.sh --profile=portable
```

## Support

If you encounter issues:

1. Check this documentation
2. Review the build logs in `build/` directory
3. Test with a clean virtual environment
4. Check Nuitka documentation: https://nuitka.net/
5. Report issues in the project repository

## License

The build scripts and configuration are part of the ROM Downloader project and follow the same license terms.