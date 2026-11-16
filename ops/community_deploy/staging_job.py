"""Short trusted GitHub job: original request -> deploy -> browser evidence -> stop."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time


def invoke(client,alias,event):
    reply=client.invoke(FunctionName=alias,InvocationType='RequestResponse',Payload=json.dumps(event).encode())
    stream=reply['Payload']
    try:data=json.loads(stream.read(262144))
    finally:stream.close()
    if reply.get('FunctionError') or data.get('outcome')!='processed':
        raise RuntimeError('coordinator_request_not_processed')
    return data['result']


def execute(client,alias,event,environment,browser_check,clock=time.time,sleep=time.sleep,keep_open=False):
    session=invoke(client,alias,{'action':'open','event':event,'environment':environment})
    lease,deadline=session['lease_id'],session['deadline']
    report={'schema':1,'target':'staging','lease_id':lease,'deadline':deadline,
            'candidate':session['commit'],'request_id':session['request_id'],'outcome':'failed'}
    try:
        while session['phase']=='starting' and clock()<deadline-60:
            sleep(5);session=invoke(client,alias,{'action':'tick'})
        if session['phase']!='ready':raise RuntimeError('staging_not_ready')
        session=invoke(client,alias,{'action':'deploy','lease_id':lease})
        while session['phase']=='deploying' and clock()<deadline-60:
            sleep(5);session=invoke(client,alias,{'action':'tick'})
        if session.get('phase')!='testing' or session.get('outcome')!='installed':
            raise RuntimeError('staging_install_not_verified')
        report['browser']=browser_check(session['commit'])
        if report['browser'].get('outcome')!='passed':raise RuntimeError('staging_browser_failed')
        report['outcome']='passed'
    except Exception:
        report['reason']='deployment_or_browser_check_failed'
    finally:
        if keep_open and report['outcome']=='passed':
            report['session_left_open_until_original_deadline']=True
        else:
            try:
                stopped=invoke(client,alias,{'action':'close','lease_id':lease})
                limit=min(deadline+120,clock()+120)
                while stopped['phase']=='stopping' and clock()<limit:
                    sleep(5);stopped=invoke(client,alias,{'action':'tick'})
                report['stop_confirmed']=stopped['phase']=='closed'
            except Exception:
                report['stop_confirmed']=False
            if not report['stop_confirmed']:
                report['outcome']='failed';report['reason']='stop_unconfirmed_inspect_original_lease'
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('alias','region','hostname','secret-arn','fixture-bucket','report'):
        parser.add_argument('--'+key,required=True)
    parser.add_argument('--keep-open',action='store_true')
    args=parser.parse_args()
    report={'schema':1,'target':'staging','outcome':'failed','reason':'request_not_admitted'}
    try:
        import boto3
        from botocore.config import Config
        client=boto3.client('lambda',region_name=args.region,
            config=Config(connect_timeout=3,read_timeout=100,retries={'total_max_attempts':1}))
        event=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
        environment={key:value for key,value in os.environ.items() if key in {
            'GITHUB_EVENT_NAME','GITHUB_REPOSITORY','GITHUB_REPOSITORY_ID','GITHUB_REF','GITHUB_SHA',
            'GITHUB_ACTOR_ID','GITHUB_ACTOR','GITHUB_TRIGGERING_ACTOR','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT',
            'GITHUB_REF_PROTECTED'}}
        def browser(expected):
            path=Path(args.report).with_name('browser-report.json')
            subprocess.run([os.sys.executable,str(Path(__file__).with_name('staging_browser.py')),
                '--base-url','https://'+args.hostname,'--secret-arn',args.secret_arn,
                '--fixture-bucket',args.fixture_bucket,'--expected',expected,'--region',args.region,
                '--report',str(path)],check=False,timeout=180)
            return json.loads(path.read_text())
        report=execute(client,args.alias,event,environment,browser,keep_open=args.keep_open)
    except Exception:
        pass
    Path(args.report).write_text(json.dumps(report,indent=2)+'\n')
    return 0 if report['outcome']=='passed' else 1


if __name__=='__main__':raise SystemExit(main())
