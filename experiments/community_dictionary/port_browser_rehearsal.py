"""Two real queue workers and browser review, with simulated AI and disposable data."""
from pathlib import Path
from browser_rehearsal import main

if __name__ == '__main__':
    main(Path(__file__).with_name('port_browser_workflow.cjs'),porting=True)
