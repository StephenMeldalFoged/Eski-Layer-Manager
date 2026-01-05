"""
Eski Exporter by Claude
Real-Time FBX Exporter with animation clips for 3ds Max 2026+

Version: 0.1.3 (2026-01-05 14:42)
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

VERSION = "0.1.3 (2026-01-05 14:42)"

# Singleton pattern - keep reference to prevent garbage collection
_exporter_instance = None


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
        main_layout.setSpacing(10)

        # === Export File Section ===
        file_group = self.create_file_section()
        main_layout.addWidget(file_group)

        # === Export Options Section ===
        options_group = self.create_export_options_section()
        main_layout.addWidget(options_group)

        # === Animation Clips Section ===
        clips_group = self.create_animation_clips_section()
        main_layout.addWidget(clips_group, 1)  # Give it stretch factor

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
        group = QtWidgets.QGroupBox("Export File")
        layout = QtWidgets.QVBoxLayout(group)

        # File path row
        file_row = QtWidgets.QHBoxLayout()

        self.file_path_edit = QtWidgets.QLineEdit()
        self.file_path_edit.setPlaceholderText("Select output FBX file path...")
        file_row.addWidget(self.file_path_edit, 1)

        browse_btn = QtWidgets.QPushButton("Browse...")
        browse_btn.setMinimumWidth(80)
        browse_btn.clicked.connect(self.browse_file)
        file_row.addWidget(browse_btn)

        layout.addLayout(file_row)

        return group

    def create_export_options_section(self):
        """Create the export options section"""
        group = QtWidgets.QGroupBox("Export Options")
        layout = QtWidgets.QVBoxLayout(group)

        # Export Set dropdown
        set_row = QtWidgets.QHBoxLayout()
        set_row.addWidget(QtWidgets.QLabel("Export Set:"))

        self.export_set_combo = QtWidgets.QComboBox()
        self.export_set_combo.addItems([
            "Export All",
            "Export Selection",
            "Export Object Set"
        ])
        set_row.addWidget(self.export_set_combo, 1)
        layout.addLayout(set_row)

        # Note: All clips will be exported to a single file
        note_label = QtWidgets.QLabel("Note: All animation clips will be exported to a single FBX file")
        note_label.setStyleSheet("color: #666; font-style: italic; padding: 5px;")
        layout.addWidget(note_label)

        return group

    def create_animation_clips_section(self):
        """Create the animation clips management section"""
        group = QtWidgets.QGroupBox("Animation Clips")
        layout = QtWidgets.QVBoxLayout(group)

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

        return group

    def browse_file(self):
        """Open file browser for FBX output"""
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export FBX File",
            "",
            "FBX Files (*.fbx);;All Files (*.*)"
        )

        if file_path:
            # Ensure .fbx extension
            if not file_path.lower().endswith('.fbx'):
                file_path += '.fbx'
            self.file_path_edit.setText(file_path)

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
        file_path = self.file_path_edit.text().strip()

        if not file_path:
            QtWidgets.QMessageBox.warning(
                self,
                "No File Selected",
                "Please select an output FBX file path."
            )
            return

        # TODO: Implement actual export logic
        self.status_label.setText("Exporting... (Implementation pending)")
        QtWidgets.QApplication.processEvents()

        # Placeholder success message
        QtWidgets.QMessageBox.information(
            self,
            "Export Ready",
            f"Export functionality will be implemented next.\nTarget file: {file_path}"
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
