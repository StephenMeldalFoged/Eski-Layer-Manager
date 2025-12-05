"""
Eski LayerManager by Claude
A dockable layer and object manager for 3ds Max

Version: 0.5.0
"""

from PySide6 import QtWidgets, QtCore, QtGui

# Import pymxs (required for 3ds Max API access)
try:
    from pymxs import runtime as rt
    pass  # Debug print removed
except ImportError as e:
    # For development/testing outside 3ds Max
    rt = None
    pass  # Debug print removed

# Import MaxPlus (optional - deprecated in 3ds Max 2023+)
try:
    import MaxPlus
    pass  # Debug print removed
except ImportError:
    MaxPlus = None
    pass  # Debug print removed

# Try to import qtmax for docking functionality
try:
    import qtmax
    QTMAX_AVAILABLE = True
except ImportError:
    QTMAX_AVAILABLE = False
    print("Warning: qtmax not available. Window will not be dockable.")


VERSION = "0.6.41"

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
        """Custom paint method for rendering icons and controlling selection highlight"""
        # Remove selection highlighting for columns 0, 1, 2 (only column 3 should show selection)
        if index.column() in [0, 1, 2]:
            # Remove the Selected state flag to prevent highlighting
            option.state &= ~QtWidgets.QStyle.State_Selected

        if index.column() == 1:
            # Column 1 is the visibility icon column
            # Just use the option.rect as-is, don't try to expand it

            # Try to get icon first (native icons)
            icon = index.data(QtCore.Qt.DecorationRole)

            if icon and isinstance(icon, QtGui.QIcon) and not icon.isNull():
                # Draw native icon centered in the cell
                painter.save()
                icon.paint(painter, option.rect, QtCore.Qt.AlignCenter)
                painter.restore()
            else:
                # Draw Unicode fallback text centered in the cell
                text = index.data(QtCore.Qt.DisplayRole)
                if text:
                    painter.save()
                    # Set font for Unicode emoji
                    font = painter.font()
                    font.setPointSize(14)
                    font.setBold(True)
                    painter.setFont(font)
                    # Draw text centered
                    painter.drawText(option.rect, QtCore.Qt.AlignCenter, str(text))
                    painter.restore()
        else:
            # Use default rendering for other columns
            super(VisibilityIconDelegate, self).paint(painter, option, index)


