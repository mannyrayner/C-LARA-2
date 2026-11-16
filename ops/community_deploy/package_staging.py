#!/usr/bin/env python3
"""Build review-only staging bundles and change-set templates. Never calls AWS."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

try:
    from .staging_templates import host_template,runtime_template
except ImportError:
    from staging_templates import host_template,runtime_template


def archive(destination,files):
    with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED) as package:
        for name,content in sorted(files.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            package.writestr(info,content)
    raw=destination.read_bytes()
    return hashlib.sha256(raw).hexdigest(),base64.b64encode(hashlib.sha256(raw).digest()).decode()


def build(root,out,revision,dirty=False):
    root,out=Path(root).resolve(),Path(out).resolve()
    if out.is_relative_to(root) or out.exists():raise ValueError('Use a new output directory outside the source checkout.')
    out.mkdir(parents=True)
    ops=root/'ops/community_deploy';runtime=ops/'staging_runtime'
    modules=['runner.py','staging_lifecycle.py','staging_aws.py','staging_request.py',
             'staging_source.py','staging_runtime_app.py']
    files={name:(ops/name).read_bytes() for name in modules}
    runtime_hash,runtime_b64=archive(out/'runtime.zip',files)
    host_files={**files,**{name:(ops/name).read_bytes() for name in
        ['staging_guard.py','staging_install.py','staging_bootstrap_host.py','staging_fault.py']}}
    host_files.update({'runtime/'+p.name:p.read_bytes() for p in runtime.iterdir() if p.is_file()})
    host_hash,_=archive(out/'host-tools.zip',host_files)
    control=out/'control';control.mkdir()
    for name in ['staging_job.py','staging_browser.py','staging_runtime_app.py','staging_source.py',
                 'staging_lifecycle.py','staging_aws.py','staging_request.py','runner.py']:
        shutil.copyfile(ops/name,control/name)
    shutil.copyfile(runtime/'requirements.txt',control/'requirements.txt')
    (control/'.github/workflows').mkdir(parents=True)
    shutil.copyfile(runtime/'staging-live.yml',control/'.github/workflows/staging-live.yml')
    operator=out/'operator';operator.mkdir()
    for name in ['staging_initialize.py','staging_operator.py',*modules]:
        shutil.copyfile(ops/name,operator/name)
    shutil.copyfile(runtime/'requirements.txt',operator/'requirements.txt')
    guard=hashlib.sha256((ops/'staging_guard.py').read_bytes()).hexdigest()
    for name,template in [('host.cfn.json',host_template((runtime/'host-user-data.sh').read_text())),
                          ('runtime.cfn.json',runtime_template(json.loads((runtime/'ssm-document.json').read_text())))]:
        (out/name).write_text(json.dumps(template,indent=2)+'\n')
    manifest={'schema':1,'source_revision':revision,'working_tree_unreviewed':dirty,
        'runtime_zip_sha256':runtime_hash,'runtime_zip_sha256_base64':runtime_b64,
        'runtime_code_key':'staging/bootstrap/runtime-'+runtime_hash+'.zip',
        'host_zip_sha256':host_hash,'host_code_key':'staging/bootstrap/host-tools-'+host_hash+'.zip',
        'guard_sha256':guard,'live_enabled':False,
        'file_sha256':{name:hashlib.sha256(data).hexdigest() for name,data in host_files.items()}}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    parser.add_argument('--allow-dirty-for-validation',action='store_true')
    args=parser.parse_args();root=Path(__file__).resolve().parents[2]
    dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip())
    if dirty and not args.allow_dirty_for_validation:raise SystemExit('Commit/review source before building an operator bundle.')
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    manifest=build(root,args.output,revision,dirty)
    print(json.dumps({k:v for k,v in manifest.items() if k!='file_sha256'},indent=2))


if __name__=='__main__':main()
