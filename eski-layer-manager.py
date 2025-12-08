"""
Eski LayerManager by Claude
A dockable layer and object manager for 3ds Max

Version: 0.13.1
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


VERSION = "0.13.1"

# Module initialization guard - prevents re-initialization on repeated imports
if '_ESKI_LAYER_MANAGER_INITIALIZED' not in globals():
    _ESKI_LAYER_MANAGER_INITIALIZED = True
    # Global instance variable - use a list to prevent garbage collection
    # List makes it a mutable container that survives module namespace issues
    _layer_manager_instance = [None]


class InlineIconDelegate(QtWidgets.QStyledItemDelegate):
    """
    Custom delegate for rendering inline icons (arrow, eye, +) and layer name in single column
    Layout: [tree lines] [arrow] [eye] [+] [layer name]
    """

    def __init__(self, layer_manager, parent=None):
        super(InlineIconDelegate, self).__init__(parent)
        self.layer_manager = layer_manager
        self.icon_size = 16
        self.icon_spacing = 4
        self.plus_icon_size = 18  # Bigger size for plus icon
        self.plus_icon_spacing = 4  # Extra spacing before plus icon

    def _get_visual_row_number(self, index):
        """Calculate the visual row number by counting all visible rows from top"""
        count = 0

        def count_rows_before(idx):
            nonlocal count
            parent = idx.parent()

            # Count siblings before this item
            for row in range(idx.row()):
                count += 1
                sibling = idx.sibling(row, 0)
                # If sibling is expanded, count its children too
                if self.layer_manager.layer_tree.isExpanded(sibling):
                    count_children(sibling)

            # Recursively count parent's position
            if parent.isValid():
                count += 1  # Count the parent itself
                count_rows_before(parent)

        def count_children(parent_idx):
            nonlocal count
            model = parent_idx.model()
            row_count = model.rowCount(parent_idx)
            for row in range(row_count):
                count += 1
                child_idx = model.index(row, 0, parent_idx)
                if self.layer_manager.layer_tree.isExpanded(child_idx):
                    count_children(child_idx)

        count_rows_before(index)
        return count

    def paint(self, painter, option, index):
        """Custom paint method for rendering inline icons"""
        painter.save()

        # Calculate visual row number (counting all visible rows from top)
        visual_row = self._get_visual_row_number(index)

        # Draw background (alternating rows) - NO full row selection highlight
        if visual_row % 2:
            painter.fillRect(option.rect, option.palette.alternateBase())
        else:
            painter.fillRect(option.rect, option.palette.base())

        # Get item data
        item = self.layer_manager.layer_tree.itemFromIndex(index)
        if not item:
            painter.restore()
            return

        # Starting X position - use the visual rect which accounts for indentation
        # option.rect gives us the item's visual rect in viewport coordinates
        x = option.rect.left()
        y = option.rect.top()
        h = option.rect.height()

        # Store click regions for later detection (in viewport coordinates)
        if not hasattr(item, 'click_regions'):
            item.click_regions = {}

        # Store the current item rect Y position for coordinate reference (store value, not QRect object)
        item.current_item_y = option.rect.y()

        # Skip drawing custom arrow - Qt's built-in tree arrows are sufficient
        # (We still store arrow data in UserRole but don't paint it)

        # 1. Draw visibility icon (👁/✖/🔒)
        vis_icon = item.data(0, QtCore.Qt.UserRole + 1)  # Store visibility icon
        if vis_icon:
            # Create rect in viewport coordinates
            vis_rect = QtCore.QRect(x, y, self.icon_size + self.icon_spacing, h)
            item.click_regions['visibility'] = vis_rect

            if isinstance(vis_icon, QtGui.QIcon):
                vis_icon.paint(painter, vis_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            else:
                painter.setFont(QtGui.QFont(painter.font().family(), 10))
                painter.drawText(vis_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, str(vis_icon))
            x += self.icon_size + self.icon_spacing

        # 2. Draw add selection icon (+) - bigger and with extra spacing
        add_icon = item.data(0, QtCore.Qt.UserRole + 2)  # Store add icon
        if add_icon:
            # Add extra spacing before the plus icon
            x += self.plus_icon_spacing

            # Create rect in viewport coordinates (bigger rect for plus icon)
            add_rect = QtCore.QRect(x, y, self.plus_icon_size, h)
            item.click_regions['add_selection'] = add_rect

            if isinstance(add_icon, QtGui.QIcon):
                add_icon.paint(painter, add_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            else:
                # Bigger font for plus icon
                painter.setFont(QtGui.QFont(painter.font().family(), 12))
                painter.drawText(add_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, str(add_icon))
            x += self.plus_icon_size + self.icon_spacing

        # 3. Draw layer name with custom highlight if selected
        layer_name = item.text(0)

        # Calculate text width for tight highlight
        font_metrics = QtGui.QFontMetrics(option.font)
        text_width = font_metrics.horizontalAdvance(layer_name)

        # Create tight rect just for the text
        text_rect = QtCore.QRect(x, y, text_width + 8, h)  # +8 for small padding
        name_rect = QtCore.QRect(x, y, option.rect.right() - x, h)  # Full clickable area
        item.click_regions['name'] = name_rect

        # Draw deep teal highlight behind text if selected
        if option.state & QtWidgets.QStyle.State_Selected:
            teal_color = QtGui.QColor(0, 128, 128)  # Deep teal
            painter.fillRect(text_rect, teal_color)
            painter.setPen(QtGui.QColor(255, 255, 255))  # White text on teal
        else:
            painter.setPen(option.palette.text().color())

        painter.setFont(option.font)
        painter.drawText(text_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, layer_name)

        painter.restore()


class CustomTreeWidget(QtWidgets.QTreeWidget):
    """Custom QTreeWidget that only allows selection on column 3"""

    def __init__(self, parent=None):
        super(CustomTreeWidget, self).__init__(parent)
        self.layer_manager = None  # Will be set by EskiLayerManager

    def mousePressEvent(self, event):
        """Intercept mouse press - only allow selection when clicking on layer name"""
        item = self.itemAt(event.pos())
        if not item:
            super(CustomTreeWidget, self).mousePressEvent(event)
            return

        # Get click position in viewport coordinates
        cursor_pos = event.pos()

        # Get the visual rect for this item
        index = self.indexAt(event.pos())
        visual_rect = self.visualRect(index)

        # Check if clicking on icons (visibility or add selection)
        if hasattr(item, 'click_regions') and hasattr(item, 'current_item_y'):
            y_offset = visual_rect.y() - item.current_item_y

            # Check if clicking on visibility icon
            if 'visibility' in item.click_regions:
                vis_rect = item.click_regions['visibility'].translated(0, y_offset)
                if vis_rect.contains(cursor_pos):
                    # Don't allow selection - just let itemClicked handle the toggle
                    event.accept()
                    self.itemClicked.emit(item, 0)
                    return

            # Check if clicking on add selection icon
            if 'add_selection' in item.click_regions:
                add_rect = item.click_regions['add_selection'].translated(0, y_offset)
                if add_rect.contains(cursor_pos):
                    # Don't allow selection - just let itemClicked handle the add
                    event.accept()
                    self.itemClicked.emit(item, 0)
                    return

        # If clicking on name region or anywhere else, allow normal selection
        super(CustomTreeWidget, self).mousePressEvent(event)

    def dropEvent(self, event):
        """Handle drop event to reparent layers or reassign objects to layers in 3ds Max"""
        # Check if this is a drag from the objects tree
        source_widget = event.source()

        # If dragging from objects tree (not layer tree)
        if source_widget != self and hasattr(self.layer_manager, 'objects_tree') and source_widget == self.layer_manager.objects_tree:
            # Get selected objects from objects tree
            dragged_objects = self.layer_manager.objects_tree.selectedItems()
            if not dragged_objects:
                event.ignore()
                return

            # Get target layer
            target_item = self.itemAt(event.pos())
            if not target_item:
                event.ignore()
                return

            target_layer_name = target_item.text(0)  # Single column - text(0) is layer name

            # Get object names
            object_names = [item.text(0) for item in dragged_objects]

            # Call the layer manager to reassign objects
            if self.layer_manager:
                self.layer_manager.reassign_objects_to_layer(object_names, target_layer_name)

            event.accept()
            return

        # Original layer reparenting logic
        # Get the dragged item
        dragged_items = self.selectedItems()
        if not dragged_items:
            event.ignore()
            return

        dragged_item = dragged_items[0]
        dragged_layer_name = dragged_item.text(0)  # Single column - text(0) is layer name

        # Get drop position
        drop_indicator = self.dropIndicatorPosition()
        target_item = self.itemAt(event.pos())

        # Determine the new parent based on drop position
        new_parent_name = None
        if target_item:
            target_layer_name = target_item.text(0)  # Single column

            if drop_indicator == QtWidgets.QAbstractItemView.OnItem:
                # Dropped ON item - make it a child
                new_parent_name = target_layer_name
            elif drop_indicator in [QtWidgets.QAbstractItemView.AboveItem, QtWidgets.QAbstractItemView.BelowItem]:
                # Dropped ABOVE or BELOW item - make it a sibling (same parent as target)
                if target_item.parent():
                    new_parent_name = target_item.parent().text(0)  # Single column
                else:
                    new_parent_name = None  # Root level
        else:
            # Dropped on empty space - make it root
            new_parent_name = None

        # Call the layer manager to update 3ds Max
        if self.layer_manager:
            self.layer_manager.reparent_layer(dragged_layer_name, new_parent_name)
            # The reparent_layer method calls populate_layers() which rebuilds the tree
            # This ensures the UI matches 3ds Max's hierarchy exactly

        # Ignore the event to prevent Qt from doing its own tree manipulation
        # We handle everything through populate_layers() refresh
        event.ignore()

    def drawBranches(self, painter, rect, index):
        """Override to draw custom tree lines, horizontal connectors, and expand/collapse arrows"""
        painter.save()

        indent = self.indentation()
        depth = 0
        parent_idx = index.parent()
        while parent_idx.isValid():
            depth += 1
            parent_idx = parent_idx.parent()

        # Center Y position for horizontal line
        center_y = rect.y() + rect.height() // 2

        # Draw vertical lines for parent hierarchy
        pen = QtGui.QPen(QtGui.QColor("#CCCCCC"), 1)  # Brighter gray
        pen.setStyle(QtCore.Qt.DotLine)  # Make lines dotted
        painter.setPen(pen)

        # Draw vertical lines for each parent level
        temp_parent = index.parent()
        temp_depth = depth - 1
        while temp_parent.isValid():
            # Check if this parent has more siblings below
            parent_of_parent = temp_parent.parent()
            if parent_of_parent.isValid():
                row = temp_parent.row()
                sibling_count = self.model().rowCount(parent_of_parent)
                if row < sibling_count - 1:  # Has siblings below
                    x = temp_depth * indent + indent // 2
                    painter.drawLine(x, rect.y(), x, rect.y() + rect.height())
            elif temp_parent.row() < self.model().rowCount(QtCore.QModelIndex()) - 1:
                # Root level with siblings below
                x = temp_depth * indent + indent // 2
                painter.drawLine(x, rect.y(), x, rect.y() + rect.height())

            temp_depth -= 1
            temp_parent = temp_parent.parent()

        # Draw horizontal line to this item (centered vertically)
        if depth > 0:
            x_start = (depth - 1) * indent + indent // 2
            # Extend line further if no children (no arrow takes up space)
            if self.model().hasChildren(index):
                x_end = depth * indent + 2
            else:
                x_end = depth * indent + 16  # Extend to reach near the eye icon
            painter.drawLine(x_start, center_y, x_end, center_y)

            # Draw vertical line from top to center for this item
            x = (depth - 1) * indent + indent // 2

            # Check if this item has siblings below
            if index.parent().isValid():
                row = index.row()
                sibling_count = self.model().rowCount(index.parent())
                if row < sibling_count - 1:  # Has siblings below
                    painter.drawLine(x, rect.y(), x, center_y)
                else:  # Last child
                    painter.drawLine(x, rect.y(), x, center_y)
            else:
                # Root level
                row = index.row()
                sibling_count = self.model().rowCount(QtCore.QModelIndex())
                if row < sibling_count - 1:
                    painter.drawLine(x, rect.y(), x, center_y)
                else:
                    painter.drawLine(x, rect.y(), x, center_y)
        else:
            # Root level (depth == 0) - draw horizontal line from left edge
            x_start = indent // 2
            x_end = indent + 2
            painter.drawLine(x_start, center_y, x_end, center_y)

            # Draw vertical line for root level connection
            x = indent // 2
            row = index.row()
            sibling_count = self.model().rowCount(QtCore.QModelIndex())

            if row == 0 and sibling_count > 1:
                # First root item - draw from center down
                painter.drawLine(x, center_y, x, rect.y() + rect.height())
            elif row == sibling_count - 1 and row > 0:
                # Last root item - draw from top to center
                painter.drawLine(x, rect.y(), x, center_y)
            elif sibling_count > 1:
                # Middle root item - draw full height
                painter.drawLine(x, rect.y(), x, rect.y() + rect.height())

        # Draw expand/collapse arrow if this item has children
        if self.model().hasChildren(index):
            arrow_y = center_y

            # Set font for arrow
            font = self.font()
            font.setPointSize(20)
            painter.setFont(font)

            if self.isExpanded(index):
                # Draw down arrow (▾) - moved left 1 pixel
                arrow_text = "▾"
                arrow_x = depth * indent + 4
            else:
                # Draw right arrow (▸) - moved up 3 pixels
                arrow_text = "▸"
                arrow_x = depth * indent + 4

            # Draw the arrow text centered
            fm = QtGui.QFontMetrics(font)
            text_width = fm.horizontalAdvance(arrow_text)
            # Move right arrow up 3 pixels
            y_offset = -3 if not self.isExpanded(index) else 0
            painter.drawText(arrow_x, arrow_y + fm.ascent() // 2 + y_offset, arrow_text)

        painter.restore()


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

        # Set default size (taller window)
        self.resize(350, 800)  # Width: 350px, Height: 800px (was default ~400px)

        # Note: Position restoration is now handled in show_layer_manager()
        # This ensures saved position is applied AFTER the widget is added to the main window

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
        self.layer_tree.layer_manager = self  # Set reference for drag-and-drop
        self.layer_tree.setHeaderLabels(["Layers"])  # Single column layout
        self.layer_tree.header().setStretchLastSection(True)  # Stretch single column
        self.layer_tree.header().setVisible(True)  # Show header
        self.layer_tree.setAlternatingRowColors(True)

        # Enable Qt's built-in tree decoration (arrows and connecting lines)
        self.layer_tree.setRootIsDecorated(True)  # Show Qt's expand/collapse arrows
        self.layer_tree.setItemsExpandable(True)  # Allow expand/collapse
        self.layer_tree.setIndentation(20)  # Indentation for hierarchy

        # Stylesheet for tree view (no custom branch drawing - handled by drawBranches override)
        self.layer_tree.setStyleSheet("""
            QTreeView {
                show-decoration-selected: 0;
            }

            QTreeView::item {
                padding: 2px;
            }

            /* Clear all branch styling - we draw everything in drawBranches */
            QTreeView::branch {
                border-image: none;
                background: transparent;
                image: none;
            }

            /* Remove selection background from branch area */
            QTreeView::branch:selected {
                background: transparent;
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

        # Enable drag-and-drop for layer reparenting and object reassignment
        self.layer_tree.setDragEnabled(True)
        self.layer_tree.setAcceptDrops(True)
        self.layer_tree.setDropIndicatorShown(True)
        self.layer_tree.setDragDropMode(QtWidgets.QAbstractItemView.DragDrop)  # Accept both internal and external drops

        # Install custom delegate for inline icon rendering
        self.custom_delegate = InlineIconDelegate(self, self.layer_tree)
        self.layer_tree.setItemDelegate(self.custom_delegate)  # Apply to all columns

        top_layout.addWidget(self.layer_tree)

        # Bottom section - object list
        bottom_widget = QtWidgets.QWidget()
        bottom_layout = QtWidgets.QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(5, 5, 5, 5)

        # Add label for objects section
        objects_label = QtWidgets.QLabel("Objects")
        objects_label.setStyleSheet("font-weight: bold; padding: 2px;")
        bottom_layout.addWidget(objects_label)

        # Create objects tree using same CustomTreeWidget as layers
        self.objects_tree = CustomTreeWidget()
        self.objects_tree.setHeaderHidden(True)
        self.objects_tree.setIndentation(20)
        self.objects_tree.setAlternatingRowColors(True)
        self.objects_tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)  # Enable multi-select
        self.objects_tree.setDragEnabled(True)  # Enable dragging from objects tree
        self.objects_tree.setItemDelegate(InlineIconDelegate(self))
        self.objects_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #2b2b2b;
                alternate-background-color: #2d2d2d;
                color: #cccccc;
                border: none;
                outline: none;
            }
            QTreeWidget::item {
                padding: 0px;
                padding-left: 2px;
                padding-right: 2px;
                height: 18px;
                border: none;
            }
            QTreeWidget::item:selected {
                background-color: transparent;
            }
            QTreeWidget::item:hover {
                background-color: #3a3a3a;
            }
            /* Clear all branch styling - we draw everything in drawBranches */
            QTreeWidget::branch {
                background: transparent;
                border: none;
            }
        """)

        # Connect object selection to scene selection
        self.objects_tree.itemSelectionChanged.connect(self.on_object_selection_changed)

        bottom_layout.addWidget(self.objects_tree)

        # Add widgets to splitter
        self.splitter.addWidget(top_widget)
        self.splitter.addWidget(bottom_widget)

        # Set initial sizes (60% top, 40% bottom)
        self.splitter.setSizes([240, 160])

        # Add splitter to main layout
        main_layout.addWidget(self.splitter)

        # Set minimum size
        self.setMinimumSize(250, 400)

        # Create horizontal layout for buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setAlignment(QtCore.Qt.AlignLeft)

        # Add refresh button with icon
        refresh_btn = QtWidgets.QPushButton()
        refresh_btn.clicked.connect(self.populate_layers)
        refresh_btn.setToolTip("Refresh Layers")
        refresh_btn.setFixedSize(32, 32)  # Square button

        # Try to load StateSets/Refresh icon
        try:
            if QTMAX_AVAILABLE:
                import qtmax
                refresh_icon = qtmax.LoadMaxMultiResIcon("StateSets/Refresh")
                if refresh_icon and not refresh_icon.isNull():
                    refresh_btn.setIcon(refresh_icon)
                    refresh_btn.setIconSize(QtCore.QSize(24, 24))
                else:
                    # Fallback to text if icon not found
                    refresh_btn.setText("R")
            else:
                refresh_btn.setText("R")
        except:
            refresh_btn.setText("R")

        button_layout.addWidget(refresh_btn)

        # Add create new layer button with icon
        create_layer_btn = QtWidgets.QPushButton()
        create_layer_btn.clicked.connect(self.create_new_layer)
        create_layer_btn.setToolTip("Create New Layer")
        create_layer_btn.setFixedSize(32, 32)  # Square button

        # Try to load Layer icon - try multiple paths following StateSets pattern
        icon_loaded = False
        if QTMAX_AVAILABLE:
            import qtmax
            # Try multiple icon paths for create new layer (following StateSets/Refresh pattern)
            icon_paths = [
                "Layers/CreateNewLayer",
                "Layers/NewLayer",
                "Layer/CreateNewLayer",
                "Layer/NewLayer",
                "Layer/Layer_NewLayer",
                "Layer/AddNewLayer",
                "SceneExplorer/CreateNewLayer",
                "SceneExplorer/NewLayer",
                "Ribbon/SceneExplorer/Layer_NewLayer"
            ]
            for icon_path in icon_paths:
                try:
                    create_icon = qtmax.LoadMaxMultiResIcon(icon_path)
                    if create_icon and not create_icon.isNull():
                        if len(create_icon.availableSizes()) > 0:
                            create_layer_btn.setIcon(create_icon)
                            create_layer_btn.setIconSize(QtCore.QSize(24, 24))
                            icon_loaded = True
                            break
                except:
                    continue

        if not icon_loaded:
            create_layer_btn.setText("+")

        button_layout.addWidget(create_layer_btn)

        # Add delete layer button with icon
        delete_layer_btn = QtWidgets.QPushButton()
        delete_layer_btn.clicked.connect(self.delete_selected_layer)
        delete_layer_btn.setToolTip("Delete Selected Layer")
        delete_layer_btn.setFixedSize(32, 32)  # Square button

        # Try to load DeleteAnimLayer icon (correct path: animationLayer/DeleteAnimLayer)
        delete_icon_loaded = False
        if QTMAX_AVAILABLE:
            import qtmax
            # Try the correct icon path first, then fallbacks
            delete_icon_paths = [
                "animationLayer/DeleteAnimLayer",  # Correct path
                "AnimationLayer/DeleteAnimLayer",
                "Animation/DeleteAnimLayer",
                "AnimLayers/DeleteAnimLayer",
                "AnimationLayers/DeleteAnimLayer"
            ]
            for icon_path in delete_icon_paths:
                try:
                    delete_icon = qtmax.LoadMaxMultiResIcon(icon_path)
                    if delete_icon and not delete_icon.isNull():
                        if len(delete_icon.availableSizes()) > 0:
                            delete_layer_btn.setIcon(delete_icon)
                            delete_layer_btn.setIconSize(QtCore.QSize(24, 24))
                            delete_icon_loaded = True
                            break
                except:
                    continue

        if not delete_icon_loaded:
            delete_layer_btn.setText("-")

        button_layout.addWidget(delete_layer_btn)

        top_layout.insertLayout(1, button_layout)

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
            # Testing mode outside 3ds Max - add dummy data with hierarchy (single column)
            parent = QtWidgets.QTreeWidgetItem(self.layer_tree, ["[TEST MODE] Parent Layer"])
            parent.setData(0, QtCore.Qt.UserRole, "▼")  # Arrow
            parent.setData(0, QtCore.Qt.UserRole + 1, "👁")  # Visibility
            parent.setData(0, QtCore.Qt.UserRole + 2, "+")  # Add selection

            child1 = QtWidgets.QTreeWidgetItem(parent, ["[TEST MODE] Child 1"])
            child1.setData(0, QtCore.Qt.UserRole + 1, "👁")
            child1.setData(0, QtCore.Qt.UserRole + 2, "+")

            child2 = QtWidgets.QTreeWidgetItem(parent, ["[TEST MODE] Child 2"])
            child2.setData(0, QtCore.Qt.UserRole + 1, "👁")
            child2.setData(0, QtCore.Qt.UserRole + 2, "+")

            root = QtWidgets.QTreeWidgetItem(self.layer_tree, ["[TEST MODE] Root Layer"])
            root.setData(0, QtCore.Qt.UserRole + 1, "👁")
            root.setData(0, QtCore.Qt.UserRole + 2, "+")

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
        """Recursively add a layer and its children to the tree (single column with inline icons)"""
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

            # Create tree item - single column with just the layer name
            if parent_item:
                item = QtWidgets.QTreeWidgetItem(parent_item, [layer_name])
            else:
                item = QtWidgets.QTreeWidgetItem(self.layer_tree, [layer_name])

            # Store icon data in UserRole for delegate to paint
            # UserRole: arrow (▼/▷)
            # UserRole+1: visibility icon
            # UserRole+2: add selection icon

            # 1. Store arrow (only if has children)
            if has_children:
                arrow = "▼"  # Will be shown as expanded by default
                item.setData(0, QtCore.Qt.UserRole, arrow)

            # 2. Store visibility icon
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
                item.setData(0, QtCore.Qt.UserRole + 1, icon)
            else:
                # Determine icon based on visibility state
                if parent_hidden:
                    icon_text = "🔒"  # Lock - hidden because parent is hidden
                elif is_hidden:
                    icon_text = "✖"  # Heavy X
                else:
                    icon_text = "👁"
                item.setData(0, QtCore.Qt.UserRole + 1, icon_text)

            # 3. Store add selection icon
            if self.use_native_add_icon:
                item.setData(0, QtCore.Qt.UserRole + 2, self.icon_add_selection)
            else:
                item.setData(0, QtCore.Qt.UserRole + 2, "+")

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
                    child = layer.getChild(i + 1)  # Note: getChild uses 1-based index
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

    def populate_objects(self, layer_name):
        """Populate the objects tree with objects from the specified layer"""
        self.objects_tree.clear()

        if rt is None:
            # Testing mode - add dummy objects
            test_objects = [
                "[TEST] Box001",
                "[TEST] Sphere001",
                "[TEST] Cylinder001"
            ]
            for obj_name in test_objects:
                item = QtWidgets.QTreeWidgetItem(self.objects_tree, [obj_name])
                # No icons for objects - just the name
            return

        try:
            # Find the layer
            layer = self._find_layer_by_name(layer_name)
            if not layer:
                print(f"[OBJECTS] Layer '{layer_name}' not found")
                return

            # Get all objects in the scene
            all_nodes = rt.objects

            # Filter objects that belong to this layer
            layer_objects = []
            for node in all_nodes:
                try:
                    if hasattr(node, 'layer') and node.layer and str(node.layer.name) == layer_name:
                        layer_objects.append(node)
                except:
                    pass

            print(f"[OBJECTS] Found {len(layer_objects)} objects in layer '{layer_name}'")

            # Sort objects by name
            layer_objects.sort(key=lambda x: str(x.name).lower())

            # Add each object to the tree
            for obj in layer_objects:
                try:
                    obj_name = str(obj.name)
                    item = QtWidgets.QTreeWidgetItem(self.objects_tree, [obj_name])
                    # No icons for objects - just the name

                except Exception as e:
                    print(f"[ERROR] Failed to add object to tree: {e}")

        except Exception as e:
            print(f"[ERROR] populate_objects failed: {e}")
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
                            # Single column - text(0) is layer name
                            if item.text(0) == current_layer_name:
                                item.setSelected(True)
                                return True
                            # Check children recursively
                            if find_and_select_children(item):
                                return True
                    return False

                def find_and_select_children(parent_item):
                    for i in range(parent_item.childCount()):
                        child = parent_item.child(i)
                        # Single column - text(0) is layer name
                        if child.text(0) == current_layer_name:
                            child.setSelected(True)
                            return True
                        # Check nested children
                        if find_and_select_children(child):
                            return True
                    return False

                find_and_select()

                # Populate objects tree with current layer's objects
                self.populate_objects(current_layer_name)

        except Exception as e:
            pass  # Debug print removed

    def on_object_selection_changed(self):
        """Handle object selection change - select objects in 3ds Max scene"""
        if rt is None:
            return

        try:
            # Get selected items from objects tree
            selected_items = self.objects_tree.selectedItems()
            if not selected_items:
                return

            # Get object names
            object_names = [item.text(0) for item in selected_items]

            # Build a selection array in 3ds Max
            selection_array = rt.Array()
            for obj_name in object_names:
                obj = rt.getNodeByName(obj_name)
                if obj:
                    rt.append(selection_array, obj)

            # Set the selection in 3ds Max
            if len(selection_array) > 0:
                rt.select(selection_array)
                print(f"[OBJECTS] Selected {len(selection_array)} object(s) in scene")

        except Exception as e:
            print(f"[ERROR] on_object_selection_changed failed: {e}")
            import traceback
            traceback.print_exc()

    def on_layer_clicked(self, item, column):
        """Handle layer click - toggle visibility, add selection, or set active layer (single column)"""
        if rt is None:
            return

        try:
            # Get the layer name from the tree item (single column)
            layer_name = item.text(0)

            # Don't process test mode items
            if layer_name.startswith("[TEST MODE]"):
                return

            # Get click position in viewport coordinates
            cursor_pos = self.layer_tree.viewport().mapFromGlobal(QtGui.QCursor.pos())
            print(f"[CLICK DEBUG] Layer: {layer_name}, Cursor pos: {cursor_pos.x()}, {cursor_pos.y()}")

            # Get the visual rect for this item to get current Y position (accounting for scroll)
            index = self.layer_tree.indexFromItem(item)
            visual_rect = self.layer_tree.visualRect(index)
            print(f"[CLICK DEBUG] Visual rect: {visual_rect.x()}, {visual_rect.y()}, {visual_rect.width()}, {visual_rect.height()}")

            # Check if item has click regions (set by delegate during last paint)
            if hasattr(item, 'click_regions') and hasattr(item, 'current_item_y'):
                print(f"[CLICK DEBUG] Has click_regions: {list(item.click_regions.keys())}")
                # Adjust click regions to current visual position (in case of scrolling)
                # The stored regions use the Y from paint time, we need current Y
                y_offset = visual_rect.y() - item.current_item_y
                print(f"[CLICK DEBUG] Y offset: {y_offset}, stored Y: {item.current_item_y}, current Y: {visual_rect.y()}")

                # Check which region was clicked
                # (Skip arrow - Qt's built-in tree arrows handle expand/collapse)
                if 'visibility' in item.click_regions:
                    vis_rect = item.click_regions['visibility'].translated(0, y_offset)
                    print(f"[CLICK DEBUG] Vis rect: {vis_rect.x()}, {vis_rect.y()}, {vis_rect.width()}, {vis_rect.height()}")
                    if vis_rect.contains(cursor_pos):
                        print(f"[CLICK DEBUG] CLICKED VISIBILITY!")
                        # Toggle visibility only - do NOT select row or activate layer
                        self.toggle_layer_visibility(item, layer_name)
                        return

                if 'add_selection' in item.click_regions:
                    add_rect = item.click_regions['add_selection'].translated(0, y_offset)
                    print(f"[CLICK DEBUG] Add rect: {add_rect.x()}, {add_rect.y()}, {add_rect.width()}, {add_rect.height()}")
                    if add_rect.contains(cursor_pos):
                        print(f"[CLICK DEBUG] CLICKED ADD SELECTION!")
                        # Add selected objects to this layer
                        self.add_selection_to_layer(layer_name)
                        return

                if 'name' in item.click_regions:
                    name_rect = item.click_regions['name'].translated(0, y_offset)
                    print(f"[CLICK DEBUG] Name rect: {name_rect.x()}, {name_rect.y()}, {name_rect.width()}, {name_rect.height()}")
                    if name_rect.contains(cursor_pos):
                        print(f"[CLICK DEBUG] CLICKED NAME!")
                        # Set as current layer (selection already handled by CustomTreeWidget)
                        self.set_current_layer(layer_name)
                        # Populate objects tree with objects from this layer
                        self.populate_objects(layer_name)
                        return
            else:
                print(f"[CLICK DEBUG] No click_regions found!")

            # Fallback - if no regions matched, treat as name click
            print(f"[CLICK DEBUG] Fallback to name click")
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
                        print(f"[DEBUG] Layer '{layer_name}' parent '{parent_layer.name}' is hidden: {parent_hidden}")
                    else:
                        print(f"[DEBUG] Layer '{layer_name}' has no parent")
                except Exception as e:
                    print(f"[DEBUG] Error checking parent for '{layer_name}': {e}")

                # If parent is hidden, don't allow toggling (child follows parent)
                if parent_hidden:
                    print(f"[DEBUG] Blocking toggle for '{layer_name}' - parent is hidden")
                    return

                # Toggle visibility
                print(f"[VISIBILITY] Toggling '{layer_name}' from ishidden={layer.ishidden} to ishidden={not layer.ishidden}")
                layer.ishidden = not layer.ishidden
                print(f"[VISIBILITY] After toggle: '{layer_name}' ishidden={layer.ishidden}")

                # Update icon in UserRole+1 (native if available, Unicode fallback otherwise)
                if self.use_native_icons:
                    item.setData(0, QtCore.Qt.UserRole + 1, self.icon_hidden if layer.ishidden else self.icon_visible)
                else:
                    new_icon_text = "✖" if layer.ishidden else "👁"
                    item.setData(0, QtCore.Qt.UserRole + 1, new_icon_text)

                # Trigger repaint
                self.layer_tree.update(self.layer_tree.indexFromItem(item))

                # Force viewport redraw to show/hide objects immediately
                rt.redrawViews()

                status = "hidden" if layer.ishidden else "visible"
                print(f"[VISIBILITY] Layer '{layer_name}' is now {status}")

                # If this layer has children, refresh the entire tree to update their icons
                try:
                    num_children = layer.getNumChildren()
                    if num_children > 0:
                        print(f"[VISIBILITY] Layer '{layer_name}' has {num_children} children, refreshing tree...")
                        self.populate_layers()
                except Exception as e:
                    print(f"[VISIBILITY] Error checking children: {e}")

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

    def reassign_objects_to_layer(self, object_names, target_layer_name):
        """Reassign objects (by name) to a different layer"""
        if rt is None:
            return

        try:
            # Find the target layer
            target_layer = self._find_layer_by_name(target_layer_name)
            if not target_layer:
                print(f"[ERROR] Target layer '{target_layer_name}' not found")
                return

            # Find and reassign each object
            success_count = 0
            for obj_name in object_names:
                try:
                    # Get object by name from 3ds Max
                    obj = rt.getNodeByName(obj_name)
                    if obj:
                        # Assign to new layer
                        target_layer.addNode(obj)
                        success_count += 1
                    else:
                        print(f"[ERROR] Object '{obj_name}' not found")
                except Exception as e:
                    print(f"[ERROR] Failed to reassign object '{obj_name}': {e}")

            print(f"[OBJECTS] Reassigned {success_count}/{len(object_names)} objects to layer '{target_layer_name}'")

            # Refresh the objects tree to show updated list
            self.populate_objects(target_layer_name)

        except Exception as e:
            import traceback
            error_msg = f"Error reassigning objects to layer: {str(e)}\n{traceback.format_exc()}"
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

    def create_new_layer(self):
        """Create a new layer in 3ds Max"""
        if rt is None:
            return

        try:
            # Create a new layer using newLayer() instead of newLayerFromName()
            layer_manager = rt.layerManager
            new_layer = layer_manager.newLayer()

            if new_layer:
                # Set the layer name
                new_layer.setName("Layer")

            # Refresh the layer list to show the new layer
            self.populate_layers()

        except Exception as e:
            import traceback
            error_msg = f"Error creating new layer: {str(e)}\n{traceback.format_exc()}"
            print(f"[ERROR] {error_msg}")

    def delete_selected_layer(self):
        """Delete the currently selected layer in the tree"""
        if rt is None:
            return

        # Get selected item
        selected_items = self.layer_tree.selectedItems()
        if not selected_items:
            print("[ERROR] No layer selected to delete")
            return

        selected_item = selected_items[0]
        layer_name = selected_item.text(3).lstrip()  # Column 3 is layer name, strip indentation

        try:
            # Find the layer (search recursively for nested layers)
            layer = self._find_layer_by_name(layer_name)

            if layer:
                # Check if layer has any objects
                node_count = len(layer.nodes) if layer.nodes else 0

                if layer.nodes and node_count > 0:
                    print(f"[ERROR] Cannot delete layer '{layer_name}' - it contains {node_count} object(s)")
                    return

                # Delete the layer
                layer_manager = rt.layerManager
                layer_manager.deleteLayerByName(layer_name)

                # Refresh the layer list
                self.populate_layers()

            else:
                print(f"[ERROR] Layer '{layer_name}' not found")

        except Exception as e:
            import traceback
            error_msg = f"Error deleting layer: {str(e)}\n{traceback.format_exc()}"
            print(f"[ERROR] {error_msg}")

    def toggle_expand_collapse(self, item):
        """Toggle expand/collapse state of a layer with children"""
        # Check if this layer has children
        if item.childCount() == 0:
            # No children, nothing to expand/collapse
            return

        # Toggle expanded state
        is_expanded = item.isExpanded()
        item.setExpanded(not is_expanded)

        # Update arrow icon in UserRole: ▼ when expanded, ▷ when collapsed
        new_arrow = "▷" if is_expanded else "▼"
        item.setData(0, QtCore.Qt.UserRole, new_arrow)

        # Trigger repaint to show new arrow
        self.layer_tree.update(self.layer_tree.indexFromItem(item))

    def reparent_layer(self, layer_name, new_parent_name):
        """Reparent a layer in 3ds Max"""
        if rt is None:
            return

        try:
            # Find the layer to move
            layer = self._find_layer_by_name(layer_name)
            if not layer:
                print(f"[ERROR] Layer '{layer_name}' not found")
                return

            # Prevent circular reference (can't make layer its own parent)
            if new_parent_name == layer_name:
                print(f"[ERROR] Cannot make layer '{layer_name}' its own parent")
                return

            # Find the new parent layer (or None for root)
            new_parent = None
            if new_parent_name:
                new_parent = self._find_layer_by_name(new_parent_name)
                if not new_parent:
                    print(f"[ERROR] Parent layer '{new_parent_name}' not found")
                    return

                # Prevent circular reference (can't make layer child of its own descendant)
                # Check if new_parent is a descendant of layer
                temp = new_parent
                while temp:
                    parent = temp.getParent()
                    if parent and str(parent) != "undefined":
                        if str(parent.name) == layer_name:
                            print(f"[ERROR] Cannot make layer '{layer_name}' a child of its descendant '{new_parent_name}'")
                            return
                        temp = parent
                    else:
                        break

            # Set the new parent
            if new_parent:
                layer.setParent(new_parent)
            else:
                # Make it a root layer by setting parent to undefined
                layer.setParent(rt.undefined)

            # Refresh the layer list to show the new hierarchy
            self.populate_layers()

        except Exception as e:
            import traceback
            error_msg = f"Error reparenting layer: {str(e)}\n{traceback.format_exc()}"
            print(f"[ERROR] {error_msg}")

    def on_layer_double_clicked(self, item, column):
        """Handle layer double-click - start inline rename (single column layout)"""
        if rt is None:
            return

        # Get click position to check if we're clicking on the name area (viewport coordinates)
        cursor_pos = self.layer_tree.viewport().mapFromGlobal(QtGui.QCursor.pos())

        # Get the visual rect for this item
        index = self.layer_tree.indexFromItem(item)
        visual_rect = self.layer_tree.visualRect(index)

        # Only rename if clicking in the name region, not on icons
        if hasattr(item, 'click_regions') and hasattr(item, 'current_item_y'):
            y_offset = visual_rect.y() - item.current_item_y

            # Check if clicking on visibility or add selection icons - if so, don't rename
            if 'visibility' in item.click_regions:
                vis_rect = item.click_regions['visibility'].translated(0, y_offset)
                if vis_rect.contains(cursor_pos):
                    return  # Don't rename when clicking eye icon

            if 'add_selection' in item.click_regions:
                add_rect = item.click_regions['add_selection'].translated(0, y_offset)
                if add_rect.contains(cursor_pos):
                    return  # Don't rename when clicking + icon

        # Don't process test mode items
        layer_name = item.text(0)
        if layer_name.startswith("[TEST MODE]"):
            return

        # Store the original name before editing
        self.editing_layer_name = layer_name

        # Block signals while making item editable to avoid premature itemChanged trigger
        self.layer_tree.blockSignals(True)
        item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
        self.layer_tree.blockSignals(False)

        # Now start editing (column 0 = single column with name)
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
            # Trigger inline rename on column 0 (single column with name)
            self.on_layer_double_clicked(item, 0)

    def on_layer_renamed(self, item, column):
        """Handle layer rename after inline editing (single column layout)"""
        # Only process renames on column 0 (single column with name)
        if column != 0:
            return

        if rt is None or self.editing_layer_name is None:
            return

        try:
            # Get the new name from the item (column 0)
            new_name = item.text(0)
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
            rt.callbacks.addScript(rt.Name("layerParentChanged"), "EskiLayerManagerCallback()")

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

    def get_dock_widgets_in_area(self, dock_area):
        """
        Get all dock widgets in the specified dock area, sorted by vertical position
        Returns list of tuples: (widget, y_position, object_name)
        """
        parent = self.parent()
        if not parent or not isinstance(parent, QtWidgets.QMainWindow):
            return []

        widgets = []
        for widget in parent.findChildren(QtWidgets.QDockWidget):
            if widget == self:
                continue  # Skip ourselves

            # Check if widget is in the same dock area
            area = parent.dockWidgetArea(widget)
            if area == dock_area and not widget.isFloating():
                # Get vertical position
                y_pos = widget.geometry().y()
                obj_name = widget.objectName()
                widgets.append((widget, y_pos, obj_name))

        # Sort by vertical position
        widgets.sort(key=lambda x: x[1])
        return widgets

    def find_relative_position(self):
        """
        Find our position relative to other dock widgets
        Returns dict with: dock_area, above_widget_name, below_widget_name
        """
        parent = self.parent()
        if not parent or not isinstance(parent, QtWidgets.QMainWindow):
            return None

        if self.isFloating():
            return None  # Not applicable for floating widgets

        # Get our dock area
        dock_area = parent.dockWidgetArea(self)
        our_y = self.geometry().y()

        # Get all widgets in same area, sorted by Y position
        widgets = self.get_dock_widgets_in_area(dock_area)

        if not widgets:
            return {'dock_area': dock_area, 'above': None, 'below': None}

        # Find widgets immediately above and below us
        above_widget = None
        below_widget = None

        for widget, y_pos, obj_name in widgets:
            if y_pos < our_y:
                above_widget = obj_name  # Keep updating - we want the closest one
            elif y_pos > our_y and below_widget is None:
                below_widget = obj_name  # First one below us
                break

        return {
            'dock_area': dock_area,
            'above': above_widget,
            'below': below_widget
        }

    def save_position(self):
        """Save window position, size, docking state, and relative dock position"""
        if rt is None:
            return

        try:
            # Get current position and docking state
            is_floating = self.isFloating()
            pos = self.pos()
            size = self.size()

            # Determine dock area if docked
            dock_area = "none"
            relative_above = "none"
            relative_below = "none"

            if not is_floating:
                # Get parent main window to check dock area
                parent = self.parent()
                if parent and hasattr(parent, 'dockWidgetArea'):
                    area = parent.dockWidgetArea(self)
                    if area == QtCore.Qt.LeftDockWidgetArea:
                        dock_area = "left"
                    elif area == QtCore.Qt.RightDockWidgetArea:
                        dock_area = "right"

                # Find our relative position to other dock widgets
                rel_pos = self.find_relative_position()
                if rel_pos:
                    if rel_pos['above']:
                        relative_above = rel_pos['above']
                        print(f"[POSITION] We are below: {relative_above}")
                    if rel_pos['below']:
                        relative_below = rel_pos['below']
                        print(f"[POSITION] We are above: {relative_below}")

            # Format: floating;dock_area;x;y;width;height;relative_above;relative_below
            position_data = f"{is_floating};{dock_area};{pos.x()};{pos.y()};{size.width()};{size.height()};{relative_above};{relative_below}"

            # Save to current .max file using fileProperties
            # First, try to delete existing properties if they exist
            try:
                existing = rt.fileProperties.findProperty(rt.Name("custom"), "EskiLayerManagerPosition")
                if existing:
                    rt.fileProperties.deleteProperty(existing)
            except:
                pass  # Property doesn't exist yet

            # Add new property - addProperty signature: (#custom, name, value)
            rt.fileProperties.addProperty(rt.Name("custom"), "EskiLayerManagerPosition", position_data)

            print(f"[POSITION] Saved to .max file: floating={is_floating}, dock={dock_area}, pos=({pos.x()},{pos.y()}), size=({size.width()},{size.height()})")
        except Exception as e:
            print(f"[ERROR] save_position failed: {e}")
            import traceback
            traceback.print_exc()

    def get_saved_position(self):
        """
        Get saved position data from current .max file
        Returns dict with keys: floating, dock_area, x, y, width, height, dock_state
        Returns None if no saved position exists
        """
        if rt is None:
            return None

        try:
            # Load from current .max file using fileProperties
            # findProperty returns the index (1-based), not the property object
            prop_index = rt.fileProperties.findProperty(rt.Name("custom"), "EskiLayerManagerPosition")

            # If findProperty returns 0, property doesn't exist
            if not prop_index or prop_index == 0:
                print("[POSITION] No saved position found in .max file")
                return None

            # Get the actual property value using the index
            position_data = str(rt.fileProperties.getPropertyValue(rt.Name("custom"), prop_index))

            if not position_data or position_data == "":
                return None

            # Parse position data
            parts = position_data.split(";")

            # Support multiple formats for backwards compatibility
            if len(parts) == 8:
                # New format: floating;dock_area;x;y;width;height;relative_above;relative_below
                result = {
                    'floating': parts[0] == "True",
                    'dock_area': parts[1],
                    'x': int(parts[2]),
                    'y': int(parts[3]),
                    'width': int(parts[4]),
                    'height': int(parts[5]),
                    'relative_above': parts[6] if parts[6] != "none" else None,
                    'relative_below': parts[7] if parts[7] != "none" else None
                }
                print(f"[POSITION] Loaded: floating={result['floating']}, dock={result['dock_area']}, above={result['relative_above']}, below={result['relative_below']}")
                return result
            elif len(parts) == 6:
                # Old format: floating;dock_area;x;y;width;height
                result = {
                    'floating': parts[0] == "True",
                    'dock_area': parts[1],
                    'x': int(parts[2]),
                    'y': int(parts[3]),
                    'width': int(parts[4]),
                    'height': int(parts[5]),
                    'relative_above': None,
                    'relative_below': None
                }
                print(f"[POSITION] Loaded (old format): floating={result['floating']}, dock={result['dock_area']}")
                return result
            elif len(parts) == 5:
                # Very old format: floating;x;y;width;height (no dock_area)
                result = {
                    'floating': parts[0] == "True",
                    'dock_area': "none",
                    'x': int(parts[1]),
                    'y': int(parts[2]),
                    'width': int(parts[3]),
                    'height': int(parts[4]),
                    'relative_above': None,
                    'relative_below': None
                }
                print(f"[POSITION] Loaded (very old format): floating={result['floating']}")
                return result
            else:
                print(f"[POSITION] Invalid format in .max file: {position_data}")
                return None

        except Exception as e:
            print(f"[ERROR] get_saved_position failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    def closeEvent(self, event):
        """Handle close event"""
        print("[CLOSE] closeEvent triggered")

        # Stop sync timer
        if hasattr(self, 'sync_timer'):
            self.sync_timer.stop()
            print("[CLOSE] Sync timer stopped")

        # Save position before closing
        print("[CLOSE] Saving position...")
        self.save_position()
        print("[CLOSE] Position saved")

        # Remove callbacks
        self.remove_callbacks()

        # Clear the global instance reference
        global _layer_manager_instance
        _layer_manager_instance[0] = None
        print("[CLOSE] Instance reference cleared")

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
    Toggle the Eski Layer Manager window (Singleton pattern)
    - If window is open and visible: close it
    - If window is closed or hidden: show it
    Call this function from 3ds Max to launch the tool
    Only one instance can exist at a time.

    Returns:
        EskiLayerManager: The singleton instance of the layer manager (or None if closed)
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
            is_visible = _layer_manager_instance[0].isVisible()

            # If we get here, the widget is still valid
            if is_visible:
                # Window is visible - CLOSE it (toggle off)
                print("[TOGGLE] Window is visible, closing it")
                _layer_manager_instance[0].close()
                return None
            else:
                # Window exists but hidden - SHOW it (toggle on)
                print("[TOGGLE] Window exists but hidden, showing it")
                _layer_manager_instance[0].show()
                _layer_manager_instance[0].raise_()
                _layer_manager_instance[0].activateWindow()
                return _layer_manager_instance[0]

        except (RuntimeError, AttributeError):
            # Window was deleted, clear the reference and create new one
            print("[TOGGLE] Window was deleted, creating new one")
            _layer_manager_instance[0] = None

    # No valid instance exists, create a new one
    print("[TOGGLE] No existing window, creating new one")

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

    # Try to restore saved position
    saved_pos = layer_manager.get_saved_position()

    if saved_pos:
        # Restore from saved position
        print(f"[POSITION] Restoring saved position")

        if max_main_window:
            # First, add widget to main window (required before restoreState)
            if saved_pos['floating']:
                # Floating window - add as floating
                print(f"[POSITION] Restoring as FLOATING at ({saved_pos['x']}, {saved_pos['y']})")
                max_main_window.addDockWidget(QtCore.Qt.RightDockWidgetArea, layer_manager)
                layer_manager.setFloating(True)
                layer_manager.move(saved_pos['x'], saved_pos['y'])
            else:
                # Docked window - restore to correct dock area and relative position
                dock_area = QtCore.Qt.RightDockWidgetArea  # default
                if saved_pos['dock_area'] == 'left':
                    dock_area = QtCore.Qt.LeftDockWidgetArea
                    print(f"[POSITION] Restoring as DOCKED LEFT")
                elif saved_pos['dock_area'] == 'right':
                    dock_area = QtCore.Qt.RightDockWidgetArea
                    print(f"[POSITION] Restoring as DOCKED RIGHT")

                # Try to find a reference widget to split from
                reference_widget = None
                orientation = QtCore.Qt.Vertical  # Split vertically (stack vertically)

                # First, try to find the widget we were below (prefer "above" reference)
                if saved_pos.get('relative_above'):
                    print(f"[POSITION] Looking for reference widget: {saved_pos['relative_above']}")
                    for widget in max_main_window.findChildren(QtWidgets.QDockWidget):
                        if widget.objectName() == saved_pos['relative_above']:
                            area = max_main_window.dockWidgetArea(widget)
                            if area == dock_area and not widget.isFloating():
                                reference_widget = widget
                                print(f"[POSITION] Found reference widget (will split below it)")
                                break

                # If not found, try the widget we were above
                if not reference_widget and saved_pos.get('relative_below'):
                    print(f"[POSITION] Looking for reference widget: {saved_pos['relative_below']}")
                    for widget in max_main_window.findChildren(QtWidgets.QDockWidget):
                        if widget.objectName() == saved_pos['relative_below']:
                            area = max_main_window.dockWidgetArea(widget)
                            if area == dock_area and not widget.isFloating():
                                reference_widget = widget
                                print(f"[POSITION] Found reference widget (will split above it)")
                                break

                # Restore using reference widget if found
                if reference_widget:
                    print(f"[POSITION] Using splitDockWidget to restore relative position")
                    print(f"[POSITION] Reference widget Y: {reference_widget.geometry().y()}")

                    # Add to the area first
                    max_main_window.addDockWidget(dock_area, layer_manager)

                    # splitDockWidget(after, before, orientation)
                    # We want to place layer_manager relative to reference_widget
                    # If we were ABOVE the reference (saved relative_below), split so we appear first (top)
                    # If we were BELOW the reference (saved relative_above), split so we appear second (bottom)

                    if saved_pos.get('relative_above'):
                        # We were below the reference widget, so: reference THEN us
                        print(f"[POSITION] Splitting: reference widget THEN our widget (we're below)")
                        max_main_window.splitDockWidget(reference_widget, layer_manager, orientation)
                    else:
                        # We were above the reference widget, so: us THEN reference
                        print(f"[POSITION] Splitting: our widget THEN reference widget (we're above)")
                        max_main_window.splitDockWidget(layer_manager, reference_widget, orientation)

                    print(f"[POSITION] After split, our Y: {layer_manager.geometry().y()}")
                else:
                    print(f"[POSITION] No reference widget found, using default position")
                    max_main_window.addDockWidget(dock_area, layer_manager)

                print(f"[POSITION] setFloating(False) to ensure docked")
                layer_manager.setFloating(False)  # Explicitly ensure it stays docked

            # Restore size
            print(f"[POSITION] Resizing to {saved_pos['width']}x{saved_pos['height']}")
            layer_manager.resize(saved_pos['width'], saved_pos['height'])
        else:
            # No main window (testing mode) - just apply position
            layer_manager.move(saved_pos['x'], saved_pos['y'])
            layer_manager.resize(saved_pos['width'], saved_pos['height'])
    else:
        # No saved position - use default: floating and centered
        print("[POSITION] No saved position, using default: floating and centered")

        if max_main_window:
            # Add as floating widget
            max_main_window.addDockWidget(QtCore.Qt.RightDockWidgetArea, layer_manager)
            layer_manager.setFloating(True)

            # Center on screen
            screen = max_main_window.screen() if hasattr(max_main_window, 'screen') else None
            if screen:
                screen_geometry = screen.availableGeometry()
                x = (screen_geometry.width() - layer_manager.width()) // 2
                y = (screen_geometry.height() - layer_manager.height()) // 2
                layer_manager.move(x, y)
            else:
                # Fallback if screen geometry not available
                layer_manager.move(100, 100)

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