class CustomTreeWidget(QtWidgets.QTreeWidget):
    """Custom QTreeWidget that only allows selection on column 3"""

    def mousePressEvent(self, event):
        """Intercept mouse press to prevent selection on columns 0, 1, 2"""
        item = self.itemAt(event.pos())
        if item:
            column = self.columnAt(event.pos().x())
            if column in [0, 1, 2]:
                # Don't call parent's mousePressEvent for icon columns
                # This prevents Qt from selecting the item
                # But we still need to emit itemPressed and itemClicked signals manually
                self.itemPressed.emit(item, column)
                # Schedule itemClicked to fire after the press
                QtCore.QTimer.singleShot(0, lambda: self.itemClicked.emit(item, column))
                return

        # For column 3 or empty space, use default behavior
        super(CustomTreeWidget, self).mousePressEvent(event)


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

        # Track the last known current layer for sync detection
        self.last_current_layer = None

        # Track visibility states for sync detection {layer_name: is_hidden}
        self.last_visibility_states = {}

        # Load native 3ds Max icons for visibility and add selection
        self.load_visibility_icons()
        self.load_add_selection_icon()

        # Initialize UI
        self.init_ui()

        # Restore window position
        self.restore_position()

        # Setup timer to poll for current layer changes (fallback if callback doesn't work)
        self.setup_sync_timer()

    def load_visibility_icons(self):
        """Load native 3ds Max visibility icons using Qt resource system"""
        self.icon_visible = None
        self.icon_hidden = None
        self.icon_hidden_light = None  # Light version for inherited hidden state
        self.use_native_icons = False

        # Try using qtmax.LoadMaxMultiResIcon first (official method)
        # Priority order: StateSets > SceneExplorer > LayerExplorer
        try:
            import qtmax

            # Try StateSets icons first (from icon resource guide)
            icon_path_candidates = [
                ("StateSets/Visible", "StateSets/Hidden"),
                ("StateSets/visible", "StateSets/hidden"),
                ("SceneExplorer/Visible", "SceneExplorer/Hidden"),
                ("LayerExplorer/Visible", "LayerExplorer/Hidden"),
            ]

            for visible_path, hidden_path in icon_path_candidates:
                try:
                    visible_icon = qtmax.LoadMaxMultiResIcon(visible_path)
                    hidden_icon = qtmax.LoadMaxMultiResIcon(hidden_path)

                    if visible_icon and not visible_icon.isNull() and hidden_icon and not hidden_icon.isNull():
                        # Check if icons have actual pixel data
                        if len(visible_icon.availableSizes()) > 0 and len(hidden_icon.availableSizes()) > 0:
                            self.icon_visible = visible_icon
                            self.icon_hidden = hidden_icon

                            # Try to load TreeView hidden icon for inherited hidden state
                            try:
                                hidden_light_icon = qtmax.LoadMaxMultiResIcon("TrackView/TreeView/Hidden")
                                if hidden_light_icon and not hidden_light_icon.isNull():
                                    if len(hidden_light_icon.availableSizes()) > 0:
                                        self.icon_hidden_light = hidden_light_icon
                            except:
                                pass

                            self.use_native_icons = True
                            pass  # Debug print removed
                            pass  # Debug print removed
                            return
                        else:
                            pass  # Debug print removed
                except Exception as e:
                    pass  # Debug print removed

        except Exception as e:
            pass  # Debug print removed

        # Try Qt resource system paths
        icon_candidates = [
            # StateSets icons (priority from icon resource guide)
            (":/StateSets/Visible_16", ":/StateSets/Hidden_16"),
            (":/StateSets/visible_16", ":/StateSets/hidden_16"),
            (":/StateSets/Visible", ":/StateSets/Hidden"),
            (":/StateSets/visible", ":/StateSets/hidden"),
            # SceneExplorer fallbacks
            (":/SceneExplorer/Visible_16", ":/SceneExplorer/Hidden_16"),
            (":/SceneExplorer/visible_16", ":/SceneExplorer/hidden_16"),
            # Other fallbacks
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

                    # Try to load TreeView hidden icon for inherited hidden state
                    try:
                        hidden_light_icon = QtGui.QIcon(":/TrackView/TreeView/Hidden_16")
                        if not hidden_light_icon.isNull() and len(hidden_light_icon.availableSizes()) > 0:
                            self.icon_hidden_light = hidden_light_icon
                    except:
                        pass

                    self.use_native_icons = True
                    pass  # Debug print removed
                    return
                else:
                    pass  # Debug print removed

        # No native icons found - will use Unicode fallback
        pass  # Debug print removed

    def load_add_selection_icon(self):
        """Load native 3ds Max icon for AddSelectionToCurrentLayer"""
        self.icon_add_selection = None
        self.use_native_add_icon = False

        # Try using qtmax.LoadMaxMultiResIcon
        try:
            import qtmax
            add_icon = qtmax.LoadMaxMultiResIcon("AddSelectionToCurrentLayer")

            if add_icon and not add_icon.isNull():
                # Check if icon has actual pixel data
                if len(add_icon.availableSizes()) > 0:
                    self.icon_add_selection = add_icon
                    self.use_native_add_icon = True
                    pass  # Debug print removed
                    return
                else:
                    pass  # Debug print removed
        except Exception as e:
            pass  # Debug print removed

        # Try Qt resource paths
        icon_candidates = [
            ":/AddSelectionToCurrentLayer",
            ":/Layers/AddSelectionToCurrentLayer",
            ":/LayerManager/AddSelectionToCurrentLayer",
        ]

        for icon_path in icon_candidates:
            add_icon = QtGui.QIcon(icon_path)
            if not add_icon.isNull() and len(add_icon.availableSizes()) > 0:
                self.icon_add_selection = add_icon
                self.use_native_add_icon = True
                pass  # Debug print removed
                return

        # No native icon found - will use Unicode fallback "+"
        pass  # Debug print removed

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

        # Create tree widget for layers (using custom widget that controls selection)
        self.layer_tree = CustomTreeWidget()
        self.layer_tree.setHeaderLabels(["1", "2", "3", "4"])  # DEBUG: Column numbers to see which are highlighted
        # Column 0: Arrow - auto-resize to fit content (handles indentation)
        self.layer_tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        # Column 1: Visibility - auto-resize to fit content
        self.layer_tree.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        # Column 2: Add selection - auto-resize to fit content
        self.layer_tree.header().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        self.layer_tree.header().setStretchLastSection(True)  # Make name column stretch
        self.layer_tree.setAlternatingRowColors(True)

        # Disable automatic tree decoration since we have manual arrows in column 0
        self.layer_tree.setRootIsDecorated(False)
        self.layer_tree.setItemsExpandable(False)  # Disable Qt's automatic expand arrows
        self.layer_tree.setIndentation(7)  # Add indentation to show hierarchy (1/3 of original 20px)

        # Hide Qt's branch indicators completely using stylesheet
        self.layer_tree.setStyleSheet("""
            QTreeView::branch {
                background: transparent;
                border: none;
            }
            QTreeView::branch:has-children {
                background: transparent;
                border: none;
                image: none;
            }
        """)

        self.layer_tree.itemClicked.connect(self.on_layer_clicked)
        self.layer_tree.itemDoubleClicked.connect(self.on_layer_double_clicked)
        self.layer_tree.itemChanged.connect(self.on_layer_renamed)
        self.layer_tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.layer_tree.customContextMenuRequested.connect(self.on_layer_context_menu)

        # Set icon size larger for better visibility
        self.layer_tree.setIconSize(QtCore.QSize(16, 16))

        # Set uniform row heights for better icon display
        self.layer_tree.setUniformRowHeights(True)

        # Install custom delegate for all columns to control selection highlighting
        # This gives us direct control over rendering and which columns show selection
        self.custom_delegate = VisibilityIconDelegate(self.layer_tree)
        for col in range(4):  # Apply to all 4 columns
            self.layer_tree.setItemDelegateForColumn(col, self.custom_delegate)
        pass  # Debug print removed

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
        """Populate the layer list with layers from 3ds Max, including hierarchy"""
        # Temporarily disconnect itemChanged signal to avoid triggering rename during population
        try:
            self.layer_tree.itemChanged.disconnect(self.on_layer_renamed)
        except:
            pass

        self.layer_tree.clear()

        if rt is None:
            # Testing mode outside 3ds Max - add dummy data with hierarchy
            parent = QtWidgets.QTreeWidgetItem(self.layer_tree, ["▼", "👁", "+", "[TEST MODE] Parent Layer"])
            child1 = QtWidgets.QTreeWidgetItem(parent, ["▶", "👁", "+", "[TEST MODE] Child 1"])
            child2 = QtWidgets.QTreeWidgetItem(parent, ["▶", "👁", "+", "[TEST MODE] Child 2"])
            root = QtWidgets.QTreeWidgetItem(self.layer_tree, ["▶", "👁", "+", "[TEST MODE] Root Layer"])
            parent.setExpanded(True)  # Expand parent by default
            # Reconnect signal
            self.layer_tree.itemChanged.connect(self.on_layer_renamed)
            return

        try:
            # Get the layer manager from 3ds Max
            layer_manager = rt.layerManager
            layer_count = layer_manager.count
            print(f"[HIERARCHY] Found {layer_count} total layers")

            # Collect all layers first
            all_layers = []
            for i in range(layer_count):
                layer = layer_manager.getLayer(i)
                if layer:
                    all_layers.append(layer)
                    print(f"[HIERARCHY] Layer {i}: {layer.name}")

            # Separate into root layers and child layers
            root_layers = []
            for layer in all_layers:
                try:
                    parent = layer.getParent()
                    # Check if parent is undefined/None (root layer)
                    if parent is None or str(parent) == "undefined":
                        root_layers.append(layer)
                        print(f"[HIERARCHY] {layer.name} is a ROOT layer")
                    else:
                        print(f"[HIERARCHY] {layer.name} has parent: {parent.name}")
                except:
                    # If getParent fails, assume it's a root layer
                    root_layers.append(layer)
                    print(f"[HIERARCHY] {layer.name} is a ROOT layer (getParent failed)")

            # Sort root layers alphabetically
            root_layers.sort(key=lambda x: str(x.name).lower())

            # Add root layers and their children recursively
            for layer in root_layers:
                self._add_layer_to_tree(layer, None)

        except Exception as e:
            print(f"[ERROR] populate_layers failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Reconnect signal
            self.layer_tree.itemChanged.connect(self.on_layer_renamed)

    def _add_layer_to_tree(self, layer, parent_item):
        """Recursively add a layer and its children to the tree"""
        try:
            layer_name = str(layer.name)
            is_hidden = layer.ishidden
            is_current = layer.current

            # Check if this layer has children
            try:
                num_children = layer.getNumChildren()
                has_children = num_children > 0
                if has_children:
                    print(f"[HIERARCHY] {layer_name} has {num_children} children")
            except:
                has_children = False

            # Column 0: Arrow (▼ solid down if has children, ▷ hollow right if not)
            # Column 1: Visibility icon
            # Column 2: Add selection icon
            # Column 3: Layer name
            arrow = "▼" if has_children else "▷"

            # Create tree item (as child of parent_item if provided, else root)
            # Calculate depth for proper indentation in column 4
            depth = 0
            temp_parent = parent_item
            while temp_parent:
                depth += 1
                temp_parent = temp_parent.parent()

            # Add extra spacing based on depth (4 spaces per level)
            display_name = ("    " * depth) + layer_name

            if parent_item:
                item = QtWidgets.QTreeWidgetItem(parent_item, [arrow, "", "", display_name])
            else:
                item = QtWidgets.QTreeWidgetItem(self.layer_tree, [arrow, "", "", display_name])

            # Set visibility icon
            # Check if parent is hidden (child inherits parent's hidden state)
            parent_hidden = False
            if parent_item:
                try:
                    parent_layer = layer.getParent()
                    if parent_layer and str(parent_layer) != "undefined":
                        parent_hidden = parent_layer.ishidden
                except:
                    pass

            if self.use_native_icons:
                # Choose icon based on visibility state
                if parent_hidden and self.icon_hidden_light:
                    # Parent is hidden - use light/disabled hidden icon
                    icon = self.icon_hidden_light
                elif is_hidden:
                    # Layer is directly hidden
                    icon = self.icon_hidden
                else:
                    # Layer is visible
                    icon = self.icon_visible
                item.setIcon(1, icon)
                item.setTextAlignment(1, QtCore.Qt.AlignCenter)
            else:
                # Determine icon based on visibility state
                if parent_hidden:
                    # Parent is hidden, so child is hidden by inheritance
                    icon_text = "✕"  # Light X - hidden because parent is hidden
                elif is_hidden:
                    # Layer is directly hidden
                    icon_text = "✖"  # Heavy X
                else:
                    # Layer is visible
                    icon_text = "👁"

                item.setText(1, icon_text)
                item.setTextAlignment(1, QtCore.Qt.AlignCenter)
                font = item.font(1)
                font.setPointSize(10)  # Reduced from 12 to 10
                font.setBold(True)
                item.setFont(1, font)

            # Add arrow styling in column 0 - left aligned with indentation
            item.setTextAlignment(0, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            arrow_font = item.font(0)
            # Hollow right arrow (▷) is 14pt, down arrow (▼) is 10pt
            arrow_font.setPointSize(14 if arrow == "▷" else 10)
            arrow_font.setBold(False)  # Not bold
            item.setFont(0, arrow_font)

            # Add selection icon in column 2
            if self.use_native_add_icon:
                item.setIcon(2, self.icon_add_selection)
                item.setTextAlignment(2, QtCore.Qt.AlignCenter)
            else:
                item.setText(2, "+")
                item.setTextAlignment(2, QtCore.Qt.AlignCenter)
                font = item.font(2)
                font.setPointSize(14)
                font.setBold(True)
                item.setFont(2, font)

            # Select the current/active layer
            if is_current:
                item.setSelected(True)

            # Recursively add children
            if has_children:
                # Expand parent layers by default (like native layer manager)
                item.setExpanded(True)

                # Get all children and sort them alphabetically
                children = []
                for i in range(num_children):
                    child = layer.getChild(i + 1)  # Note: getChild uses 1-based index (MAXScript convention)
                    if child:
                        children.append(child)

                # Sort children alphabetically
                children.sort(key=lambda x: str(x.name).lower())

                # Add each child recursively
                for child in children:
                    self._add_layer_to_tree(child, item)

        except Exception as e:
            print(f"[ERROR] _add_layer_to_tree failed for layer: {e}")
            import traceback
            traceback.print_exc()

    def select_active_layer(self):
        """Find and select the currently active layer in the tree"""
        if rt is None:
            return

        try:
            # Clear all existing selections first (only one layer can be active)
            self.layer_tree.clearSelection()

            # Get the current layer from 3ds Max
            layer_manager = rt.layerManager
            current_layer = layer_manager.current

            if current_layer:
                current_layer_name = str(current_layer.name)

                # Recursively find and select the matching item in the tree
                def find_and_select(parent_item=None):
                    if parent_item is None:
                        # Check top-level items
                        for i in range(self.layer_tree.topLevelItemCount()):
                            item = self.layer_tree.topLevelItem(i)
                            if item.text(3) == current_layer_name:  # Column 3 is layer name
                                item.setSelected(True)
                                return True
                            # Check children recursively
                            if find_and_select_children(item):
                                return True
                    return False

                def find_and_select_children(parent_item):
                    for i in range(parent_item.childCount()):
                        child = parent_item.child(i)
                        if child.text(3) == current_layer_name:  # Column 3 is layer name
                            child.setSelected(True)
                            return True
                        # Check nested children
                        if find_and_select_children(child):
                            return True
                    return False

                find_and_select()

        except Exception as e:
            pass  # Debug print removed

    def on_layer_clicked(self, item, column):
        """Handle layer click - toggle visibility, add selection, or set active layer"""
        if rt is None:
            return

        try:
            # Get the layer name from the tree item (column 3)
            layer_name = item.text(3)

            # Don't process test mode items
            if layer_name.startswith("[TEST MODE]"):
                return

            # Column 0 = arrow (expand/collapse - will implement later)
            # Column 1 = visibility icon (toggle visibility)
            # Column 2 = add selection icon (assign selected objects to layer)
            # Column 3 = layer name (set as current layer)
            if column == 0:
                # Arrow click - expand/collapse (TODO: implement hierarchy)
                pass
            elif column == 1:
                # Toggle visibility only - do NOT select row or activate layer
                self.toggle_layer_visibility(item, layer_name)
            elif column == 2:
                # Add selected objects to this layer
                self.add_selection_to_layer(layer_name)
            elif column == 3:
                # Set as current layer (selection already handled by CustomTreeWidget)
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
            # Find the layer in 3ds Max by name (search recursively for nested layers)
            layer = self._find_layer_by_name(layer_name)

            if layer:
                # Check if parent is hidden
                parent_hidden = False
                try:
                    parent_layer = layer.getParent()
                    if parent_layer and str(parent_layer) != "undefined":
                        parent_hidden = parent_layer.ishidden
                except:
                    pass

                # If parent is hidden, don't allow toggling (child follows parent)
                if parent_hidden:
                    return

                # Toggle visibility
                layer.ishidden = not layer.ishidden

                # Update icon in column 1 (native if available, Unicode fallback otherwise)
                if self.use_native_icons:
                    item.setIcon(1, self.icon_hidden if layer.ishidden else self.icon_visible)
                    item.setTextAlignment(1, QtCore.Qt.AlignCenter)
                else:
                    new_icon_text = "✖" if layer.ishidden else "👁"
                    item.setText(1, new_icon_text)
                    item.setTextAlignment(1, QtCore.Qt.AlignCenter)

                status = "hidden" if layer.ishidden else "visible"
                pass  # Debug print removed

                # If this layer has children, refresh the entire tree to update their icons
                try:
                    if layer.getNumChildren() > 0:
                        self.populate_layers()
                except:
                    pass

        except Exception as e:
            import traceback
            error_msg = f"Error toggling layer visibility: {str(e)}\n{traceback.format_exc()}"
            print(f"[ERROR] {error_msg}")

    def _find_layer_by_name(self, layer_name):
        """Recursively search for a layer by name in the entire layer hierarchy"""
        if rt is None:
            return None

        layer_manager = rt.layerManager
        layer_count = layer_manager.count

        # Helper function to search recursively
        def search_children(parent_layer):
            try:
                num_children = parent_layer.getNumChildren()
                for i in range(num_children):
                    child = parent_layer.getChild(i + 1)  # 1-based index
                    if child:
                        if str(child.name) == layer_name:
                            return child
                        # Recursively search this child's children
                        result = search_children(child)
                        if result:
                            return result
            except:
                pass
            return None

        # First check root level layers
        for i in range(layer_count):
            layer = layer_manager.getLayer(i)
            if layer:
                if str(layer.name) == layer_name:
                    return layer
                # Search this layer's children
                result = search_children(layer)
                if result:
                    return result

        return None

    def add_selection_to_layer(self, layer_name):
        """Add all currently selected objects to the specified layer"""
        if rt is None:
            return

        try:
            # Get currently selected objects
            selected_objects = rt.selection

            if len(selected_objects) == 0:
                pass  # Debug print removed
                return

            # Find the target layer (search recursively for nested layers)
            target_layer = self._find_layer_by_name(layer_name)

            if target_layer:
                # Assign all selected objects to this layer
                object_count = 0
                for obj in selected_objects:
                    target_layer.addNode(obj)
                    object_count += 1

                pass  # Debug print removed
            else:
                print(f"[ERROR] Layer '{layer_name}' not found")

        except Exception as e:
            import traceback
            error_msg = f"Error adding selection to layer: {str(e)}\n{traceback.format_exc()}"
            print(f"[ERROR] {error_msg}")

    def set_current_layer(self, layer_name):
        """Set the layer as current/active in 3ds Max"""
        if rt is None:
            return

        try:
            # Find the layer (search recursively for nested layers)
            layer = self._find_layer_by_name(layer_name)

            if layer:
                # Set this layer as the current layer
                layer.current = True
                pass  # Debug print removed

        except Exception as e:
            import traceback
            error_msg = f"Error setting active layer: {str(e)}\n{traceback.format_exc()}"
            print(f"[ERROR] {error_msg}")

    def on_layer_double_clicked(self, item, column):
        """Handle layer double-click - start inline rename"""
        pass  # Debug print removed

        # Only rename on column 3 (name column), not other columns
        if column != 3:
            return

        # Don't process test mode items
        if item.text(3).startswith("[TEST MODE]"):
            pass  # Debug print removed
            return

        # Store the original name before editing
        self.editing_layer_name = item.text(3)
        pass  # Debug print removed

        # Block signals while making item editable to avoid premature itemChanged trigger
        self.layer_tree.blockSignals(True)
        item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
        self.layer_tree.blockSignals(False)

        # Now start editing (column 2 = name)
        self.layer_tree.editItem(item, 2)
        pass  # Debug print removed

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
            # Trigger inline rename on column 3 (name column)
            self.on_layer_double_clicked(item, 3)

    def on_layer_renamed(self, item, column):
        """Handle layer rename after inline editing"""
        pass  # Debug print removed

        # Only process renames on column 3 (name column)
        if column != 3:
            return

        if rt is None or self.editing_layer_name is None:
            pass  # Debug print removed
            return

        try:
            # Get the new name from the item (column 3)
            new_name = item.text(3)
            old_name = self.editing_layer_name

            pass  # Debug print removed

            # Don't process test mode items
            if old_name.startswith("[TEST MODE]"):
                pass  # Debug print removed
                return

            # Only process if name actually changed
            if new_name != old_name and new_name:
                pass  # Debug print removed
                # Find the layer in 3ds Max by name
                layer_manager = rt.layerManager
                layer_count = layer_manager.count

                for i in range(layer_count):
                    layer = layer_manager.getLayer(i)
                    if layer and str(layer.name) == old_name:
                        # Rename the layer in 3ds Max
                        layer.setname(new_name)
                        pass  # Debug print removed

                        # Refresh the layer list to re-sort alphabetically
                        self.populate_layers()
                        break
            else:
                pass  # Debug print removed

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

    def setup_sync_timer(self):
        """Setup timer to poll for current layer changes (syncs with native layer manager)"""
        self.sync_timer = QtCore.QTimer(self)
        self.sync_timer.timeout.connect(self.check_current_layer_sync)
        # Check every 500ms for current layer changes
        self.sync_timer.start(500)
        pass  # Debug print removed

    def check_current_layer_sync(self):
        """Check if the current layer or visibility states changed in Max and update UI"""
        if rt is None:
            return

        try:
            # Get current layer from Max
            layer_manager = rt.layerManager
            current_layer = layer_manager.current

            # Check if current layer changed
            if current_layer:
                current_layer_name = str(current_layer.name)

                if current_layer_name != self.last_current_layer:
                    pass  # Debug print removed
                    self.last_current_layer = current_layer_name
                    # Update selection in tree
                    self.select_active_layer()

            # Check visibility states for all layers
            layer_count = layer_manager.count
            visibility_changed = False

            for i in range(layer_count):
                layer = layer_manager.getLayer(i)
                if layer:
                    layer_name = str(layer.name)
                    is_hidden = layer.ishidden

                    # Check if visibility changed for this layer
                    if layer_name not in self.last_visibility_states or self.last_visibility_states[layer_name] != is_hidden:
                        pass  # Debug print removed
                        self.last_visibility_states[layer_name] = is_hidden
                        visibility_changed = True

                        # Update the icon in the tree
                        for j in range(self.layer_tree.topLevelItemCount()):
                            item = self.layer_tree.topLevelItem(j)
                            if item.text(2) == layer_name:  # Column 2 is layer name
                                # Update icon
                                if self.use_native_icons:
                                    item.setIcon(0, self.icon_hidden if is_hidden else self.icon_visible)
                                else:
                                    new_icon_text = "✖" if is_hidden else "👁"
                                    item.setText(0, new_icon_text)
                                break

        except Exception as e:
            # Silently fail - this runs frequently so don't spam errors
            pass

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

global EskiLayerManagerCurrentCallback
fn EskiLayerManagerCurrentCallback = (
    python.Execute "import eski_layer_manager; eski_layer_manager.sync_current_layer()"
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

            # Register callback for current layer changes (just update selection, no full refresh)
            # Try both possible callback names for layer current change
            try:
                rt.callbacks.addScript(rt.Name("layerCurrent"), "EskiLayerManagerCurrentCallback()")
                pass  # Debug print removed
            except:
                pass  # Debug print removed
                # Some Max versions might use different callback names
                # We'll rely on the refresh from clicking in our UI instead

            # Register callbacks for scene events (use scene refresh - reopen window)
            rt.callbacks.addScript(rt.Name("filePostOpen"), "EskiLayerManagerSceneCallback()")
            rt.callbacks.addScript(rt.Name("systemPostReset"), "EskiLayerManagerSceneCallback()")
            rt.callbacks.addScript(rt.Name("systemPostNew"), "EskiLayerManagerSceneCallback()")
            # Note: postMerge callback not supported in 3ds Max 2026

            pass  # Debug print removed
        except Exception as e:
            pass  # Debug print removed

    def remove_callbacks(self):
        """Remove 3ds Max callbacks"""
        if rt is None:
            return

        try:
            # Remove all instances of our callback
            rt.callbacks.removeScripts(rt.Name("layerCreated"), id=rt.Name("EskiLayerManagerCallback"))
            rt.callbacks.removeScripts(rt.Name("layerDeleted"), id=rt.Name("EskiLayerManagerCallback"))
            rt.callbacks.removeScripts(rt.Name("nodeLayerChanged"), id=rt.Name("EskiLayerManagerCallback"))
            rt.callbacks.removeScripts(rt.Name("layerCurrent"), id=rt.Name("EskiLayerManagerCurrentCallback"))
            rt.callbacks.removeScripts(rt.Name("filePostOpen"), id=rt.Name("EskiLayerManagerCallback"))
            rt.callbacks.removeScripts(rt.Name("systemPostReset"), id=rt.Name("EskiLayerManagerCallback"))
            rt.callbacks.removeScripts(rt.Name("systemPostNew"), id=rt.Name("EskiLayerManagerCallback"))
            # Note: postMerge callback not supported in 3ds Max 2026
            pass  # Debug print removed
        except Exception as e:
            pass  # Debug print removed

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

            pass  # Debug print removed
        except Exception as e:
            pass  # Debug print removed

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
                    pass  # Debug print removed
            except:
                pass

            # If not in scene, try global preferences
            if not position_data:
                try:
                    position_data = rt.getINISetting(rt.maxFilePath + rt.maxFileName + ".ini", "EskiLayerManager", "LastPosition")
                    if position_data and position_data != "":
                        pass  # Debug print removed
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

                    pass  # Debug print removed
        except Exception as e:
            pass  # Debug print removed

    def closeEvent(self, event):
        """Handle close event"""
        # Stop sync timer
        if hasattr(self, 'sync_timer'):
            self.sync_timer.stop()
            pass  # Debug print removed

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


def sync_current_layer():
    """
    Called by layerCurrent callback when the active layer changes in 3ds Max
    Updates the selection in the tree to match without full refresh
    """
    global _layer_manager_instance

    if _layer_manager_instance[0] is not None:
        try:
            # Check if widget is still valid
            _layer_manager_instance[0].isVisible()
            # Update selection to match current layer
            _layer_manager_instance[0].select_active_layer()
            print("[CALLBACK] Synced current layer selection")
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
