# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Eski Layer Manager** is a dockable layer and object manager utility for Autodesk 3ds Max 2026+. It provides a modern Qt-based UI for managing layers and objects within 3ds Max, improving upon the built-in layer management tools.

**Current Versions:**
- Layer Manager: 0.24.3 (2026-01-05 14:27)
- Layer Exporter: 0.7.1 (2026-01-05 20:05) - *in exporter branch*

## Quick Reference

```bash
# Test UI standalone (no 3ds Max)
python eski-layer-manager.py

# Install/upgrade in 3ds Max
# F11 → File > Open → install-Eski-Layer-Manager.ms → Ctrl+E

# Test singleton pattern (in 3ds Max)
python.ExecuteFile "E:\\Github\\Eski-Layer-Manager\\tests\\test_singleton.py"

# Launch Layer Manager from 3ds Max Python console
import eski_layer_manager
eski_layer_manager.show_layer_manager()

# Launch Exporter from 3ds Max Python console
import eski_layer_exporter
eski_layer_exporter.show_exporter()
```

## Project Structure

```
Eski-Layer-Manager/
├── eski-layer-manager.py          # Main Python application (1100+ lines)
├── eski-layer-exporter.py         # FBX exporter module (1113 lines) - in exporter branch
├── install-Eski-Layer-Manager.ms  # MAXScript installer with GUI
├── CLAUDE.md                      # This file - development guide
├── README.md                      # User-facing documentation
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

**eski-layer-exporter.py** - FBX export module (v0.7.1 - in exporter branch)
- `EskiExporterDialog` class: Main dialog with collapsible sections (QDialog-based, not dockable)
- `CollapsibleSection` class: Custom widget for collapsible UI sections
- Singleton pattern with global `_exporter_instance` to prevent multiple windows
- `show_exporter()`: Toggle entry point (open if closed, close if open)
- **Settings persistence**: Export folder, checked layers, and animation clips saved with .max file
- **Adaptive gradient highlighting**: Checked layers highlighted with depth-based color gradient
- **Hierarchical layer export**: Top-level layer checks include all sublayers recursively
- **Animation clips management**: Define multiple animation clips with frame ranges
- **FBX export**: Each checked layer exported as separate .fbx file

**install-Eski-Layer-Manager.ms** - MAXScript installer with GUI (v0.21.0+)
- Creates macro button in "Eski Tools" category
- Auto-copies **both Python modules** (eski-layer-manager.py and eski-layer-exporter.py) from repo to user scripts directory
- Searches multiple locations: script folder, Desktop, Downloads, Documents
- Installs to `#userScripts` (user-writable), NOT `#scripts` (requires admin)
- Generates `EskiLayerManager.mcr` in `#userMacros`
- Uninstaller removes .mcr and both .py files
- Note: Actions persist in memory until 3ds Max restart (MAXScript limitation)

### File Naming Convention

Important: The installer copies files with hyphens to underscores to make them importable as Python modules:
- `eski-layer-manager.py` → `eski_layer_manager.py`
- `eski-layer-exporter.py` → `eski_layer_exporter.py`

This allows importing via: `import eski_layer_manager` and `import eski_layer_exporter`

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

**Keyboard modifiers (v0.19.8+):**
- **Eye icon click**: Toggle layer visibility
- **Ctrl+Click eye icon**: Isolate layer (hide all other layers)
- **Ctrl+Click eye icon again (v0.19.9+)**: Restore pre-isolation visibility state (undo isolation)

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
- **Object names display:** Shows object name with object count when layer is selected

Key methods:
- `populate_objects(layer_name)` - Fills objects tree for specified layer
- `on_object_selection_changed()` - Syncs tree selection to scene selection
- `reassign_objects_to_layer()` - Handles drag-drop reassignment from objects to layers

**Important:** Objects tree has simpler rendering than layers tree - no custom inline icons, just standard tree view with object names.

### Position Persistence (v0.11.7+)

