"""
Run the full test suite.

Discovers every test under ``tests/`` (via pytest.ini's ``testpaths``) instead
of a hardcoded list, so newly added test files are always picked up.

Usage:
    python tests/run_tests.py            # run all suites
    python tests/run_tests.py -v         # verbose output
    python tests/run_tests.py -x         # stop on first failure
    python tests/run_tests.py -v -x      # verbose + stop on first failure
    python tests/run_tests.py tests/test_auth.py   # run a specific file
"""

import sys
import pytest


def main():
    # Forward any CLI args (e.g. -v, -x, -s, or explicit paths) to pytest.
    # With no path args, pytest falls back to testpaths in pytest.ini and
    # collects every tests/test_*.py file.
    extra_args = sys.argv[1:]

    exit_code = pytest.main(extra_args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
