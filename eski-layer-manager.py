"""
Eski LayerManager by Claude
A dockable layer and object manager for 3ds Max

Version: 0.5.0
"""

from PySide6 import QtWidgets, QtCore, QtGui

# Import pymxs (required for 3ds Max API access)
try:
    from pymxs import runtime as rt
    print("[IMPORT] Successfully imported pymxs")
except ImportError as e:
    # For development/testing outside 3ds Max
    rt = None
    print(f"[IMPORT] Failed to import pymxs: {e}")

# Import MaxPlus (optional - deprecated in 3ds Max 2023+)
try:
    import MaxPlus
    print("[IMPORT] Successfully imported MaxPlus")
except ImportError:
    MaxPlus = None
    print("[IMPORT] MaxPlus not available (deprecated in 3ds Max 2023+)")

# Try to import qtmax for docking functionality
try:
    import qtmax
    QTMAX_AVAILABLE = True
except ImportError:
    QTMAX_AVAILABLE = False
    print("Warning: qtmax not available. Window will not be dockable.")


VERSION = "0.5.3"

# Module initialization guard - prevents re-initialization on repeated imports
if '_ESKI_LAYER_MANAGER_INITIALIZED' not in globals():
    _ESKI_LAYER_MANAGER_INITIALIZED = True
    # Global instance variable - use a list to prevent garbage collection
    # List makes it a mutable container that survives module namespace issues
    _layer_manager_instance = [None]


class VisibilityIconDelegate(QtWidgets.QStyledItemDelegate):
    """
    Custom delegate for rendering visibility icons in the tree widget
    This gives us full control over icon rendering, fixing display issues in 3ds Max
    """

    def __init__(self, parent=None):
        super(VisibilityIconDelegate, self).__init__(parent)

    def paint(self, painter, option, index):
        """Custom paint method for rendering icons"""
        if index.column() == 0:
            # Column 0 is the visibility icon column

            # Get the tree widget to access column width
            tree_widget = self.parent()
            if tree_widget:
                # Get the full column width
                col_width = tree_widget.columnWidth(0)
                # Create a rect that uses the full column width
                full_rect = QtCore.QRect(0, option.rect.y(), col_width, option.rect.height())
                print(f"[DELEGATE] option.rect: {option.rect}, full column width: {col_width}, full_rect: {full_rect}")
            else:
                full_rect = option.rect

            # Try to get icon first (native icons)
            icon = index.data(QtCore.Qt.DecorationRole)

            if icon and isinstance(icon, QtGui.QIcon) and not icon.isNull():
                # Draw native icon centered in full column width
                painter.save()
                icon.paint(painter, full_rect, QtCore.Qt.AlignCenter)
                painter.restore()
                print(f"[DELEGATE] Painted native icon, isNull={icon.isNull()}, availableSizes={icon.availableSizes()}")
            else:
                # Draw Unicode fallback text centered in full column width
                text = index.data(QtCore.Qt.DisplayRole)
                if text:
                    painter.save()
                    # Set font for Unicode emoji
                    font = painter.font()
                    font.setPointSize(14)
                    font.setBold(True)
                    painter.setFont(font)
                    # Draw text centered
                    painter.drawText(full_rect, QtCore.Qt.AlignCenter, str(text))
                    painter.restore()
                    print(f"[DELEGATE] Painted Unicode '{text}'")
        else:
            # Use default rendering for other columns
            super(VisibilityIconDelegate, self).paint(painter, option, index)