Window docking position and state are preserved between sessions:
- Position stored relative to 3ds Max main window
- Dock stacking order tracked and restored
- Settings persist across 3ds Max restarts
- Toggle feature available through UI

### UI State Persistence (v0.24.0+)

Layer tree state is preserved across refresh operations:
- **Expand/collapse state (v0.24.1+):** Tree expansion state maintained when refreshing
- **Inline rename persistence (v0.24.2+):** Layer names retain edit state during creation
- **Parent-hidden inheritance (v0.24.0+):** Child layers correctly show inherited hidden state from parents
- State tracking uses layer names as keys to survive tree rebuilds

### Context Menu System (v0.19.0+)

Right-click context menus provide quick access to layer operations:
- **Layer tree context menu:** Right-click on layers for operations
  - Create new layer (on empty area or on existing layer)
  - Delete layer
  - Rename layer (inline edit)
  - Hide/Show layer
  - Freeze/Unfreeze layer
  - Select all objects on layer
  - Isolate layer
- **Objects tree context menu:** Right-click on objects for operations
  - Select object in viewport
  - Remove from layer
  - Focus on object in viewport
- **Instant highlighting:** Zero-lag visual feedback on context menu opening (v0.19.1+)
- **Empty area detection:** Right-click on empty space to create new layers (v0.19.2+)
- **Qt-based menus:** Uses native Qt context menus (QMenu) with QAction triggers
- **menuMan integration:** Can access 3ds Max's built-in menu system via `rt.menuMan` (v0.18.7+)

Key implementation patterns:
```python
# Context menu on right-click
def contextMenuEvent(self, event):
    item = self.itemAt(event.pos())
    menu = QtWidgets.QMenu(self)

    # Add actions
    action = menu.addAction("Action Name")
    action.triggered.connect(lambda: self.handle_action(item))

    # Show menu at cursor
    menu.exec_(event.globalPos())
```

### Status Bar with Tips System (v0.20.2+)

Built-in status bar displays helpful tips and version information:
- **Version display:** Shows version for 10 seconds on launch
- **Cycling tips:** Rotates through 40+ tips and tricks every 12 seconds
- **Pause on hover:** Timer pauses when mouse hovers over status bar
- **Click to skip:** Click status bar to advance to next tip immediately
- **Right-click tips window:** Right-click status bar to open scrollable tips reference window
- **Persistent across sessions:** Last shown tip index persisted via QSettings

Key implementation:
```python
self.status_timer = QtCore.QTimer()
self.status_timer.timeout.connect(self.show_next_tip)
self.status_timer.start(12000)  # 12 second interval

# Status bar events
self.status_bar.enterEvent = lambda e: self.status_timer.stop()
self.status_bar.leaveEvent = lambda e: self.status_timer.start(12000)
```

Tips array stored in `self.tips` list with 40+ entries covering:
- Layer management workflows
- Keyboard shortcuts
- Drag-and-drop techniques
- Context menu features
- Visibility and isolation tips

### FBX Exporter Architecture (v0.7.1+) - *exporter branch*

The FBX exporter provides streamlined workflow for exporting layers to separate FBX files with settings persistence:

**Settings Persistence with .max Files:**
- Uses 3ds Max `fileProperties` API to store settings as JSON in custom properties
- Stores: export folder path, checked layers (by name), animation clips data
- Critical API quirk: `findProperty()` returns INDEX, not value - use `getPropertyValue()` to retrieve actual data
- Pattern: Delete old property before adding new one to update values
- Settings automatically reload when file is opened via callback system

```python
# Save settings to file
settings_json = json.dumps(settings)
try:
    rt.fileProperties.deleteProperty(rt.Name("custom"), rt.Name("EskiExporterSettings"))
except:
    pass
escaped_json = settings_json.replace("\\", "\\\\").replace('"', '\\"')
maxscript_cmd = f'fileProperties.addProperty #custom #EskiExporterSettings "{escaped_json}"'
rt.execute(maxscript_cmd)

# Load settings from file
prop_index = rt.fileProperties.findProperty(rt.Name("custom"), rt.Name("EskiExporterSettings"))
if prop_index and str(prop_index) != "undefined" and prop_index != 0:
    settings_json = rt.fileProperties.getPropertyValue(rt.Name("custom"), prop_index)
    settings = json.loads(str(settings_json))
```

