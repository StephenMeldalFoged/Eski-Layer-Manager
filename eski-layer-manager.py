"""
Eski LayerManager by Claude
A dockable layer and object manager for 3ds Max

Version: 0.4.7
"""

from PySide6 import QtWidgets, QtCore

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


VERSION = "0.4.7"

# Module initialization guard - prevents re-initialization on repeated imports
if '_ESKI_LAYER_MANAGER_INITIALIZED' not in globals():
    _ESKI_LAYER_MANAGER_INITIALIZED = True
    # Global instance variable - use a list to prevent garbage collection
    # List makes it a mutable container that survives module namespace issues
    _layer_manager_instance = [None]


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

        # Initialize UI
        self.init_ui()

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
        self.layer_tree.setHeaderLabel("Layer Hierarchy")
        self.layer_tree.setAlternatingRowColors(True)
        self.layer_tree.itemClicked.connect(self.on_layer_selected)
        self.layer_tree.itemDoubleClicked.connect(self.on_layer_double_clicked)
        self.layer_tree.itemChanged.connect(self.on_layer_renamed)
        self.layer_tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.layer_tree.customContextMenuRequested.connect(self.on_layer_context_menu)
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
        self.layer_tree.clear()

        if rt is None:
            # Testing mode outside 3ds Max - add dummy data
            print("[POPULATE] rt is None - running in TEST MODE")
            QtWidgets.QTreeWidgetItem(self.layer_tree, ["[TEST MODE] 0 (default)"])
            QtWidgets.QTreeWidgetItem(self.layer_tree, ["[TEST MODE] Layer 1"])
            QtWidgets.QTreeWidgetItem(self.layer_tree, ["[TEST MODE] Layer 2"])
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
                    # Get the layer name directly
                    layer_name = str(layer.name)
                    print(f"[DEBUG] Layer {i}: '{layer_name}'")
                    # Add to tree as flat list (no hierarchy)
                    QtWidgets.QTreeWidgetItem(self.layer_tree, [layer_name])

        except Exception as e:
            # If layer access fails, show error
            import traceback
            error_msg = f"Error loading layers: {str(e)}\n{traceback.format_exc()}"
            print(f"[ERROR] {error_msg}")
            QtWidgets.QTreeWidgetItem(self.layer_tree, [error_msg])

    def on_layer_selected(self, item, column):
        """Handle layer selection - make the selected layer active in 3ds Max"""
        if rt is None:
            return

        try:
            # Get the layer name from the tree item
            layer_name = item.text(0)

            # Don't process test mode items
            if layer_name.startswith("[TEST MODE]"):
                return

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
        # Don't process test mode items
        if item.text(0).startswith("[TEST MODE]"):
            return

        # Store the original name before editing
        self.editing_layer_name = item.text(0)

        # Make the item editable
        item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
        self.layer_tree.editItem(item, 0)

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
            # Trigger inline rename
            self.on_layer_double_clicked(item, 0)

    def on_layer_renamed(self, item, column):
        """Handle layer rename after inline editing"""
        if rt is None or self.editing_layer_name is None:
            return

        try:
            # Get the new name from the item
            new_name = item.text(0)
            old_name = self.editing_layer_name

            # Don't process test mode items
            if old_name.startswith("[TEST MODE]"):
                return

            # Only process if name actually changed
            if new_name != old_name and new_name:
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
            rt.callbacks.addScript(rt.Name("postMerge"), "EskiLayerManagerSceneCallback()")

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
            rt.callbacks.removeScripts(rt.Name("postMerge"), id=rt.Name("EskiLayerManagerCallback"))
            print("[CALLBACKS] All callbacks removed")
        except Exception as e:
            print(f"[CALLBACKS] Failed to remove callbacks: {e}")

    def closeEvent(self, event):
        """Handle close event"""
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
