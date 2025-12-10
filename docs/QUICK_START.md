# Quick Start - Singleton Pattern Implementation

## What Changed?

The Eski Layer Manager now implements a **proper singleton pattern** to prevent multiple instances from being created.

## Installation

1. Run the installer script in 3ds Max:
   ```
   File → Run Script → install-Eski-Layer-Manager.ms
   ```

2. Click "Install / Upgrade to Latest Version"

3. Add the macro button to your toolbar (if not already there):
   - Press `Y` or go to: Customize → Customize User Interface
   - Find "Eski Tools" category
   - Drag "EskiLayerManager" to your toolbar

## Expected Behavior

### ✓ CORRECT (Singleton Working)

```
Click button #1 → Window opens
Click button #2 → Same window comes to front (no new window created)
Click button #3 → Same window comes to front (no new window created)
Close window
Click button #4 → New window opens (old one was closed)
```

### ✗ WRONG (If singleton was broken)

```
Click button #1 → Window opens
Click button #2 → SECOND window opens (duplicate)  ← This should NOT happen
```

## Testing

### Quick Test (Manual)
1. Click the macro button → Window appears
2. Click the macro button again → Same window activates (no duplicate)
3. Success! Singleton is working

### Automated Test
Run this in 3ds Max Listener:
```
python.ExecuteFile "E:\\Github\\Eski-Layer-Manager\\test_singleton.py"
```

Look for this output:
```
[TEST 4] Verifying singleton behavior...
SUCCESS: Both references point to the SAME object (singleton working)
```

## Console Debug Messages

When working correctly, you should see:

### First Launch
```
[INIT] Eski Layer Manager module initialized (version 0.3.4)
[DEBUG] show_layer_manager called, instance list: [None]
[DEBUG] No existing instance, will create new one
[DEBUG] Creating new EskiLayerManager instance
[DEBUG] New instance stored: <EskiLayerManager object at 0x...>
[DEBUG] Layer manager shown
```

### Second Launch (Same Session)
```
[INIT] Eski Layer Manager module already initialized, preserving instance: [<EskiLayerManager ...>]
[DEBUG] show_layer_manager called, instance list: [<EskiLayerManager ...>]
[DEBUG] Existing instance found: <EskiLayerManager object at 0x...>
[DEBUG] Instance is valid, bringing to front
```

## Key Points

1. **Only ONE instance exists** at any time
2. **Clicking the button** brings existing window to front
3. **Closing the window** allows creating a new one
4. **No memory leaks** - proper cleanup on close
5. **Fast performance** - <1ms to return existing instance

## Troubleshooting

If you see multiple windows:

1. **Check version:**
   ```python
   import eski_layer_manager
   print(eski_layer_manager.VERSION)  # Should be 0.3.4+
   ```

2. **Reinstall macro:**
   Run `install-Eski-Layer-Manager.ms` again

3. **Restart 3ds Max:**
   Close Max and reopen

4. **Run test script:**
   See the "Automated Test" section above

5. **Read full guide:**
   See `TROUBLESHOOTING.md` for detailed help

## Technical Details

For developers and technical users, see:
- `SINGLETON_IMPLEMENTATION.md` - Full technical documentation
- `SINGLETON_SOLUTION_SUMMARY.md` - Before/after comparison
- `TROUBLESHOOTING.md` - Common issues and solutions

## Files Overview

| File | Purpose |
|------|---------|
| `eski-layer-manager.py` | Main tool (with singleton) |
| `install-Eski-Layer-Manager.ms` | Installer/Upgrader |
| `test_singleton.py` | Automated test suite |
| `QUICK_START.md` | This file |
| `SINGLETON_IMPLEMENTATION.md` | Technical docs |
| `TROUBLESHOOTING.md` | User help guide |

## Support

Questions? Check the documentation files above or examine the debug console output when launching the tool.
