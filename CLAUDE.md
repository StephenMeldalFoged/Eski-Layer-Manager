# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Eski Layer Manager** is a dockable layer and object manager utility for Autodesk 3ds Max 2026+. It provides a modern Qt-based UI for managing layers and objects within 3ds Max, with bi-directional synchronization with the native layer manager and full support for nested layer hierarchies.

**Current Version:** 0.6.5

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

**eski-layer-manager.py** (~1200 lines) - Main Python application
- `EskiLayerManager` class: QDockWidget-based main window
- Singleton pattern with list-based instance variable: `_layer_manager_instance = [None]`
- `show_layer_manager()`: Entry point function called from 3ds Max
- `VisibilityIconDelegate`: Custom Qt delegate for rendering visibility icons correctly in 3ds Max
- Bi-directional sync: Timer-based polling (500ms) syncs with native layer manager changes
- Callback system: Registers 3ds Max callbacks for automatic refresh on layer events
- **Nested layer hierarchy support**: Full parent-child relationships with drag-and-drop reparenting
- Alphabetical sorting: Layers sorted by name (case-insensitive) at each hierarchy level
- Three columns: Visibility icon | Add selection icon | Layer name
- Drag-and-drop: Reorder and reparent layers with visual feedback

**install-macro-button.ms** - MAXScript installer with GUI
- Creates macro button in "Eski Tools" category
- Auto-copies Python file from repo to user scripts directory
- Searches multiple locations: script folder, Desktop, Downloads, Documents
- Installs to `#userScripts` (user-writable), NOT `#scripts` (requires admin)
- Generates `EskiLayerManager.mcr` in `#userMacros`
- Uninstaller removes both .mcr and .py files
- Version tracking: Update `installerVersion` variable to match Python `VERSION`

### File Naming Convention

The installer copies `eski-layer-manager.py` → `eski_layer_manager.py` (hyphen becomes underscore) to make it importable as a Python module.

## Critical Implementation Details

### Singleton Pattern (Lines 38-43, 1025-1080)

**IMPORTANT:** The singleton uses a list container `_layer_manager_instance = [None]` instead of a simple variable. This prevents garbage collection issues in 3ds Max's embedded Python environment.

```python
# Module initialization guard prevents re-initialization
if '_ESKI_LAYER_MANAGER_INITIALIZED' not in globals():
    _ESKI_LAYER_MANAGER_INITIALIZED = True
    _layer_manager_instance = [None]

# Access pattern
_layer_manager_instance[0] = layer_manager  # Store instance
instance = _layer_manager_instance[0]        # Retrieve instance
```

**Why list container:**
- Mutable objects resist garbage collection better than simple references
- Prevents accidental rebinding
- List object persists across function calls even if module namespace is modified

**C++ Object Lifetime Validation:**
Always check if Qt widget is still valid before accessing:
```python
try:
    _layer_manager_instance[0].isVisible()  # Test if C++ object exists
    # Object is valid, use it
except (RuntimeError, AttributeError):
    # C++ object was deleted, create new instance
    _layer_manager_instance[0] = None
```

### Icon Loading (Lines 146-260)

Icons are loaded using multiple fallback strategies due to 3ds Max's inconsistent icon resource paths:

1. **Primary:** `qtmax.LoadMaxMultiResIcon("StateSets/Visible")` - Official method
2. **Fallback:** Qt resource paths like `":/StateSets/Visible_16"`
3. **Ultimate fallback:** Unicode emojis ("👁" for visible, "✖" for hidden, "+" for add selection)

Priority order: StateSets > SceneExplorer > LayerExplorer

Icons must have pixel data to be valid (check `availableSizes()` length > 0).

### Custom Icon Delegate (Lines 46-97)

`VisibilityIconDelegate` is required because 3ds Max's Qt integration has display issues with icons in tree widgets. The delegate:
- Manually renders icons in column 0 using full column width
- Handles both native QIcon and Unicode text fallbacks
- Centers icons properly in the cell
- Uses `AlignCenter` for proper positioning

### Bi-Directional Sync (Lines 714-772)

Two mechanisms keep the UI in sync with 3ds Max:

