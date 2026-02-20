"""
Run all tests sequentially: auth → users → house.

Usage:
    python tests/run_tests.py            # run all suites
    python tests/run_tests.py -v         # verbose output
    python tests/run_tests.py -x         # stop on first failure
    python tests/run_tests.py -v -x      # verbose + stop on first failure
"""

import sys
import pytest


def main():
    # Test files in execution order
    test_files = [
        "tests/test_auth.py",
        "tests/test_users.py",
        "tests/test_house.py",
    ]

    # Forward any CLI args (e.g. -v, -x, -s) to pytest
    extra_args = sys.argv[1:]

    exit_code = pytest.main(test_files + extra_args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
