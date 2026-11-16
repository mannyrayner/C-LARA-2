#!/usr/bin/env python3
"""One-time operator bootstrap on the NEW staging host only; never a request action.

Read a reviewed root-owned JSON config. Provider/production credentials and data
are never copied. All subprocess arguments are fixed or validated data. The
machine stops at completion or failure; its bootstrap timer remains a backstop.
"""
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import time

try:
    from .staging_guard import instance_identity
    from .staging_lifecycle import require, sha
except ImportError:
    from staging_guard import instance_identity
    from staging_lifecycle import require, sha


REPO='/srv/C-LARA-2-staging'
ROOT=Path('/opt/clara-staging-deploy')


def command(args, input=None, user=None):
    if user:
        args=['/usr/bin/sudo','-u',user,*args]
    result=subprocess.run(args,input=input,capture_output=True,text=True,timeout=900,
                          env={**os.environ,'GIT_TERMINAL_PROMPT':'0','DEBIAN_FRONTEND':'noninteractive'})
    require(result.returncode==0,'bootstrap_command_failed')
    return result.stdout.strip()


def write(path,text,mode=0o600,group=None):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text);os.chmod(path,mode)
    if group:
        import grp
        os.chown(path,0,grp.getgrnam(group).gr_gid)


def setup(config,clients):
    require(os.geteuid()==0 and instance_identity()==config['instance_id'],'new_staging_host_required')
    require(Path('/var/lib/clara-staging-bootstrap/os-ready').is_file(),'os_preparation_not_confirmed')
    hostname=config['hostname'];baseline=sha(config['baseline'])
    require(re.fullmatch(r'[a-z0-9][a-z0-9.-]+\.c-lara\.org',hostname),'invalid_staging_hostname')
    require(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',config['admin_email']),'admin_email_required')
    require(hashlib.sha256((ROOT/'staging_guard.py').read_bytes()).hexdigest()==config['guard_sha256'],
            'reviewed_guard_hash_mismatch')
    for user in ('ssm-user','clara-staging'):
        try:pwd.getpwnam(user)
        except KeyError:command(['/usr/sbin/useradd','--system','--create-home','--shell','/bin/bash',user])
    command(['/usr/sbin/usermod','-a','-G','www-data','clara-staging'])
    if not Path(REPO).exists():
        command(['/usr/bin/install','-d','-o','ssm-user','-g','ssm-user',REPO])
        command(['/usr/bin/git','clone','https://github.com/mannyrayner/C-LARA-2.git',REPO],user='ssm-user')
    require(command(['/usr/bin/git','-C',REPO,'status','--porcelain'],user='ssm-user')=='',
            'staging_checkout_not_clean')
    command(['/usr/bin/git','-C',REPO,'fetch','--no-tags','origin','main'],user='ssm-user')
    command(['/usr/bin/git','-C',REPO,'merge-base','--is-ancestor',baseline,'FETCH_HEAD'],user='ssm-user')
    command(['/usr/bin/git','-C',REPO,'checkout','--detach',baseline],user='ssm-user')
    command(['/usr/bin/python3','-m','venv',REPO+'/.venv'],user='ssm-user')
    command([REPO+'/.venv/bin/pip','install','-r',REPO+'/requirements.txt',
             'gunicorn==23.0.0','psycopg[binary]==3.2.9'],user='ssm-user')
    secret=json.loads(clients['secretsmanager'].get_secret_value(SecretId=config['credential_secret_arn'])['SecretString'])
    require(isinstance(secret.get('seed'),str) and len(secret['seed'])>=24,'staging_seed_required')
    derive=lambda name:hmac.new(secret['seed'].encode(),name.encode(),hashlib.sha256).hexdigest()
    password=derive('database_password')
    sql="DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='clara_staging') THEN CREATE ROLE clara_staging LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION; END IF; END $$;\nALTER ROLE clara_staging PASSWORD '"+password+"';\n"
    command(['/usr/bin/psql','--set','ON_ERROR_STOP=on'],input=sql,user='postgres')
    exists=command(['/usr/bin/psql','-tAc',"SELECT 1 FROM pg_database WHERE datname='clara_staging'"],user='postgres')
    if not exists:command(['/usr/bin/createdb','--owner=clara_staging','clara_staging'],user='postgres')
    for path in ('/var/lib/clara-staging-media','/var/lib/clara-staging-private',
                 '/var/lib/clara-staging-mail','/var/lib/clara-staging-activity'):
        command(['/usr/bin/install','-d','-m','0750','-o','clara-staging','-g','www-data',path])
    command(['/usr/bin/install','-d','-m','0700','-o','ssm-user','-g','ssm-user','/var/lib/clara-staging-deploy'])
    # Both service users need access to the activity directory, never production paths.
    command(['/usr/sbin/usermod','-a','-G','www-data','ssm-user'])
    command(['/bin/chmod','0770','/var/lib/clara-staging-activity'])
    env={'DJANGO_SETTINGS_MODULE':'platform_server.staging_settings','CLARA_STAGING_MODE':'1',
        'CLARA_STAGING_HOSTNAME':hostname,'DJANGO_SECRET_KEY':derive('django_secret'),
        'DJANGO_DB_ENGINE':'postgresql','POSTGRES_HOST':'127.0.0.1','POSTGRES_DB':'clara_staging',
        'POSTGRES_USER':'clara_staging','POSTGRES_PASSWORD':password,
        'CLARA_DEPLOY_ACTIVITY_DIR':'/var/lib/clara-staging-activity',
        'CLARA_STAGING_LEASE_FILE':'/run/clara-staging-deploy/lease.json',
        'CLARA_COMMUNITY_MEDIA_ROOT':'/var/lib/clara-staging-private/community_dictionary'}
    write('/etc/clara-staging.env',''.join(k+'='+v+'\n' for k,v in env.items()),0o640,'www-data')
    manage=['/usr/bin/systemd-run','--quiet','--wait','--pipe','--collect',
        '--property=User=clara-staging','--property=Group=www-data',
        '--property=WorkingDirectory='+REPO+'/platform_server','--property=EnvironmentFile=/etc/clara-staging.env',
        REPO+'/.venv/bin/python','manage.py']
    command(manage+['migrate','--noinput'])
    command(['/usr/bin/install','-d','-o','clara-staging','-g','www-data',REPO+'/platform_server/staticfiles'])
    command(manage+['collectstatic','--noinput'])
    temporary=Path('/var/lib/clara-staging-private/fixture-credentials.json')
    temporary.write_text(json.dumps(secret));os.chmod(temporary,0o400)
    os.chown(temporary,pwd.getpwnam('clara-staging').pw_uid,-1)
    fixture=Path('/var/lib/clara-staging-private/fixture.json')
    try:command(manage+['community_staging_seed','--secret-file',str(temporary),'--output',str(fixture)])
    finally:temporary.unlink(missing_ok=True)
    clients['s3'].put_object(Bucket=config['state_bucket'],Key='staging/fixture.json',
        Body=fixture.read_bytes(),ServerSideEncryption='AES256',ContentType='application/json')
    from staging_runtime_app import credentials
    command(['/usr/bin/htpasswd','-iBc','/etc/nginx/clara-staging.htpasswd','pilot'],
            input=credentials(secret)['basic_password']+'\n')
    os.chmod('/etc/nginx/clara-staging.htpasswd',0o640)
    import grp
    os.chown('/etc/nginx/clara-staging.htpasswd',0,grp.getgrnam('www-data').gr_gid)
    command(['/usr/bin/install','-d','-m','0755','/var/www/letsencrypt'])
    write('/etc/nginx/sites-available/clara-staging',
        (ROOT/'runtime/nginx-bootstrap.conf').read_text().replace('STAGING_HOSTNAME',hostname),0o644)
    Path('/etc/nginx/sites-enabled/default').unlink(missing_ok=True)
    link=Path('/etc/nginx/sites-enabled/clara-staging')
    if not link.exists():link.symlink_to('/etc/nginx/sites-available/clara-staging')
    command(['/usr/sbin/nginx','-t']);command(['/usr/bin/systemctl','restart','nginx'])
    command(['/usr/bin/certbot','certonly','--webroot','-w','/var/www/letsencrypt','-d',hostname,
             '--non-interactive','--agree-tos','--email',config['admin_email']])
    write('/etc/nginx/sites-available/clara-staging',
        (ROOT/'runtime/nginx.conf').read_text().replace('STAGING_HOSTNAME',hostname),0o644)
    command(['/usr/sbin/nginx','-t']);command(['/usr/bin/systemctl','reload','nginx'])
    lease={key:config[key] for key in ('instance_id','region','state_bucket','policy_revision',
                                      'guard_revision','guard_sha256')}
    lease.update(state_key='staging/lifecycle.json',repo=REPO,activity_dir='/var/lib/clara-staging-activity')
    write('/etc/clara-staging-lease.json',json.dumps(lease,indent=2)+'\n')
    controller=json.loads((ROOT/'runtime/controller.json').read_text())
    write('/etc/clara-staging-deploy.json',json.dumps(controller,indent=2)+'\n',0o640,'www-data')
    # Helpers accept a fixed service set and fixed unprivileged management commands.
    write('/etc/sudoers.d/clara-staging-deploy','ssm-user ALL=(root) NOPASSWD: /opt/clara-staging-deploy/runtime/services.sh *, /opt/clara-staging-deploy/runtime/manage.sh *\n',0o440)
    command(['/usr/sbin/visudo','-cf','/etc/sudoers.d/clara-staging-deploy'])
    for unit in ('gunicorn-clara-staging','understanding-clara-staging'):
        shutil.copyfile(ROOT/'runtime'/ (unit+'.service'),'/etc/systemd/system/'+unit+'.service')
        drop=Path('/etc/systemd/system')/(unit+'.service.d');drop.mkdir(exist_ok=True)
        shutil.copyfile(ROOT/'runtime/app-lease.conf',drop/'lease.conf')
    shutil.copyfile(ROOT/'runtime/clara-staging-lease.service','/etc/systemd/system/clara-staging-lease.service')
    os.chmod(ROOT/'runtime/services.sh',0o755)
    os.chmod(ROOT/'runtime/manage.sh',0o755)
    command(['/usr/bin/systemctl','daemon-reload'])
    command(['/usr/bin/systemctl','enable','clara-staging-lease','gunicorn-clara-staging',
             'understanding-clara-staging'])
    receipt={'schema':1,'instance_id':config['instance_id'],'baseline':baseline,
             'policy_revision':config['policy_revision'],'guard_revision':config['guard_revision'],
             'guard_sha256':config['guard_sha256'],'prepared_at':int(time.time())}
    clients['s3'].put_object(Bucket=config['state_bucket'],Key='staging/bootstrap-receipt.json',
        Body=json.dumps(receipt).encode(),ServerSideEncryption='AES256',ContentType='application/json')
    command(['/usr/bin/systemctl','disable','--now','clara-bootstrap-deadline.timer'])
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True)
    args=parser.parse_args();authorized=False
    try:
        path=Path(args.config)
        require(path.stat().st_uid==0 and path.stat().st_mode & 0o022==0,'root_owned_bootstrap_config_required')
        config=json.loads(path.read_text())
        require(instance_identity()==config['instance_id'],'new_staging_host_required');authorized=True
        import boto3
        from botocore.config import Config
        sdk=Config(connect_timeout=2,read_timeout=5,retries={'total_max_attempts':1})
        clients={name:boto3.client(name,region_name=config['region'],config=sdk) for name in ('s3','secretsmanager')}
        print(json.dumps(setup(config,clients)))
        return 0
    except Exception:
        print(json.dumps({'outcome':'refused','reason':'staging_bootstrap_incomplete'}));return 1
    finally:
        if authorized:subprocess.run(['/usr/bin/systemctl','poweroff','--no-block'],timeout=10,check=True)


if __name__=='__main__':raise SystemExit(main())