1. **Timer-based polling (500ms):** `check_current_layer_sync()`
   - Detects current layer changes
   - Detects visibility state changes
   - Updates UI without full refresh
   - Silently fails to avoid error spam

2. **Callback system:** `setup_callbacks()` (Lines 774-823)
   - Registers MaxScript callbacks for layer events
   - `layerCreated`, `layerDeleted`, `nodeLayerChanged` → full refresh
   - `layerCurrent` → selection update only
   - Scene events (`filePostOpen`, `systemPostReset`, `systemPostNew`) → close and reopen window

**IMPORTANT:** Callbacks execute MaxScript code that calls back into Python:
```maxscript
fn EskiLayerManagerCallback = (
    python.Execute "import eski_layer_manager; eski_layer_manager.refresh_from_callback()"
)
```

### Layer Operations

**Visibility Toggle (Column 0, Lines 511-543):**
- Toggles `layer.ishidden` property
- Updates icon immediately
- Does NOT change current layer or selection

**Add Selection to Layer (Column 1, Lines 545-583):**
- Assigns selected objects to clicked layer using `layer.addNode(obj)`
- Does NOT change current layer
- Processes all objects in `rt.selection`

**Set Current Layer (Column 2, Lines 585-606):**
- Sets `layer.current = True`
- Updates selection in tree to match

**Rename Layer (Double-click Column 2, Lines 608-706):**
- Stores original name in `self.editing_layer_name`
- Makes item editable with `ItemIsEditable` flag
- On commit, calls `layer.setname(new_name)`
- Re-sorts layer list alphabetically after rename

### Nested Layer Hierarchy (Lines 349-504)

**Full support for nested layers like the native layer manager.**

**Building the hierarchy:**
1. Get all layers from `layerManager`
2. Filter to find root layers: `layer.getParent() is None or == rt.undefined`
3. Sort root layers alphabetically
4. Recursively add each layer and its children using `_add_layer_to_tree()`

**Key methods:**
- `layer.getParent()` - Returns parent layer or None/undefined for root layers
- `layer.getNumChildren()` - Count of direct children
- `layer.getChild(index)` - Get child by 1-based index (MAXScript convention)
- `layer.setParent(parent)` - Set parent layer (use `rt.undefined` for root)

**Parent layers:**
- Automatically expanded by default (`item.setExpanded(True)`)
- Children sorted alphabetically within each parent

**Drag-and-Drop Reparenting (Lines 767-885):**
- Drop **ON** an item → make dragged layer a child of target
- Drop **ABOVE/BELOW** an item → make dragged layer a sibling (same parent as target)
- Drop on **empty space** → make dragged layer a root layer
- Circular reference prevention: Cannot make layer child of itself or its own descendant
- `_is_descendant()` walks up parent chain to prevent invalid hierarchies
- After drop, calls `populate_layers()` to refresh UI

**Recursive search:**
- `_find_layer_item()` recursively searches tree to find layer by name
- Required because layers can be nested at any depth

### Window Position Memory (Lines 943-1008)

Position is saved to both:
1. Scene file properties: `rt.fileProperties.addProperty()`
2. Global INI file: `rt.setINISetting()`

Data format: `"{is_floating};{x};{y};{width};{height}"`

Priority: Scene file > Global INI > Default position

## Development Workflow

### Testing the UI Without 3ds Max

```bash
python eski-layer-manager.py
```
This runs standalone mode with a basic Qt window (no 3ds Max integration, uses test data).

### Installing in 3ds Max

1. Keep `install-macro-button.ms` and `eski-layer-manager.py` in the same directory
2. In 3ds Max: F11 → File > Open → select installer script → Ctrl+E
3. Click "Install / Upgrade to Latest Version"
4. Installer auto-copies Python file to user scripts directory
5. Add macro button to toolbar via Customize UI (instructions in installer)

### Making Changes

After modifying code:
1. Run installer again (upgrades existing installation)
2. **Restart 3ds Max** (clears old actions from memory - MaxScript limitation)
3. Macro button automatically uses `importlib.reload()` to load latest code

