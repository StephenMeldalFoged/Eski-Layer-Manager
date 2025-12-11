# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Eski Layer Manager** is a dockable layer and object manager utility for Autodesk 3ds Max 2026+. It provides a modern Qt-based UI for managing layers and objects within 3ds Max, improving upon the built-in layer management tools.

**Current Version:** 0.18.1

## Quick Reference

```bash
# Test UI standalone (no 3ds Max)
python eski-layer-manager.py

# Install/upgrade in 3ds Max
# F11 → File > Open → install-Eski-Layer-Manager.ms → Ctrl+E

# Test singleton pattern (in 3ds Max)
python.ExecuteFile "E:\\Github\\Eski-Layer-Manager\\tests\\test_singleton.py"

# Launch from 3ds Max Python console
import eski_layer_manager
eski_layer_manager.show_layer_manager()
```

## Project Structure

```
Eski-Layer-Manager/
├── eski-layer-manager.py          # Main Python application (830+ lines)
├── install-Eski-Layer-Manager.ms        # MAXScript installer with GUI
├── CLAUDE.md                       # This file - development guide
├── README.md                       # User-facing documentation
├── docs/
│   ├── wishlist.txt               # Feature specifications and priorities
│   ├── TROUBLESHOOTING.md         # Common issues and solutions
│   ├── QUICK_START.md             # Installation quickstart
│   ├── SINGLETON_*.md             # Singleton pattern documentation
│   └── *.txt                      # Version history, notes, reminders
└── tests/
    └── test_singleton.py          # Singleton pattern test script
```

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
- `EskiLayerManager` class: QDockWidget-based main window with vertical splitter (layers top, objects bottom)
- `InlineIconDelegate` class: Custom delegate for rendering inline icons in single column layout
- `CustomTreeWidget` class: Tree widget with custom mouse handling and drag-and-drop (used for both layers and objects)
- Singleton pattern with class-level `instance` variable to prevent garbage collection
- `show_layer_manager()`: Entry point function called from 3ds Max
- Docks to left/right only (not top/bottom), defaults to right
- Uses `qtmax.GetQMaxMainWindow()` for proper 3ds Max integration
- Standalone testing mode: Can run outside 3ds Max for UI development
- **Split-view UI:** Top section shows layers tree, bottom section shows objects in selected layer
- **Object management:** Select objects in tree to select them in scene, drag objects to reassign to different layers

**install-Eski-Layer-Manager.ms** - MAXScript installer with GUI
- Creates macro button in "Eski Tools" category
- Auto-copies Python file from repo to user scripts directory
- Searches multiple locations: script folder, Desktop, Downloads, Documents
- Installs to `#userScripts` (user-writable), NOT `#scripts` (requires admin)
- Generates `EskiLayerManager.mcr` in `#userMacros`
- Uninstaller removes both .mcr and .py files
- Note: Actions persist in memory until 3ds Max restart (MAXScript limitation)

### File Naming Convention

Important: The installer copies `eski-layer-manager.py` → `eski_layer_manager.py` (hyphen becomes underscore) to make it importable as a Python module.

## Critical Architecture Details

### Single Column Layout with Inline Icons (v0.8.0+)

The UI uses a **single column layout** where all elements are painted inline:
- Layout: `[tree lines] [custom arrow ▶▼] [eye 👁] [+ icon] [layer name]`
- Custom `InlineIconDelegate` paints everything in the `paint()` method
- Icons stored in `QtCore.Qt.UserRole` data on tree items
- Click detection uses stored click regions with viewport coordinate translation

**Key implementation details:**
- `_get_visual_row_number()`: Calculates visual row position for alternating backgrounds
- Click regions stored as `item.click_regions` dict with 'visibility', 'add_selection', 'name' keys
- Current Y position stored as `item.current_item_y` (integer, not QRect to avoid GC issues)
- Viewport coordinates used for all click detection

### Custom Tree Rendering (v0.8.0+)

Tree lines and expand/collapse arrows are drawn programmatically:
- `CustomTreeWidget.drawBranches()` override draws all tree visualization
- Connecting lines: Vertical │ and horizontal ─ lines at center Y position
- Arrows: ▶ (collapsed) and ▼ (expanded) drawn with `painter.drawText()`
- Color: `#CCCCCC` (bright light gray) for visibility
- No stylesheet-based tree lines - all custom painting

### Custom Highlighting (v0.8.5+)

Active layer highlighting is **text-only** with custom styling:
- Only the layer name text is highlighted, not the full row
- Deep teal color: `QtGui.QColor(0, 128, 128)`
- White text on teal background for contrast
- Tight fit around text using `QFontMetrics.horizontalAdvance()`
- Selection only occurs when clicking layer name, not icons

### Click Region Detection

