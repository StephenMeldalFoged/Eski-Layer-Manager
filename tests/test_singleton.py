"""
Test script for verifying singleton pattern in Eski Layer Manager
Run this in 3ds Max Python console to test the singleton behavior

Usage:
    In 3ds Max Listener, run:
    python.ExecuteFile "E:\\Github\\Eski-Layer-Manager\\test_singleton.py"
"""

import sys
import os

# Add the script directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

# Import the module
import eski_layer_manager

print("\n" + "="*70)
print("SINGLETON PATTERN TEST FOR ESKI LAYER MANAGER")
print("="*70)

# Test 1: Check initial status
print("\n[TEST 1] Checking initial status...")
status = eski_layer_manager.get_instance_status()
print(f"Status: {status}")

# Test 2: Create first instance
print("\n[TEST 2] Creating first instance...")
instance1 = eski_layer_manager.show_layer_manager()
print(f"Instance 1 created: {instance1}")
status = eski_layer_manager.get_instance_status()
print(f"Status after creation: {status}")

# Test 3: Try to create second instance (should return same instance)
print("\n[TEST 3] Attempting to create second instance...")
print("This should return the SAME instance, not create a new one")
instance2 = eski_layer_manager.show_layer_manager()
print(f"Instance 2 'created': {instance2}")

# Test 4: Verify they are the same object
print("\n[TEST 4] Verifying singleton behavior...")
if instance1 is instance2:
    print("SUCCESS: Both references point to the SAME object (singleton working)")
    print(f"  instance1 id: {id(instance1)}")
    print(f"  instance2 id: {id(instance2)}")
else:
    print("FAILURE: Different objects created (singleton NOT working)")
    print(f"  instance1 id: {id(instance1)}")
    print(f"  instance2 id: {id(instance2)}")

# Test 5: Multiple calls
print("\n[TEST 5] Multiple rapid calls (should all return same instance)...")
for i in range(3):
    instance = eski_layer_manager.show_layer_manager()
    print(f"  Call {i+1}: id={id(instance)}, same={instance is instance1}")

# Test 6: Check instance list
print("\n[TEST 6] Checking internal instance list...")
print(f"Instance list: {eski_layer_manager._layer_manager_instance}")
print(f"Instance list[0]: {eski_layer_manager._layer_manager_instance[0]}")
print(f"Is same as instance1: {eski_layer_manager._layer_manager_instance[0] is instance1}")

print("\n" + "="*70)
print("TEST COMPLETE")
print("="*70)
print("\nInstructions:")
print("1. If all tests show SUCCESS, the singleton is working correctly")
print("2. Close the Layer Manager window and run this test again")
print("3. After closing, it should create a NEW instance")
print("4. Multiple calls while open should always return the SAME instance")
print("="*70 + "\n")
