"""Isolate Qt/WebEngine test modules and fail on a stuck process shutdown."""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
failed = False
for test in sorted(root.glob('test_*.py')):
    print(f'\nRunning {test.name}', flush=True)
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'unittest', 'discover', '-s', str(root), '-p', test.name, '-v'],
            timeout=90,
        )
        failed |= result.returncode != 0
    except subprocess.TimeoutExpired:
        print(f'{test.name}: timed out (including Qt shutdown)', flush=True)
        failed = True
sys.exit(1 if failed else 0)
