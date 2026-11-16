"""Operator-only, expiring, one-use staging service-start fault for recovery rehearsal."""
import argparse
import json
import os
from pathlib import Path
import stat
import subprocess
import time
import uuid

try:
    from .staging_lifecycle import require, sha
except ImportError:
    from staging_lifecycle import require, sha


MARKER=Path('/var/lib/clara-staging-bootstrap/fault-once.json')


def consume(path, candidate, now):
    if not path.exists():return False
    info=path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid==0 and info.st_mode & 0o077==0,
            'root_owned_fault_marker_required')
    value=json.loads(path.read_text())
    require(set(value)=={'candidate','armed_at','deadline'} and
        type(value['armed_at']) is int and type(value['deadline']) is int and
        0 < value['deadline']-value['armed_at']<=600,'invalid_fault_marker')
    sha(value['candidate'])
    if now>=value['deadline']:
        path.unlink();return False
    require(now>=value['armed_at'],'fault_clock_regressed')
    if value['candidate']!=candidate:return False
    # Atomic consumption precedes the simulated failure; recovery of B bypasses C.
    path.rename(path.with_name('consumed-'+uuid.uuid4().hex+'.json'))
    return True


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--arm');group.add_argument('--consume',action='store_true')
    args=parser.parse_args();require(os.geteuid()==0,'operator_root_required')
    now=int(time.time())
    if args.arm:
        candidate=sha(args.arm);MARKER.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        with MARKER.open('x') as stream:
            os.chmod(MARKER,0o600);json.dump(dict(candidate=candidate,armed_at=now,deadline=now+600),stream)
        print('Armed one staging-only start failure for ten minutes.');return 0
    candidate=subprocess.check_output(['/usr/bin/git','-c','safe.directory=/srv/C-LARA-2-staging',
        '-C','/srv/C-LARA-2-staging','rev-parse','HEAD'],text=True,timeout=5).strip()
    return 20 if consume(MARKER,sha(candidate),now) else 0


if __name__=='__main__':raise SystemExit(main())
