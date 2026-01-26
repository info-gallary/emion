import emion
from emion import Node, Endpoint

def test_api_existence():
    print("Testing API existence...")
    assert hasattr(emion, 'bp_open')
    assert hasattr(emion, 'bp_close')
    assert hasattr(emion, 'bp_receive')
    assert hasattr(Endpoint, 'receive')
    print("API exists.")

if __name__ == "__main__":
    test_api_existence()
