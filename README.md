# Eski Layer Manager by Claude

A dockable layer and object manager utility for Autodesk 3ds Max.

## Current Version: 0.2.0

### Features
- Dockable window interface that can be docked left or right
- Built with Python and PySide6 (Qt)
- Integrates with 3ds Max main window
- Clean, modern UI shell ready for layer management features

## Installation

1. Copy `eski-layer-manager.py` to your 3ds Max scripts directory:
   - Default location: `C:\Users\<YourUsername>\AppData\Local\Autodesk\3dsMax\<Version>\ENU\scripts\`
   - Or use your custom scripts directory

## Usage

### Method 1: Macro Button (Recommended - One-Click Access)

1. **Install the macro button** (one-time setup):
   - In 3ds Max, press **F11** to open MAXScript Editor
   - Go to **File > Open** and select `install-Eski-Layer-Manager.ms`
   - Press **Ctrl+E** to execute the script
   - You'll see a confirmation message

2. **Add button to toolbar**:
   - Go to **Customize > Customize User Interface** (or press **Ctrl+Alt+X**)
   - In the **Category** dropdown, select **"Eski Tools"**
   - Find **"EskiLayerManager"** in the action list
   - **Drag it** to any toolbar (Main toolbar, etc.)
   - Click **Save** and close the dialog

3. **Use the button**:
   - Click the **"Eski Layers"** button on your toolbar anytime!

### Method 2: Launch from Script Editor

Open the MAXScript Editor (F11), switch to **Python** mode, and run:

```python
import eski_layer_manager
eski_layer_manager.show_layer_manager()
```

### Docking

The window can be docked to the left or right sides of the 3ds Max interface. It defaults to the right side when first opened.

## Requirements

- Autodesk 3ds Max 2026 or later (with Python support)
- PySide6 (included with 3ds Max)
- pymxs (included with 3ds Max)

## Version History

See `Eski-LayerManager-By-Claude-Version-History.txt` for detailed version information and how to jump between versions using git tags.

## Upcoming Features

- Version 0.3.0: Layer list display with layer information
- Version 0.4.0: Object list per layer with selection
- Version 0.5.0: Layer management operations (create, delete, rename, assign objects)
