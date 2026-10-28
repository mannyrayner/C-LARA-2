#!/usr/bin/env python3
"""Prepare files only; never register a runner, create a repo, or contact AWS."""
import argparse
import json
from pathlib import Path
import shutil
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    repo = here.parent.parent
    target = Path(args.destination).resolve()
    if target.exists() or target.is_relative_to(repo):
        parser.error('Choose a NEW directory outside the application checkout.')
    target.mkdir(parents=True)
    (target / 'bin').mkdir()
    (target / 'activity').mkdir()
    (target / 'state').mkdir()
    shutil.copy2(here / 'runner.py', target / 'bin' / 'runner.py')
    shutil.copytree(here / 'control', target / 'control')
    for name in ('runner.py', 'cloud.py'):
        shutil.copy2(here / name, target / 'control' / name)
    shutil.copy2(target / 'control' / 'current_release.example.json', target / 'control' / 'current_release.json')
    python = repo / '.venv' / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    manage = [str(python), '-E', 'manage.py']
    config = {'target': 'laptop', 'repo': str(repo), 'state': str(target / 'state'),
              'activity_dir': str(target / 'activity'), 'manage': manage, 'static_manage': manage,
              'address': '127.0.0.1:8000', 'git': shutil.which('git') or 'git',
              'health_url': 'http://127.0.0.1:8000/community-dictionaries/deployment-health/',
              'timeout_seconds': 120}
    (target / 'laptop.json').write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    print('Prepared controller:', target / 'bin' / 'runner.py')
    print('Prepared host configuration:', target / 'laptop.json')
    print('Private control repository files:', target / 'control')
    print('No services, application data, GitHub settings or AWS resources were changed.')


if __name__ == '__main__':
    main()
