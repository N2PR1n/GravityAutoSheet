import sys
import os
import ctypes.util

print(f"Python: {sys.executable}")
print(f"CWD: {os.getcwd()}")

try:
    from pyzbar.pyzbar import decode
    print("✅ pyzbar imported successfully")
except ImportError as e:
    print(f"❌ ImportError: {e}")
except Exception as e:
    print(f"❌ Error: {e}")

# Check for library
lib_path = ctypes.util.find_library('zbar')
print(f"find_library('zbar'): {lib_path}")

if not lib_path:
    # Try looking in common brew spots
    possible_paths = [
        "/opt/homebrew/lib/libzbar.dylib",
        "/usr/local/lib/libzbar.dylib"
    ]
    for p in possible_paths:
        print(f"Checking {p}: {os.path.exists(p)}")