Position-based click detection using stored rectangles:
```python
# In delegate paint():
vis_rect = QtCore.QRect(x, y, icon_size, h)
item.click_regions['visibility'] = vis_rect
item.current_item_y = option.rect.y()  # Store Y as int, not QRect

# In click handler:
y_offset = visual_rect.y() - item.current_item_y
adjusted_rect = click_region.translated(0, y_offset)
if adjusted_rect.contains(cursor_pos):
    # Handle click
```

**CRITICAL:** Always use `self.layer_tree.viewport().mapFromGlobal()` for cursor position, not `self.layer_tree.mapFromGlobal()`. Viewport coordinates match the delegate's paint coordinates.

### Icon Loading (v0.5.0+)

Icons loaded using 3ds Max native StateSets icons with fallback:
1. **Primary:** `qtmax.LoadMaxMultiResIcon("StateSets/Visible")` for visibility
2. **Primary:** `qtmax.LoadMaxMultiResIcon("AnimLayerToolbar", index=11)` for add selection
3. **Ultimate fallback:** Unicode text ("👁" visible, "✖" hidden, "🔒" frozen, "+" add)

Icons painted directly in delegate using stored UserRole data.

### Nested Layer Hierarchy (v0.6.1+)

Full support for parent-child layer relationships:
- `layer.getParent()` - Returns parent layer or None/undefined for root
- `layer.setParent(parent)` - Set parent (use `rt.undefined` for root)
- `layer.getNumChildren()` - Count direct children
- `layer.getChild(index)` - Get child by 1-based index (MAXScript convention)

**Drag-and-drop reparenting:**
- Drop **ON** item → make child of target
- Drop **ABOVE/BELOW** item → make sibling (same parent as target)
- Drop on **empty space** → make root layer
- Circular reference prevention with `_is_descendant()` check

### Bi-Directional Sync (v0.5.0+)

Two mechanisms keep UI in sync with 3ds Max:

1. **Timer-based polling (500ms):** Checks current layer and visibility state changes
   ```python
   self.refresh_timer = QtCore.QTimer()
   self.refresh_timer.timeout.connect(self.check_for_updates)
   self.refresh_timer.start(500)  # 500ms interval
   ```

2. **Callback system:** Registers MAXScript callbacks for layer events
   ```python
   # Register callbacks via pymxs
   rt.callbacks.addScript(rt.Name("layerCreated"), "python.execute('...')", id=rt.Name("EskiLayerMgr"))
   ```

   Events monitored:
   - `layerCreated`, `layerDeleted` → Full layer tree refresh
   - `nodeLayerChanged` → Update layer object counts
   - `layerCurrent` → Highlight active layer
   - `filePostOpen`, `systemPostReset`, `systemPostNew` → Close and reopen window

**Important:** Callbacks must be unregistered in `closeEvent()` to prevent memory leaks:
```python
rt.callbacks.removeScripts(id=rt.Name("EskiLayerMgr"))
```

### Objects Tree (v0.10.0+)

Bottom panel shows objects in the selected layer:
- **Object listing:** Displays all objects assigned to the currently selected layer
- **Scene selection sync:** Click objects in tree to select them in 3ds Max viewport
- **Multi-selection:** Ctrl+Click for multiple object selection
- **Drag-and-drop reassignment:** Drag objects from objects tree to any layer in layers tree to reassign
- **Cross-tree drag-drop:** `CustomTreeWidget.dropEvent()` detects source widget and handles appropriately
- **Automatic refresh:** Object list updates when selecting different layers
- Key methods:
  - `populate_objects(layer_name)` - Fills objects tree for specified layer
  - `on_object_selection_changed()` - Syncs tree selection to scene selection
  - `reassign_objects_to_layer()` - Handles drag-drop reassignment from objects to layers

### Position Persistence (v0.11.7+)

Window docking position and state are preserved between sessions:
- Position stored relative to 3ds Max main window
- Dock stacking order tracked and restored
- Settings persist across 3ds Max restarts
- Toggle feature available through UI

## Development Workflow

### Git Branching Strategy

- **main**: Stable releases with version tags
- **Feature branches**: Named descriptively (e.g., `Objects-Tasks`)
- Version tags follow semantic versioning (v0.x.x)
- Detailed version history available in `docs/Eski-LayerManager-By-Claude-Version-History.txt`

### Testing the UI

To test UI changes without 3ds Max:
```bash
python eski-layer-manager.py
```
This runs standalone mode with a basic Qt window (no 3ds Max integration).

### Running Tests

Test the singleton pattern implementation:
```maxscript
-- In 3ds Max MAXScript Listener:
python.ExecuteFile "E:\\Github\\Eski-Layer-Manager\\tests\\test_singleton.py"
```

This verifies:
- Only one instance is created when called multiple times
- Instance is properly reused across calls
- Singleton pattern survives module reloads

### Installing in 3ds Max

1. Keep `install-Eski-Layer-Manager.ms` and `eski-layer-manager.py` in the same directory
2. In 3ds Max: F11 → File > Open → select installer script → Ctrl+E
3. Click "Install / Upgrade to Latest Version"
4. Installer auto-copies Python file to user scripts directory
5. Add macro button to toolbar via Customize UI (instructions in installer)

