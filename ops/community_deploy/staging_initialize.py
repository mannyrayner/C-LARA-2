#!/usr/bin/env python3
"""Operator-only initial state creation. Never starts a host or overwrites state."""
import argparse
import json
from pathlib import Path

try:
    from .staging_lifecycle import Policy, initial_state, require, sha
    from .staging_source import SourceVerifier
except ImportError:
    from staging_lifecycle import Policy, initial_state, require, sha
    from staging_source import SourceVerifier


def initialize(config, clients, verify):
    baseline=sha(config['baseline'])
    policy=Policy(config['instance_id'],config['policy_revision'],config['guard_revision'])
    require(verify({'commit':baseline,'expected_staging':baseline}) is True,'bootstrap_source_not_verified')
    response=clients['ec2'].describe_instances(InstanceIds=[policy.instance_id])
    rows=[i for r in response.get('Reservations',[]) for i in r.get('Instances',[])]
    require(len(rows)==1 and rows[0].get('InstanceId')==policy.instance_id and
            rows[0].get('State',{}).get('Name')=='stopped','bootstrap_host_not_confirmed_stopped')
    tags={t['Key']:t['Value'] for t in rows[0].get('Tags',[])}
    require(tags.get('ClaraEnvironment')=='staging' and
            tags.get('ClaraGuardRevision')==policy.guard_revision and
            tags.get('ClaraGuardSha256')==config['guard_sha256'],'bootstrap_guard_not_attested')
    reply=clients['s3'].get_object(Bucket=config['state_bucket'],Key='staging/bootstrap-receipt.json')
    try:receipt=json.loads(reply['Body'].read(8192))
    finally:reply['Body'].close()
    require(receipt.get('instance_id')==policy.instance_id and receipt.get('baseline')==baseline and
            receipt.get('guard_sha256')==config['guard_sha256'] and
            receipt.get('policy_revision')==policy.revision,'bootstrap_receipt_mismatch')
    state=initial_state(policy,baseline);state['watchdog_at']=0
    clients['s3'].put_object(Bucket=config['state_bucket'],Key='staging/lifecycle.json',
        Body=json.dumps(state).encode(),IfNoneMatch='*',ServerSideEncryption='AES256',
        ContentType='application/json')
    return {'schema':1,'outcome':'initialized','instance_id':policy.instance_id,'baseline':baseline}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True)
    args=parser.parse_args()
    try:
        config=json.loads(Path(args.config).read_text())
        import boto3
        from botocore.config import Config
        sdk=Config(connect_timeout=2,read_timeout=5,retries={'total_max_attempts':1})
        clients={name:boto3.client(name,region_name=config['region'],config=sdk) for name in ('s3','ec2')}
        print(json.dumps(initialize(config,clients,SourceVerifier())));return 0
    except Exception:
        print(json.dumps({'outcome':'refused','reason':'bootstrap_state_not_initialized'}));return 1


if __name__=='__main__':raise SystemExit(main())
