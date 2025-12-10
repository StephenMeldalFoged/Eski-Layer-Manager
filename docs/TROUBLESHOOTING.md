# Troubleshooting Guide - Eski Layer Manager

## Singleton Pattern Issues

### Problem: Multiple instances are being created

**Symptoms:**
- Clicking the macro button creates multiple windows
- Multiple dock widgets appear in the Max interface
- Console shows "Creating new instance" every time

**Solutions:**

1. **Verify you're using the latest version**
   ```python
   import eski_layer_manager
   print(eski_layer_manager.VERSION)  # Should be 0.3.4 or higher
   ```

2. **Check if the module is being reloaded**
   Look for these messages in the console:
   ```
   [INIT] Eski Layer Manager module already initialized, preserving instance
   ```
   If you see `[INIT] Eski Layer Manager module initialized` multiple times, the module is being reloaded.

3. **Run the singleton test**
   ```
   python.ExecuteFile "E:\\Github\\Eski-Layer-Manager\\test_singleton.py"
   ```

4. **Reinstall the macro**
   - Run `install-Eski-Layer-Manager.ms`
   - Choose "Install / Upgrade to Latest Version"
   - This ensures the macro uses the correct import pattern

5. **Restart 3ds Max**
   If the problem persists, restart Max to clear the Python interpreter state.

### Problem: Instance appears to be None even when window is open

**Symptoms:**
- Window is visible but `get_instance_status()` shows `exists: False`
- Console shows "No existing instance, will create new one" when window is already open

**Solutions:**

1. **Check for C++ object deletion**
   The C++ widget might have been destroyed. Close all instances and create a new one.

2. **Verify global variable state**
   ```python
   import eski_layer_manager
   print(eski_layer_manager._layer_manager_instance)
   ```
   Should show: `[<EskiLayerManager object at 0x...>]` when window is open
   Should show: `[None]` when window is closed

3. **Look for exceptions**
   Check the Max Listener for RuntimeError or AttributeError messages.

### Problem: Window won't close properly

**Symptoms:**
- Closing the window doesn't clear the instance
- Next opening shows stale data
- Close button doesn't respond

**Solutions:**

1. **Force close and clear**
   ```python
   import eski_layer_manager
   if eski_layer_manager._layer_manager_instance[0]:
       eski_layer_manager._layer_manager_instance[0].close()
       eski_layer_manager._layer_manager_instance[0] = None
   ```

2. **Check WA_DeleteOnClose attribute**
   This should be set in the `__init__` method (line 53).

### Problem: Module won't import

**Symptoms:**
- Error: "Cannot find eski-layer-manager.py"
- Import fails in Max Python console

**Solutions:**

1. **Verify file location**
   ```maxscript
   print (getDir #userScripts)
   ```
   The file `eski_layer_manager.py` must be in this directory.

2. **Check Python path**
   ```python
   import sys
   scripts_dir = "C:\\Users\\YourName\\AppData\\Local\\Autodesk\\3dsMax\\2026 - 64bit\\ENU\\scripts\\python"
   if scripts_dir not in sys.path:
       sys.path.insert(0, scripts_dir)
   ```

3. **Verify file permissions**
   Ensure the `.py` file is readable and not blocked by Windows.

## Debug Commands

### Check Current Status
```python
import eski_layer_manager
status = eski_layer_manager.get_instance_status()
print(status)
```

### Force New Instance (for testing only)
```python
import eski_layer_manager
# Clear existing instance
eski_layer_manager._layer_manager_instance[0] = None
# Create new one
instance = eski_layer_manager.show_layer_manager()
```

### Check Module Initialization State
```python
import eski_layer_manager
print(f"Initialized: {eski_layer_manager._ESKI_LAYER_MANAGER_INITIALIZED}")
print(f"Instance: {eski_layer_manager._layer_manager_instance}")
```

### Verify Object Identity
```python
import eski_layer_manager
instance1 = eski_layer_manager.show_layer_manager()
instance2 = eski_layer_manager.show_layer_manager()
print(f"Same object: {instance1 is instance2}")
print(f"Instance 1 ID: {id(instance1)}")
print(f"Instance 2 ID: {id(instance2)}")
```

## Common Error Messages

### RuntimeError: wrapped C/C++ object has been deleted
**Cause:** The Qt C++ object was destroyed but Python still has a reference.

**Solution:** The singleton implementation handles this automatically by catching the error and creating a new instance. If you see this repeatedly, restart Max.

### AttributeError: 'NoneType' object has no attribute 'isVisible'
**Cause:** Instance was None when the code tried to check it.

**Solution:** This should be prevented by the defensive checks in the code. If you see this, please report it as a bug.

### ImportError: No module named 'eski_layer_manager'
**Cause:** The Python file is not in the scripts directory or path is incorrect.

**Solution:**
1. Run the installer: `install-Eski-Layer-Manager.ms`
2. Verify file location: Should be in `getDir #userScripts`
3. Check for typos: File must be named exactly `eski_layer_manager.py` (underscore, not hyphen)

## Getting Help

If none of these solutions work:

1. Run the test script and save the output:
   ```
   python.ExecuteFile "E:\\Github\\Eski-Layer-Manager\\test_singleton.py"
   ```

2. Check the Max Listener for all debug messages

3. Collect this information:
   - 3ds Max version
   - Python version (run `python.Execute "import sys; print(sys.version)"`)
   - Module version (run `import eski_layer_manager; print(eski_layer_manager.VERSION)`)
   - Complete error messages
   - Steps to reproduce

4. Report the issue with all the above information

## Performance Tips

- The singleton pattern is very fast (<1ms for returning existing instance)
- First launch takes ~50ms to build UI
- Multiple rapid clicks are handled efficiently
- No memory leaks - only one instance exists at a time

## Best Practices

1. **Don't reload the module manually**
   Avoid using `importlib.reload()` - it breaks the singleton pattern

2. **Use the macro button**
   The macro is configured to work with the singleton pattern

3. **Close properly**
   Use the window close button or `instance.close()` - don't force kill

4. **One instance at a time**
   This is enforced automatically, but don't try to work around it

5. **Restart Max for clean state**
   If developing or debugging, restart Max to clear all Python state
