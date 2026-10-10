# Email password recovery

This increment adds **Forgotten password?** to both login pages, using the same
account and Django's standard reset-token machinery. Community Dictionaries users
remain in its interface. Existing authenticated password changes and admin resets
remain available.

The feature is off until `CLARA_PASSWORD_RESET_ENABLED=1`. Registration already
collects an email address. Profile now displays that address; an administrator can
correct an inaccessible or mistyped address after checking the person's identity.
This release does not introduce email-change verification or social login.

## Behaviour

- Request a link using the registered email address. Known, unknown, inactive and
  unusable-password accounts receive the same browser response. The latter three
  receive no mail. Existing accounts sharing an address receive separate links.
- Valid requests are dispatched through the existing bounded task runner. Account
  lookup and SMTP happen outside the HTTP request. No reset tokens or SMTP secrets
  are placed in task arguments. Real Django Q may retain the recipient address in
  its task records; the current fallback holds it in process memory.
- Links expire after one hour and stop working after a successful password reset,
  password change, login, or change to the account email. Inactive/unusable-password
  accounts cannot redeem links. A successful reset requires a fresh login and
  invalidates other authenticated sessions through Django's password hash.
- Newly chosen passwords use our existing password-policy form. CSRF protection
  applies to requests and password changes. Reset pages are not cacheable.
- Links use `CLARA_PUBLIC_BASE_URL`, never the incoming Host/forwarded-host header.
  Remote origins must use HTTPS. Console email is allowed only for localhost.
- Database counters enforce three accepted requests per normalized email address
  per 15-minute window, and 30 accepted requests across the installation per hour.
  These are request limits, not a per-dictionary quota or an exact email-message
  quota (a shared email address can identify more than one account). All valid
  addresses consume limits, including unknown ones. Limits are shared across
  processes and both login interfaces. The database stores HMACs, not addresses.
  Expired address counters are removed after a day on the next admitted request.
- Queue/SMTP errors are logged by exception class only. The normal browser reply
  does not disclose account existence or transport failures. A disabled or invalid
  configuration shows an explicit unavailable page instead of offering a form.

`projects.0044_passwordresetlimit` adds one counter table. It does not modify
accounts, passwords, dictionaries, contributions, or media. No dependency changes.

## Configuration

| Environment variable | Meaning |
| --- | --- |
| `CLARA_PASSWORD_RESET_ENABLED` | `1` to enable; default disabled |
| `CLARA_PUBLIC_BASE_URL` | Canonical origin, e.g. `https://c-lara-2.c-lara.org` |
| `EMAIL_BACKEND` | Default `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST` | For Google Workspace SMTP: `smtp.gmail.com` |
| `EMAIL_PORT` | Default `587` |
| `EMAIL_HOST_USER` | Full mailbox address |
| `EMAIL_HOST_PASSWORD` | Google app password, stored only in protected configuration |
| `EMAIL_USE_TLS` | Default `true` for STARTTLS |
| `EMAIL_USE_SSL` | Default `false`; do not enable together with STARTTLS |
| `DEFAULT_FROM_EMAIL` | Mailbox address used as sender |

The existing `DJANGO_SECRET_KEY` must be private and non-default for SMTP recovery.
Do not change an established production key as part of routine mail setup. SMTP
operations have a 15-second timeout. This first configuration expects authenticated
SMTP; an unauthenticated IP-authorized Workspace relay would require adjustment.

## Diagnostics and known limits

`python manage.py account_email_check` validates configuration and the counter
table without contacting SMTP. Add `--send-to ADDRESS` to send one harmless test
message, with no reset token or account changes. A successful command means the
backend accepted it; checking the actual inbox/spam folder is still necessary.

The current fallback queue is bounded but not durable. A process restart may lose
an unsent request; the user can request another link. Busy AI jobs can delay mail.
Requests older than 15 minutes when their task starts are dropped. There are no
automatic SMTP retries: a timeout can leave delivery uncertain. Ordinary access
logs can contain the initial reset-link URL, so retain existing restrictions on
server logs; do not post raw reset links in issue reports. Application mail-error
logs do not include recipients, passwords, message bodies or tokens.

For an immediate rollback of the feature, set `CLARA_PASSWORD_RESET_ENABLED=0`
and restart Gunicorn and Django Q. Keep migration 0044 applied; no database restore
or reverse migration is needed to disable recovery. Public/anonymous dictionary
browsing remains proposed and is not enabled by this patch.

## Provider references

Checked 10 October 2026:

- [Google Workspace: sending from an app](https://knowledge.workspace.google.com/admin/gmail/send-email-from-a-printer-scanner-or-app)
- [Google: app passwords](https://support.google.com/accounts/answer/185833?hl=en)
- [Django 5.2 password reset](https://docs.djangoproject.com/en/5.2/topics/auth/default/#django.contrib.auth.views.PasswordResetView)

See [installation instructions](email-password-reset-install.md).
