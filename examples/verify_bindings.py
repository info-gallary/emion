import emion
import pytest

def test_version():
    print(f"Version: {emion.c_version()}")
    assert "ION wrapper" in emion.c_version()

def test_attach_fail_without_config():
    # Expect failure because ION is not running
    try:
        emion.ion_attach()
    except RuntimeError as e:
        print(f"Caught expected error: {e}")
        assert "Failed to attach" in str(e)
    except Exception as e:
        pytest.fail(f"Unexpected error: {e}")

if __name__ == "__main__":
    test_version()
    test_attach_fail_without_config()

    from emion import Node
    try:
        with Node() as node:
            print("Attached via Node context manager")
            # This should fail if ION not running, but `ion_attach` might succeed if just attaching to shared mem that doesn't exist? 
            # Actually weak error checking in my C code? No, ionAttach returns < 0.
            # So `Node()` enter will verify attach failure.
            pass
    except RuntimeError as e:
         print(f"Caught expected Node attach error: {e}")

    # Verify CGR functions exist (even if not callable without ION attach)
    assert hasattr(emion, "add_contact")
    assert hasattr(emion, "add_range")
    print("CGR functions verified.")
