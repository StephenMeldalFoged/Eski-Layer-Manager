"""
Eski Exporter by Claude
Real-Time FBX Exporter with animation clips for 3ds Max 2026+

Version: 0.2.5 (2026-01-05 15:15)
"""

from PySide6 import QtWidgets, QtCore, QtGui

# Import pymxs (required for 3ds Max API access)
try:
    from pymxs import runtime as rt
except ImportError as e:
    # For development/testing outside 3ds Max
    rt = None
    print(f"Warning: pymxs not available - {e}")

# Try to import qtmax for docking functionality
try:
    import qtmax
    QTMAX_AVAILABLE = True
except ImportError:
    QTMAX_AVAILABLE = False
    print("Warning: qtmax not available. Window will not have Max integration.")

VERSION = "0.2.5 (2026-01-05 15:15)"

# Singleton pattern - keep reference to prevent garbage collection
_exporter_instance = None


class CollapsibleSection(QtWidgets.QWidget):
    """
    A collapsible section widget with a clickable header
    """
    def __init__(self, title, parent=None):
        super().__init__(parent)

        self.is_collapsed = False

        # Main layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header button
        self.header_btn = QtWidgets.QPushButton(f"▼ {title}")
        self.header_btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 5px 8px;
                background-color: #3a3a3a;
                border: 1px solid #555;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        self.header_btn.clicked.connect(self.toggle_collapsed)
        layout.addWidget(self.header_btn)

        # Content widget (plain widget, no group box border)
        self.content_widget = QtWidgets.QWidget()
        self.content_widget.setStyleSheet("QWidget { border: 1px solid #555; border-top: none; background-color: palette(window); }")
        self.content_layout = QtWidgets.QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(8, 8, 8, 8)
        self.content_layout.setSpacing(5)
        layout.addWidget(self.content_widget)

        self.title = title

    def toggle_collapsed(self):
        """Toggle the collapsed state"""
        self.is_collapsed = not self.is_collapsed
        self.content_widget.setVisible(not self.is_collapsed)

        # Update arrow
        arrow = "▶" if self.is_collapsed else "▼"
        self.header_btn.setText(f"{arrow} {self.title}")

    def get_content_layout(self):
        """Get the layout to add content to"""
        return self.content_layout


