import os
import sys


def main():
    os.environ.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")

    import pytest

    raise SystemExit(pytest.main(sys.argv[1:]))
