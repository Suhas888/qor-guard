"""Entry point: python -I -B qorguard.py <capture|baseline|compare> ...  (see qorguard/cli.py)"""
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qorguard.cli import main  # noqa: E402

if __name__ == '__main__':
    sys.exit(main())
