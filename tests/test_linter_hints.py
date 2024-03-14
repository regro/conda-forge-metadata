from conda_forge_metadata.linter import get_hints


def test_get_hints():
    hints = get_hints()
    assert "jpeg" in hints.keys()
    assert "abseil-cpp" in hints.keys()
    assert "matplotlib" in hints.keys()