class EskiLayerManager(QtWidgets.QDockWidget):
    """
    Main dockable window for Eski Layer Manager
    """

    def __init__(self, parent=None):
        super(EskiLayerManager, self).__init__(parent)

        # Set window title with version
        self.setWindowTitle(f"Eski LayerManager by Claude {VERSION}")

        # Set window flags for proper integration with 3ds Max
        self.setWindowFlags(QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        # Allow the widget to float
        self.setFloating(False)

        # Set allowed dock areas (left and right as requested)
        self.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)

        # Setup callback for automatic refresh
        self.callback_id = None
        self.setup_callbacks()

        # Track layer names before editing to detect renames
        self.editing_layer_name = None

        # Load native 3ds Max icons for visibility
        self.load_visibility_icons()

        # Initialize UI
        self.init_ui()

        # Restore window position
        self.restore_position()

    def load_visibility_icons(self):
        """Load native 3ds Max visibility icons using Qt resource system"""
        self.icon_visible = None
        self.icon_hidden = None
        self.use_native_icons = False

        # Try using qtmax.LoadMaxMultiResIcon first (official method)
        try:
            import qtmax
            visible_icon = qtmax.LoadMaxMultiResIcon("SceneExplorer/Visible")
            hidden_icon = qtmax.LoadMaxMultiResIcon("SceneExplorer/Hidden")

            if visible_icon and not visible_icon.isNull() and hidden_icon and not hidden_icon.isNull():
                self.icon_visible = visible_icon
                self.icon_hidden = hidden_icon
                self.use_native_icons = True
                # Debug: Check if icons actually have pixmap data
                print(f"[ICONS] Loaded icons using LoadMaxMultiResIcon")
                print(f"[ICONS] Visible icon: isNull={visible_icon.isNull()}, sizes={visible_icon.availableSizes()}")
                print(f"[ICONS] Hidden icon: isNull={hidden_icon.isNull()}, sizes={hidden_icon.availableSizes()}")
                # Try to get a pixmap to verify it has content
                pixmap = visible_icon.pixmap(16, 16)
                print(f"[ICONS] Visible pixmap 16x16: isNull={pixmap.isNull()}, size={pixmap.size()}")
                return
        except Exception as e:
            print(f"[ICONS] LoadMaxMultiResIcon failed: {e}")

        # Try Qt resource system paths
        icon_candidates = [
            (":/SceneExplorer/Visible_16", ":/SceneExplorer/Hidden_16"),
            (":/SceneExplorer/visible_16", ":/SceneExplorer/hidden_16"),
            (":/LayerExplorer/Visible_16", ":/LayerExplorer/Hidden_16"),
            (":/MainUI/Visible_16", ":/MainUI/Hidden_16"),
            (":/Visibility/Visible_16", ":/Visibility/Hidden_16"),
        ]

        for visible_path, hidden_path in icon_candidates:
            visible_icon = QtGui.QIcon(visible_path)
            hidden_icon = QtGui.QIcon(hidden_path)

            if not visible_icon.isNull() and not hidden_icon.isNull():
                # Icons loaded, but check if they have actual pixel data
                # availableSizes() returns empty list if icon has no renderable content
                if len(visible_icon.availableSizes()) > 0 and len(hidden_icon.availableSizes()) > 0:
                    self.icon_visible = visible_icon
                    self.icon_hidden = hidden_icon
                    self.use_native_icons = True
                    print(f"[ICONS] Loaded Qt resource icons with pixel data: {visible_path} / {hidden_path}")
                    return
                else:
                    print(f"[ICONS] Icons at {visible_path} exist but have no pixel data (empty/transparent)")

        # No native icons found - will use Unicode fallback
        print("[ICONS] Native icons not found or empty, using Unicode fallback")

    def init_ui(self):
        """Initialize the user interface"""
        # Create central widget
        central_widget = QtWidgets.QWidget()
        self.setWidget(central_widget)

        # Create main layout
        main_layout = QtWidgets.QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create splitter for top/bottom division
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)

        # Top section - Layer tree view
        top_widget = QtWidgets.QWidget()
        top_layout = QtWidgets.QVBoxLayout(top_widget)
        top_layout.setContentsMargins(5, 5, 5, 5)

        # Add label for layers section
        layers_label = QtWidgets.QLabel("Layers")
        layers_label.setStyleSheet("font-weight: bold; padding: 2px;")
        top_layout.addWidget(layers_label)

        # Create tree widget for layers
        self.layer_tree = QtWidgets.QTreeWidget()
        self.layer_tree.setHeaderLabels(["V", "Layer Name"])  # First column for visibility icon
        self.layer_tree.setColumnWidth(0, 40)  # Icon column width
        self.layer_tree.header().setStretchLastSection(True)  # Make name column stretch
        self.layer_tree.setAlternatingRowColors(True)
        self.layer_tree.itemClicked.connect(self.on_layer_clicked)
        self.layer_tree.itemDoubleClicked.connect(self.on_layer_double_clicked)
        self.layer_tree.itemChanged.connect(self.on_layer_renamed)
        self.layer_tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.layer_tree.customContextMenuRequested.connect(self.on_layer_context_menu)

        # Set icon size larger for better visibility
        self.layer_tree.setIconSize(QtCore.QSize(16, 16))

        # Set uniform row heights for better icon display
        self.layer_tree.setUniformRowHeights(True)

        # Install custom delegate for column 0 (visibility icons)
        # This gives us direct control over rendering and fixes display issues
        self.visibility_delegate = VisibilityIconDelegate(self.layer_tree)
        self.layer_tree.setItemDelegateForColumn(0, self.visibility_delegate)
        print("[UI] Custom visibility icon delegate installed")

        top_layout.addWidget(self.layer_tree)

        # Bottom section - will contain object list
        bottom_widget = QtWidgets.QWidget()
        bottom_layout = QtWidgets.QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(5, 5, 5, 5)

        # Add label for objects section
        objects_label = QtWidgets.QLabel("Objects")
        objects_label.setStyleSheet("font-weight: bold; padding: 2px;")
        bottom_layout.addWidget(objects_label)

        # Placeholder for objects list
        bottom_placeholder = QtWidgets.QLabel("Objects in selected layer will appear here")
        bottom_placeholder.setAlignment(QtCore.Qt.AlignCenter)
        bottom_placeholder.setStyleSheet("padding: 20px; color: #999;")
        bottom_layout.addWidget(bottom_placeholder)

        # Add widgets to splitter
        self.splitter.addWidget(top_widget)
        self.splitter.addWidget(bottom_widget)

        # Set initial sizes (60% top, 40% bottom)
        self.splitter.setSizes([240, 160])

        # Add splitter to main layout
        main_layout.addWidget(self.splitter)

        # Set minimum size
        self.setMinimumSize(250, 400)

        # Add refresh button
        refresh_btn = QtWidgets.QPushButton("Refresh Layers")
        refresh_btn.clicked.connect(self.populate_layers)
        top_layout.insertWidget(1, refresh_btn)

        # Populate layers from 3ds Max
        self.populate_layers()

    def populate_layers(self):
        """Populate the layer list with layers from 3ds Max"""
        # Temporarily disconnect itemChanged signal to avoid triggering rename during population
        try:
            self.layer_tree.itemChanged.disconnect(self.on_layer_renamed)
        except:
            pass

        self.layer_tree.clear()

        if rt is None:
            # Testing mode outside 3ds Max - add dummy data
            print("[POPULATE] rt is None - running in TEST MODE")
            item1 = QtWidgets.QTreeWidgetItem(self.layer_tree, ["👁", "[TEST MODE] 0 (default)"])
            item2 = QtWidgets.QTreeWidgetItem(self.layer_tree, ["👁", "[TEST MODE] Layer 1"])
            item3 = QtWidgets.QTreeWidgetItem(self.layer_tree, ["👁", "[TEST MODE] Layer 2"])
            # Reconnect signal
            self.layer_tree.itemChanged.connect(self.on_layer_renamed)
            return

        print("[POPULATE] rt is available - loading real layers")

        try:
            # Get the layer manager from 3ds Max
            layer_manager = rt.layerManager

            # Get all layers and add them to the list
            layer_count = layer_manager.count
            print(f"[DEBUG] Found {layer_count} layers in scene")

            for i in range(layer_count):
                layer = layer_manager.getLayer(i)
                if layer:
                    # Get the layer name and visibility
                    layer_name = str(layer.name)
                    is_hidden = layer.ishidden

                    print(f"[DEBUG] Layer {i}: '{layer_name}', hidden={is_hidden}")

                    # Add to tree with icon in first column, name in second
                    if self.use_native_icons:
                        # Use native icons
                        item = QtWidgets.QTreeWidgetItem(self.layer_tree, ["", layer_name])
                        item.setIcon(0, self.icon_hidden if is_hidden else self.icon_visible)
                        item.setTextAlignment(0, QtCore.Qt.AlignCenter)
                    else:
                        # Unicode fallback with larger font and center alignment
                        icon_text = "👁" if not is_hidden else "✖"
                        item = QtWidgets.QTreeWidgetItem(self.layer_tree, [icon_text, layer_name])
                        item.setTextAlignment(0, QtCore.Qt.AlignCenter)
                        # Make icon text larger and bold
                        font = item.font(0)
                        font.setPointSize(12)
                        font.setBold(True)
                        item.setFont(0, font)

        except Exception as e:
            # If layer access fails, show error
            import traceback
            error_msg = f"Error loading layers: {str(e)}\n{traceback.format_exc()}"
            print(f"[ERROR] {error_msg}")
            QtWidgets.QTreeWidgetItem(self.layer_tree, [error_msg])

        # Reconnect the itemChanged signal
        self.layer_tree.itemChanged.connect(self.on_layer_renamed)

    def on_layer_clicked(self, item, column):
        """Handle layer click - toggle visibility on icon column, set active on name column"""
        if rt is None:
            return

        try:
            # Get the layer name from the tree item (column 1)
            layer_name = item.text(1)

            # Don't process test mode items
            if layer_name.startswith("[TEST MODE]"):
                return

            # Column 0 = icon (toggle visibility)
            # Column 1 = name (set as current layer)
            if column == 0:
                # Toggle visibility
                self.toggle_layer_visibility(item, layer_name)
            elif column == 1:
                # Set as current layer
                self.set_current_layer(layer_name)

        except Exception as e:
            import traceback
            error_msg = f"Error handling layer click: {str(e)}\n{traceback.format_exc()}"
            print(f"[ERROR] {error_msg}")

    def toggle_layer_visibility(self, item, layer_name):
        """Toggle layer visibility (hide/unhide)"""
        if rt is None:
            return

        try:
            # Find the layer in 3ds Max by name
            layer_manager = rt.layerManager
            layer_count = layer_manager.count

            for i in range(layer_count):
                layer = layer_manager.getLayer(i)
                if layer and str(layer.name) == layer_name:
                    # Toggle visibility
                    layer.ishidden = not layer.ishidden

                    # Update icon (native if available, Unicode fallback otherwise)
                    if self.use_native_icons:
                        item.setIcon(0, self.icon_hidden if layer.ishidden else self.icon_visible)
                        item.setTextAlignment(0, QtCore.Qt.AlignCenter)
                    else:
                        new_icon_text = "✖" if layer.ishidden else "👁"
                        item.setText(0, new_icon_text)
                        item.setTextAlignment(0, QtCore.Qt.AlignCenter)

                    status = "hidden" if layer.ishidden else "visible"
                    print(f"[LAYER] Set layer '{layer_name}' to {status}")
                    break

        except Exception as e:
            import traceback
            error_msg = f"Error toggling layer visibility: {str(e)}\n{traceback.format_exc()}"
            print(f"[ERROR] {error_msg}")

    def set_current_layer(self, layer_name):
        """Set the layer as current/active in 3ds Max"""
        if rt is None:
            return

        try:
            # Find the layer in 3ds Max by name
            layer_manager = rt.layerManager
            layer_count = layer_manager.count

            for i in range(layer_count):
                layer = layer_manager.getLayer(i)
                if layer and str(layer.name) == layer_name:
                    # Set this layer as the current layer
                    layer.current = True
                    print(f"[LAYER] Set current layer to: {layer_name}")
                    break

        except Exception as e:
            import traceback
            error_msg = f"Error setting active layer: {str(e)}\n{traceback.format_exc()}"
            print(f"[ERROR] {error_msg}")

    def on_layer_double_clicked(self, item, column):
        """Handle layer double-click - start inline rename"""
        print("[RENAME] Double-click detected")

        # Only rename on column 1 (name column), not column 0 (icon)
        if column != 1:
            return

        # Don't process test mode items
        if item.text(1).startswith("[TEST MODE]"):
            print("[RENAME] Skipping test mode item")
            return

        # Store the original name before editing
        self.editing_layer_name = item.text(1)
        print(f"[RENAME] Starting edit for layer: {self.editing_layer_name}")

        # Block signals while making item editable to avoid premature itemChanged trigger
        self.layer_tree.blockSignals(True)
        item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
        self.layer_tree.blockSignals(False)

        # Now start editing (column 1 = name)
        self.layer_tree.editItem(item, 1)
        print("[RENAME] Edit mode activated")

    def on_layer_context_menu(self, position):
        """Handle right-click context menu on layer"""
        item = self.layer_tree.itemAt(position)
        if item is None:
            return

        # Create context menu
        menu = QtWidgets.QMenu(self)
        rename_action = menu.addAction("Rename Layer")

        # Show menu and get selected action
        action = menu.exec(self.layer_tree.viewport().mapToGlobal(position))

        if action == rename_action:
            # Trigger inline rename on column 1 (name column)
            self.on_layer_double_clicked(item, 1)

    def on_layer_renamed(self, item, column):
        """Handle layer rename after inline editing"""
        print(f"[RENAME] on_layer_renamed called, column: {column}, editing_layer_name: {self.editing_layer_name}")

        # Only process renames on column 1 (name column)
        if column != 1:
            return

        if rt is None or self.editing_layer_name is None:
            print("[RENAME] Skipping - rt is None or not editing")
            return

        try:
            # Get the new name from the item (column 1)
            new_name = item.text(1)
            old_name = self.editing_layer_name

            print(f"[RENAME] Old name: '{old_name}', New name: '{new_name}'")

            # Don't process test mode items
            if old_name.startswith("[TEST MODE]"):
                print("[RENAME] Skipping test mode item")
                return

            # Only process if name actually changed
            if new_name != old_name and new_name:
                print(f"[RENAME] Name changed, updating in 3ds Max")
                # Find the layer in 3ds Max by name
                layer_manager = rt.layerManager
                layer_count = layer_manager.count

                for i in range(layer_count):
                    layer = layer_manager.getLayer(i)
                    if layer and str(layer.name) == old_name:
                        # Rename the layer in 3ds Max
                        layer.setname(new_name)
                        print(f"[LAYER] Renamed layer from '{old_name}' to '{new_name}'")
                        break
            else:
                print("[RENAME] Name unchanged or empty")

            # Reset editing flag
            self.editing_layer_name = None

            # Make item non-editable again
            item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)

        except Exception as e:
            import traceback
            error_msg = f"Error renaming layer: {str(e)}\n{traceback.format_exc()}"
            print(f"[ERROR] {error_msg}")
            # Reset editing flag
            self.editing_layer_name = None

    def showEvent(self, event):
        """Handle show event - refresh layers when window is shown"""
        super(EskiLayerManager, self).showEvent(event)
        # Refresh layers when window is shown
        self.populate_layers()

    def setup_callbacks(self):
        """Setup 3ds Max callbacks for automatic layer refresh"""
        if rt is None:
            return

        try:
            # Create callback functions
            callback_code = """
global EskiLayerManagerCallback
fn EskiLayerManagerCallback = (
    python.Execute "import eski_layer_manager; eski_layer_manager.refresh_from_callback()"
)

global EskiLayerManagerSceneCallback
fn EskiLayerManagerSceneCallback = (
    python.Execute "import eski_layer_manager; eski_layer_manager.refresh_on_scene_change()"
)
"""
            rt.execute(callback_code)

            # Register callbacks for layer-related events (use regular refresh)
            rt.callbacks.addScript(rt.Name("layerCreated"), "EskiLayerManagerCallback()")
            rt.callbacks.addScript(rt.Name("layerDeleted"), "EskiLayerManagerCallback()")
            rt.callbacks.addScript(rt.Name("nodeLayerChanged"), "EskiLayerManagerCallback()")

            # Register callbacks for scene events (use scene refresh - reopen window)
            rt.callbacks.addScript(rt.Name("filePostOpen"), "EskiLayerManagerSceneCallback()")
            rt.callbacks.addScript(rt.Name("systemPostReset"), "EskiLayerManagerSceneCallback()")
            rt.callbacks.addScript(rt.Name("systemPostNew"), "EskiLayerManagerSceneCallback()")
            # Note: postMerge callback not supported in 3ds Max 2026

            print("[CALLBACKS] Layer change and scene callbacks registered")
        except Exception as e:
            print(f"[CALLBACKS] Failed to register callbacks: {e}")

    def remove_callbacks(self):
        """Remove 3ds Max callbacks"""
        if rt is None:
            return

        try:
            # Remove all instances of our callback
            rt.callbacks.removeScripts(rt.Name("layerCreated"), id=rt.Name("EskiLayerManagerCallback"))
            rt.callbacks.removeScripts(rt.Name("layerDeleted"), id=rt.Name("EskiLayerManagerCallback"))
            rt.callbacks.removeScripts(rt.Name("nodeLayerChanged"), id=rt.Name("EskiLayerManagerCallback"))
            rt.callbacks.removeScripts(rt.Name("filePostOpen"), id=rt.Name("EskiLayerManagerCallback"))
            rt.callbacks.removeScripts(rt.Name("systemPostReset"), id=rt.Name("EskiLayerManagerCallback"))
            rt.callbacks.removeScripts(rt.Name("systemPostNew"), id=rt.Name("EskiLayerManagerCallback"))
            # Note: postMerge callback not supported in 3ds Max 2026
            print("[CALLBACKS] All callbacks removed")
        except Exception as e:
            print(f"[CALLBACKS] Failed to remove callbacks: {e}")

    def save_position(self):
        """Save window position to 3ds Max scene and global settings"""
        if rt is None:
            return

        try:
            # Get current position and docking state
            is_floating = self.isFloating()
            pos = self.pos()
            size = self.size()

            # Save to scene file data
            position_data = f"{is_floating};{pos.x()};{pos.y()};{size.width()};{size.height()}"
            rt.fileProperties.addProperty(rt.Name("EskiLayerManagerPosition"), position_data)

            # Also save to global preferences (INI-like storage)
            rt.setINISetting(rt.maxFilePath + rt.maxFileName + ".ini", "EskiLayerManager", "LastPosition", position_data)

            print(f"[POSITION] Saved: {position_data}")
        except Exception as e:
            print(f"[POSITION] Error saving: {e}")

    def restore_position(self):
        """Restore window position from scene or global settings"""
        if rt is None:
            return

        try:
            position_data = None

            # First try to load from scene file
            try:
                position_data = rt.fileProperties.findProperty(rt.Name("EskiLayerManagerPosition"))
                if position_data:
                    position_data = str(position_data.value)
                    print(f"[POSITION] Loaded from scene: {position_data}")
            except:
                pass

            # If not in scene, try global preferences
            if not position_data:
                try:
                    position_data = rt.getINISetting(rt.maxFilePath + rt.maxFileName + ".ini", "EskiLayerManager", "LastPosition")
                    if position_data and position_data != "":
                        print(f"[POSITION] Loaded from global: {position_data}")
                except:
                    pass

            # Parse and apply position data
            if position_data:
                parts = position_data.split(";")
                if len(parts) == 5:
                    is_floating = parts[0] == "True"
                    x = int(parts[1])
                    y = int(parts[2])
                    width = int(parts[3])
                    height = int(parts[4])

                    # Apply position
                    self.move(x, y)
                    self.resize(width, height)
                    self.setFloating(is_floating)

                    print(f"[POSITION] Restored position")
        except Exception as e:
            print(f"[POSITION] Error restoring: {e}")

    def closeEvent(self, event):
        """Handle close event"""
        # Save position before closing
        self.save_position()

        # Remove callbacks
        self.remove_callbacks()

        # Clear the global instance reference
        global _layer_manager_instance
        _layer_manager_instance[0] = None
        super().closeEvent(event)


