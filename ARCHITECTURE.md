# ROM Downloader - Architecture Documentation

## Overview

ROM Downloader is a Python-based GUI application designed to download and manage ROM files for retro gaming systems. The application provides a modular architecture with clear separation of concerns, enabling efficient ROM discovery, filtering, downloading, and deployment to network storage.

## Directory Structure

```
rom-downloader/
├── main.py                    # Primary entry point
├── run.py                     # Alternative entry point with auto-dependency install
├── requirements.txt           # Python dependencies
├── config/
│   └── platforms.json         # Platform configurations and app settings
├── src/                       # Core application modules
│   ├── config/                # Configuration management
│   ├── scraper/               # Web scraping functionality
│   ├── rom_manager/           # ROM filtering and deduplication
│   ├── downloader/            # Download management and processing
│   ├── network/               # Network drive handling
│   ├── gui/                   # Tkinter-based user interface
│   └── state/                 # Application state persistence
├── state/                     # Runtime state storage
│   └── app_state.json         # User selections and download history
├── temp_downloads/            # Temporary download storage
├── local_roms/                # Local ROM storage fallback
└── tools/                     # External utilities (chdman.exe, etc.)
```

## Core Modules

### 1. Configuration System (`src/config/`)

**Primary Class:** `ConfigManager`

**Purpose:** Manages platform configurations, application settings, and target paths.

**Key Responsibilities:**
- Load/save platform configurations from JSON
- Manage network drive paths and WSL compatibility
- Handle platform-specific settings (file patterns, extraction preferences)
- Provide target path resolution for different platforms
- Support CHD format detection per platform

**Key Methods:**
- `get_platforms()` - Returns all configured platforms
- `get_target_path(platform)` - Resolves network/local target paths
- `should_extract_archives(platform)` - Checks extraction preferences
- `supports_chd(platform)` - Determines CHD format support

**Configuration Structure:**
```json
{
  "settings": {
    "network_drive_path": "//BATOCERA/share/roms",
    "temp_download_path": "./temp_downloads",
    "preferred_regions": ["USA", "US", "En", "English"]
  },
  "platforms": {
    "PlatformName": {
      "name": "Display Name",
      "url": "https://download-site.com/path/",
      "target_folder": "subfolder_name",
      "file_extensions": [".ext1", ".ext2"],
      "file_pattern": ".*\\.(ext1|ext2)$",
      "extract_archives": true
    }
  }
}
```

### 2. Web Scraping Module (`src/scraper/`)

**Primary Classes:** `WebScraper`, `RomInfo`

**Purpose:** Scrapes ROM download sites to enumerate available files.

**Key Responsibilities:**
- HTTP requests to ROM archive sites with proper headers
- HTML parsing using BeautifulSoup
- ROM metadata extraction (name, size, region, file type)
- URL construction for downloads
- Performance optimization with timing metrics

**RomInfo Class:**
- Represents individual ROM files with cleaned names
- Automatic region detection from filename patterns
- File type and size tracking
- Name normalization for comparison

**Key Methods:**
- `scrape_roms(url, file_pattern)` - Main scraping functionality
- `test_connection(url)` - Connectivity testing
- `get_file_info(url)` - File metadata retrieval

**Data Flow:**
```
URL + File Pattern → HTTP Request → HTML Parsing → RomInfo Objects
```

### 3. ROM Management (`src/rom_manager/`)

**Primary Class:** `RomFilter`

**Purpose:** Filters, deduplicates, and manages ROM collections.

**Key Responsibilities:**
- Duplicate ROM detection and removal
- Region preference enforcement (USA → Europe → Japan priority)
- File format scoring and selection
- Existing ROM scanning with network optimization
- Name normalization for comparison

**Filtering Logic:**
1. **Name Normalization:** Remove file extensions, brackets, and common prefixes
2. **Duplicate Detection:** Group ROMs by normalized name
3. **Region Scoring:** Prioritize based on configured preferences
4. **Format Selection:** Choose best file format (CHD > ISO > ZIP)
5. **Existing ROM Check:** Mark already downloaded files

**Key Methods:**
- `filter_and_deduplicate(roms)` - Main filtering logic
- `scan_existing_roms(directory)` - Fast existing ROM detection
- `_normalize_name(name)` - Consistent name comparison
- `_select_best_rom(duplicates)` - Quality-based ROM selection

