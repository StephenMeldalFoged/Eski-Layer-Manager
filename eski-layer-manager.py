"""
Eski LayerManager by Claude
A dockable layer and object manager for 3ds Max

Version: 0.24.2 (2026-01-05)
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


VERSION = "0.24.2 (2026-01-05)"
VERSION_DISPLAY_DURATION = 10000  # Show version for 10 seconds before tips

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
        self.icon_size = 14  # Compact size to save vertical space
        self.icon_spacing = 3
        self.plus_icon_size = 14  # Match main icon size for consistency
        self.plus_icon_spacing = 3  # Compact spacing

    def _get_visual_row_number(self, index, tree_widget):
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
                if tree_widget.isExpanded(sibling):
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
                if tree_widget.isExpanded(child_idx):
                    count_children(child_idx)

        count_rows_before(index)
        return count

    def paint(self, painter, option, index):
        """Custom paint method for rendering inline icons"""
        painter.save()

        # Determine which tree widget this index belongs to
        item = self.layer_manager.layer_tree.itemFromIndex(index)
        if item:
            tree_widget = self.layer_manager.layer_tree
        else:
            item = self.layer_manager.objects_tree.itemFromIndex(index)
            tree_widget = self.layer_manager.objects_tree

        if not item:
            painter.restore()
            return

        # Calculate visual row number (counting all visible rows from top)
        visual_row = self._get_visual_row_number(index, tree_widget)

        # Check if this item is being hovered
        # Safely check if hovered item is still valid (not deleted)
        is_hovered = False
        if hasattr(tree_widget, '_hovered_item') and tree_widget._hovered_item is not None:
            try:
                # Try to access the item - will raise RuntimeError if deleted
                is_hovered = (tree_widget._hovered_item == item)
            except RuntimeError:
                # Item was deleted, clear the reference
                tree_widget._hovered_item = None

        # Check if item has custom background (e.g., drag highlight)
        custom_bg = item.background(0)
        if custom_bg.color().alpha() > 0:
            # Use custom background (drag highlight)
            painter.fillRect(option.rect, custom_bg)
        else:
            # Draw background (alternating rows) - NO full row selection highlight
            # NOTE: Hover highlight will be drawn LATER, after active layer highlight
            if visual_row % 2:
                painter.fillRect(option.rect, option.palette.alternateBase())
            else:
                painter.fillRect(option.rect, option.palette.base())

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

        # Check if this item is selected (active layer) - draw highlight EARLY, before everything
        is_selected = option.state & QtWidgets.QStyle.State_Selected
        if is_selected:
            # Draw active layer highlight UNDER everything (after background, before icons/text)
            # This ensures the text remains readable and not affected by transparency
            # Full row highlight from left edge to right edge
            highlight_rect = QtCore.QRect(option.rect.left(), y, option.rect.width(), h)
            highlight_color = QtGui.QColor(0, 100, 100, 120)  # Darker teal with alpha
            painter.fillRect(highlight_rect, highlight_color)

        # Draw hover highlight AFTER active layer highlight (so it shows on top)
        if is_hovered:
            # Draw hover overlay on top of everything so far
            hover_rect = QtCore.QRect(option.rect.left(), y, option.rect.width(), h)
            hover_color = QtGui.QColor(0, 140, 140, 80)  # Brighter teal with lower alpha so it layers nicely
            painter.fillRect(hover_rect, hover_color)

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

        # 3. Draw layer name
        layer_name = item.text(0)

        # Calculate text width
        font_metrics = QtGui.QFontMetrics(option.font)
        text_width = font_metrics.horizontalAdvance(layer_name)

        # Create rects for rendering and click detection
        name_rect = QtCore.QRect(x, y, option.rect.right() - x, h)  # Full clickable area
        item.click_regions['name'] = name_rect

        # Set text color (same for all layers)
        painter.setPen(option.palette.text().color())

        painter.setFont(option.font)
        # Draw text at the same position
        text_rect = QtCore.QRect(x, y, text_width + 12, h)
        painter.drawText(text_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, layer_name)

        # 4. Draw green dot indicator if layer contains selected objects (right-aligned)
        # Only draw in layer tree, not objects tree
        if tree_widget == self.layer_manager.layer_tree and layer_name in self.layer_manager.layers_with_selection:
            # Green dot size
            dot_size = 6
            dot_margin = 8  # Distance from right edge

            # Position on the right side
            dot_x = option.rect.right() - dot_margin - dot_size
            dot_y = y + (h - dot_size) // 2  # Center vertically

            # Draw green circle
            painter.setBrush(QtGui.QColor(0, 255, 0))  # Bright green
            painter.setPen(QtCore.Qt.NoPen)  # No outline
            painter.drawEllipse(dot_x, dot_y, dot_size, dot_size)

        painter.restore()

    def createEditor(self, parent, option, index):
        """Create editor widget for inline editing"""
        editor = QtWidgets.QLineEdit(parent)
        return editor

    def setEditorData(self, editor, index):
        """Set initial text in editor"""
        value = index.data(QtCore.Qt.DisplayRole)
        editor.setText(value)

    def setModelData(self, editor, model, index):
        """Save edited text back to model"""
        model.setData(index, editor.text(), QtCore.Qt.EditRole)

    def setEditorGeometry(self, editor, option, index):
        """Position editor at the correct location where layer name is painted"""
        # Calculate X offset to match where layer name is painted
        x_offset = 0

        # Get the item to check for icons
        item = self.layer_manager.layer_tree.itemFromIndex(index)
        if item:
            # Add offset for visibility icon if present
            vis_icon = item.data(0, QtCore.Qt.UserRole + 1)
            if vis_icon:
                x_offset += self.icon_size + self.icon_spacing

            # Add offset for add selection icon if present
            add_icon = item.data(0, QtCore.Qt.UserRole + 2)
            if add_icon:
                x_offset += self.plus_icon_spacing + self.plus_icon_size + self.icon_spacing

        # Position editor at the calculated offset
        editor_rect = QtCore.QRect(
            option.rect.left() + x_offset,
            option.rect.top(),
            option.rect.width() - x_offset,
            option.rect.height()
        )
        editor.setGeometry(editor_rect)


class CustomTreeWidget(QtWidgets.QTreeWidget):
    """Custom QTreeWidget that only allows selection on column 3"""

    def __init__(self, parent=None):
        super(CustomTreeWidget, self).__init__(parent)
        self.layer_manager = None  # Will be set by EskiLayerManager

        # Enable drops from external sources (like Scene Explorer)
        self.setAcceptDrops(True)

        # Track highlighted item during drag operations
        self._drag_highlight_item = None

        # Track hovered item for hover highlighting
        self._hovered_item = None

        # Enable mouse tracking to get mouseMoveEvent without button press
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

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

    def mouseMoveEvent(self, event):
        """Track which item the mouse is hovering over"""
        item = self.itemAt(event.pos())

        # Only update if hover changed
        if item != self._hovered_item:
            old_hovered = self._hovered_item
            self._hovered_item = item

            # Repaint old hovered item (if still valid)
            if old_hovered:
                try:
                    index = self.indexFromItem(old_hovered)
                    if index.isValid():
                        rect = self.visualRect(index)
                        self.viewport().update(rect)
                except RuntimeError:
                    # Old item was deleted, ignore
                    pass

            # Repaint new hovered item
            if self._hovered_item:
                index = self.indexFromItem(self._hovered_item)
                if index.isValid():
                    rect = self.visualRect(index)
                    self.viewport().update(rect)

        # Call parent implementation
        super(CustomTreeWidget, self).mouseMoveEvent(event)

    def leaveEvent(self, event):
        """Clear hover highlight when mouse leaves the widget"""
        if self._hovered_item:
            old_hovered = self._hovered_item
            self._hovered_item = None

            # Repaint the item that was hovered (if still valid)
            try:
                index = self.indexFromItem(old_hovered)
                if index.isValid():
                    rect = self.visualRect(index)
                    self.viewport().update(rect)
            except RuntimeError:
                # Item was already deleted, ignore
                pass

        # Call parent implementation
        super(CustomTreeWidget, self).leaveEvent(event)

    def dragEnterEvent(self, event):
        """Accept drag events from external sources (Scene Explorer) and internal sources"""
        # Accept all drag events - we'll filter in dropEvent
        event.acceptProposedAction()

    def dragMoveEvent(self, event):
        """Accept drag move events and highlight target item"""
        event.acceptProposedAction()

        # Get the item under the cursor
        target_item = self.itemAt(event.pos())

        # Clear previous highlight
        if self._drag_highlight_item and self._drag_highlight_item != target_item:
            self._clear_drag_highlight(self._drag_highlight_item)

        # Highlight new target
        if target_item:
            self._set_drag_highlight(target_item)
            self._drag_highlight_item = target_item

    def _set_drag_highlight(self, item):
        """Set visual highlight on drop target"""
        if item:
            # Use a bright teal+green highlight color for maximum visibility
            item.setBackground(0, QtGui.QColor(0, 220, 180, 200))  # Bright teal-green with high alpha
            # Only repaint the specific item rect for better performance
            index = self.indexFromItem(item)
            if index.isValid():
                rect = self.visualRect(index)
                self.viewport().update(rect)

    def _clear_drag_highlight(self, item):
        """Clear visual highlight from item"""
        if item:
            # Reset to transparent (let alternating row colors show through)
            item.setBackground(0, QtGui.QColor(0, 0, 0, 0))
            # Only repaint the specific item rect for better performance
            index = self.indexFromItem(item)
            if index.isValid():
                rect = self.visualRect(index)
                self.viewport().update(rect)

    def dragLeaveEvent(self, event):
        """Clear highlight when drag leaves the widget"""
        if self._drag_highlight_item:
            self._clear_drag_highlight(self._drag_highlight_item)
            self._drag_highlight_item = None
        super(CustomTreeWidget, self).dragLeaveEvent(event)

    def dropEvent(self, event):
        """Handle drop event to reparent layers, reassign objects, or accept external drops from Scene Explorer"""

        # Clear drag highlight at start of drop
        if self._drag_highlight_item:
            self._clear_drag_highlight(self._drag_highlight_item)
            self._drag_highlight_item = None

        # Check if this is a drag from the objects tree
        source_widget = event.source()

        # Handle external drops (from Scene Explorer or other Qt widgets outside our app)
        if source_widget is None or (source_widget != self and source_widget != getattr(self.layer_manager, 'objects_tree', None)):

            # Get target layer
            target_item = self.itemAt(event.pos())
            if not target_item:
                event.ignore()
                return

            target_layer_name = target_item.text(0)

            # Try to get the currently selected objects in 3ds Max
            # When user drags from Scene Explorer, those objects should be selected
            if rt and self.layer_manager:
                try:
                    selection = rt.selection
                    if len(selection) > 0:
                        object_names = [str(obj.name) for obj in selection]
                        self.layer_manager.reassign_objects_to_layer(object_names, target_layer_name)
                        event.accept()
                        return
                    else:
                        pass  # No objects selected
                except Exception as e:
                    print(f"[DROP ERROR] Failed to get selection: {e}")

            event.ignore()
            return

        # If dragging from objects tree TO layer tree (reassign layer)
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

        # Track which layer is currently displayed in the objects tree
        self.current_objects_layer = None

        # Track visibility states for sync detection {layer_name: is_hidden}
        self.last_visibility_states = {}

        # Track layers that contain selected objects (for green dot indicator)
        self.layers_with_selection = set()

        # Track isolation state for undo functionality
        self.isolation_state = None  # Stores {layer_name: is_hidden} before isolation
        self.isolated_layer = None  # Name of currently isolated layer

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

        # Setup tips rotation
        self.tips = [
            "Tip: Ctrl+Click the eye icon to isolate a layer",
            "Tip: Drag layers onto each other to create parent-child relationships",
            "Tip: Double-click a layer name to rename it",
            "Tip: Right-click for quick access to layer operations",
            "Tip: Drag objects from the Objects panel to reassign to different layers",
            "Tip: Click the + icon to quickly add selected objects to a layer",
            "Tip: Use the Objects toggle button to show/hide the objects panel",
            "Tip: Ctrl+Click an isolated layer's eye icon again to restore visibility",
            "Tip: Drag from 3ds Max Scene Explorer directly into layers",
            "Tip: Click a layer name to make it the active layer in 3ds Max",
            "Tip: Use the + button at the top to create a new layer",
            "Tip: Select a layer and click the delete button to remove it",
            "Tip: Click the refresh button to reload layers from 3ds Max",
            "Tip: Right-click empty space in the layer tree to create a new root layer",
            "Tip: Ctrl+Click objects in the Objects panel for multi-selection",
            "Tip: Click an object in the Objects panel to select it in the viewport",
            "Tip: Drag the window to the left or right edge to dock it",
            "Tip: Window position is saved per scene file automatically",
            "Tip: The green progress bar shows when operations are running",
            "Tip: Hidden parent layers make child layers inherit the hidden state",
            "Tip: Drag a layer above/below another to make them siblings",
            "Tip: Drag a layer to empty space to move it to the root level",
            "Tip: Click the arrow next to a layer to expand/collapse children",
            "Tip: The active layer name is highlighted in teal color",
            "Tip: Layers highlight in bright teal when dragging objects over them",
            "Tip: Click the status bar to skip to the next tip instantly",
            "Tip: Hover over the status bar to pause tip rotation and read",
            "Tip: Alternating row colors help distinguish between layers",
            "Tip: Use parent-child relationships to organize complex scenes",
            "Tip: Right-click the status bar to view all tips at once"
        ]
        self.current_tip_index = 0
        self.tip_timer = QtCore.QTimer(self)
        self.tip_timer.timeout.connect(self.rotate_tip)

        # Show version number first for 10 seconds, then start tips
        self.status_label.setText(f"Eski Layer Manager v{VERSION}")
        QtCore.QTimer.singleShot(VERSION_DISPLAY_DURATION, self.start_tip_rotation)

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
                padding: 0px;
                height: 16px;
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

        # Set compact icon size to save vertical space
        self.layer_tree.setIconSize(QtCore.QSize(14, 14))

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
        self.bottom_widget = QtWidgets.QWidget()
        bottom_layout = QtWidgets.QVBoxLayout(self.bottom_widget)
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
                height: 16px;
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
        self.splitter.addWidget(self.bottom_widget)

        # Set initial sizes (60% top, 40% bottom)
        self.splitter.setSizes([240, 160])

        # Hide objects panel by default (Objects button starts unchecked)
        self.bottom_widget.hide()

        # Add splitter to main layout
        main_layout.addWidget(self.splitter)

        # Add status bar at the very bottom (spanning full width)
        self.status_label = QtWidgets.QLabel(f"Version {VERSION}")
        self.status_label.setFixedHeight(18)
        self.status_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.status_label.setCursor(QtCore.Qt.PointingHandCursor)  # Show pointer cursor
        self.status_label.setStyleSheet("""
            QLabel {
                padding: 2px 5px;
                color: #aaaaaa;
                background-color: #2a2a2a;
                font-size: 10px;
                border-top: 1px solid #3a3a3a;
            }
            QLabel:hover {
                background-color: #3a3a3a;
                color: #ffffff;
            }
        """)
        self.status_label.mousePressEvent = self.on_status_clicked
        self.status_label.enterEvent = self.on_status_hover_enter
        self.status_label.leaveEvent = self.on_status_hover_leave
        self.status_label.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.status_label.customContextMenuRequested.connect(self.show_all_tips_window)
        main_layout.addWidget(self.status_label)

        # Set minimum size
        self.setMinimumSize(250, 150)  # Minimum width 250, minimum height 150

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

        # Add spacer to push the Objects toggle button to the right
        button_layout.addStretch()

        # Add Objects toggle button
        self.objects_toggle_btn = QtWidgets.QPushButton("Objects")
        self.objects_toggle_btn.setCheckable(True)  # Makes it a toggle button
        self.objects_toggle_btn.setChecked(False)  # Start unchecked (objects hidden by default)
        self.objects_toggle_btn.setToolTip("Toggle Objects Panel")
        self.objects_toggle_btn.clicked.connect(self.on_objects_toggle)
        self.objects_toggle_btn.setFixedHeight(32)  # Match other button height
        self.objects_toggle_btn.setMinimumWidth(70)  # Minimum width for text

        button_layout.addWidget(self.objects_toggle_btn)

        # Add Export button
        self.export_btn = QtWidgets.QPushButton("Export")
        self.export_btn.setToolTip("Export (Coming Soon)")
        self.export_btn.clicked.connect(self.on_export_click)
        self.export_btn.setFixedHeight(32)  # Match other button height
        self.export_btn.setMinimumWidth(70)  # Minimum width for text

        button_layout.addWidget(self.export_btn)

        top_layout.insertLayout(0, button_layout)

        # Add progress bar (1 pixel tall, green, full width) below buttons
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setFixedHeight(1)  # 1 pixel tall
        self.progress_bar.setTextVisible(False)  # No text
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)  # Start at 0
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: transparent;
            }
            QProgressBar::chunk {
                background-color: #00ff00;  /* Green */
            }
        """)
        top_layout.insertWidget(1, self.progress_bar)

        # Populate layers from 3ds Max
        self.populate_layers()

    def populate_layers(self):
        """Populate the layer list with layers from 3ds Max, including hierarchy"""
        # Temporarily disconnect itemChanged signal to avoid triggering rename during population
        try:
            self.layer_tree.itemChanged.disconnect(self.on_layer_renamed)
        except:
            pass

        # Save expanded state before clearing
        expanded_layers = self._save_expanded_state()

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

            # Collect all layers first
            all_layers = []
            for i in range(layer_count):
                layer = layer_manager.getLayer(i)
                if layer:
                    all_layers.append(layer)

            # Separate into root layers and child layers
            root_layers = []
            for layer in all_layers:
                try:
                    parent = layer.getParent()
                    # Check if parent is undefined/None (root layer)
                    if parent is None or str(parent) == "undefined":
                        root_layers.append(layer)
                    else:
                        pass  # Has parent, will be added as child later
                except:
                    # If getParent fails, assume it's a root layer
                    root_layers.append(layer)

            # Sort root layers alphabetically
            root_layers.sort(key=lambda x: str(x.name).lower())

            # Add root layers and their children recursively
            for layer in root_layers:
                self._add_layer_to_tree(layer, None)

            # Restore expanded state after populating
            self._restore_expanded_state(expanded_layers)

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
                    pass  # Children will be added recursively
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
                    # Check if parent exists (not rt.undefined)
                    if parent_layer != rt.undefined and parent_layer is not None:
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
                # Don't expand by default - will be handled by _restore_expanded_state()
                # (First time opening, all layers will be expanded by default)

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
        """Populate the objects tree with objects from the specified layer (flat list)"""
        # Show progress start
        self.progress_bar.setValue(30)

        self.objects_tree.clear()

        # Track which layer we're currently displaying
        self.current_objects_layer = layer_name

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
            # Complete progress
            self.progress_bar.setValue(100)
            QtCore.QTimer.singleShot(200, lambda: self.progress_bar.setValue(0))
            return

        try:
            # Find the layer
            layer = self._find_layer_by_name(layer_name)
            if not layer:
                self.progress_bar.setValue(0)
                return

            # Get all objects in the scene
            all_nodes = rt.objects

            self.progress_bar.setValue(50)

            # Filter objects that belong to this layer
            layer_objects = []
            for node in all_nodes:
                try:
                    if hasattr(node, 'layer') and node.layer and str(node.layer.name) == layer_name:
                        layer_objects.append(node)
                except:
                    pass

            self.progress_bar.setValue(70)

            # Sort objects by name
            layer_objects.sort(key=lambda x: str(x.name).lower())

            # Add each object to the tree (flat list)
            for obj in layer_objects:
                try:
                    obj_name = str(obj.name)
                    item = QtWidgets.QTreeWidgetItem(self.objects_tree, [obj_name])
                    # No icons for objects - just the name

                except Exception as e:
                    print(f"[ERROR] Failed to add object to tree: {e}")

            self.progress_bar.setValue(90)

            # Complete progress
            self.progress_bar.setValue(100)
            QtCore.QTimer.singleShot(200, lambda: self.progress_bar.setValue(0))

        except Exception as e:
            print(f"[ERROR] populate_objects failed: {e}")
            import traceback
            traceback.print_exc()
            # Reset progress on error
            self.progress_bar.setValue(0)

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

                found = find_and_select()
                if found:
                    # Force viewport repaint to show highlight
                    self.layer_tree.viewport().update()

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

            # Get the visual rect for this item to get current Y position (accounting for scroll)
            index = self.layer_tree.indexFromItem(item)
            visual_rect = self.layer_tree.visualRect(index)

            # Check if item has click regions (set by delegate during last paint)
            if hasattr(item, 'click_regions') and hasattr(item, 'current_item_y'):
                # Adjust click regions to current visual position (in case of scrolling)
                # The stored regions use the Y from paint time, we need current Y
                y_offset = visual_rect.y() - item.current_item_y

                # Check which region was clicked
                # (Skip arrow - Qt's built-in tree arrows handle expand/collapse)
                if 'visibility' in item.click_regions:
                    vis_rect = item.click_regions['visibility'].translated(0, y_offset)
                    if vis_rect.contains(cursor_pos):
                        # Check if Ctrl is pressed for isolate mode
                        modifiers = QtWidgets.QApplication.keyboardModifiers()
                        if modifiers & QtCore.Qt.ControlModifier:
                            # Ctrl+Click on eye = Isolate layer (hide all others)
                            self.isolate_layer(layer_name)
                        else:
                            # Normal click = Toggle visibility only
                            self.toggle_layer_visibility(item, layer_name)
                        return

                if 'add_selection' in item.click_regions:
                    add_rect = item.click_regions['add_selection'].translated(0, y_offset)
                    if add_rect.contains(cursor_pos):
                        # Add selected objects to this layer
                        self.add_selection_to_layer(layer_name)
                        return

                if 'name' in item.click_regions:
                    name_rect = item.click_regions['name'].translated(0, y_offset)
                    if name_rect.contains(cursor_pos):
                        # Set as current layer (selection already handled by CustomTreeWidget)
                        self.set_current_layer(layer_name)
                        # Populate objects tree with objects from this layer
                        self.populate_objects(layer_name)
                        return
            else:
                pass  # No click_regions found

            # Fallback - if no regions matched, treat as name click
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
                    if parent_layer != rt.undefined and parent_layer is not None:
                        parent_hidden = parent_layer.ishidden
                    else:
                        parent_hidden = False  # No parent
                except Exception as e:
                    parent_hidden = False  # Error checking parent

                # If parent is hidden, don't allow toggling (child follows parent)
                if parent_hidden:
                    return

                # Show progress
                self.progress_bar.setValue(30)

                # Get the new visibility state (toggled)
                new_hidden_state = not layer.ishidden

                # Toggle visibility - set the layer hidden state
                layer.ishidden = new_hidden_state

                self.progress_bar.setValue(50)

                # Also hide/unhide all objects on this layer in the viewport
                # This ensures objects actually disappear/appear in the scene
                try:
                    if layer.nodes:
                        for node in layer.nodes:
                            node.isHidden = new_hidden_state
                except Exception as e:
                    print(f"[ERROR] Failed to hide/unhide objects: {e}")

                self.progress_bar.setValue(70)

                # Update our internal tracking BEFORE updating UI to prevent sync timer from reverting
                self.last_visibility_states[layer_name] = new_hidden_state

                # Update icon in UserRole+1 (native if available, Unicode fallback otherwise)
                if self.use_native_icons:
                    item.setData(0, QtCore.Qt.UserRole + 1, self.icon_hidden if new_hidden_state else self.icon_visible)
                else:
                    new_icon_text = "✖" if new_hidden_state else "👁"
                    item.setData(0, QtCore.Qt.UserRole + 1, new_icon_text)

                # Trigger repaint
                self.layer_tree.update(self.layer_tree.indexFromItem(item))

                # If this layer has children, update their icons too (they inherit hidden state)
                self._update_child_layer_icons(item, new_hidden_state)

                self.progress_bar.setValue(85)

                # Force complete viewport refresh to show/hide objects immediately
                rt.execute("redrawViews #all")
                rt.completeRedraw()

                # Complete progress
                self.progress_bar.setValue(100)

                # Reset progress after short delay
                QtCore.QTimer.singleShot(200, lambda: self.progress_bar.setValue(0))

        except Exception as e:
            import traceback
            error_msg = f"Error toggling layer visibility: {str(e)}\n{traceback.format_exc()}"
            print(f"[ERROR] {error_msg}")

    def _update_child_layer_icons(self, parent_item, parent_is_hidden):
        """Recursively update icons for all child layers when parent visibility changes"""
        if not parent_item:
            return

        # Iterate through all children
        for i in range(parent_item.childCount()):
            child_item = parent_item.child(i)
            child_layer_name = child_item.text(0)

            try:
                # Get the actual layer from 3ds Max
                child_layer = self._find_layer_by_name(child_layer_name)
                if not child_layer:
                    continue

                # Determine which icon to use
                if parent_is_hidden:
                    # Parent is hidden - use lock/disabled icon
                    if self.use_native_icons and self.icon_hidden_light:
                        child_item.setData(0, QtCore.Qt.UserRole + 1, self.icon_hidden_light)
                    else:
                        child_item.setData(0, QtCore.Qt.UserRole + 1, "🔒")
                else:
                    # Parent is visible - show child's own visibility state
                    child_is_hidden = child_layer.ishidden
                    if self.use_native_icons:
                        icon = self.icon_hidden if child_is_hidden else self.icon_visible
                        child_item.setData(0, QtCore.Qt.UserRole + 1, icon)
                    else:
                        icon_text = "✖" if child_is_hidden else "👁"
                        child_item.setData(0, QtCore.Qt.UserRole + 1, icon_text)

                # Trigger repaint
                self.layer_tree.update(self.layer_tree.indexFromItem(child_item))

                # Recursively update grandchildren
                self._update_child_layer_icons(child_item, parent_is_hidden)

            except Exception as e:
                print(f"[ERROR] Failed to update child icon for '{child_layer_name}': {e}")

    def _save_expanded_state(self):
        """Save the expanded/collapsed state of all layers before refresh"""
        expanded_layers = set()

        def save_recursive(parent_item):
            """Recursively save expanded state for all items"""
            for i in range(parent_item.childCount()):
                item = parent_item.child(i)
                layer_name = item.text(0)
                if item.isExpanded():
                    expanded_layers.add(layer_name)
                # Recursively check children
                save_recursive(item)

        # Save root items
        for i in range(self.layer_tree.topLevelItemCount()):
            item = self.layer_tree.topLevelItem(i)
            layer_name = item.text(0)
            if item.isExpanded():
                expanded_layers.add(layer_name)
            save_recursive(item)

        return expanded_layers

    def _restore_expanded_state(self, expanded_layers):
        """Restore the expanded/collapsed state of all layers after refresh"""
        # If this is the first time (no saved state), expand all by default
        if not hasattr(self, '_has_saved_state') or not self._has_saved_state:
            self._has_saved_state = True
            # Expand all layers on first load
            self.layer_tree.expandAll()
            return

        def restore_recursive(parent_item):
            """Recursively restore expanded state for all items"""
            for i in range(parent_item.childCount()):
                item = parent_item.child(i)
                layer_name = item.text(0)
                # Set expanded state based on saved state
                if layer_name in expanded_layers:
                    item.setExpanded(True)
                else:
                    item.setExpanded(False)
                # Recursively restore children
                restore_recursive(item)

        # Restore root items
        for i in range(self.layer_tree.topLevelItemCount()):
            item = self.layer_tree.topLevelItem(i)
            layer_name = item.text(0)
            if layer_name in expanded_layers:
                item.setExpanded(True)
            else:
                item.setExpanded(False)
            restore_recursive(item)

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

    def _find_tree_item_by_name(self, layer_name):
        """Recursively search for a tree item by layer name"""
        def search_recursive(parent_item):
            """Recursively search children"""
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                if child.text(0) == layer_name:  # Column 0 in single column layout
                    return child
                # Search this child's children
                result = search_recursive(child)
                if result:
                    return result
            return None

        # Search top-level items first
        for i in range(self.layer_tree.topLevelItemCount()):
            item = self.layer_tree.topLevelItem(i)
            if item.text(0) == layer_name:
                return item
            # Search children
            result = search_recursive(item)
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
                return

            # Find the target layer (search recursively for nested layers)
            target_layer = self._find_layer_by_name(layer_name)

            if target_layer:
                object_count = len(selected_objects)

                # Show progress start
                self.progress_bar.setValue(30)

                # Only use performance optimization for 10+ objects
                if object_count >= 10:
                    try:
                        # Disable scene redraw for many objects
                        rt.disableSceneRedraw()
                        self.progress_bar.setValue(50)

                        # Batch assign - use MAXScript with quiet mode to suppress listener output
                        rt.execute(f"""
                        with quiet on
                        (
                            local targetLayer = layerManager.getLayerFromName "{layer_name}"
                            for obj in selection do targetLayer.addNode obj
                        )
                        """)

                        self.progress_bar.setValue(80)

                    finally:
                        # Always re-enable scene redraw
                        rt.enableSceneRedraw()
                else:
                    # For small number of objects, just do it normally
                    for obj in selected_objects:
                        target_layer.addNode(obj)
                    self.progress_bar.setValue(80)

                # Complete refresh
                rt.execute("redrawViews #all")
                rt.completeRedraw()

                # Complete progress
                self.progress_bar.setValue(100)
                QtCore.QTimer.singleShot(200, lambda: self.progress_bar.setValue(0))
            else:
                print(f"[ERROR] Layer '{layer_name}' not found")

        except Exception as e:
            import traceback
            error_msg = f"Error adding selection to layer: {str(e)}\n{traceback.format_exc()}"
            print(f"[ERROR] {error_msg}")
            # Make sure to re-enable scene redraw if we crashed mid-operation
            try:
                rt.enableSceneRedraw()
            except:
                pass

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

            # Only use performance optimization for 10+ objects
            if len(object_names) >= 10:
                try:
                    # Disable scene redraw for performance with many objects
                    rt.disableSceneRedraw()

                    # Find and reassign each object
                    success_count = 0
                    failed_objects = []
                    for obj_name in object_names:
                        try:
                            # Get object by name from 3ds Max
                            obj = rt.getNodeByName(obj_name)
                            if obj:
                                # Assign to new layer
                                target_layer.addNode(obj)
                                success_count += 1
                            else:
                                failed_objects.append(obj_name)
                        except Exception as e:
                            failed_objects.append(obj_name)

                finally:
                    # Always re-enable scene redraw
                    rt.enableSceneRedraw()
            else:
                # For small number of objects, just do it normally
                success_count = 0
                failed_objects = []
                for obj_name in object_names:
                    try:
                        # Get object by name from 3ds Max
                        obj = rt.getNodeByName(obj_name)
                        if obj:
                            # Assign to new layer
                            target_layer.addNode(obj)
                            success_count += 1
                        else:
                            failed_objects.append(obj_name)
                    except Exception as e:
                        failed_objects.append(obj_name)

            # Refresh the objects tree to show updated list
            # Refresh the currently displayed layer (where objects were dragged from)
            if self.current_objects_layer:
                self.populate_objects(self.current_objects_layer)

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
                new_layer_name = str(new_layer.name)

            # Refresh the layer list to show the new layer
            self.populate_layers()

            # Find the newly created layer in the tree and enter rename mode
            # Use a timer to delay editing until after the tree is fully updated
            if new_layer:
                def start_rename():
                    item = self._find_tree_item_by_name(new_layer_name)
                    if item:
                        # Select the item
                        self.layer_tree.setCurrentItem(item)
                        # Scroll to make it visible
                        self.layer_tree.scrollToItem(item)
                        # Store the original name before editing (required for on_layer_renamed to work)
                        self.editing_layer_name = new_layer_name
                        # Set the editable flag (required for editItem to work)
                        self.layer_tree.blockSignals(True)
                        item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
                        self.layer_tree.blockSignals(False)
                        # Enter edit mode (column 0 is the single column with all content)
                        self.layer_tree.editItem(item, 0)

                # Delay by 100ms to ensure tree is fully populated and painted
                QtCore.QTimer.singleShot(100, start_rename)

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
        layer_name = selected_item.text(0)  # Column 0 in single column layout

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

    def on_objects_toggle(self):
        """Handle Objects toggle button click - show/hide objects panel"""
        is_checked = self.objects_toggle_btn.isChecked()

        if is_checked:
            # Show objects panel
            self.bottom_widget.show()
        else:
            # Hide objects panel
            self.bottom_widget.hide()

    def on_export_click(self):
        """Handle Export button click - placeholder for future export functionality"""
        # TODO: Implement export functionality
        pass

    def delete_layer(self, layer_name):
        """Delete a layer by name"""
        if rt is None:
            return

        try:
            layer = self._find_layer_by_name(layer_name)
            if not layer:
                print(f"[ERROR] Layer '{layer_name}' not found")
                return

            # Check if layer has objects
            node_count = len(layer.nodes) if layer.nodes else 0
            if node_count > 0:
                print(f"[ERROR] Cannot delete layer '{layer_name}' - it contains {node_count} object(s)")
                return

            # Delete the layer
            rt.layerManager.deleteLayerByName(layer_name)
            self.populate_layers()

        except Exception as e:
            print(f"[ERROR] Failed to delete layer: {e}")

    def duplicate_layer(self, layer_name):
        """Duplicate a layer (create a copy with same properties)"""
        if rt is None:
            return

        try:
            source_layer = self._find_layer_by_name(layer_name)
            if not source_layer:
                print(f"[ERROR] Layer '{layer_name}' not found")
                return

            # Create new layer
            new_layer = rt.layerManager.newLayer()
            new_layer.setName(f"{layer_name}_copy")

            # Copy properties
            new_layer.wireColor = source_layer.wireColor
            new_layer.ishidden = source_layer.ishidden
            new_layer.isfrozen = source_layer.isfrozen

            # Set parent if source has parent
            parent = source_layer.getParent()
            if parent and parent != rt.undefined:
                new_layer.setParent(parent)

            self.populate_layers()

        except Exception as e:
            print(f"[ERROR] Failed to duplicate layer: {e}")

    def select_layer_objects(self, layer_name):
        """Select all objects in the specified layer"""
        if rt is None:
            return

        try:
            layer = self._find_layer_by_name(layer_name)
            if not layer:
                print(f"[ERROR] Layer '{layer_name}' not found")
                return

            # Select all objects on this layer
            if layer.nodes:
                rt.select(layer.nodes)

        except Exception as e:
            print(f"[ERROR] Failed to select layer objects: {e}")

    def isolate_layer(self, layer_name):
        """Toggle isolation: Hide all layers except specified one, or restore previous state"""
        if rt is None:
            return

        try:
            layer_manager = rt.LayerManager
            layer_count = layer_manager.count

            # Check if we're already isolating this layer
            if self.isolated_layer == layer_name and self.isolation_state is not None:
                # Restore previous visibility state
                for i in range(layer_count):
                    layer = layer_manager.getLayer(i)
                    if layer.name in self.isolation_state:
                        layer.ishidden = self.isolation_state[layer.name]

                # Clear isolation state
                self.isolation_state = None
                self.isolated_layer = None
            else:
                # Save current visibility state before isolating
                self.isolation_state = {}
                for i in range(layer_count):
                    layer = layer_manager.getLayer(i)
                    self.isolation_state[layer.name] = layer.ishidden

                # Isolate the target layer
                for i in range(layer_count):
                    layer = layer_manager.getLayer(i)
                    if layer.name == layer_name:
                        layer.ishidden = False
                    else:
                        layer.ishidden = True

                # Track which layer is isolated
                self.isolated_layer = layer_name

            self.populate_layers()

        except Exception as e:
            print(f"[ERROR] Failed to isolate/restore layer: {e}")

    def toggle_layer_freeze(self, layer_name):
        """Toggle freeze state of a layer"""
        if rt is None:
            return

        try:
            layer = self._find_layer_by_name(layer_name)
            if not layer:
                print(f"[ERROR] Layer '{layer_name}' not found")
                return

            # Toggle freeze state
            layer.isfrozen = not layer.isfrozen
            self.populate_layers()

        except Exception as e:
            print(f"[ERROR] Failed to toggle layer freeze: {e}")

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
        """Handle right-click context menu - show Qt context menu"""
        if rt is None:
            return

        item = self.layer_tree.itemAt(position)

        # Create Qt context menu
        menu = QtWidgets.QMenu(self)

        # Disable menu animations for instant response
        menu.setAttribute(QtCore.Qt.WA_NoSystemBackground, False)
        menu.setWindowFlags(menu.windowFlags() | QtCore.Qt.FramelessWindowHint | QtCore.Qt.NoDropShadowWindowHint)

        # Set style for instant highlighting (no fade/animation)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b2b;
                border: 1px solid #555;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 25px 6px 10px;
                background-color: transparent;
            }
            QMenu::item:selected {
                background-color: #0078d4;
                color: white;
            }
            QMenu::separator {
                height: 1px;
                background: #555;
                margin: 4px 0px;
            }
        """)

        # Check if clicked on empty area or on a layer
        if item is None:
            # Empty area - show simple menu
            new_layer_action = menu.addAction("New Layer...")
            new_layer_action.triggered.connect(self.create_new_layer)
        else:
            # Clicked on a layer - show full layer menu
            layer_name = item.text(0)

            # Don't show menu for test mode items
            if layer_name.startswith("[TEST MODE]"):
                return

            # Get layer object
            layer = rt.LayerManager.getLayerFromName(layer_name)
            if not layer:
                return

            # Rename action
            rename_action = menu.addAction("Rename Layer")
            rename_action.triggered.connect(lambda: self.on_layer_double_clicked(item, 0))

            # Delete action
            delete_action = menu.addAction("Delete Layer")
            delete_action.triggered.connect(lambda: self.delete_layer(layer_name))

            # Duplicate action
            duplicate_action = menu.addAction("Duplicate Layer")
            duplicate_action.triggered.connect(lambda: self.duplicate_layer(layer_name))

            menu.addSeparator()

            # New layer action
            new_layer_action = menu.addAction("New Layer...")
            new_layer_action.triggered.connect(self.create_new_layer)

            menu.addSeparator()

            # Select objects action
            select_action = menu.addAction("Select Objects in Layer")
            select_action.triggered.connect(lambda: self.select_layer_objects(layer_name))

            # Isolate action
            isolate_action = menu.addAction("Isolate Layer")
            isolate_action.triggered.connect(lambda: self.isolate_layer(layer_name))

            menu.addSeparator()

            # Toggle visibility action
            if layer.ishidden:
                show_action = menu.addAction("Show Layer")
                show_action.triggered.connect(lambda: self.toggle_layer_visibility(layer_name))
            else:
                hide_action = menu.addAction("Hide Layer")
                hide_action.triggered.connect(lambda: self.toggle_layer_visibility(layer_name))

            # Toggle freeze action
            if layer.isfrozen:
                unfreeze_action = menu.addAction("Unfreeze Layer")
                unfreeze_action.triggered.connect(lambda: self.toggle_layer_freeze(layer_name))
            else:
                freeze_action = menu.addAction("Freeze Layer")
                freeze_action.triggered.connect(lambda: self.toggle_layer_freeze(layer_name))

        # Show menu at cursor position
        menu.exec_(self.layer_tree.viewport().mapToGlobal(position))

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

    def start_tip_rotation(self):
        """Start the tip rotation timer and show first tip"""
        self.tip_timer.start(12000)  # 12 seconds
        self.rotate_tip()  # Show first tip immediately

    def rotate_tip(self):
        """Rotate to the next tip in the status bar"""
        if hasattr(self, 'status_label') and hasattr(self, 'tips'):
            self.status_label.setText(self.tips[self.current_tip_index])
            self.current_tip_index = (self.current_tip_index + 1) % len(self.tips)

    def on_status_clicked(self, event):
        """Handle click on status bar to skip to next tip"""
        self.rotate_tip()

    def on_status_hover_enter(self, event):
        """Handle mouse entering status bar - pause timer"""
        if hasattr(self, 'tip_timer'):
            self.tip_timer.stop()

    def on_status_hover_leave(self, event):
        """Handle mouse leaving status bar - restart timer from 0"""
        if hasattr(self, 'tip_timer'):
            self.tip_timer.start(12000)  # Reset and restart timer

    def show_all_tips_window(self):
        """Show a window with all tips when right-clicking status bar"""
        if not hasattr(self, 'tips'):
            return

        # Create dialog window
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Eski Layer Manager - All Tips & Tricks")
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(500)

        # Create layout
        layout = QtWidgets.QVBoxLayout(dialog)

        # Add header label
        header = QtWidgets.QLabel(f"All Tips & Tricks ({len(self.tips)} total)")
        header.setStyleSheet("font-weight: bold; font-size: 12px; padding: 5px;")
        layout.addWidget(header)

        # Create text browser for tips
        text_browser = QtWidgets.QTextBrowser()
        text_browser.setOpenExternalLinks(False)
        text_browser.setStyleSheet("""
            QTextBrowser {
                background-color: #2a2a2a;
                color: #cccccc;
                border: 1px solid #3a3a3a;
                padding: 10px;
                font-size: 11px;
                line-height: 1.6;
            }
        """)

        # Format all tips as HTML with numbering
        tips_html = "<html><body>"
        for i, tip in enumerate(self.tips, 1):
            # Remove "Tip: " prefix for cleaner display
            tip_text = tip.replace("Tip: ", "")
            tips_html += f"<p><b>{i}.</b> {tip_text}</p>"
        tips_html += "</body></html>"

        text_browser.setHtml(tips_html)
        layout.addWidget(text_browser)

        # Add close button
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(dialog.close)
        close_btn.setFixedHeight(32)
        layout.addWidget(close_btn)

        # Show the dialog (non-modal so user can still interact with main window)
        dialog.show()

    def _update_layer_icon_recursive(self, parent_item, layer_name, is_hidden):
        """Recursively search tree and update icon for matching layer"""
        for i in range(parent_item.childCount()):
            item = parent_item.child(i)
            if item.text(0) == layer_name:  # Single column - layer name in column 0
                # Check if this layer's parent is hidden
                parent_is_hidden = False
                parent_tree_item = item.parent()

                # If this item has a parent in the tree (not root), check if parent layer is hidden
                if parent_tree_item and parent_tree_item != self.layer_tree.invisibleRootItem():
                    try:
                        # Get the layer from 3ds Max
                        layer = self._find_layer_by_name(layer_name)
                        if layer:
                            parent_layer = layer.getParent()
                            if parent_layer != rt.undefined and parent_layer is not None:
                                parent_is_hidden = parent_layer.ishidden
                    except:
                        pass

                # Update icon based on parent state
                if parent_is_hidden:
                    # Parent is hidden - use lock/disabled icon
                    if self.use_native_icons and self.icon_hidden_light:
                        item.setData(0, QtCore.Qt.UserRole + 1, self.icon_hidden_light)
                    else:
                        item.setData(0, QtCore.Qt.UserRole + 1, "🔒")
                else:
                    # Parent is visible - use normal icon based on layer's own state
                    if self.use_native_icons:
                        item.setData(0, QtCore.Qt.UserRole + 1, self.icon_hidden if is_hidden else self.icon_visible)
                    else:
                        new_icon_text = "✖" if is_hidden else "👁"
                        item.setData(0, QtCore.Qt.UserRole + 1, new_icon_text)

                # Trigger repaint
                self.layer_tree.update(self.layer_tree.indexFromItem(item))
                return True
            # Recursively check children
            if self._update_layer_icon_recursive(item, layer_name, is_hidden):
                return True
        return False

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
                        self.last_visibility_states[layer_name] = is_hidden
                        visibility_changed = True

                        # Update the icon in the tree (single column layout - column 0)
                        self._update_layer_icon_recursive(self.layer_tree.invisibleRootItem(), layer_name, is_hidden)

            # Check which layers contain selected objects
            self.update_selection_indicators()

        except Exception as e:
            # Silently fail - this runs frequently so don't spam errors
            pass

    def update_selection_indicators(self):
        """Update which layers contain selected objects (for green dot indicators)"""
        if rt is None:
            return

        try:
            # Get currently selected objects
            selection = rt.selection

            # Build set of layer names that contain selected objects
            new_layers_with_selection = set()

            # For each selected object, find which layer it belongs to
            for obj in selection:
                try:
                    # Direct approach: get the layer property from the object
                    obj_layer = obj.layer
                    if obj_layer:
                        layer_name = str(obj_layer.name)
                        new_layers_with_selection.add(layer_name)
                except:
                    pass  # Silently skip objects without layers

            # Only update if the set changed
            if new_layers_with_selection != self.layers_with_selection:
                self.layers_with_selection = new_layers_with_selection
                # Trigger repaint of the entire tree to update indicators
                self.layer_tree.viewport().update()

        except:
            pass  # Silently fail

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

global EskiLayerManagerSelectionCallback
fn EskiLayerManagerSelectionCallback = (
    python.Execute "import eski_layer_manager; eski_layer_manager.update_selection_from_callback()"
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

            # Register callback for selection changes (update green dot indicators)
            rt.callbacks.addScript(rt.Name("selectionSetChanged"), "EskiLayerManagerSelectionCallback()")

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
                    if rel_pos['below']:
                        relative_below = rel_pos['below']

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
                return result
            else:
                return None

        except Exception as e:
            print(f"[ERROR] get_saved_position failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    def closeEvent(self, event):
        """Handle close event"""

        # Stop sync timer
        if hasattr(self, 'sync_timer'):
            self.sync_timer.stop()

        # Stop tip rotation timer
        if hasattr(self, 'tip_timer'):
            self.tip_timer.stop()

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
        except (RuntimeError, AttributeError):
            # Widget was deleted
            _layer_manager_instance[0] = None


def update_selection_from_callback():
    """
    Called by selectionSetChanged callback when the user selects/deselects objects
    Updates the green dot indicators without full refresh
    """
    global _layer_manager_instance

    if _layer_manager_instance[0] is not None:
        try:
            # Check if widget is still valid
            _layer_manager_instance[0].isVisible()
            # Update selection indicators (green dots)
            _layer_manager_instance[0].update_selection_indicators()
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
                _layer_manager_instance[0].close()
                return None
            else:
                # Window exists but hidden - SHOW it (toggle on)
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

    # Try to restore saved position
    saved_pos = layer_manager.get_saved_position()

    if saved_pos:
        # Restore from saved position
        if max_main_window:
            # First, add widget to main window (required before restoreState)
            if saved_pos['floating']:
                # Floating window - add as floating
                max_main_window.addDockWidget(QtCore.Qt.RightDockWidgetArea, layer_manager)
                layer_manager.setFloating(True)
                layer_manager.move(saved_pos['x'], saved_pos['y'])
            else:
                # Docked window - restore to correct dock area and relative position
                dock_area = QtCore.Qt.RightDockWidgetArea  # default
                if saved_pos['dock_area'] == 'left':
                    dock_area = QtCore.Qt.LeftDockWidgetArea
                elif saved_pos['dock_area'] == 'right':
                    dock_area = QtCore.Qt.RightDockWidgetArea

                # Try to find a reference widget to split from
                reference_widget = None
                orientation = QtCore.Qt.Vertical  # Split vertically (stack vertically)

                # First, try to find the widget we were below (prefer "above" reference)
                if saved_pos.get('relative_above'):
                    for widget in max_main_window.findChildren(QtWidgets.QDockWidget):
                        if widget.objectName() == saved_pos['relative_above']:
                            area = max_main_window.dockWidgetArea(widget)
                            if area == dock_area and not widget.isFloating():
                                reference_widget = widget
                                break

                # If not found, try the widget we were above
                if not reference_widget and saved_pos.get('relative_below'):
                    for widget in max_main_window.findChildren(QtWidgets.QDockWidget):
                        if widget.objectName() == saved_pos['relative_below']:
                            area = max_main_window.dockWidgetArea(widget)
                            if area == dock_area and not widget.isFloating():
                                reference_widget = widget
                                break

                # Restore using reference widget if found
                if reference_widget:

                    # Add to the area first
                    max_main_window.addDockWidget(dock_area, layer_manager)

                    # splitDockWidget(after, before, orientation)
                    # We want to place layer_manager relative to reference_widget
                    # If we were ABOVE the reference (saved relative_below), split so we appear first (top)
                    # If we were BELOW the reference (saved relative_above), split so we appear second (bottom)

                    if saved_pos.get('relative_above'):
                        # We were below the reference widget, so: reference THEN us
                        max_main_window.splitDockWidget(reference_widget, layer_manager, orientation)
                    else:
                        # We were above the reference widget, so: us THEN reference
                        max_main_window.splitDockWidget(layer_manager, reference_widget, orientation)

                else:
                    max_main_window.addDockWidget(dock_area, layer_manager)

                layer_manager.setFloating(False)  # Explicitly ensure it stays docked

            # Restore size
            layer_manager.resize(saved_pos['width'], saved_pos['height'])
        else:
            # No main window (testing mode) - just apply position
            layer_manager.move(saved_pos['x'], saved_pos['y'])
            layer_manager.resize(saved_pos['width'], saved_pos['height'])
    else:
        # No saved position - use default: floating and centered

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
