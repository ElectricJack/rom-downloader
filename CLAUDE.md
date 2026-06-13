# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Rom-downloader is a Python-based GUI tool for downloading and installing ROMs onto a Batocera Linux machine remotely. The application allows users to queue downloads and automatically deploy ROMs to network drive locations with intelligent filtering and deduplication.

## Core Architecture

The application is built using Python with a modular architecture:

- **Configuration System** (`src/config/`): JSON-based config files defining platforms, URLs, target directories, and settings
- **Web Scraping Module** (`src/scraper/`): Scrapes ROM sites using requests and BeautifulSoup to enumerate available files
- **ROM Management** (`src/rom_manager/`): Filters duplicates, prioritizes regions (USA/English), and manages ROM metadata
- **Download Engine** (`src/downloader/`): Sequential downloads with configurable random delays and progress tracking
- **Network Handler** (`src/network/`): Manages network drive access with local fallback
- **GUI Layer** (`src/gui/`): Tkinter-based interface with platform selection, ROM list, and download controls
- **State Persistence** (`src/state/`): Saves user selections and download history per platform

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run app
python main.py

```

## Configuration

- **Platform Config**: `config/platforms.json` - Define new platforms, URLs, file patterns
- **Application State**: `state/app_state.json` - User selections and history (auto-created)
- **Logs**: `rom_downloader.log` - Application logs

## Key Features

- **Network Drive Integration**: Primary target `\\BATOCERA\share\roms` with local fallback
- **Smart Filtering**: Removes duplicates, prioritizes USA/English regions, skips existing files
- **Rate Limiting**: Configurable delays (2-5 seconds default) between downloads
- **State Persistence**: Saves ROM selections per platform across sessions
- **Progress Tracking**: Real-time download progress with speed and ETA
- **Error Handling**: Graceful fallback for network issues and download failures
- **Concurrent Operations**: Parallel downloading and network copying with dual progress bars
- **Queue Management**: Smart coordination to prevent network saturation

## Adding New Platforms

Add to `config/platforms.json`:
```json
{
  "PlatformName": {
    "name": "Display Name",
    "url": "https://download-site.com/path/",
    "target_folder": "subfolder_name",
    "file_extensions": [".ext1", ".ext2"],
    "extract_archives": true
  }
}
```

Note: File patterns are automatically generated from the `file_extensions` list, so there's no need to specify `file_pattern` manually.

## Git Workflow

**IMPORTANT**: Always commit changes after completing a batch of work or implementing a feature. Use descriptive commit messages that explain what was changed and why.

Example commit workflow:
```bash
git add <modified-files>
git commit -m "Brief description of changes

- Detailed bullet points of what was changed
- Why the changes were made
- Any important technical details

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.
ALWAYS COMMIT CHANGES after completing a batch of work or implementing a feature.