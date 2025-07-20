# 🚀 Quick Build Guide

**Choose your build method based on your platform:**

## Windows Users (Recommended)

### 🥇 Easiest Method
```cmd
build_windows.bat
```
- **No setup required** - just double-click or run from Command Prompt
- Works on any Windows machine with Python installed
- Creates ready-to-distribute folder and ZIP file

### 🥈 PowerShell Method (Advanced)
```powershell
.\build_release.ps1
```
- Rich colored output and advanced options
- Better error handling and logging
- Same result as above but with more features

## Linux/macOS Users

### Cross-compile to Windows
```bash
./build_release.sh
```
- Requires MinGW-w64 for cross-compilation
- See [BUILD.md](BUILD.md) for setup instructions

### Python Method (Any Platform)
```bash
python build_simple.py
```
- Pure Python implementation
- Works anywhere Python is available

## 📋 Prerequisites

**All you need:**
- **Python 3.8+** (Download from [python.org](https://www.python.org/downloads/))
- **Internet connection** (for downloading build tools)

**That's it!** The build scripts handle everything else automatically.

## 📁 What You Get

After building, you'll find:
```
dist/ROMDownloader_v1.0.0_Windows/
├── ROMDownloader.exe          ← Your standalone executable
├── launch.bat                 ← Easy launcher
├── config/                    ← Default configuration
├── tools/                     ← Required tools
└── README.md                  ← Documentation
```

## 🎯 Quick Test

1. Run the build script
2. Navigate to `dist/ROMDownloader_v1.0.0_Windows/`
3. Double-click `ROMDownloader.exe` or `launch.bat`

## ❓ Having Issues?

1. **Python not found?** Install from [python.org](https://www.python.org/downloads/) and add to PATH
2. **Build fails?** Try running as Administrator
3. **Want details?** See the full [BUILD.md](BUILD.md) guide
4. **Still stuck?** Check the troubleshooting section in [BUILD.md](BUILD.md)

## 🔄 Development Builds

For development, use the fast build:
```cmd
# Windows
build_windows.bat

# Add --no-cleanup to keep temp files for debugging  
.\build_release.ps1 -NoCleanup
```

---

**⭐ Pro Tip:** The `build_windows.bat` method is recommended for most Windows users - it's the simplest and most reliable!