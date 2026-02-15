# Element Browser

A DaVinci Resolve PySide6 panel for importing image sequences (EXR, PNG, JPG, JPEG) as shots, previewing them, and batch importing into the Media Pool with automatic timeline creation. Includes optional ShotGrid integration and Lua shortcut launcher.


## New Features (2026)
- Integrated sequence player: Preview and play image sequences directly in the panel (no external viewer needed)
- Player controls: Play, Pause, Stop, and FPS adjustment for in-panel playback
- Checkbox selection: Each sequence row has a checkbox for selective import
- Only checked sequences are imported and added to the timeline
- "Import Checked Sequences & Create Timeline" button for targeted batch import

## Usage
### Sequence Player & Selective Import
1. Click a sequence row to preview and play it in the right panel.
2. Use Play, Pause, Stop, and FPS controls below the preview.
3. Check the box next to each sequence you want to import.
4. Click "Import Checked Sequences & Create Timeline" to import only the checked items.
1. Place the Python script in your DaVinci Resolve Fusion Scripts directory (e.g., `Scripts/Utility/Element Browser.py`).
2. Place the Lua launcher (`ElementBrowserShortcut.lua`) in the same folder.
3. Restart DaVinci Resolve.
4. Assign a keyboard shortcut to the Lua script via Workspace > Keyboard Customization.
5. Use the UI to browse, preview, and import shots.

## Requirements
- DaVinci Resolve (with scripting enabled)
- Python 3.x
- PySide6 (`pip install PySide6`)
- Optional: `shotgun_api3` for ShotGrid integration

## GitHub
This repository is maintained at: https://github.com/dna1989/Davanci-Reslove

## License
MIT License
