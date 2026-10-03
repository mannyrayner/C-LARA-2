"""Practice UI trial with a disposable DB and synthetic media; no providers."""
from pathlib import Path
from browser_rehearsal import main

if __name__ == '__main__':
    main(Path(__file__).with_name('practice_browser_workflow.cjs'), practice=True)
