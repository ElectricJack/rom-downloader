#!/bin/bash
#
# ROM Downloader - Release Build Script
# Compiles a Windows binary using Nuitka with optimizations
#

set -e  # Exit on any error

# Configuration
APP_NAME="ROMDownloader"
VERSION="1.0.0"
PYTHON_VERSION="3.11"
NUITKA_VERSION=">=1.8.0"

# Directories
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$PROJECT_ROOT/src"
BUILD_DIR="$PROJECT_ROOT/build"
DIST_DIR="$PROJECT_ROOT/dist"
TOOLS_DIR="$PROJECT_ROOT/tools"
CONFIG_DIR="$PROJECT_ROOT/config"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Check if we're on Windows or WSL
check_platform() {
    log_info "Checking platform..."
    
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        PLATFORM="windows"
        PYTHON_CMD="python"
    elif grep -qi microsoft /proc/version 2>/dev/null; then
        PLATFORM="wsl"
        PYTHON_CMD="python3"
        log_warn "Running on WSL - cross-compilation to Windows"
    else
        PLATFORM="linux"
        PYTHON_CMD="python3"
        log_warn "Running on Linux - cross-compilation to Windows"
    fi
    
    log_info "Platform detected: $PLATFORM"
}

# Check dependencies
check_dependencies() {
    log_info "Checking dependencies..."
    
    # Check Python
    if ! command -v $PYTHON_CMD &> /dev/null; then
        log_error "Python not found. Please install Python $PYTHON_VERSION or later."
        exit 1
    fi
    
    PYTHON_VER=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
    log_info "Python version: $PYTHON_VER"
    
    # Check pip
    if ! $PYTHON_CMD -m pip --version &> /dev/null; then
        log_error "pip not found. Please install pip."
        exit 1
    fi
    
    # Check cross-compilation dependencies for Linux
    if [[ "$PLATFORM" == "linux" || "$PLATFORM" == "wsl" ]]; then
        log_info "Checking cross-compilation dependencies..."
        
        # Check for patchelf (required for standalone mode)
        if ! command -v patchelf &> /dev/null; then
            log_warn "patchelf not found. Attempting to install..."
            if command -v apt-get &> /dev/null; then
                sudo apt-get update && sudo apt-get install -y patchelf
            elif command -v dnf &> /dev/null; then
                sudo dnf install -y patchelf
            elif command -v yum &> /dev/null; then
                sudo yum install -y patchelf
            elif command -v pacman &> /dev/null; then
                sudo pacman -S --noconfirm patchelf
            else
                log_error "Could not install patchelf automatically. Please install it manually:"
                log_error "  Ubuntu/Debian: sudo apt-get install patchelf"
                log_error "  Fedora/RHEL: sudo dnf install patchelf"
                log_error "  Arch: sudo pacman -S patchelf"
                exit 1
            fi
        fi
        
        # Check for MinGW-w64 for Windows cross-compilation
        if ! command -v x86_64-w64-mingw32-gcc &> /dev/null; then
            log_warn "MinGW-w64 not found. Attempting to install..."
            if command -v apt-get &> /dev/null; then
                sudo apt-get update && sudo apt-get install -y gcc-mingw-w64-x86-64
            elif command -v dnf &> /dev/null; then
                sudo dnf install -y mingw64-gcc
            elif command -v yum &> /dev/null; then
                sudo yum install -y mingw64-gcc
            elif command -v pacman &> /dev/null; then
                sudo pacman -S --noconfirm mingw-w64-gcc
            else
                log_warn "Could not install MinGW-w64 automatically. Cross-compilation may fail."
                log_warn "To install manually:"
                log_warn "  Ubuntu/Debian: sudo apt-get install gcc-mingw-w64-x86-64"
                log_warn "  Fedora/RHEL: sudo dnf install mingw64-gcc"
                log_warn "  Arch: sudo pacman -S mingw-w64-gcc"
            fi
        fi
        
        log_info "Cross-compilation dependencies checked"
    fi
    
    # Check if Nuitka is installed
    if ! $PYTHON_CMD -c "import nuitka" 2>/dev/null; then
        log_warn "Nuitka not found. Installing..."
        $PYTHON_CMD -m pip install "nuitka$NUITKA_VERSION"
    fi
    
    # Check application dependencies
    log_info "Installing application dependencies..."
    $PYTHON_CMD -m pip install -r requirements-build.txt
    
    log_success "Dependencies check completed"
}

# Prepare build environment
prepare_build() {
    log_info "Preparing build environment..."
    
    # Clean previous builds
    if [[ -d "$BUILD_DIR" ]]; then
        log_info "Cleaning previous build directory..."
        rm -rf "$BUILD_DIR"
    fi
    
    if [[ -d "$DIST_DIR" ]]; then
        log_info "Cleaning previous dist directory..."
        rm -rf "$DIST_DIR"
    fi
    
    # Create directories
    mkdir -p "$BUILD_DIR"
    mkdir -p "$DIST_DIR"
    
    log_success "Build environment prepared"
}

