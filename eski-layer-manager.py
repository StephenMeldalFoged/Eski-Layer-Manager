"""
Eski LayerManager by Claude
A dockable layer and object manager for 3ds Max

Version: 0.4.1
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


VERSION = "0.4.1"

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
            # Create a callback function that will refresh the layers
            callback_code = """
global EskiLayerManagerCallback
fn EskiLayerManagerCallback = (
    python.Execute "import eski_layer_manager; eski_layer_manager.refresh_from_callback()"
)
"""
            rt.execute(callback_code)

            # Register callbacks for layer-related events
            # layerCreated, layerDeleted, layerRenamed
            self.callback_id = rt.callbacks.addScript(rt.Name("layerCreated"), "EskiLayerManagerCallback()")
            rt.callbacks.addScript(rt.Name("layerDeleted"), "EskiLayerManagerCallback()")
            rt.callbacks.addScript(rt.Name("nodeLayerChanged"), "EskiLayerManagerCallback()")

            print("[CALLBACKS] Layer change callbacks registered")
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
            print("[CALLBACKS] Layer change callbacks removed")
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
