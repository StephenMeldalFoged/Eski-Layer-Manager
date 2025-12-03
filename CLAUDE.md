# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Eski Layer Manager** is a dockable layer and object manager utility for Autodesk 3ds Max 2026+. It provides a modern Qt-based UI for managing layers and objects within 3ds Max, improving upon the built-in layer management tools.

**Current Version:** 0.2.0 (Basic dockable window implemented)

## Technology Stack

- **UI Framework:** PySide6 (Qt) - Modern dockable interface
- **3ds Max Integration:** pymxs - Python wrapper around MAXScript for accessing 3ds Max API
- **Installer:** MAXScript (.ms) - Handles macro button installation and file deployment
- **Python Version:** Compatible with 3ds Max 2026's embedded Python

### Key Design Decision: Hybrid Approach

The project uses a hybrid Python/MAXScript approach:
- **Python (PySide6)** for the UI - provides modern, dockable interfaces superior to MAXScript's .NET UI
- **pymxs (MAXScript via Python)** for 3ds Max API access - required for layer operations, object queries, etc.
- **MAXScript** for installer/deployment - native integration with 3ds Max's macro system

This is the recommended pattern for 3ds Max tool development when building complex UIs.

## Architecture

### Core Components

**eski-layer-manager.py** - Main Python application
- `EskiLayerManager` class: QDockWidget-based main window
- Singleton pattern with class-level `instance` variable to prevent garbage collection
- `show_layer_manager()`: Entry point function called from 3ds Max
- Docks to left/right only (not top/bottom), defaults to right
- Uses `qtmax.GetQMaxMainWindow()` for proper 3ds Max integration
- Standalone testing mode: Can run outside 3ds Max for UI development

**install-macro-button.ms** - MAXScript installer with GUI
- Creates macro button in "Eski Tools" category
- Auto-copies Python file from repo to user scripts directory
- Searches multiple locations: script folder, Desktop, Downloads, Documents
- Installs to `#userScripts` (user-writable), NOT `#scripts` (requires admin)
- Generates `EskiLayerManager.mcr` in `#userMacros`
- Uninstaller removes both .mcr and .py files
- Note: Actions persist in memory until 3ds Max restart (MAXScript limitation)

### File Naming Convention

Important: The installer copies `eski-layer-manager.py` → `eski_layer_manager.py` (hyphen becomes underscore) to make it importable as a Python module.

## Development Workflow

### Testing the UI

To test UI changes without 3ds Max:
```bash
python eski-layer-manager.py
```
This runs standalone mode with a basic Qt window (no 3ds Max integration).

### Installing in 3ds Max

1. Keep `install-macro-button.ms` and `eski-layer-manager.py` in the same directory
2. In 3ds Max: F11 → File > Open → select installer script → Ctrl+E
3. Click "Install / Upgrade to Latest Version"
4. Installer auto-copies Python file to user scripts directory
5. Add macro button to toolbar via Customize UI (instructions in installer)

### Making Changes

After modifying code:
1. Run installer again (upgrades existing installation)
2. Restart 3ds Max (clears old actions from memory)
3. Macro button automatically reloads the module on each click

### Uninstalling

Run installer → "Uninstall Current and Older Versions"
- Removes macro file and Python file
- Restart 3ds Max to fully clear actions from Customize UI

## Version Management

**Eski-LayerManager-By-Claude-Version-History.txt** tracks all versions:
- Documents features added in each version
- Includes git tag info for checking out specific versions
- Usage examples for each version

When adding features:
1. Update `VERSION` constant in Python file
2. Update version in installer script (`installerVersion`)
3. Add entry to version history file with date, tag, and features
4. Update README.md if user-facing changes

## Git Branching Strategy

- **main** - Stable releases
- **Feature branches** - Named descriptively (e.g., "Dockable-window-fix")
- Create branches for fixes/features, merge to main when stable

## Important 3ds Max Integration Notes

### Python Path Handling
The macro button adds `#userScripts` to Python's `sys.path` at runtime. This is necessary because 3ds Max doesn't automatically include user script directories in Python's search path.

### Docking API
- Use `qtmax.GetQMaxMainWindow()` to get the 3ds Max main window as QMainWindow
- Parent QDockWidget to this window
- Use `addDockWidget()` to dock programmatically
- Setting `QDockWidget.setAllowedAreas()` restricts docking positions

### Garbage Collection
Qt widgets can be garbage collected in 3ds Max's Python environment. Always keep a reference:
```python
EskiLayerManager.instance = layer_manager
```

### Action Manager Limitations
MAXScript provides no API to unregister actions at runtime. Actions loaded during a session persist in the Customize UI until 3ds Max restarts. This is a 3ds Max limitation, not a bug.

## Planned Features (v0.3.0+)

- Layer list display with status
- Object list per layer
- Layer management operations (create, delete, rename)
- Object assignment to layers
- Selection integration

## Common Issues

**"ModuleNotFoundError: No module named 'eski_layer_manager'"**
- Python file not in user scripts directory
- Run installer to auto-copy, or manually copy to: `C:\Users\<User>\AppData\Local\Autodesk\3dsMax\<Version>\ENU\scripts\`

**Old macro button errors after update**
- Restart 3ds Max to clear old actions from memory

**Installer can't find Python file**
- Keep installer and Python file in same folder
- Check MAXScript Listener for search paths