# Create application icon (optional)
create_icon() {
    log_info "Checking for application icon..."
    
    ICON_PATH="$PROJECT_ROOT/icon.ico"
    if [[ ! -f "$ICON_PATH" ]]; then
        log_warn "No icon.ico found. Creating placeholder..."
        # You can add icon creation logic here or skip
        ICON_ARGS=""
    else
        ICON_ARGS="--windows-icon-from-ico=$ICON_PATH"
        log_info "Using icon: $ICON_PATH"
    fi
}

# Build with Nuitka
build_executable() {
    log_info "Building executable with Nuitka..."
    
    cd "$PROJECT_ROOT"
    
    # Nuitka build command
    NUITKA_ARGS=(
        --onefile
        --windows-console-mode=disable
        --enable-plugin=tk-inter
        --enable-plugin=multiprocessing
        --windows-product-name="$APP_NAME"
        --windows-company-name="ROM Downloader"
        --windows-product-version="$VERSION"
        --windows-file-version="$VERSION"
        --windows-file-description="ROM Download and Management Tool"
        --output-dir="$DIST_DIR"
        --output-filename="$APP_NAME.exe"
        --assume-yes-for-downloads
        --show-progress
        --show-memory
    )
    
    # Add icon if available
    if [[ -n "$ICON_ARGS" ]]; then
        NUITKA_ARGS+=($ICON_ARGS)
    fi
    
    # Include data files and directories
    NUITKA_ARGS+=(
        --include-data-dir="$CONFIG_DIR=config"
        --include-data-dir="$TOOLS_DIR=tools"
    )
    
    # Include source modules
    NUITKA_ARGS+=(
        --include-package=src
        --include-package=src.config
        --include-package=src.gui
        --include-package=src.models
        --include-package=src.downloader
        --include-package=src.scraper
        --include-package=src.processors
        --include-package=src.filters
        --include-package=src.tools
        --include-package=src.state
        --include-package=src.network
        --include-package=src.rom_manager
        --include-package=src.utils
    )
    
    # Optimization flags
    NUITKA_ARGS+=(
        --lto=yes
        --static-libpython=yes
        --remove-output
    )
    
    # Add cross-compilation for Windows if on Linux/WSL
    if [[ "$PLATFORM" != "windows" ]]; then
        NUITKA_ARGS+=(
            --mingw64
        )
    fi
    
    log_info "Running Nuitka with the following arguments:"
    printf '%s\n' "${NUITKA_ARGS[@]}"
    
    # Execute Nuitka
    $PYTHON_CMD -m nuitka "${NUITKA_ARGS[@]}" main.py
    
    if [[ $? -eq 0 ]]; then
        log_success "Executable built successfully"
    else
        log_error "Build failed"
        exit 1
    fi
}

# Package release
package_release() {
    log_info "Packaging release..."
    
    RELEASE_DIR="$DIST_DIR/${APP_NAME}_v${VERSION}_Windows"
    mkdir -p "$RELEASE_DIR"
    
    # Copy executable
    cp "$DIST_DIR/$APP_NAME.exe" "$RELEASE_DIR/"
    
    # Copy configuration files
    cp -r "$CONFIG_DIR" "$RELEASE_DIR/"
    
    # Copy tools
    cp -r "$TOOLS_DIR" "$RELEASE_DIR/"
    
    # Copy documentation
    cp README.md "$RELEASE_DIR/"
    cp CLAUDE.md "$RELEASE_DIR/"
    
    # Create requirements file for reference
    cp requirements.txt "$RELEASE_DIR/"
    
    # Create launcher script (optional)
    cat > "$RELEASE_DIR/launch.bat" << 'EOF'
@echo off
title ROM Downloader
echo Starting ROM Downloader...
ROMDownloader.exe
if errorlevel 1 (
    echo.
    echo Application exited with error. Press any key to close.
    pause >nul
)
EOF
    
    # Create ZIP archive
    cd "$DIST_DIR"
    ZIP_NAME="${APP_NAME}_v${VERSION}_Windows.zip"
    
    if command -v 7z &> /dev/null; then
        7z a "$ZIP_NAME" "${APP_NAME}_v${VERSION}_Windows/*"
    elif command -v zip &> /dev/null; then
        zip -r "$ZIP_NAME" "${APP_NAME}_v${VERSION}_Windows"
    else
        log_warn "No zip utility found. Skipping archive creation."
    fi
    
    # Calculate file sizes
    EXE_SIZE=$(stat -c%s "$RELEASE_DIR/$APP_NAME.exe" 2>/dev/null || stat -f%z "$RELEASE_DIR/$APP_NAME.exe" 2>/dev/null || echo "unknown")
    
    log_success "Release packaged successfully"
    log_info "Executable size: $(numfmt --to=iec $EXE_SIZE 2>/dev/null || echo "$EXE_SIZE bytes")"
    log_info "Release directory: $RELEASE_DIR"
    
    if [[ -f "$DIST_DIR/$ZIP_NAME" ]]; then
        ZIP_SIZE=$(stat -c%s "$DIST_DIR/$ZIP_NAME" 2>/dev/null || stat -f%z "$DIST_DIR/$ZIP_NAME" 2>/dev/null || echo "unknown")
        log_info "Archive: $ZIP_NAME ($(numfmt --to=iec $ZIP_SIZE 2>/dev/null || echo "$ZIP_SIZE bytes"))"
    fi
}

