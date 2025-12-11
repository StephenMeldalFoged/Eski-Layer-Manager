# Quad Menu Research for 3ds Max 2026

## Executive Summary

**CRITICAL FINDING:** The `menuMan` interface used for creating and showing quad menus **is completely deprecated** in 3ds Max 2025 and 2026. All previous methods like `menuMan.createQuadMenu()`, `menuMan.findQuadMenu()`, and `popUpContextMenu()` **DO NOT WORK** in these versions.

## The Menu System Revolution (3ds Max 2025+)

### What Changed

3ds Max 2025 introduced a **complete rewrite** of the menu system:

- **Old System (2024 and earlier):** `menuMan` interface with imperative API
- **New System (2025/2026):** `CuiMenuManager` and `CuiQuadMenuManager` with callback-based registration

The new system uses a **delta-based approach** that stores only differences from default menus, making customizations portable across versions.

**Source:** [New 3dsMax 2025 Menu System - Changsoo Eun](https://cganimator.com/new-3dsmax-2025-menu-system-and-how-to-transfer-ui-customization-to-a-new-version/)

## How Quad Menus Work in 3ds Max 2026

### Key Concept: Callback Registration

You **CANNOT** dynamically show a quad menu whenever you want. Instead, you must:

1. **Register a callback** during 3ds Max startup
2. The callback is triggered by specific events (keyboard modifiers + right-click)
3. The callback **builds** the menu structure at that moment
4. 3ds Max displays the menu automatically

### Registration Process

```maxscript
-- Register callback for quad menu creation
callbacks.addScript #cuiRegisterQuadMenus "myQuadMenuCallback()"

-- Callback function that builds the menu
fn myQuadMenuCallback =
(
    -- Get the CuiQuadMenuManager from maxOps
    local quadMenuMgr = maxOps.CuiQuadMenuMgr

    -- Get a specific context (e.g., viewport right-click with modifiers)
    local context = quadMenuMgr.GetContextById "QuadMenuContext.VP.Ctrl+Shift"

    -- Build the menu structure
    local myMenu = context.CreateSubMenu "My Custom Menu"
    myMenu.CreateAction "MyMacroScript" "My Category"

    -- Set which modifier keys trigger this menu
    context.SetRightClickModifiers #(#shift, #control)
)
```

**Source:** [The Menu System - 3ds Max 2025](https://help.autodesk.com/cloudhelp/2025/ENU/MAXScript-Help/files/MAXScript-Tools-and-Interaction/Interacting-with-the-3ds-Max/GUID-FF48D0EC-6669-4EC7-AB43-E9998A14A198.html)

### Important Interfaces (3ds Max 2026)

- **`maxOps.CuiQuadMenuMgr`** - Main interface for quad menu management (available since 3ds Max 2025)
- **`CuiQuadMenuManager`** - Manages all quad menu contexts
- **`CuiMenu`** - Individual menu object with `CreateSubMenu()`, `CreateAction()`, `CreateSeparator()`
- **`CuiActionMenu`** - Submenu container
- **`CuiMenuItem`** - Individual menu items

**Source:** [Interface: maxOps - 3ds Max 2026](https://help.autodesk.com/cloudhelp/2026/ENU/MAXScript-Help/files/3ds-Max-Objects-and-Interfaces/Interfaces/Core-Interfaces/Core-Interfaces-Documentation/M/GUID-48C5E2F2-DE34-4EA3-A84C-4DBD463DBF90.html)

## What You CANNOT Do Anymore

### ❌ Deprecated/Removed in 3ds Max 2026

- `menuMan.createQuadMenu()` - NO LONGER EXISTS
- `menuMan.findQuadMenu()` - NO LONGER EXISTS
- `menuMan.registerQuadMenu()` - NO LONGER EXISTS
- `popUpContextMenu()` - NO LONGER EXISTS
- Dynamic on-demand quad menu display - NOT SUPPORTED

### Why Our Previous Attempts Failed

All our attempts to show a quad menu failed because we were trying to:

1. Find existing quad menus with `menuMan.findQuadMenu()` - **menuMan doesn't exist**
2. Call `popUpContextMenu()` - **function doesn't exist**
3. Dynamically show menus on Qt widget right-click - **not how the new system works**

## Alternative Solutions for Layer Manager

### Option 1: Use Qt Context Menu (RECOMMENDED)

Since we're building a Qt-based UI, we should use Qt's native context menu system:

```python
def on_layer_context_menu(self, position):
    """Show Qt context menu"""
    menu = QtWidgets.QMenu(self)

    # Get layer name
    item = self.layer_tree.itemAt(position)
    layer_name = item.text(0)

    # Add actions
    rename_action = menu.addAction("Rename Layer")
    delete_action = menu.addAction("Delete Layer")
    properties_action = menu.addAction("Layer Properties...")

    # Connect actions
    rename_action.triggered.connect(lambda: self.rename_layer(layer_name))
    delete_action.triggered.connect(lambda: self.delete_layer(layer_name))
    properties_action.triggered.connect(lambda: self.show_properties(layer_name))

    # Show menu at cursor
    menu.exec_(self.layer_tree.viewport().mapToGlobal(position))
```

**Advantages:**
- ✅ Works immediately, no registration needed
- ✅ Full control over menu appearance and behavior
- ✅ Integrates seamlessly with Qt UI
- ✅ Can show menu whenever we want
- ✅ Can dynamically build menu based on context

**Disadvantages:**
- ❌ Not editable in 3ds Max Customize UI
- ❌ Separate from native 3ds Max menus
- ❌ Not accessible via 3ds Max hotkeys

### Option 2: Register Startup Callback (NOT RECOMMENDED)

Register a callback that triggers only with specific keyboard modifiers:

```maxscript
-- In startup script
callbacks.addScript #cuiRegisterQuadMenus "eskiLayerMenuCallback()"

fn eskiLayerMenuCallback =
(
    local quadMgr = maxOps.CuiQuadMenuMgr
    -- Must define context with specific modifier keys
    -- Can ONLY show with those modifiers, not on-demand
)
```

**Disadvantages:**
- ❌ Requires startup script modification
- ❌ Only triggers with specific keyboard modifiers (e.g., Ctrl+Shift+Right-click)
- ❌ Cannot trigger from Python/Qt widget clicks
- ❌ Complex callback setup
- ❌ Cannot dynamically show on regular right-click

### Option 3: Hybrid Approach

Use Qt menu as primary, but register macroScripts that can be added to native quad menus:

```maxscript
-- Register macroScript actions
macroScript EskiLayerManager_RenameLayer
    category:"Eski Layer Manager"
    buttonText:"Rename Layer"
(
    -- Action code
)
```

Users can manually add these actions to their preferred quad menus via Customize UI.

**Advantages:**
- ✅ Qt menu works out of the box
- ✅ Advanced users can customize 3ds Max menus
- ✅ Actions available in Customize UI

**Disadvantages:**
- ❌ Requires manual user setup for 3ds Max integration
- ❌ Two separate menu systems

## Recommended Implementation

**Use Qt's native context menu system** (Option 1). This gives us:

1. **Full control** - Show menu whenever we want
2. **Dynamic content** - Build menu based on layer state
3. **Qt integration** - Seamless with our existing UI
4. **No compatibility issues** - Doesn't depend on 3ds Max menu APIs

The native 3ds Max quad menu system in 2026 is designed for **global application menus**, not for custom Qt widget context menus. Trying to force it to work with our layer tree is fighting against the architecture.

## New Features in 3ds Max 2026

### CuiDynamicMenu Enhancements

- **AddItem()** now accepts icon and tooltip arguments
- **AddMacroScriptAction()** convenience function for adding macroScripts
- **CuiMenu.CreateMacroScriptAction()** for easier macroScript integration

**Source:** [What's New in MAXScript - 3ds Max 2026](https://help.autodesk.com/cloudhelp/2026/ENU/MAXScript-Help/files/What-is-New-in-MAXScript/What-s-New-in-MAXScript-in-3ds.html)

## Migration Notes

### If You Had Old menuMan Code

Old code like this **will not work**:

```maxscript
-- ❌ BROKEN in 3ds Max 2026
quadMenu = menuMan.createQuadMenu "MyQuad" "Menu1" "Menu2" "Menu3" "Menu4"
menuMan.registerQuadMenu quadMenu
menuMan.setViewportRightClickMenu #someModifier quadMenu
popUpContextMenu quadMenu
```

Must be rewritten to:

```maxscript
-- ✅ 3ds Max 2026 approach
callbacks.addScript #cuiRegisterQuadMenus "myQuadCallback()"

fn myQuadCallback =
(
    local mgr = maxOps.CuiQuadMenuMgr
    local ctx = mgr.GetContextById "QuadMenuContext.VP.Ctrl"
    local menu = ctx.CreateSubMenu "My Menu"
    -- Build menu structure
    ctx.SetRightClickModifiers #(#control)
)
```

## Additional Resources

### Official Documentation
- [The Menu System - 3ds Max 2025](https://help.autodesk.com/cloudhelp/2025/ENU/MAXScript-Help/files/MAXScript-Tools-and-Interaction/Interacting-with-the-3ds-Max/GUID-FF48D0EC-6669-4EC7-AB43-E9998A14A198.html)
- [Interface: maxOps - 3ds Max 2026](https://help.autodesk.com/cloudhelp/2026/ENU/MAXScript-Help/files/3ds-Max-Objects-and-Interfaces/Interfaces/Core-Interfaces/Core-Interfaces-Documentation/M/GUID-48C5E2F2-DE34-4EA3-A84C-4DBD463DBF90.html)
- [3ds Max 2026 Developer Help - Quad Menu](https://help.autodesk.com/view/MAXDEV/2026/ENU/?guid=GUID-C5835D80-FE88-459C-BD84-6C7817500627)
- [Menu Migration Guide - 3ds Max 2026](https://help.autodesk.com/view/MAXDEV/2026/ENU/?guid=menu_migration_guide)

### Community Resources
- [menuMan in 3ds Max 2025 - ScriptSpot](https://www.scriptspot.com/forums/3ds-max/general-scripting/menuman-in-3ds-max-2025)
- [Unable to assign new quad menu - Tech-Artists.Org](https://www.tech-artists.org/t/3ds-max-maxscript-unable-to-assign-new-quad-menu-to-right-click-entry/10417)
- [New 3dsMax 2025 Menu System - Changsoo Eun](https://cganimator.com/new-3dsmax-2025-menu-system-and-how-to-transfer-ui-customization-to-a-new-version/)

## Conclusion

For the Eski Layer Manager, **we should use Qt's native context menu system**. Attempting to integrate with 3ds Max's quad menu system is:

1. **Architecturally wrong** - Quad menus are for global viewport contexts, not widget-specific menus
2. **Technically complex** - Requires startup callbacks and modifier key triggers
3. **Functionally limited** - Cannot show on-demand from Qt widgets
4. **Unnecessary** - Qt menus provide everything we need

The quad menu system in 3ds Max 2026 is powerful for creating **application-level menus** that appear in specific contexts (viewport, modifier panel, etc.), but it's not designed for custom Qt widget context menus.
