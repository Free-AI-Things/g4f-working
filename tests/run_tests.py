"""Runner script for the test suite — works without pytest.

Usage::

    python tests/run_tests.py            # run everything
    python tests/run_tests.py models     # run only test_models
"""

import os, sys, importlib, traceback

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(THIS_DIR, "..")))

MODULES = [
    "tests.test_models",
    "tests.test_config",
    "tests.test_media_saver",
    "tests.test_fetcher",
    "tests.test_reporter",
    "tests.test_tester",
    "tests.test_server",
    "tests.test_facade",
]


def run_module(mod_name):
    print(f"\n=== {mod_name} ===")
    mod = importlib.import_module(mod_name)
    passed = 0
    failed = 0
    for name, fn in vars(mod).items():
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS  {name}")
                passed += 1
            except Exception as e:
                print(f"  FAIL  {name}: {e}")
                traceback.print_exc()
                failed += 1
    return passed, failed


def main(argv):
    selected = argv[1:] if len(argv) > 1 else MODULES
    # Allow shorthand "models" -> "tests.test_models"
    selected = [
        f"tests.test_{s}" if not s.startswith("tests.") else s
        for s in selected
    ]
    total_p = total_f = 0
    for m in selected:
        p, f = run_module(m)
        total_p += p
        total_f += f
    print(f"\n========================================")
    print(f"TOTAL: {total_p} passed, {total_f} failed")
    print(f"========================================")
    sys.exit(0 if total_f == 0 else 1)


if __name__ == "__main__":
    main(sys.argv)
