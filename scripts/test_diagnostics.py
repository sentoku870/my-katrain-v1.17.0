
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from katrain.core.diagnostics import collect_system_info

def test_hardware_info():
    print("Collecting system info...")
    try:
        info = collect_system_info()
        print(f"OS: {info.os_name} {info.os_release}")
        print(f"CPU: {info.processor}")
        print(f"RAM: {info.ram_total}")
        print(f"GPU: {info.gpu_info}")
        print("Success!")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_hardware_info()