# Verify build
verify_build() {
    log_info "Verifying build..."
    
    EXE_PATH="$DIST_DIR/${APP_NAME}_v${VERSION}_Windows/$APP_NAME.exe"
    
    if [[ ! -f "$EXE_PATH" ]]; then
        log_error "Executable not found at $EXE_PATH"
        exit 1
    fi
    
    # Check if executable is valid
    if command -v file &> /dev/null; then
        FILE_INFO=$(file "$EXE_PATH")
        log_info "Executable info: $FILE_INFO"
        
        if [[ "$FILE_INFO" =~ "PE32" ]]; then
            log_success "Valid Windows PE executable"
        else
            log_warn "May not be a valid Windows executable"
        fi
    fi
    
    # Test import on current system (if possible)
    if [[ "$PLATFORM" == "windows" ]]; then
        log_info "Testing executable launch (Windows)..."
        timeout 10s "$EXE_PATH" --help 2>/dev/null || log_warn "Could not test executable (timeout or error)"
    fi
    
    log_success "Build verification completed"
}

# Clean up temporary files
cleanup() {
    log_info "Cleaning up temporary files..."
    
    # Remove Nuitka cache
    if [[ -d "$PROJECT_ROOT/main.build" ]]; then
        rm -rf "$PROJECT_ROOT/main.build"
    fi
    
    if [[ -d "$PROJECT_ROOT/main.dist" ]]; then
        rm -rf "$PROJECT_ROOT/main.dist"
    fi
    
    # Remove Python cache
    find "$PROJECT_ROOT" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find "$PROJECT_ROOT" -name "*.pyc" -delete 2>/dev/null || true
    
    log_success "Cleanup completed"
}

# Print usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --clean-only     Only clean build artifacts"
    echo "  --no-cleanup     Skip cleanup after build"
    echo "  --verify-only    Only verify existing build"
    echo "  --help           Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  NUITKA_CACHE_DIR    Directory for Nuitka cache"
    echo "  BUILD_JOBS          Number of parallel build jobs"
    echo ""
}

# Main function
main() {
    log_info "ROM Downloader Release Build Script"
    log_info "Version: $VERSION"
    log_info "========================================"
    
    # Parse arguments
    CLEAN_ONLY=false
    NO_CLEANUP=false
    VERIFY_ONLY=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --clean-only)
                CLEAN_ONLY=true
                shift
                ;;
            --no-cleanup)
                NO_CLEANUP=true
                shift
                ;;
            --verify-only)
                VERIFY_ONLY=true
                shift
                ;;
            --help)
                usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done
    
    # Set Nuitka cache directory if not set
    if [[ -z "$NUITKA_CACHE_DIR" ]]; then
        export NUITKA_CACHE_DIR="$BUILD_DIR/nuitka_cache"
    fi
    
    # Set build jobs if not set
    if [[ -z "$BUILD_JOBS" ]]; then
        export BUILD_JOBS=$(nproc 2>/dev/null || echo "4")
    fi
    
    log_info "Build jobs: $BUILD_JOBS"
    log_info "Nuitka cache: $NUITKA_CACHE_DIR"
    
    # Handle special modes
    if [[ "$CLEAN_ONLY" == true ]]; then
        cleanup
        exit 0
    fi
    
    if [[ "$VERIFY_ONLY" == true ]]; then
        verify_build
        exit 0
    fi
    
    # Main build process
    local start_time=$(date +%s)
    
    check_platform
    check_dependencies
    prepare_build
    create_icon
    build_executable
    package_release
    verify_build
    
    if [[ "$NO_CLEANUP" != true ]]; then
        cleanup
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log_success "Build completed successfully in ${duration}s"
    log_info "Release files are in: $DIST_DIR"
    
    echo ""
    echo "========================================"
    echo "🎉 ROM Downloader Windows Build Ready!"
    echo "========================================"
    echo "📁 Location: $DIST_DIR/${APP_NAME}_v${VERSION}_Windows/"
    echo "🚀 Executable: $APP_NAME.exe"
    echo "📦 Archive: ${APP_NAME}_v${VERSION}_Windows.zip"
    echo ""
    echo "Next steps:"
    echo "1. Test the executable on a Windows machine"
    echo "2. Distribute the ZIP file to users"
    echo "3. Consider code signing for production releases"
    echo ""
}

# Handle interruption
trap 'log_error "Build interrupted"; cleanup; exit 1' INT TERM

# Run main function
main "$@"