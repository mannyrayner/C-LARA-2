# Changing and recovering account passwords

30 September 2026. This patch follows the installed
`community_dictionary_save_ux.patch` on main at `c72c33b`.

## Using the commands

- **Admin → Reset a user's password**: select the username, Continue, enter the
  new password twice, then Reset password. The old password is not required.
  Sign out of admin and sign in as the recovered user with the new password.
- **Profile → Change my password**: any signed-in user can supply their current
  password and enter their new password twice. The current session stays signed
  in; other sessions need to sign in again.
- From Community Dictionaries, the username at the top now links to Profile.

C-LARA and Community Dictionaries share accounts. Laptop and AWS databases are
separate: changing a laptop password does not change the AWS account password.
No email is sent and no password is displayed after submission. If helping
another person, give them the new password privately; they can change it in
Profile. This does not implement emailed forgotten-password links or a mandatory
first-login password change.

Admin access follows the existing C-LARA staff/bootstrapped-admin rule. The menu
lists active accounts, excludes the admin's own account, and exposes no emails.
Only a Django superuser can reset another superuser's password. The reset form
rechecks eligibility on every request; a hidden menu is not its access control.
Each successful admin reset records the actor and target in Django's existing
admin log, without recording the password. Password forms use CSRF protection,
private non-cacheable responses and sensitive-POST filtering for error reports.

Both commands use Django's password forms and configured validators. Where an
installation still has no password validators configured, these two forms use
Django's usual similarity, minimum-length (8), common-password and numeric-password
checks. This does not change existing passwords or the registration policy.

## Laptop installation and recovery

Stop the development server. Save `clara2_account_passwords.patch` in
`/home/github`, beside the checkout. Keep the earlier UX patch installed; its
changes can remain staged. In Cygwin:

```bash
cd /home/github/c-lara-2
git apply --check ../clara2_account_passwords.patch &&
git apply --index ../clara2_account_passwords.patch
```

Then:

```bash
cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test projects.tests.test_passwords projects.tests.test_profile projects.tests.test_admin_tools community_dictionary &&
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

Expect 123 tests. Intentional mocked provider failures can print TimeoutError or
JSONDecodeError before the final OK. No migration or dependency update is needed.
Log in as admin, choose **Admin → Reset a user's password**, and recover your
normal account. You can then resume testing the saving/invitation improvements.

After acceptance, the two staged patches can be committed together:

```bash
cd /home/github/c-lara-2
git diff --cached --check &&
git diff --cached --stat &&
git commit -m "Improve dictionary saving and add account password management" &&
git push
```

AWS can use the established update runbook when ready. The assistant has neither
deployed this patch nor changed any real account password.

## Verification

The 123 passing Django tests comprise 15 new password-management tests, existing
Profile/Admin tests, and all 70 Community Dictionary tests. They exercise
authentication/authorization, target eligibility and tampering, password policy,
CSRF, session invalidation/preservation, audit content, cache headers and error
report redaction. Tests use a disposable database with a fast test-only hasher.

The controlled Chromium browser rehearsal uses a Pixel 7 viewport and a disposable
database: bootstrap test admin registration → admin reset → login with the reset
password → dictionary username link → Profile → personal change → subsequent
login. This is not evidence of a physical-phone or production trial. The initial
probe matched a label without Django's trailing colon; correcting the probe to
use field IDs resolved that test-harness timeout, without changing the app.

To repeat the optional browser rehearsal, install Playwright separately and set
`COMMUNITY_PLAYWRIGHT_MODULE` / `COMMUNITY_CHROMIUM_PATH` if needed. From the repo
root with the application dependencies available:

```bash
python -c 'from pathlib import Path; from experiments.community_dictionary.browser_rehearsal import main; main(Path("experiments/community_dictionary/password_browser_workflow.cjs").resolve())' /tmp/clara-password-browser
```

The helper creates and deletes its own database; it never uses the laptop or AWS
database. The bootstrap admin setting must retain the default `admin` username
for this synthetic rehearsal.
