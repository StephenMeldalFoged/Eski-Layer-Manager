"""
Eski Exporter by Claude
FBX export functionality with animation takes and timeline management for 3ds Max

Version: 0.1.0 (2026-01-05)
"""

from PySide6 import QtWidgets, QtCore, QtGui

# Import pymxs (required for 3ds Max API access)
try:
    from pymxs import runtime as rt
except ImportError as e:
    # For development/testing outside 3ds Max
    rt = None
    print(f"Warning: pymxs not available - {e}")

VERSION = "0.1.0 (2026-01-05)"


class FBXExporter:
    """
    Main FBX exporter class
    Handles FBX export with animation takes and timeline management
    """

    def __init__(self):
        """Initialize the FBX exporter"""
        self.takes = []  # List of animation takes
        self.current_timeline_range = None

    def export_fbx(self, file_path, options=None):
        """
        Export scene or selection to FBX

        Args:
            file_path (str): Output FBX file path
            options (dict): Export options

        Returns:
            bool: True if export succeeded, False otherwise
        """
        if rt is None:
            print("Error: pymxs not available")
            return False

        # TODO: Implement FBX export logic
        print(f"[FBX Export] Would export to: {file_path}")
        return True

    def create_take(self, name, start_frame, end_frame):
        """
        Create an animation take

        Args:
            name (str): Take name
            start_frame (int): Start frame
            end_frame (int): End frame
        """
        take = {
            'name': name,
            'start': start_frame,
            'end': end_frame
        }
        self.takes.append(take)
        print(f"[Take] Created: {name} ({start_frame}-{end_frame})")

    def get_takes(self):
        """Get list of all takes"""
        return self.takes

    def delete_take(self, take_name):
        """Delete a take by name"""
        self.takes = [t for t in self.takes if t['name'] != take_name]
        print(f"[Take] Deleted: {take_name}")

    def get_timeline_range(self):
        """Get current timeline range from 3ds Max"""
        if rt is None:
            return (0, 100)

        start = int(rt.animationRange.start)
        end = int(rt.animationRange.end)
        return (start, end)

    def set_timeline_range(self, start_frame, end_frame):
        """Set timeline range in 3ds Max"""
        if rt is None:
            print("Error: pymxs not available")
            return False

        rt.animationRange = rt.interval(start_frame, end_frame)
        print(f"[Timeline] Set range: {start_frame}-{end_frame}")
        return True


class FBXExportDialog(QtWidgets.QDialog):
    """
    Dialog for FBX export options
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.exporter = FBXExporter()
        self.setup_ui()

    def setup_ui(self):
        """Setup the UI"""
        self.setWindowTitle(f"FBX Exporter {VERSION}")
        self.setMinimumWidth(400)
        self.setMinimumHeight(500)

        layout = QtWidgets.QVBoxLayout(self)

        # Header
        header = QtWidgets.QLabel("FBX Export with Animation Takes")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header)

        # File path selection
        file_group = QtWidgets.QGroupBox("Export File")
        file_layout = QtWidgets.QHBoxLayout(file_group)

        self.file_path_edit = QtWidgets.QLineEdit()
        self.file_path_edit.setPlaceholderText("Select output FBX file...")
        file_layout.addWidget(self.file_path_edit)

        browse_btn = QtWidgets.QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_file)
        file_layout.addWidget(browse_btn)

        layout.addWidget(file_group)

        # Takes list (placeholder for future implementation)
        takes_group = QtWidgets.QGroupBox("Animation Takes")
        takes_layout = QtWidgets.QVBoxLayout(takes_group)
        takes_layout.addWidget(QtWidgets.QLabel("Takes management coming soon..."))
        layout.addWidget(takes_group)

        # Export button
        export_btn = QtWidgets.QPushButton("Export FBX")
        export_btn.setMinimumHeight(40)
        export_btn.clicked.connect(self.do_export)
        layout.addWidget(export_btn)

        # Status
        self.status_label = QtWidgets.QLabel("Ready")
        layout.addWidget(self.status_label)

    def browse_file(self):
        """Open file browser for FBX output"""
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export FBX",
            "",
            "FBX Files (*.fbx);;All Files (*.*)"
        )

        if file_path:
            self.file_path_edit.setText(file_path)

    def do_export(self):
        """Perform the export"""
        file_path = self.file_path_edit.text()

        if not file_path:
            QtWidgets.QMessageBox.warning(
                self,
                "No File Selected",
                "Please select an output FBX file."
            )
            return

        self.status_label.setText("Exporting...")
        QtWidgets.QApplication.processEvents()

        success = self.exporter.export_fbx(file_path)

        if success:
            self.status_label.setText(f"✓ Exported to: {file_path}")
            QtWidgets.QMessageBox.information(
                self,
                "Export Complete",
                f"FBX exported successfully to:\n{file_path}"
            )
        else:
            self.status_label.setText("✗ Export failed")
            QtWidgets.QMessageBox.critical(
                self,
                "Export Failed",
                "Failed to export FBX. Check MAXScript Listener for details."
            )


def show_exporter():
    """
    Show the FBX exporter dialog
    Entry point for launching the exporter
    """
    try:
        # Import qtmax for proper 3ds Max integration
        import qtmax
        parent = qtmax.GetQMaxMainWindow()
    except ImportError:
        # Fallback for standalone testing
        parent = None

    dialog = FBXExportDialog(parent)
    dialog.show()
    return dialog


# For standalone testing
if __name__ == '__main__':
    import sys
    app = QtWidgets.QApplication.instance()
    if not app:
        app = QtWidgets.QApplication(sys.argv)

    dialog = show_exporter()

    if not QtWidgets.QApplication.instance():
        sys.exit(app.exec())
