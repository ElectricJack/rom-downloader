# Rom-downloader

Rom-downloader is a desktop client that makes it easier to download ROMs from sites you already use and deploy them onto an emulation cabinet (such as a [Batocera](https://batocera.org/) Linux machine) over your network.

It provides a simple GUI to pick a platform, browse the ROMs available on a configured source page, select the ones you want, and have them downloaded and copied into the correct folder on your emulation machine — handling region filtering, deduplication, archive extraction, and rate limiting along the way.

## What this app is

- **A client, and only a client.** It is a convenience front-end for browsing and downloading from ROM sites that you provide in the configuration.
- **A deployment helper.** It copies downloaded files to the right target folder on a network share (e.g. `\\BATOCERA\share\roms`), with a local-temp fallback when a direct write isn't possible.
- **An organizer.** It groups duplicates, prioritizes USA/English regions, skips files already installed, and can extract or convert archives into emulator-ready formats.

## What this app is **not**

- **It does not host, distribute, or bundle any ROMs or copyrighted material.** No game data ships with this software.
- **It is not a source of ROMs.** Every download URL is supplied by you in `config/platforms.json`. The app only reads the pages you point it at.
- **It is not a circumvention tool.** It simply automates browsing and downloading from existing, user-configured sites so you don't have to do it by hand.

You are responsible for ensuring that your use of this tool, and the sources you configure, comply with the laws in your jurisdiction. Only download content you are legally entitled to.

## How it works

1. **Select a platform** from a dropdown (e.g. Nintendo GameCube, Sony PlayStation 2).
2. The app **scrapes the configured source URL** for that platform and enumerates the available downloads.
3. Results are **filtered and deduplicated**, preferring USA/English releases.
4. You **check the games** you want. The app can scan the target network drive to mark titles already installed (done once on initialization).
5. Your selection is **saved per platform**, so it's restored if you reopen the app or it restarts mid-job.
6. The app **downloads one file at a time** (with a configurable random delay between downloads) directly to the network share, falling back to a local temp directory + move when needed.
7. Archives are **extracted/converted** as configured (e.g. unzip, CHD conversion, Xbox ISO extraction) into emulator-ready files.

## Requirements

- Python 3.x
- Dependencies in `requirements.txt`:
  - `requests`, `beautifulsoup4`, `lxml`, `py7zr`
- Optional external tools for certain platforms (paths configured per platform), e.g. `chdman` and `extract-xiso` for CHD/Xbox conversion.

## Installation & usage

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python main.py
```

## Configuration

All sources and settings live in `config/platforms.json`.

**Global settings:**

```json
{
  "settings": {
    "download_delay_min": 2,
    "download_delay_max": 5,
    "preferred_regions": ["USA", "US", "En", "English"],
    "max_concurrent_downloads": 1,
    "network_drive_paths": ["//BATOCERA/share/roms"],
    "current_network_drive_path": "//BATOCERA/share/roms"
  }
}
```

**Adding a platform:**

```json
{
  "PlatformName": {
    "name": "Display Name",
    "url": "https://your-configured-source/path/",
    "target_folder": "subfolder_name",
    "file_extensions": [".ext1", ".ext2"],
    "extract_archives": true
  }
}
```

File-matching patterns are generated automatically from `file_extensions`. Platforms that need post-processing (archive extraction, CHD conversion, Xbox extraction) can define a `tool_pipeline`; see the existing entries in `config/platforms.json` for examples.

Application state (your selections and history) is auto-created under `state/app_state.json`, and runtime logs are written to `rom_downloader.log`.

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE).

It bundles third-party command-line tools (`chdman`, `extract-xiso`) under their own respective licenses; see [tools/THIRD_PARTY.md](tools/THIRD_PARTY.md) for attribution and details.