### 4. Download Engine (`src/downloader/`)

**Primary Classes:** `DownloadManager`, `DownloadProgress`, `CopyQueueItem`

**Purpose:** Handles ROM downloads, processing, and network deployment.

**Key Responsibilities:**
- Sequential downloads with configurable delays (2-5 seconds)
- Archive extraction (ZIP, 7Z) when configured
- CHD conversion using external chdman.exe tool
- Queue-based network copying to prevent saturation
- Progress tracking and real-time callbacks
- Error handling and retry logic

**Download Process:**
1. **Download:** Stream file to temp directory
2. **Extract:** Unpack archives if configured
3. **Convert:** Transform to CHD format if supported
4. **Queue:** Add to network copy queue
5. **Copy:** Background thread transfers to network drive
6. **Cleanup:** Remove temporary files

**Key Methods:**
- `download_roms(roms, target_path)` - Main download orchestration
- `_download_single_rom(rom)` - Individual ROM processing
- `_extract_archive(archive_path)` - Archive extraction
- `_convert_to_chd(source_file)` - CHD format conversion
- `_copy_worker()` - Background network copying thread

### 5. Network Handler (`src/network/`)

**Primary Class:** `NetworkHandler`

**Purpose:** Manages network drive connectivity with local fallback.

**Key Responsibilities:**
- Network drive availability testing
- Local storage fallback when network unavailable
- Progress-tracked file copying
- Batch synchronization operations
- Storage status reporting

**Network Strategy:**
- **Primary Target:** `\\BATOCERA\share\roms` (Batocera Linux)
- **WSL Compatibility:** Automatic UNC path conversion
- **Local Fallback:** `./local_roms` when network unavailable
- **Platform Mapping:** Each platform has a specific target subfolder

**Key Methods:**
- `check_network_availability()` - Tests network connectivity
- `copy_to_network(file, subfolder)` - Network file transfer
- `sync_local_to_network(platform)` - Bulk synchronization
- `get_storage_info()` - Current storage status

### 6. GUI Layer (`src/gui/`)

**Primary Class:** `MainWindow`

**Purpose:** Provides the primary user interface using Tkinter.

**Key Responsibilities:**
- Platform selection and configuration
- ROM list display with filtering capabilities
- Download progress visualization with dual progress bars
- Real-time status updates
- User interaction handling (selection, filtering, deletion)
- Context menus and keyboard shortcuts

**UI Components:**
- **Platform Selection:** Dropdown with all configured platforms
- **ROM Tree View:** Sortable list with columns (Name, Region, Size, Type, Status)
- **Filter Controls:** Region filtering, search functionality
- **Progress Bars:** Individual ROM and overall download progress
- **Status Bar:** Real-time operation feedback
- **Context Menus:** Right-click actions for ROM management

**Key Methods:**
- `setup_ui()` - Interface construction
- `scan_roms()` - Initiates ROM discovery
- `apply_region_filter()` - Updates display filtering
- `start_download()` - Begins download process
- `_update_progress(progress)` - Progress bar updates

### 7. State Persistence (`src/state/`)

**Primary Class:** `StateManager`

**Purpose:** Manages application state and user preferences.

**Key Responsibilities:**
- ROM selection persistence per platform
- Download history tracking
- Application settings storage
- Window geometry persistence
- Download statistics calculation

**State Structure:**
```json
{
  "platform_selections": {
    "PlatformName": ["rom1.zip", "rom2.iso"]
  },
  "download_history": {
    "PlatformName": [
      {"name": "rom1.zip", "success": true, "timestamp": "2024-01-01T12:00:00"}
    ]
  },
  "window_geometry": "800x600+100+100"
}
```

**Key Methods:**
- `save_platform_selections(platform, roms)` - Persist user choices
- `load_platform_selections(platform)` - Restore selections
- `add_download_history(platform, rom, success)` - Track downloads
- `get_download_stats(platform)` - Generate statistics

## Module Interactions

### Data Flow Architecture

```
ConfigManager → (Platform configs) → MainWindow
                                          ↓
WebScraper → RomInfo[] → RomFilter → Filtered ROMs → MainWindow
                                          ↓
MainWindow → Selected ROMs → DownloadManager → NetworkHandler
                                          ↓
StateManager ← (Results) ← DownloadManager → Progress Updates → MainWindow
```