class EskiExporterDialog(QtWidgets.QDialog):
    """
    Main dialog for Real-Time FBX Exporter
    Provides streamlined workflow for exporting models and animation clips
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Set as normal window (not always on top)
        self.setWindowFlags(QtCore.Qt.Window)

        self.animation_clips = []  # List of animation clips
        self.setup_ui()

    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle(f"Eski Real-Time Exporter - {VERSION}")
        self.setMinimumWidth(500)
        self.setMinimumHeight(600)

        # Main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(2)

        # === Export File Section ===
        file_group = self.create_file_section()
        main_layout.addWidget(file_group)

        # === Export Options Section ===
        options_group = self.create_export_options_section()
        main_layout.addWidget(options_group)

        # === Animation Clips Section ===
        clips_group = self.create_animation_clips_section()
        main_layout.addWidget(clips_group)

        # Add stretch to push export button to bottom
        main_layout.addStretch(1)

        # === Export Button ===
        export_btn = QtWidgets.QPushButton("Export FBX")
        export_btn.setMinimumHeight(40)
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        export_btn.clicked.connect(self.do_export)
        main_layout.addWidget(export_btn)

        # Status bar
        self.status_label = QtWidgets.QLabel("Ready to export")
        self.status_label.setStyleSheet("padding: 5px; background-color: #f0f0f0; border-radius: 3px;")
        main_layout.addWidget(self.status_label)

    def create_file_section(self):
        """Create the file selection section"""
        section = CollapsibleSection("Export file to")
        layout = section.get_content_layout()

        # File path row
        file_row = QtWidgets.QHBoxLayout()

        self.file_path_edit = QtWidgets.QLineEdit()
        self.file_path_edit.setPlaceholderText("Select output folder for FBX files...")
        file_row.addWidget(self.file_path_edit, 1)

        browse_btn = QtWidgets.QPushButton("Browse...")
        browse_btn.setMinimumWidth(80)
        browse_btn.clicked.connect(self.browse_folder)
        file_row.addWidget(browse_btn)

        layout.addLayout(file_row)

        return section

    def create_export_options_section(self):
        """Create the layers selection section"""
        section = CollapsibleSection("Layers to Export")
        layout = section.get_content_layout()

        # Info label
        info_label = QtWidgets.QLabel("Check layers to export (includes all sublayers)")
        info_label.setStyleSheet("color: #666; font-style: italic; padding: 5px;")
        layout.addWidget(info_label)

        # Layers tree
        self.layers_tree = QtWidgets.QTreeWidget()
        self.layers_tree.setHeaderHidden(True)
        self.layers_tree.setAlternatingRowColors(True)
        self.layers_tree.setMinimumHeight(150)
        self.layers_tree.itemChanged.connect(self.on_layer_check_changed)
        layout.addWidget(self.layers_tree)

        # Populate layers
        self.populate_layers()

        return section

    def create_animation_clips_section(self):
        """Create the animation clips management section"""
        section = CollapsibleSection("Animation Clips")
        layout = section.get_content_layout()

        # Toolbar
        toolbar = QtWidgets.QHBoxLayout()

        add_clip_btn = QtWidgets.QPushButton("Add Clip")
        add_clip_btn.clicked.connect(self.add_clip)
        toolbar.addWidget(add_clip_btn)

        remove_clip_btn = QtWidgets.QPushButton("Remove Clip")
        remove_clip_btn.clicked.connect(self.remove_clip)
        toolbar.addWidget(remove_clip_btn)

        toolbar.addStretch()

        info_label = QtWidgets.QLabel("Tip: Add clips for different animations (walk, run, idle, etc.)")
        info_label.setStyleSheet("color: #666; font-style: italic;")
        toolbar.addWidget(info_label)

        layout.addLayout(toolbar)

        # Clips table (placeholder - will be enhanced later)
        self.clips_table = QtWidgets.QTableWidget()
        self.clips_table.setColumnCount(4)
        self.clips_table.setHorizontalHeaderLabels(["Export", "Clip Name", "Start Frame", "End Frame"])
        self.clips_table.horizontalHeader().setStretchLastSection(True)
        self.clips_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.clips_table.setAlternatingRowColors(True)

        # Set column widths
        self.clips_table.setColumnWidth(0, 60)  # Checkbox column
        self.clips_table.setColumnWidth(1, 150)  # Name column
        self.clips_table.setColumnWidth(2, 100)  # Start frame

        layout.addWidget(self.clips_table)

        return section

    def browse_folder(self):
        """Open folder browser for FBX export location using 3ds Max native dialog"""
        if rt:
            # Use 3ds Max native folder dialog
            folder_path = rt.getSavePath(
                caption="Select Export Folder for FBX Files"
            )
        else:
            # Fallback to Qt dialog for standalone testing
            folder_path = QtWidgets.QFileDialog.getExistingDirectory(
                self,
                "Select Export Folder for FBX Files",
                ""
            )

        # Check if folder_path is valid (not None/undefined)
        if folder_path and str(folder_path) != "undefined":
            folder_path = str(folder_path)
            self.file_path_edit.setText(folder_path)

    def populate_layers(self):
        """Populate the layers tree from 3ds Max"""
        self.layers_tree.clear()

        if not rt:
            # Standalone mode - add dummy layers
            dummy_item = QtWidgets.QTreeWidgetItem(["Layer_01"])
            dummy_item.setFlags(dummy_item.flags() | QtCore.Qt.ItemIsUserCheckable)
            dummy_item.setCheckState(0, QtCore.Qt.Unchecked)
            self.layers_tree.addTopLevelItem(dummy_item)
            return

        # Get layer manager
        layer_manager = rt.layerManager

        # Build dictionary of layers by parent
        root_layers = []
        for i in range(layer_manager.count):
            layer = layer_manager.getLayer(i)
            parent = layer.getParent()

            # Check if this is a root layer (no parent or parent is undefined)
            if parent is None or str(parent) == "undefined":
                root_layers.append(layer)

        # Add root layers to tree
        for layer in root_layers:
            self.add_layer_to_tree(layer, None)

        # Expand all items by default
        self.layers_tree.expandAll()

    def add_layer_to_tree(self, layer, parent_item):
        """Recursively add layer and its children to tree"""
        if not layer:
            return

        # Create tree item
        item = QtWidgets.QTreeWidgetItem([layer.name])
        item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
        item.setCheckState(0, QtCore.Qt.Unchecked)

        # Store layer reference
        item.setData(0, QtCore.Qt.UserRole, layer.name)

        # Add to parent or root
        if parent_item:
            parent_item.addChild(item)
        else:
            self.layers_tree.addTopLevelItem(item)

        # Add children
        num_children = layer.getNumChildren()
        for i in range(num_children):
            child_layer = layer.getChild(i + 1)  # MAXScript uses 1-based indexing
            self.add_layer_to_tree(child_layer, item)

        return item

    def on_layer_check_changed(self, item, column):
        """Handle layer checkbox state changes"""
        # Block signals to prevent recursive updates
        self.layers_tree.blockSignals(True)

        # Update highlighting for all items
        self.update_layer_highlighting()

        self.layers_tree.blockSignals(False)

    def update_layer_highlighting(self):
        """Update green highlighting for checked layers and their children"""
        def update_item_highlight(item):
            is_checked = item.checkState(0) == QtCore.Qt.Checked
            is_parent_checked = self.is_parent_checked(item)

            # Apply green background if checked or parent is checked
            if is_checked or is_parent_checked:
                item.setBackground(0, QtGui.QColor(144, 238, 144))  # Light green
            else:
                item.setBackground(0, QtGui.QColor(0, 0, 0, 0))  # Transparent

            # Recursively update children
            for i in range(item.childCount()):
                update_item_highlight(item.child(i))

        # Update all top-level items
        for i in range(self.layers_tree.topLevelItemCount()):
            update_item_highlight(self.layers_tree.topLevelItem(i))

    def is_parent_checked(self, item):
        """Check if any parent of this item is checked"""
        parent = item.parent()
        while parent:
            if parent.checkState(0) == QtCore.Qt.Checked:
                return True
            parent = parent.parent()
        return False

    def add_clip(self):
        """Add a new animation clip"""
        # Get current timeline range as default
        if rt:
            start = int(rt.animationRange.start)
            end = int(rt.animationRange.end)
        else:
            start = 0
            end = 100

        # For now, just add a placeholder row
        row = self.clips_table.rowCount()
        self.clips_table.insertRow(row)

        # Checkbox
        checkbox = QtWidgets.QCheckBox()
        checkbox.setChecked(True)
        checkbox_widget = QtWidgets.QWidget()
        checkbox_layout = QtWidgets.QHBoxLayout(checkbox_widget)
        checkbox_layout.addWidget(checkbox)
        checkbox_layout.setAlignment(QtCore.Qt.AlignCenter)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        self.clips_table.setCellWidget(row, 0, checkbox_widget)

        # Clip name
        name_item = QtWidgets.QTableWidgetItem(f"Clip_{row + 1}")
        self.clips_table.setItem(row, 1, name_item)

        # Start frame
        start_item = QtWidgets.QTableWidgetItem(str(start))
        self.clips_table.setItem(row, 2, start_item)

        # End frame
        end_item = QtWidgets.QTableWidgetItem(str(end))
        self.clips_table.setItem(row, 3, end_item)

        self.status_label.setText(f"Added clip: Clip_{row + 1}")

    def remove_clip(self):
        """Remove selected animation clip"""
        current_row = self.clips_table.currentRow()
        if current_row >= 0:
            clip_name = self.clips_table.item(current_row, 1).text()
            self.clips_table.removeRow(current_row)
            self.status_label.setText(f"Removed clip: {clip_name}")
        else:
            self.status_label.setText("No clip selected to remove")

    def do_export(self):
        """Perform the FBX export"""
        folder_path = self.file_path_edit.text().strip()

        if not folder_path:
            QtWidgets.QMessageBox.warning(
                self,
                "No Folder Selected",
                "Please select an output folder for FBX files."
            )
            return

        # TODO: Implement actual export logic
        self.status_label.setText("Exporting... (Implementation pending)")
        QtWidgets.QApplication.processEvents()

        # Placeholder success message
        QtWidgets.QMessageBox.information(
            self,
            "Export Ready",
            f"Export functionality will be implemented next.\nTarget folder: {folder_path}\n\nFiles will be named based on layer names."
        )
        self.status_label.setText("Ready to export")

    def closeEvent(self, event):
        """Handle window close event"""
        global _exporter_instance
        _exporter_instance = None
        event.accept()


def show_exporter():
    """
    Toggle the Eski Exporter window (Singleton pattern)
    - If window is open and visible: close it
    - If window is closed or hidden: show it

    Entry point function called from 3ds Max macro
    Only one instance can exist at a time.

    Returns:
        EskiExporterDialog: The singleton instance (or None if closed)
    """
    global _exporter_instance

    # Check if instance already exists and is valid
    if _exporter_instance is not None:
        try:
            # Try to access the widget to see if it's still alive
            # This will raise RuntimeError if the C++ object was deleted
            is_visible = _exporter_instance.isVisible()

            # If we get here, the widget is still valid
            if is_visible:
                # Window is visible - CLOSE it (toggle off)
                _exporter_instance.close()
                print("[Eski Exporter] Closed window")
                return None
            else:
                # Window exists but hidden - SHOW it (toggle on)
                _exporter_instance.show()
                _exporter_instance.raise_()
                _exporter_instance.activateWindow()
                print("[Eski Exporter] Showing existing window")
                return _exporter_instance

        except (RuntimeError, AttributeError):
            # Widget was deleted, need to create new one
            _exporter_instance = None

    # No valid instance exists - create new one
    try:
        import qtmax
        parent = qtmax.GetQMaxMainWindow()
    except ImportError:
        parent = None

    # Create new instance
    _exporter_instance = EskiExporterDialog(parent)
    _exporter_instance.show()

    print(f"[Eski Exporter] Opened new window - version {VERSION}")
    return _exporter_instance


# For standalone testing outside 3ds Max
if __name__ == '__main__':
    import sys

    print("Running Eski Exporter in standalone mode (no 3ds Max)")

    app = QtWidgets.QApplication.instance()
    if not app:
        app = QtWidgets.QApplication(sys.argv)

    dialog = show_exporter()

    sys.exit(app.exec())
