"""
Eski LayerManager by Claude
A dockable layer and object manager for 3ds Max

Version: 0.2.0
"""

from PySide6 import QtWidgets, QtCore
try:
    from pymxs import runtime as rt
    import MaxPlus
except ImportError:
    # For development/testing outside 3ds Max
    rt = None
    MaxPlus = None

# Try to import qtmax for docking functionality
try:
    import qtmax
    QTMAX_AVAILABLE = True
except ImportError:
    QTMAX_AVAILABLE = False
    print("Warning: qtmax not available. Window will not be dockable.")


VERSION = "0.2.0"


class EskiLayerManager(QtWidgets.QDockWidget):
    """
    Main dockable window for Eski Layer Manager
    """

    # Class variable to keep reference and prevent garbage collection
    instance = None

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

        # Initialize UI
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface"""
        # Create central widget
        central_widget = QtWidgets.QWidget()
        self.setWidget(central_widget)

        # Create main layout
        main_layout = QtWidgets.QVBoxLayout(central_widget)

        # Placeholder label (will be replaced with actual layer manager in next version)
        placeholder_label = QtWidgets.QLabel(
            "Eski LayerManager\n\n"
            "Dockable window initialized successfully!\n\n"
            "Layer and object management\ncoming in next version..."
        )
        placeholder_label.setAlignment(QtCore.Qt.AlignCenter)
        placeholder_label.setStyleSheet("padding: 20px; color: #666;")

        main_layout.addWidget(placeholder_label)

        # Set minimum size
        self.setMinimumSize(250, 400)

    def closeEvent(self, event):
        """Handle close event"""
        # Clear the instance reference
        EskiLayerManager.instance = None
        super(EskiLayerManager, self).closeEvent(event)


def show_layer_manager():
    """
    Show the Eski Layer Manager window
    Call this function from 3ds Max to launch the tool
    """
    # Close existing instance if any
    if EskiLayerManager.instance is not None:
        try:
            EskiLayerManager.instance.close()
        except:
            pass
        EskiLayerManager.instance = None

    # Get the 3ds Max main window
    if QTMAX_AVAILABLE:
        max_main_window = qtmax.GetQMaxMainWindow()
    else:
        # Fallback for testing outside 3ds Max
        max_main_window = None

    # Create and show the layer manager
    layer_manager = EskiLayerManager(parent=max_main_window)

    # Keep reference to prevent garbage collection
    EskiLayerManager.instance = layer_manager

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