### Thread Management

**Main Thread:** GUI operations, user interactions
**Download Thread:** ROM downloading and processing
**Copy Worker Thread:** Background network file copying
**Scan Thread:** ROM discovery and filtering

### Error Handling Strategy

- **Network Errors:** Automatic fallback to local storage
- **Download Failures:** Individual ROM error tracking with continuation
- **Archive Errors:** Fallback to original files if extraction fails
- **CHD Conversion:** Graceful failure with original format retention

## Application Flow

### 1. Startup Process

1. **main.py** → Creates Tkinter root and MainWindow
2. **MainWindow** → Initializes all managers (Config, Scraper, Filter, Download)
3. **ConfigManager** → Loads platform configurations
4. **StateManager** → Restores previous user selections
5. **GUI** → Displays platform selection interface

### 2. ROM Discovery Process

1. **User selects platform** → MainWindow.on_platform_selected()
2. **ConfigManager** → Provides platform URL and settings
3. **WebScraper** → Fetches and parses ROM listings
4. **RomFilter** → Deduplicates and scores ROMs
5. **RomFilter** → Scans for existing ROMs (with network optimization)
6. **MainWindow** → Updates UI with filtered results

### 3. Download Process

1. **User selects ROMs** → MainWindow tracks selections
2. **DownloadManager** → Processes ROM queue sequentially
3. **For each ROM:**
   - Downloads to temp directory
   - Extracts archives if configured
   - Converts to CHD if supported
   - Queues for network copying
4. **Copy Worker** → Transfers files to network drive
5. **Progress callbacks** → Update GUI in real-time
6. **StateManager** → Records download history

## Key Design Patterns

### 1. Configuration-Driven Architecture

The application is highly configurable through **config/platforms.json**:
- **28 supported platforms** (GameCube, Wii, PlayStation, etc.)
- **Platform-specific settings:** URLs, file patterns, extraction preferences
- **Global settings:** Network paths, download delays, region preferences
- **Extensible design** for adding new platforms

### 2. Observer Pattern

- **Progress callbacks** for real-time UI updates
- **Event-driven state changes** between modules
- **Asynchronous communication** between threads

### 3. Strategy Pattern

- **Multiple ROM selection strategies** (region, format preferences)
- **Pluggable network handling** (network vs local storage)
- **Configurable extraction methods** per platform

### 4. Queue-Based Processing

- **Download queue** for sequential processing
- **Network copy queue** for batch operations
- **Progress tracking** across all operations

## Performance Optimizations

### 1. Network Optimization

- **Cached directory scanning** to avoid repeated network calls
- **Batch operations** for existing ROM detection
- **Queue-based copying** to prevent network saturation
- **Timeout protection** for slow network responses

### 2. UI Responsiveness

- **Threaded operations** for all blocking tasks
- **Progress callbacks** for real-time updates
- **Chunked processing** for large ROM collections
- **Efficient tree view updates** with minimal redraws

### 3. Memory Management

- **Streaming downloads** with chunked reading
- **Temporary file cleanup** after processing
- **State persistence** to avoid recomputation
- **Lazy loading** of ROM metadata

## External Dependencies

### Core Dependencies

- `requests` - HTTP operations and session management
- `beautifulsoup4` + `lxml` - HTML parsing for ROM sites
- `py7zr` - 7Z archive extraction
- `tkinter` - GUI framework (built-in to Python)

### External Tools

- `chdman.exe` - CHD format conversion (MAME tool)
- `extract-xiso.exe` - Xbox ISO extraction (optional)

### Target Environment

- **Primary Target:** Windows systems with WSL2
- **Network Target:** Batocera Linux retro gaming OS
- **Storage Protocol:** SMB/CIFS network shares
- **Python Version:** 3.7+ compatible

## Security Considerations

### 1. Network Security

- **UNC path validation** for network drives
- **HTTP header spoofing** for site compatibility
- **Timeout controls** to prevent hanging requests

### 2. File System Security

- **Filename sanitization** for cross-platform compatibility
- **Path traversal prevention** during extraction
- **Temporary file cleanup** to prevent disk bloat

### 3. Data Validation

- **URL validation** before requests
- **File type verification** during processing
- **Archive integrity checks** before extraction

This architecture provides a robust, scalable solution for ROM management with strong separation of concerns, comprehensive error handling, and optimized performance for network operations.