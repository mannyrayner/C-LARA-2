"""Baseline browser evidence for a private synthetic fixture; no traces/secrets printed."""
import argparse
import json
from pathlib import Path

try:
    from .staging_runtime_app import credentials
except ImportError:
    from staging_runtime_app import credentials


def check(base, secret, fixture, expected, browser):
    passwords = credentials(secret)
    context = browser.new_context(http_credentials={'origin':base,'username':'pilot','password':passwords['basic_password']},
                                  viewport={'width':390,'height':844})
    page = context.new_page()
    def health():
        reply = context.request.get(base+'/community-dictionaries/deployment-health/')
        assert reply.status == 200 and reply.json()['release'] == expected
    def login(username,password):
        page.goto(base+'/community-dictionaries/login/')
        page.get_by_label('Username',exact=True).fill(username)
        page.get_by_label('Password',exact=True).fill(password)
        page.get_by_role('button',name='Log in',exact=True).click()
        page.wait_for_load_state('networkidle')
    try:
        health()
        login('staging-owner',passwords['owner_password'])
        response = page.goto(base+fixture['entry_url'])
        assert response.status == 200 and fixture['word'] in page.locator('body').inner_text()
        for key,mime in [('image_url','image/'),('audio_url','audio/')]:
            reply=context.request.get(base+fixture[key])
            assert reply.status == 200 and reply.headers.get('content-type','').startswith(mime)
            assert len(reply.body()) > 0
        assert page.goto(base+'/').status == 200
        assert context.request.get(base+'/static/admin/css/base.css').status == 200
        context.clear_cookies()
        login('staging-outsider',passwords['other_password'])
        for key in ('entry_url','image_url','audio_url'):
            assert context.request.get(base+fixture[key]).status in (403,404)
        health()
        return {'schema':1,'candidate':expected,'browser':browser.version,'viewport':[390,844],
                'checks':{'owner_login':True,'private_entry':True,'image':True,'audio_response':True,
                          'static_assets':True,'outside_dictionary_page':True,'outsider_denied':True,
                          'release_before_and_after':True},'outcome':'passed'}
    finally:
        context.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',required=True); parser.add_argument('--secret-arn',required=True)
    parser.add_argument('--fixture-bucket',required=True); parser.add_argument('--expected',required=True)
    parser.add_argument('--region',required=True); parser.add_argument('--report',required=True)
    args=parser.parse_args()
    report={'schema':1,'candidate':args.expected,'outcome':'failed'}
    try:
        assert args.base_url.startswith('https://') and args.base_url.endswith('.c-lara.org')
        import boto3
        from botocore.config import Config
        from playwright.sync_api import sync_playwright
        config=Config(connect_timeout=2,read_timeout=5,retries={'total_max_attempts':1})
        secret=json.loads(boto3.client('secretsmanager',region_name=args.region,config=config)
                          .get_secret_value(SecretId=args.secret_arn)['SecretString'])
        stream=boto3.client('s3',region_name=args.region,config=config).get_object(
            Bucket=args.fixture_bucket,Key='staging/fixture.json')['Body']
        try:fixture=json.loads(stream.read(8192))
        finally:stream.close()
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch()
            try:report=check(args.base_url,secret,fixture,args.expected,browser)
            finally:browser.close()
    except Exception:
        report['reason']='browser_baseline_failed'
    Path(args.report).write_text(json.dumps(report,indent=2)+'\n')
    return 0 if report['outcome']=='passed' else 1


if __name__=='__main__':
    raise SystemExit(main())
