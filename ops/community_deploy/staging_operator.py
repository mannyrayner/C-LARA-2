"""Prepare private operator JSON from reviewed bundle/stack outputs. No AWS calls."""
import argparse
import json
from pathlib import Path
import re
import shlex


def outputs(path):
    value=json.loads(Path(path).read_text())
    rows=value['Stacks'][0]['Outputs']
    return {row['OutputKey']:row['OutputValue'] for row in rows}


def prepare(manifest,host,runtime,baseline,admin_email,artifact_bucket):
    if manifest.get('working_tree_unreviewed') is not False or manifest.get('live_enabled') is not False:
        raise ValueError('A clean reviewed disabled bundle is required.')
    if not re.fullmatch('[0-9a-f]{40}',baseline):raise ValueError('Full baseline SHA required.')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',admin_email):raise ValueError('Admin email required.')
    if not re.fullmatch('[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]',artifact_bucket):raise ValueError('Bucket name required.')
    revision=manifest['source_revision']
    if not re.fullmatch('[0-9a-f]{40}',revision):raise ValueError('Reviewed revision required.')
    config=dict(region='ap-southeast-2',instance_id=host['InstanceId'],
        hostname='c-lara-2-staging.c-lara.org',baseline=baseline,admin_email=admin_email,
        credential_secret_arn=runtime['CredentialSecretArn'],state_bucket=runtime['StateBucket'],
        guard_sha256=manifest['guard_sha256'],guard_revision=revision,policy_revision=revision)
    # The config contains resource identifiers only. Passwords are never copied into SSM input.
    import base64
    data=base64.b64encode(json.dumps(config).encode()).decode()
    script="printf %s "+shlex.quote(data)+' | base64 --decode >/etc/clara-staging-bootstrap.json; chmod 0600 /etc/clara-staging-bootstrap.json'
    commands=['set -eu',
        'aws s3 cp '+shlex.quote('s3://'+artifact_bucket+'/'+manifest['host_code_key'])+' /tmp/clara-host-tools.zip --region ap-southeast-2',
        "echo "+shlex.quote(manifest['host_zip_sha256']+'  /tmp/clara-host-tools.zip')+' | sha256sum --check --status',
        'install -d -m 0755 /opt/clara-staging-deploy',
        'unzip -oq /tmp/clara-host-tools.zip -d /opt/clara-staging-deploy',
        'chown -R root:root /opt/clara-staging-deploy',
        'chmod -R go-w /opt/clara-staging-deploy',
        'python3 -m venv /opt/clara-staging-guard',
        '/opt/clara-staging-guard/bin/pip install boto3==1.35.99',script,
        '/opt/clara-staging-guard/bin/python /opt/clara-staging-deploy/staging_bootstrap_host.py --config /etc/clara-staging-bootstrap.json']
    return config,{'commands':commands,'executionTimeout':['1800']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('manifest','host-outputs','runtime-outputs','baseline','admin-email','artifact-bucket','output'):
        parser.add_argument('--'+key,required=True)
    args=parser.parse_args();destination=Path(args.output)
    if destination.exists():raise SystemExit('Use a new private output directory.')
    config,parameters=prepare(json.loads(Path(args.manifest).read_text()),outputs(args.host_outputs),
        outputs(args.runtime_outputs),args.baseline,args.admin_email,args.artifact_bucket)
    destination.mkdir(parents=True,mode=0o700)
    for name,value in [('bootstrap-config.json',config),('bootstrap-ssm-parameters.json',parameters)]:
        path=destination/name;path.write_text(json.dumps(value,indent=2)+'\n');path.chmod(0o600)
    print('Prepared bootstrap-config.json and bootstrap-ssm-parameters.json; no AWS calls made.')


if __name__=='__main__':main()
