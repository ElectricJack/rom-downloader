#!/usr/bin/env python3
"""
ROM Downloader - Main Entry Point
A tool for downloading and installing ROMs onto Batocera Linux remotely.
"""

import tkinter as tk
from pathlib import Path
import sys
import os

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from gui.main_window import MainWindow

def main():
    """Main entry point for the ROM Downloader application."""
    # Create the main window
    root = tk.Tk()
    app = MainWindow(root)
    
    # Start the GUI event loop
    root.mainloop()

if __name__ == "__main__":
    main()