**CRITICAL:** Do NOT use `importlib.reload()` in the macro button code - it breaks the singleton pattern. The current implementation imports normally and relies on module initialization guards.

### Version Management

When adding features, update ALL THREE locations:
1. `VERSION` constant in `eski-layer-manager.py` (line 36)
2. `installerVersion` in `install-macro-button.ms` (line 6)
3. Add entry to `Eski-LayerManager-By-Claude-Version-History.txt` with date, tag, and features

### Debugging

The code includes extensive debug output with prefixes:
- `[IMPORT]` - Module imports
- `[INIT]` - Module initialization
- `[ICONS]` - Icon loading
- `[UI]` - UI setup
- `[POPULATE]` - Layer population
- `[HIERARCHY]` - Layer hierarchy operations (v0.6.1+)
- `[DRAG]` - Drag-and-drop operations (v0.6.1+)
- `[SELECT]` - Layer selection
- `[LAYER]` - Layer operations
- `[RENAME]` - Rename operations
- `[SYNC]` - Synchronization
- `[CALLBACKS]` - Callback registration/execution
- `[POSITION]` - Window position save/restore
- `[ERROR]` - Errors with stack traces

Use `get_instance_status()` helper function to inspect singleton state.

## Important 3ds Max Integration Notes

### Python Path Handling
The macro button adds `#userScripts` to Python's `sys.path` at runtime because 3ds Max doesn't automatically include user script directories in Python's search path.

### Docking API
- Use `qtmax.GetQMaxMainWindow()` to get the 3ds Max main window as QMainWindow
- Parent QDockWidget to this window
- Use `addDockWidget(QtCore.Qt.RightDockWidgetArea, widget)` to dock programmatically
- `setAllowedAreas(LeftDockWidgetArea | RightDockWidgetArea)` restricts docking positions

### Garbage Collection in 3ds Max
Qt widgets can be garbage collected in 3ds Max's Python environment. Always keep a reference in a mutable container (list, dict) at module level, not just a simple variable.

### Action Manager Limitations
MAXScript provides no API to unregister actions at runtime. Actions loaded during a session persist in the Customize UI until 3ds Max restarts. This is a 3ds Max limitation, not a bug.

### MaxScript Callback Limitations
- `postMerge` callback is NOT supported in 3ds Max 2026
- `layerCurrent` callback may not exist in all Max versions
- Callbacks persist until explicitly removed or Max restarts

## Common Issues

**"ModuleNotFoundError: No module named 'eski_layer_manager'"**
- Python file not in user scripts directory
- Run installer to auto-copy, or manually copy to: `C:\Users\<User>\AppData\Local\Autodesk\3dsMax\<Version>\ENU\scripts\`

**Multiple instances appear (singleton broken)**
- Check that module initialization guard is working (`_ESKI_LAYER_MANAGER_INITIALIZED`)
- Verify instance is stored in list container: `_layer_manager_instance = [None]`
- Do NOT use `importlib.reload()` in macro button

**Old macro button errors after update**
- Restart 3ds Max to clear old actions from memory

**Installer can't find Python file**
- Keep installer and Python file in same folder
- Check MAXScript Listener for search paths

**Icons not displaying**
- Check debug output for icon loading attempts
- Icons fall back to Unicode emojis if native icons fail
- Custom delegate is required for correct rendering in 3ds Max

**Callbacks not working**
- Check MAXScript Listener for callback errors
- Verify callback functions are defined globally
- Some callbacks may not be available in all Max versions

**Window doesn't remember position**
- Position is saved on close - check `closeEvent()` is called
- Try saving scene file (scene properties persist with file)
- Check INI file permissions

## Planned Features (wishlist.txt)

Top priorities based on user research:
1. Bulk layer visibility & freeze control with isolation mode
2. Quick object selection by layer (click to select all objects)
3. Drag-and-drop object assignment between layers
4. Layer hierarchy with parent/child relationships (nested layers)
5. Smart layer search/filter with property display

See `wishlist.txt` for detailed feature specifications and API methods.

## Reference Documentation

See `External-Links.txt` for:
- 3ds Max Python API documentation
- pymxs and MaxPlus documentation
- Qt icon resource guides
- Community forums and tutorials