**Adaptive Gradient Highlighting:**
- Checked layers and their children highlighted with depth-based gradient
- Algorithm: Find max depth in tree, then distribute color range from dark green (60,120,60) to desaturated gray (35,45,35)
- Adapts to any hierarchy depth automatically
- Updates on checkbox state changes

**Layer.nodes() API Pattern:**
- MAXScript's `layer.nodes` is a function requiring a class filter argument passed by reference
- Must pass variable with `&` reference operator
- Pattern: Create local array, pass with `&`, return array

```python
maxscript_cmd = f'''
(
    local theLayer = layerManager.getLayerFromName "{escaped_name}"
    local result = #()
    theLayer.nodes &result
    result
)
'''
nodes_array = rt.execute(maxscript_cmd)
```

**Callback System:**
- `filePostOpen`: Close and reopen window to load fresh settings
- `systemPostReset` / `systemPostNew`: Clear all UI and settings
- `layerCreated` / `layerDeleted`: Refresh layer tree
- Timer-based refresh (500ms): Detect scene reset by checking if settings disappeared

**Export Workflow:**
1. User checks top-level layers to export (includes all sublayers)
2. Each checked layer collected recursively with all children
3. Objects selected in 3ds Max viewport
4. FBX exported with `exportFile` MAXScript command
5. Silent operation - no success dialog, only status label update

Key methods:
- `populate_layers()` - Build hierarchical layer tree from 3ds Max
- `get_layer_objects_recursive()` - Collect objects from layer and all children
- `save_settings()` / `load_settings()` - Persist settings with file
- `update_layer_highlighting()` - Apply adaptive gradient to checked layers
- `do_export()` - Main export logic, creates one .fbx per checked layer

## Development Workflow

### Git Branching Strategy

- **main**: Stable releases with version tags for layer manager
- **exporter**: Development branch for FBX exporter module (eski-layer-exporter.py)
- **Feature branches**: Named descriptively for specific features
- Version tags follow semantic versioning (v0.x.x)
- Detailed version history available in `docs/Eski-LayerManager-By-Claude-Version-History.txt`
- When creating PRs, target the `main` branch (or `exporter` branch for exporter features)

### Testing the UI

To test UI changes without 3ds Max:
```bash
# Test Layer Manager standalone
python eski-layer-manager.py

# Test Exporter standalone (exporter branch)
python eski-layer-exporter.py
```
Both run in standalone mode with basic Qt windows (no 3ds Max integration, uses dummy data).

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

Update these locations when bumping versions (use date and time of last edit):
- eski-layer-manager.py line 5: Docstring `Version: X.X.X (YYYY-MM-DD HH:MM)`
- eski-layer-manager.py line 36: `VERSION = "X.X.X (YYYY-MM-DD HH:MM)"`
- eski-layer-exporter.py line 5: Docstring `Version: X.X.X (YYYY-MM-DD HH:MM)`
- eski-layer-exporter.py line 26: `VERSION = "X.X.X (YYYY-MM-DD HH:MM)"`
- install-Eski-Layer-Manager.ms line 6: `local installerVersion = "X.X.X (YYYY-MM-DD HH:MM)"` (only when installer changes)
- CLAUDE.md line 10-11: Update both Layer Manager and Exporter versions in `**Current Versions:**` section

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

# Get nodes (CRITICAL: nodes is a function, not a property)
# Must pass array by reference with & operator
maxscript_cmd = '''
(
    local result = #()
    theLayer.nodes &result
    result
)
'''
nodes_array = rt.execute(maxscript_cmd)

# Current layer
rt.layerManager.current = layer      # Set active layer

