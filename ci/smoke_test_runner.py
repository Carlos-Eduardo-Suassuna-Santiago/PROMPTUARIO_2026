"""
Simple smoke test runner used by CI to validate deployed services.
This script calls the project-level smoke script if present and exits with non-zero code on failures.
"""
import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.dirname(__file__))
SMOKE_SCRIPT = os.path.join(ROOT, 'backend', 'scripts', 'fastapi_services_smoke.py')

if __name__ == '__main__':
    if os.path.exists(SMOKE_SCRIPT):
        print('Running smoke tests:', SMOKE_SCRIPT)
        rc = subprocess.call([sys.executable, SMOKE_SCRIPT])
        if rc != 0:
            print('Smoke tests failed with code', rc)
            sys.exit(rc)
        print('Smoke tests passed')
        sys.exit(0)
    else:
        print('No smoke script found at', SMOKE_SCRIPT)
        sys.exit(0)
