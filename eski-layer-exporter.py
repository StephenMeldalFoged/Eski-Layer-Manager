"""
Eski Exporter by Claude
Real-Time FBX Exporter with animation clips for 3ds Max 2026+

Version: 0.4.5 (2026-01-05 16:51)
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

VERSION = "0.4.5 (2026-01-05 16:51)"

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
        self.layer_snapshot = {}  # Track layer names for change detection
        self.setup_ui()
        self.load_settings()  # Load saved settings from file
        self.register_callbacks()
        self.start_refresh_timer()

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
        self.status_label.setStyleSheet("padding: 5px;")
        main_layout.addWidget(self.status_label)

    def create_file_section(self):
        """Create the file selection section"""
        section = CollapsibleSection("Export file to")
        layout = section.get_content_layout()

        # File path row
        file_row = QtWidgets.QHBoxLayout()

        self.file_path_edit = QtWidgets.QLineEdit()
        self.file_path_edit.setPlaceholderText("Select output folder for FBX files...")
        self.file_path_edit.setReadOnly(True)
        self.file_path_edit.setStyleSheet("QLineEdit[readOnly=\"true\"] { background-color: #3a3a3a; }")
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
        info_label = QtWidgets.QLabel("Check top-level layers to export (includes all sublayers)")
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
        self.clips_table.itemChanged.connect(lambda: self.save_settings())

        # Set column widths
        self.clips_table.setColumnWidth(0, 60)  # Checkbox column
        self.clips_table.setColumnWidth(1, 150)  # Name column
        self.clips_table.setColumnWidth(2, 100)  # Start frame

        layout.addWidget(self.clips_table)

        return section

    def browse_folder(self):
        """Open folder browser for FBX export location using 3ds Max native dialog"""
        if rt:
            # Use 3ds Max file dialog (has history dropdown) and extract folder
            file_path = rt.getSaveFileName(
                caption="Select Export Folder (filename will be ignored)",
                filename="export.fbx",
                types="FBX Files (*.fbx)|*.fbx"
            )

            # Extract folder from the selected file path
            if file_path and str(file_path) != "undefined":
                file_path = str(file_path)
                # Get the directory part only
                import os
                folder_path = os.path.dirname(file_path)
                self.file_path_edit.setText(folder_path)
                self.save_settings()
        else:
            # Fallback to Qt dialog for standalone testing
            folder_path = QtWidgets.QFileDialog.getExistingDirectory(
                self,
                "Select Export Folder for FBX Files",
                ""
            )

            if folder_path:
                self.file_path_edit.setText(folder_path)
                self.save_settings()

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

        # Sort root layers alphabetically by name
        root_layers.sort(key=lambda layer: layer.name.lower())

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

        # Only top-level layers can be checked
        if parent_item is None:
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(0, QtCore.Qt.Unchecked)

        # Store layer reference
        item.setData(0, QtCore.Qt.UserRole, layer.name)

        # Add to parent or root
        if parent_item:
            parent_item.addChild(item)
        else:
            self.layers_tree.addTopLevelItem(item)

        # Add children (sorted alphabetically)
        num_children = layer.getNumChildren()
        children = []
        for i in range(num_children):
            child_layer = layer.getChild(i + 1)  # MAXScript uses 1-based indexing
            children.append(child_layer)

        # Sort children alphabetically by name
        children.sort(key=lambda child: child.name.lower())

        for child_layer in children:
            self.add_layer_to_tree(child_layer, item)

        return item

    def on_layer_check_changed(self, item, column):
        """Handle layer checkbox state changes"""
        # Block signals to prevent recursive updates
        self.layers_tree.blockSignals(True)

        # Update highlighting for all items
        self.update_layer_highlighting()

        self.layers_tree.blockSignals(False)

        # Save settings
        self.save_settings()

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

    def save_settings(self):
        """Save exporter settings to the 3ds Max file"""
        if not rt:
            return

        try:
            import json

            # Collect current settings
            settings = {
                'export_folder': self.file_path_edit.text(),
                'checked_layers': [],
                'animation_clips': []
            }

            # Save checked layers
            for i in range(self.layers_tree.topLevelItemCount()):
                item = self.layers_tree.topLevelItem(i)
                if item.checkState(0) == QtCore.Qt.Checked:
                    layer_name = item.data(0, QtCore.Qt.UserRole)
                    settings['checked_layers'].append(layer_name)

            # Save animation clips
            for row in range(self.clips_table.rowCount()):
                clip_data = {
                    'name': self.clips_table.item(row, 1).text(),
                    'start': self.clips_table.item(row, 2).text(),
                    'end': self.clips_table.item(row, 3).text(),
                    'export': self.clips_table.cellWidget(row, 0).findChild(QtWidgets.QCheckBox).isChecked()
                }
                settings['animation_clips'].append(clip_data)

            # Save to file properties
            settings_json = json.dumps(settings)
            rt.fileProperties.addProperty(rt.Name("custom"), rt.Name("EskiExporterSettings"), settings_json)

        except Exception as e:
            print(f"[Exporter] Error saving settings: {e}")

    def load_settings(self):
        """Load exporter settings from the 3ds Max file"""
        if not rt:
            return

        try:
            import json

            # Try to load settings from file properties
            settings_json = rt.fileProperties.findProperty(rt.Name("custom"), rt.Name("EskiExporterSettings"))

            if settings_json and str(settings_json) != "undefined":
                settings = json.loads(str(settings_json))

                # Restore export folder
                if settings.get('export_folder'):
                    self.file_path_edit.setText(settings['export_folder'])

                # Restore checked layers (will be applied after layers are populated)
                self.saved_checked_layers = set(settings.get('checked_layers', []))

                # Restore animation clips
                for clip_data in settings.get('animation_clips', []):
                    row = self.clips_table.rowCount()
                    self.clips_table.insertRow(row)

                    # Checkbox
                    checkbox = QtWidgets.QCheckBox()
                    checkbox.setChecked(clip_data.get('export', True))
                    checkbox_widget = QtWidgets.QWidget()
                    checkbox_layout = QtWidgets.QHBoxLayout(checkbox_widget)
                    checkbox_layout.addWidget(checkbox)
                    checkbox_layout.setAlignment(QtCore.Qt.AlignCenter)
                    checkbox_layout.setContentsMargins(0, 0, 0, 0)
                    self.clips_table.setCellWidget(row, 0, checkbox_widget)

                    # Clip name
                    name_item = QtWidgets.QTableWidgetItem(clip_data.get('name', ''))
                    self.clips_table.setItem(row, 1, name_item)

                    # Start frame
                    start_item = QtWidgets.QTableWidgetItem(clip_data.get('start', '0'))
                    self.clips_table.setItem(row, 2, start_item)

                    # End frame
                    end_item = QtWidgets.QTableWidgetItem(clip_data.get('end', '100'))
                    self.clips_table.setItem(row, 3, end_item)

        except Exception as e:
            print(f"[Exporter] Error loading settings: {e}")

        # Initialize saved_checked_layers if not set
        if not hasattr(self, 'saved_checked_layers'):
            self.saved_checked_layers = set()

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

        # Save settings
        self.save_settings()

    def remove_clip(self):
        """Remove selected animation clip"""
        current_row = self.clips_table.currentRow()
        if current_row >= 0:
            clip_name = self.clips_table.item(current_row, 1).text()
            self.clips_table.removeRow(current_row)
            self.status_label.setText(f"Removed clip: {clip_name}")

            # Save settings
            self.save_settings()
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

    def start_refresh_timer(self):
        """Start timer to check for layer changes"""
        if rt:
            self.refresh_timer = QtCore.QTimer()
            self.refresh_timer.timeout.connect(self.check_for_layer_changes)
            self.refresh_timer.start(500)  # Check every 500ms

    def check_for_layer_changes(self):
        """Check if layers have changed and refresh if needed"""
        if not rt:
            return

        try:
            layer_manager = rt.layerManager
            current_snapshot = {}

            # Build current snapshot of all layers
            for i in range(layer_manager.count):
                layer = layer_manager.getLayer(i)
                current_snapshot[i] = layer.name

            # Compare with previous snapshot
            if current_snapshot != self.layer_snapshot:
                self.layer_snapshot = current_snapshot
                self.refresh_layers()

        except Exception as e:
            print(f"[Exporter] Error checking layer changes: {e}")

    def refresh_layers(self):
        """Refresh the layer tree while preserving check states"""
        if not rt:
            return

        # Save current check states
        checked_layers = set()
        for i in range(self.layers_tree.topLevelItemCount()):
            item = self.layers_tree.topLevelItem(i)
            if item.checkState(0) == QtCore.Qt.Checked:
                layer_name = item.data(0, QtCore.Qt.UserRole)
                checked_layers.add(layer_name)

        # Merge with saved checked layers from file
        if hasattr(self, 'saved_checked_layers'):
            checked_layers.update(self.saved_checked_layers)
            self.saved_checked_layers = set()  # Clear after first use

        # Repopulate layers
        self.populate_layers()

        # Restore check states
        for i in range(self.layers_tree.topLevelItemCount()):
            item = self.layers_tree.topLevelItem(i)
            layer_name = item.data(0, QtCore.Qt.UserRole)
            if layer_name in checked_layers:
                item.setCheckState(0, QtCore.Qt.Checked)

    def register_callbacks(self):
        """Register 3ds Max callbacks for layer events"""
        if not rt:
            return

        try:
            # Layer created callback
            rt.callbacks.addScript(
                rt.Name("layerCreated"),
                "python.execute('import eski_layer_exporter; eski_layer_exporter.refresh_from_callback()')",
                id=rt.Name("EskiExporterLayerCreated")
            )

            # Layer deleted callback
            rt.callbacks.addScript(
                rt.Name("layerDeleted"),
                "python.execute('import eski_layer_exporter; eski_layer_exporter.refresh_from_callback()')",
                id=rt.Name("EskiExporterLayerDeleted")
            )

            # File reset callback - clear settings
            rt.callbacks.addScript(
                rt.Name("systemPostReset"),
                "python.execute('print(\"[Exporter] systemPostReset callback fired\"); import eski_layer_exporter; eski_layer_exporter.clear_settings_from_callback()')",
                id=rt.Name("EskiExporterReset")
            )

            # File new callback - clear settings
            rt.callbacks.addScript(
                rt.Name("systemPostNew"),
                "python.execute('import eski_layer_exporter; eski_layer_exporter.clear_settings_from_callback()')",
                id=rt.Name("EskiExporterNew")
            )

            # File open callback - reload settings
            rt.callbacks.addScript(
                rt.Name("filePostOpen"),
                "python.execute('import eski_layer_exporter; eski_layer_exporter.reload_settings_from_callback()')",
                id=rt.Name("EskiExporterOpen")
            )

            print("[Exporter] Callbacks registered")
        except Exception as e:
            print(f"[Exporter] Error registering callbacks: {e}")

    def remove_callbacks(self):
        """Remove all registered callbacks"""
        if not rt:
            return

        try:
            rt.callbacks.removeScripts(id=rt.Name("EskiExporterLayerCreated"))
            rt.callbacks.removeScripts(id=rt.Name("EskiExporterLayerDeleted"))
            rt.callbacks.removeScripts(id=rt.Name("EskiExporterReset"))
            rt.callbacks.removeScripts(id=rt.Name("EskiExporterNew"))
            rt.callbacks.removeScripts(id=rt.Name("EskiExporterOpen"))
            print("[Exporter] Callbacks removed")
        except Exception as e:
            print(f"[Exporter] Error removing callbacks: {e}")

    def clear_all_settings(self):
        """Clear all exporter settings"""
        print("[Exporter] clear_all_settings called")

        try:
            # Block signals to prevent auto-save during clear
            self.layers_tree.blockSignals(True)
            self.clips_table.blockSignals(True)

            # Clear folder path
            self.file_path_edit.clear()
            self.file_path_edit.setText("")  # Force empty
            print(f"[Exporter] Folder path cleared, current value: '{self.file_path_edit.text()}'")

            # Clear animation clips
            self.clips_table.setRowCount(0)
            print(f"[Exporter] Clips cleared, count: {self.clips_table.rowCount()}")

            # Clear saved checked layers to prevent restore
            self.saved_checked_layers = set()

            # Clear layer snapshot to force refresh
            self.layer_snapshot = {}

            # Repopulate layers without preserving any check states
            self.populate_layers()
            print(f"[Exporter] Layers repopulated, count: {self.layers_tree.topLevelItemCount()}")

            # Restore signals
            self.layers_tree.blockSignals(False)
            self.clips_table.blockSignals(False)

            # Update status
            self.status_label.setText("Ready to export")

            print("[Exporter] Settings cleared successfully")
        except Exception as e:
            print(f"[Exporter] Error clearing settings: {e}")
            import traceback
            traceback.print_exc()

    def closeEvent(self, event):
        """Handle window close event"""
        global _exporter_instance

        # Stop refresh timer
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.stop()

        # Remove callbacks
        self.remove_callbacks()

        _exporter_instance = None
        event.accept()


def refresh_from_callback():
    """
    Called by 3ds Max callbacks to refresh the exporter
    This is a module-level function that callbacks can invoke
    """
    global _exporter_instance
    if _exporter_instance is not None:
        try:
            _exporter_instance.refresh_layers()
        except (RuntimeError, AttributeError):
            pass


def clear_settings_from_callback():
    """
    Called by 3ds Max callbacks when file is reset or new
    Clears all exporter settings
    """
    global _exporter_instance
    if _exporter_instance is not None:
        try:
            _exporter_instance.clear_all_settings()
        except (RuntimeError, AttributeError):
            pass


def reload_settings_from_callback():
    """
    Called by 3ds Max callbacks when file is opened
    Reloads settings from the file
    """
    global _exporter_instance
    if _exporter_instance is not None:
        try:
            _exporter_instance.load_settings()
            _exporter_instance.refresh_layers()
        except (RuntimeError, AttributeError):
            pass


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
