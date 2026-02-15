# Element Browser

A DaVinci Resolve PySide6 panel for importing image sequences (EXR, PNG, JPG, JPEG) as shots, previewing them, and batch importing into the Media Pool with automatic timeline creation. Includes optional ShotGrid integration.

## Features
- Detects and displays only valid image sequences (shots)
- Supports EXR, PNG, JPG, JPEG formats
- Lazy thumbnail generation for fast UI
- Batch import all detected shots into the Media Pool
- Automatically creates a timeline with imported shots
- PySide6-based UI for native look and feel
- Optional ShotGrid integration (requires `shotgun_api3`)
- Default path set to `D:\Projects`

## Usage
1. Place this script in your DaVinci Resolve Fusion Scripts directory.
2. Launch DaVinci Resolve and run the script from the Scripts menu.
3. Use the UI to browse, preview, and import shots.

## Requirements
- DaVinci Resolve (with scripting enabled)
- Python 3.x
- PySide6 (`pip install PySide6`)
- Optional: `shotgun_api3` for ShotGrid integration

## GitHub
This repository is maintained at: https://github.com/dna1989/Davanci-Reslove

## License
MIT License