# File Properties API (for saving settings with .max file)
# findProperty returns INDEX, not value!
prop_index = rt.fileProperties.findProperty(rt.Name("custom"), rt.Name("PropertyName"))
if prop_index and str(prop_index) != "undefined" and prop_index != 0:
    value = rt.fileProperties.getPropertyValue(rt.Name("custom"), prop_index)

# To update property, must delete then add
rt.fileProperties.deleteProperty(rt.Name("custom"), rt.Name("PropertyName"))
rt.fileProperties.addProperty(rt.Name("custom"), rt.Name("PropertyName"), "value")
```

**Critical:**
- MAXScript uses **1-based indexing** for children (`getChild()`), but Python/pymxs uses **0-based indexing** for layers (`getLayer()`)
- `layer.nodes` is a FUNCTION requiring a reference argument with `&`, not a property
- `fileProperties.findProperty()` returns INDEX, use `getPropertyValue()` to get actual value

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

**Exporter: Settings not saving/loading (exporter branch)**
- Ensure using `getPropertyValue()` not `findProperty()` to retrieve value
- `findProperty()` returns INDEX, not the actual stored value
- Must delete old property before adding new one to update

**Exporter: "error return without exception set" when exporting (exporter branch)**
- Issue is with `layer.nodes` access - it's a function, not a property
- Must use MAXScript with reference variable: `theLayer.nodes &result`
- Cannot access directly via pymxs like `layer.nodes[i]`

**Exporter: Settings don't clear on file reset (exporter branch)**
- Use timer to detect scene reset by checking if settings disappeared
- Check if file property exists but UI has data - means scene was reset
- Callback system may not fire reliably for all reset scenarios

## Feature Implementation Status

**Layer Manager - Implemented Features:**
- ✓ Dockable window interface (left/right docking)
- ✓ Live layer list with automatic refresh via timer and callbacks
- ✓ Layer hierarchy with parent-child relationships and drag-drop reparenting
- ✓ Bi-directional sync between UI and 3ds Max (500ms polling + callbacks)
- ✓ Object tree showing objects in selected layer
- ✓ Object selection sync (click in tree → select in viewport)
- ✓ Drag-and-drop object reassignment between layers
- ✓ Layer visibility toggle (eye icon)
- ✓ Add selection to layer (+ icon)
- ✓ Set current layer (click layer name)
- ✓ Context menus for layers and objects (right-click)
- ✓ Create/delete/rename layers via context menu
- ✓ Hide/show/freeze/unfreeze layers
- ✓ Isolate layer functionality (Ctrl+Click eye icon)
- ✓ Position persistence across sessions
- ✓ UI state persistence (expand/collapse, inline rename)
- ✓ Parent-hidden inheritance icon display
- ✓ Singleton pattern (prevents multiple instances)
- ✓ Custom tree rendering with inline icons
- ✓ Status bar with cycling tips and tricks
- ✓ Right-click tips reference window
- ✓ Hover-to-pause status bar timer

**FBX Exporter - Implemented Features (exporter branch):**
- ✓ Settings persistence with .max file (fileProperties API)
- ✓ Export folder selection with native 3ds Max dialog
- ✓ Hierarchical layer tree display
- ✓ Top-level layer checkbox selection (includes all sublayers)
- ✓ Adaptive gradient highlighting for checked layers
- ✓ Collapsible UI sections
- ✓ Animation clips management (add/remove clips with frame ranges)
- ✓ FBX export (one file per checked layer)
- ✓ Recursive object collection from layer hierarchy
- ✓ Silent export operation (no success dialog)
- ✓ Automatic refresh on layer changes
- ✓ File open/reset/new callback handling
- ✓ Singleton pattern (toggle show/hide)
- ✓ Standalone testing mode

**Planned Features:**
See `docs/wishlist.txt` for detailed feature specifications and priorities.

**Development Guidelines:**
- Always increment version number for EVERY change (patch version: 0.19.x → 0.19.y)
- Target 3ds Max 2026+ only - do not reference Max 2024 or earlier documentation
- Search for Max 2026 API documentation first before checking older versions
- Version number is displayed in the window title