import sys
from emion import Node
print("Importing PyQt5...")
from PyQt5.QtWidgets import QApplication, QWidget

def test_order_1():
    print("\n--- Test 1: Attach BEFORE QApplication ---")
    try:
        n = Node()
        n.attach()
        print("Attached successfully.")
        app = QApplication(sys.argv)
        print("QApplication created.")
        n.detach()
        print("Detached.")
    except Exception as e:
        print(f"FAILED: {e}")

def test_order_2():
    print("\n--- Test 2: Attach AFTER QApplication ---")
    try:
        app = QApplication(sys.argv)
        print("QApplication created.")
        n = Node()
        n.attach()
        print("Attached successfully.")
        n.detach()
        print("Detached.")
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    # test_order_1()
    test_order_2()
