"""Disposable browser trial with a simulated provider. No OpenAI request is made."""
from pathlib import Path
from browser_rehearsal import main

if __name__ == '__main__':
    main(Path(__file__).with_name('image_browser_workflow.cjs'), image_generation=True)