def refresh_from_callback():
    """
    Called by 3ds Max callbacks when layer changes occur
    Refreshes the layer list in the active instance
    """
    global _layer_manager_instance

    if _layer_manager_instance[0] is not None:
        try:
            # Check if widget is still valid
            _layer_manager_instance[0].isVisible()
            # Refresh the layers
            _layer_manager_instance[0].populate_layers()
        except (RuntimeError, AttributeError):
            # Widget was deleted
            _layer_manager_instance[0] = None


def refresh_on_scene_change():
    """
    Called by scene change callbacks (file open, reset, new, merge)
    Closes current instance and opens a fresh one
    """
    global _layer_manager_instance

    if _layer_manager_instance[0] is not None:
        try:
            # Check if widget is still valid and visible
            if _layer_manager_instance[0].isVisible():
                # Close the current instance
                _layer_manager_instance[0].close()
                # Open a new instance
                show_layer_manager()
        except (RuntimeError, AttributeError):
            # Widget was deleted
            _layer_manager_instance[0] = None


def get_instance_status():
    """
    Get the current status of the singleton instance
    Useful for debugging

    Returns:
        dict: Status information about the singleton instance
    """
    global _layer_manager_instance

    if '_layer_manager_instance' not in globals():
        return {
            'exists': False,
            'reason': 'Global variable not initialized'
        }

    if _layer_manager_instance[0] is None:
        return {
            'exists': False,
            'reason': 'Instance is None'
        }

    try:
        # Try to check if widget is alive
        is_visible = _layer_manager_instance[0].isVisible()
        return {
            'exists': True,
            'instance': _layer_manager_instance[0],
            'visible': is_visible,
            'widget_valid': True
        }
    except (RuntimeError, AttributeError) as e:
        return {
            'exists': False,
            'reason': f'Widget deleted: {e}',
            'widget_valid': False
        }


