"""
Eski Exporter by Claude
Real-Time FBX Exporter with animation clips for 3ds Max 2026+

Version: 0.7.1 (2026-01-05 20:05)
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

VERSION = "0.7.1 (2026-01-05 20:05)"

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
        """Update green highlighting for checked layers with adaptive gradient based on actual depth"""
        def get_item_depth(item):
            """Calculate depth of item in tree (0 = top-level)"""
            depth = 0
            parent = item.parent()
            while parent:
                depth += 1
                parent = parent.parent()
            return depth

        def find_max_depth(item):
            """Recursively find maximum depth in tree"""
            max_depth = get_item_depth(item)
            for i in range(item.childCount()):
                child_max = find_max_depth(item.child(i))
                max_depth = max(max_depth, child_max)
            return max_depth

        def get_color_for_depth(depth, max_depth):
            """Calculate color based on depth - darker and less saturated as we go deeper"""
            # Start color (top-level): darker green (60, 120, 60)
            # End color (deepest level): very desaturated dark gray (35, 45, 35)
            start_r, start_g, start_b = 60, 120, 60
            end_r, end_g, end_b = 35, 45, 35

            # If max_depth is 0 (only top-level items), use start color
            if max_depth == 0:
                return QtGui.QColor(start_r, start_g, start_b)

            # Linear interpolation from start to end based on depth relative to max_depth
            t = depth / float(max_depth)  # Normalized position (0.0 to 1.0)
            r = int(start_r + (end_r - start_r) * t)
            g = int(start_g + (end_g - start_g) * t)
            b = int(start_b + (end_b - start_b) * t)

            return QtGui.QColor(r, g, b)

        # First pass: find maximum depth in the entire tree
        max_depth = 0
        for i in range(self.layers_tree.topLevelItemCount()):
            item_max = find_max_depth(self.layers_tree.topLevelItem(i))
            max_depth = max(max_depth, item_max)

        # Second pass: apply colors based on adaptive gradient
        def update_item_highlight(item):
            is_checked = item.checkState(0) == QtCore.Qt.Checked
            is_parent_checked = self.is_parent_checked(item)

            # Apply background if checked or parent is checked
            if is_checked or is_parent_checked:
                depth = get_item_depth(item)
                item.setBackground(0, get_color_for_depth(depth, max_depth))
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

            # Delete old property if it exists
            try:
                rt.fileProperties.deleteProperty(rt.Name("custom"), rt.Name("EskiExporterSettings"))
            except:
                pass  # Property doesn't exist yet

            # Add new property - use rt.execute to ensure proper MAXScript string handling
            escaped_json = settings_json.replace("\\", "\\\\").replace('"', '\\"')
            maxscript_cmd = f'fileProperties.addProperty #custom #EskiExporterSettings "{escaped_json}"'
            rt.execute(maxscript_cmd)

        except Exception as e:
            print(f"[Exporter] Error saving settings: {e}")
            import traceback
            traceback.print_exc()

    def load_settings(self):
        """Load exporter settings from the 3ds Max file"""
        if not rt:
            return

        settings_found = False

        try:
            import json

            # Try to load settings from file properties
            # findProperty returns the index, we need getPropertyValue to get the actual value
            prop_index = rt.fileProperties.findProperty(rt.Name("custom"), rt.Name("EskiExporterSettings"))

            if prop_index and str(prop_index) != "undefined" and prop_index != 0:
                # Get the actual value using the index
                settings_json = rt.fileProperties.getPropertyValue(rt.Name("custom"), prop_index)
                settings_str = str(settings_json)

                settings = json.loads(settings_str)

                # Ensure settings is a dictionary
                if isinstance(settings, dict):
                    settings_found = True

                    # Restore export folder
                    if settings.get('export_folder'):
                        self.file_path_edit.setText(settings['export_folder'])

                    # Restore checked layers (will be applied after layers are populated)
                    self.saved_checked_layers = set(settings.get('checked_layers', []))

                    # Apply check states immediately to currently populated layers
                    self.layers_tree.blockSignals(True)
                    for i in range(self.layers_tree.topLevelItemCount()):
                        item = self.layers_tree.topLevelItem(i)
                        layer_name = item.data(0, QtCore.Qt.UserRole)
                        if layer_name in self.saved_checked_layers:
                            item.setCheckState(0, QtCore.Qt.Checked)
                    self.layers_tree.blockSignals(False)
                    self.update_layer_highlighting()  # Update green highlighting
                    self.saved_checked_layers = set()  # Clear after applying

                    # Restore animation clips
                    self.clips_table.blockSignals(True)
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

                    self.clips_table.blockSignals(False)

        except Exception as e:
            print(f"[Exporter] Error loading settings: {e}")

        # If no settings found, this is a new/reset scene - clear everything
        if not settings_found:
            # Block signals to prevent auto-save
            self.layers_tree.blockSignals(True)
            self.clips_table.blockSignals(True)

            self.file_path_edit.clear()
            self.clips_table.setRowCount(0)

            self.layers_tree.blockSignals(False)
            self.clips_table.blockSignals(False)

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

        if not rt:
            QtWidgets.QMessageBox.warning(
                self,
                "No 3ds Max",
                "FBX export requires 3ds Max."
            )
            return

        # Get all checked layers
        checked_layers = []
        for i in range(self.layers_tree.topLevelItemCount()):
            item = self.layers_tree.topLevelItem(i)
            if item.checkState(0) == QtCore.Qt.Checked:
                layer_name = item.data(0, QtCore.Qt.UserRole)
                checked_layers.append(layer_name)

        if not checked_layers:
            QtWidgets.QMessageBox.warning(
                self,
                "No Layers Selected",
                "Please check at least one layer to export."
            )
            return

        # Verify folder exists
        import os
        if not os.path.exists(folder_path):
            QtWidgets.QMessageBox.warning(
                self,
                "Folder Not Found",
                f"The folder does not exist:\n{folder_path}"
            )
            return

        # Export each checked layer
        exported_files = []
        errors = []

        for layer_name in checked_layers:
            try:
                self.status_label.setText(f"Exporting {layer_name}...")
                QtWidgets.QApplication.processEvents()

                print(f"[Exporter] Starting export for layer: {layer_name}")

                # Get the layer object
                layer = rt.layerManager.getLayerFromName(layer_name)
                if not layer:
                    errors.append(f"{layer_name}: Layer not found")
                    print(f"[Exporter] Layer not found: {layer_name}")
                    continue

                print(f"[Exporter] Layer found: {layer_name}")

                # Collect all objects in this layer and its children
                try:
                    objects_to_export = self.get_layer_objects_recursive(layer)
                    print(f"[Exporter] Found {len(objects_to_export)} objects to export")
                except Exception as e:
                    errors.append(f"{layer_name}: Error collecting objects - {str(e)}")
                    print(f"[Exporter] Error collecting objects: {e}")
                    continue

                if not objects_to_export or len(objects_to_export) == 0:
                    errors.append(f"{layer_name}: No objects to export")
                    print(f"[Exporter] No objects to export")
                    continue

                # Select the objects
                try:
                    rt.clearSelection()
                    rt.select(objects_to_export)
                    print(f"[Exporter] Objects selected")
                except Exception as e:
                    errors.append(f"{layer_name}: Error selecting objects - {str(e)}")
                    print(f"[Exporter] Error selecting objects: {e}")
                    continue

                # Build output file path
                output_file = os.path.join(folder_path, f"{layer_name}.fbx")
                print(f"[Exporter] Output file: {output_file}")

                # Escape backslashes for MAXScript
                escaped_path = output_file.replace("\\", "\\\\")

                # Export to FBX using MAXScript command
                export_cmd = f'exportFile "{escaped_path}" #noPrompt selectedOnly:true using:FBXEXP'
                print(f"[Exporter] Export command: {export_cmd}")

                try:
                    result = rt.execute(export_cmd)
                    print(f"[Exporter] Export result: {result}")

                    if result:
                        exported_files.append(layer_name)
                        print(f"[Exporter] Export successful")
                    else:
                        errors.append(f"{layer_name}: Export command returned false")
                        print(f"[Exporter] Export command returned false")
                except Exception as e:
                    errors.append(f"{layer_name}: Export command error - {str(e)}")
                    print(f"[Exporter] Export command exception: {e}")
                    import traceback
                    traceback.print_exc()

            except Exception as e:
                errors.append(f"{layer_name}: {str(e)}")
                print(f"[Exporter] Outer exception: {e}")
                import traceback
                traceback.print_exc()

        # Show results
        if exported_files:
            if errors:
                # Show errors if any, but keep it brief
                self.status_label.setText(f"Exported {len(exported_files)} layer(s) with {len(errors)} error(s)")
            else:
                # Silent success - just update status
                self.status_label.setText(f"Exported {len(exported_files)} layer(s) successfully")
        else:
            # Only show dialog if everything failed
            error_msg = "Export failed:\n\n"
            error_msg += "\n".join([f"  • {err}" for err in errors])
            QtWidgets.QMessageBox.warning(
                self,
                "Export Failed",
                error_msg
            )
            self.status_label.setText("Export failed")

    def get_layer_objects_recursive(self, layer):
        """Get all objects in a layer and its children recursively"""
        objects = []

        # Get layer name for MAXScript query
        layer_name = layer.name

        # Use MAXScript to collect nodes into an array using a for loop
        # Escape quotes in layer name
        escaped_name = layer_name.replace('"', '\\"')

        # Build array by iterating through layer nodes in MAXScript
        # nodes is a function that requires a class filter argument
        maxscript_cmd = f'''
(
    local theLayer = layerManager.getLayerFromName "{escaped_name}"
    local result = #()
    theLayer.nodes &result
    result
)
'''

        try:
            nodes_array = rt.execute(maxscript_cmd)
            print(f"[Exporter] Nodes array type: {type(nodes_array)}, str: {str(nodes_array)[:100]}")

            # Convert MAXScript array to Python list
            if nodes_array and str(nodes_array) != "undefined" and str(nodes_array) != "#()":
                # Get array count using MAXScript
                count_cmd = f'''
(
    local theLayer = layerManager.getLayerFromName "{escaped_name}"
    local result = #()
    theLayer.nodes &result
    result.count
)
'''
                count = rt.execute(count_cmd)
                print(f"[Exporter] Found {count} nodes in layer {layer_name}")

                # Iterate through array (pymxs arrays can be iterated with Python for loop)
                for node in nodes_array:
                    objects.append(node)
                    print(f"[Exporter]   - Added node: {node.name}")
        except Exception as e:
            print(f"[Exporter] Error getting nodes from layer {layer_name}: {e}")
            import traceback
            traceback.print_exc()

        # Get objects from child layers
        num_children = layer.getNumChildren()
        for i in range(num_children):
            child_layer = layer.getChild(i + 1)  # MAXScript uses 1-based indexing
            child_objects = self.get_layer_objects_recursive(child_layer)
            objects.extend(child_objects)

        return objects

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
            # Check if settings still exist in file
            try:
                prop_index = rt.fileProperties.findProperty(rt.Name("custom"), rt.Name("EskiExporterSettings"))
                settings_exist = prop_index and str(prop_index) != "undefined" and prop_index != 0
            except:
                settings_exist = False

            # If we have UI state but no file settings, scene was reset - reload
            if not settings_exist and (self.file_path_edit.text() or self.clips_table.rowCount() > 0):
                self.load_settings()
                self.refresh_layers()
                return

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

            # File open callback - close and reopen window to load fresh settings
            rt.callbacks.addScript(
                rt.Name("filePostOpen"),
                'python.execute("import eski_layer_exporter; eski_layer_exporter.close_on_file_open()")',
                id=rt.Name("EskiExporterOpen")
            )
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
        except Exception as e:
            print(f"[Exporter] Error removing callbacks: {e}")

    def clear_all_settings(self):
        """Clear all exporter settings"""
        try:
            # Block signals to prevent auto-save during clear
            self.layers_tree.blockSignals(True)
            self.clips_table.blockSignals(True)

            # Clear folder path
            self.file_path_edit.clear()

            # Clear animation clips
            self.clips_table.setRowCount(0)

            # Clear saved checked layers to prevent restore
            self.saved_checked_layers = set()

            # Clear layer snapshot to force refresh
            self.layer_snapshot = {}

            # Repopulate layers without preserving any check states
            self.populate_layers()

            # Restore signals
            self.layers_tree.blockSignals(False)
            self.clips_table.blockSignals(False)

            # Update status
            self.status_label.setText("Ready to export")

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


def close_on_file_open():
    """
    Called by 3ds Max callbacks when file is opened
    Closes and reopens the exporter window to load fresh settings
    """
    global _exporter_instance
    if _exporter_instance is not None:
        try:
            # Close the window
            _exporter_instance.close()

            # Reopen immediately with fresh settings
            show_exporter()
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
                return None
            else:
                # Window exists but hidden - SHOW it (toggle on)
                _exporter_instance.show()
                _exporter_instance.raise_()
                _exporter_instance.activateWindow()
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