### Making Changes

After modifying code:
1. Run installer again (upgrades existing installation)
2. Restart 3ds Max (clears old actions from memory)
3. Macro button automatically reloads the module on each click

### Version Management

**IMPORTANT VERSION POLICY:**

When updating versions:
1. **Python script version** (`eski-layer-manager.py`): Update `VERSION` constant for EVERY change
2. **Installer version** (`install-Eski-Layer-Manager.ms`): Update `installerVersion` ONLY when installer script changes

Both versions should match for major releases, but installer version may lag behind if only Python code changes.

Update these locations when bumping versions:
- eski-layer-manager.py line 5: Docstring `Version: X.X.X`
- eski-layer-manager.py line 36: `VERSION = "X.X.X"`
- install-Eski-Layer-Manager.ms line 6: `local installerVersion = "X.X.X"` (only when installer changes)

## Important 3ds Max Integration Notes

### MAXScript API via pymxs

Key patterns for accessing 3ds Max layer API:

```python
from pymxs import runtime as rt

# Layer Manager access
layer_manager = rt.layerManager
layer_count = layer_manager.count
layer = layer_manager.getLayer(index)  # 0-based index
layer = layer_manager.getLayerFromName("LayerName")

# Layer properties (read/write)
layer.name           # Layer name
layer.ishidden       # Visibility state
layer.isfrozen       # Frozen state
layer.current        # Is current layer
layer.wireColor      # Wireframe color

# Layer hierarchy (3ds Max 2026+)
parent = layer.getParent()           # Returns parent or rt.undefined for root
layer.setParent(parent)              # Set parent (use rt.undefined for root)
num_children = layer.getNumChildren()
child = layer.getChild(index)        # 1-based index (MAXScript convention)

# Object operations
layer.select(True)                   # Select all objects on layer
num_objects = layer.getNumNodes()
layer.addnode(node)                  # Assign object to layer
nodes_array = layer.nodes            # Get all nodes on layer

# Current layer
rt.layerManager.current = layer      # Set active layer
```

**Critical:** MAXScript uses **1-based indexing** for children (`getChild()`), but Python/pymxs uses **0-based indexing** for layers (`getLayer()`).

### Python Path Handling
The macro button adds `#userScripts` to Python's `sys.path` at runtime because 3ds Max doesn't automatically include user script directories in Python's search path.

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

### QRect Garbage Collection Issue

**CRITICAL:** Never store QRect objects directly on tree items - they get garbage collected by Qt's C++ layer.

```python
# WRONG - QRect gets deleted:
item.current_item_rect = option.rect

# CORRECT - Store primitive values:
item.current_item_y = option.rect.y()
```

Always extract primitive values (int, float, string) from Qt objects when storing on Python objects.

## Debugging

### Print Statements
All debug output goes to 3ds Max's MAXScript Listener (F11). Use standard Python `print()`:
```python
print(f"[DEBUG] Layer count: {layer_manager.count}")
```

### Common Debugging Commands

In 3ds Max Python console:
```python
# Check if module is loaded
import sys
'eski_layer_manager' in sys.modules

# Force module reload (for development)
import importlib
importlib.reload(sys.modules['eski_layer_manager'])

# Check singleton status
import eski_layer_manager
eski_layer_manager.get_instance_status()

# Inspect layer manager
from pymxs import runtime as rt
rt.layerManager.count  # Number of layers
rt.layerManager.current.name  # Current layer name
```

### Callback Debugging
Check registered callbacks:
```maxscript
-- In MAXScript Listener
callbacks.show()
```

## Common Issues

**"ModuleNotFoundError: No module named 'eski_layer_manager'"**
- Python file not in user scripts directory
- Run installer to auto-copy, or manually copy to: `C:\Users\<User>\AppData\Local\Autodesk\3dsMax\<Version>\ENU\scripts\`

**Old macro button errors after update**
- Restart 3ds Max to clear old actions from memory

**Installer can't find Python file**
- Keep installer and Python file in same folder
- Check MAXScript Listener for search paths

**Click detection not working**
- Verify using `viewport().mapFromGlobal()` not `mapFromGlobal()`
- Check `click_regions` are stored with proper viewport coordinates
- Ensure `current_item_y` is stored as int, not QRect

**Icons not displaying**
- Icons fall back to Unicode emojis if native icons fail
- Custom delegate is required for correct rendering in 3ds Max

**Double-click firing twice**
- Ensure only ONE `itemClicked.emit()` per click event
- Don't manually emit `itemClicked` in `mousePressEvent` if calling `super()`

## Planned Features

See `wishlist.txt` for detailed feature specifications.
- always increment the version number of the tool in the minor minor number, So I can keep track of if I have the latest version. And print the version made in this window.