def show_layer_manager():
    """
    Show the Eski Layer Manager window (Singleton pattern)
    Call this function from 3ds Max to launch the tool
    Only one instance can exist at a time.

    Returns:
        EskiLayerManager: The singleton instance of the layer manager
    """
    global _layer_manager_instance

    # Ensure the instance list exists (defensive programming)
    if '_layer_manager_instance' not in globals():
        _layer_manager_instance = [None]

    # Check if instance already exists and is valid
    if _layer_manager_instance[0] is not None:
        try:
            # Try to access the widget to see if it's still alive
            # This will raise RuntimeError if the C++ object was deleted
            _layer_manager_instance[0].isVisible()

            # If we get here, the widget is still valid - bring to front
            _layer_manager_instance[0].show()
            _layer_manager_instance[0].raise_()
            _layer_manager_instance[0].activateWindow()
            return _layer_manager_instance[0]

        except (RuntimeError, AttributeError):
            # Window was deleted, clear the reference and create new one
            _layer_manager_instance[0] = None

    # No valid instance exists, create a new one

    # Get the 3ds Max main window
    if QTMAX_AVAILABLE:
        max_main_window = qtmax.GetQMaxMainWindow()
    else:
        # Fallback for testing outside 3ds Max
        max_main_window = None

    # Create the layer manager
    layer_manager = EskiLayerManager(parent=max_main_window)

    # Store reference in the list to prevent garbage collection
    _layer_manager_instance[0] = layer_manager

    # Show the window
    if max_main_window:
        # Dock it to the right side by default
        max_main_window.addDockWidget(QtCore.Qt.RightDockWidgetArea, layer_manager)

    layer_manager.show()

    return layer_manager


# For testing or direct execution
if __name__ == "__main__":
    # This allows testing outside 3ds Max with a standalone Qt application
    import sys

    app = QtWidgets.QApplication.instance()
    if not app:
        app = QtWidgets.QApplication(sys.argv)

    window = EskiLayerManager()
    window.show()

    sys.exit(app.exec())
