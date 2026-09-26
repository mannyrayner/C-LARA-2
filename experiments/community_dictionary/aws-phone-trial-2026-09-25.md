# AWS deployment and first physical-phone trial

Trial date: 25 September 2026. Recorded: 26 September 2026, with a deployment
configuration follow-up from that day. Evidence is Manny's reported use, not
an independently observed browser session by the assistant.

## Result

Manny reported successful deployment on the existing AWS C-LARA-2 server and
access from his laptop at `https://c-lara-2.c-lara.org/community-dictionaries/`.
He then reported that everything in the proposed laptop workflow worked. That
workflow comprised creating an entry with an image, recording and playing audio,
adding words/translation/category, saving and reloading, and browsing/searching.
The report is an overall confirmation, not a separately instrumented result for
each action.

He subsequently reported: "It all works on Cathy's mobile phone - she was able
to take a picture and save it, then I added a recording."

This establishes a successful initial physical-phone contribution trial and
the intended division of image/audio work between two people. The phone model,
operating system and browser were not supplied. The device used for the added
recording and whether separate user accounts or a registered partnership were
used were not specified. Do not infer all iPhone/Safari and Android/Chrome
paths, cross-device codec compatibility or the full partnership/request workflow
from this result. Broader acceptance and sustained use remain untested.

Manny has invited Kate and Axel to try an Icelandic dictionary. Their trial has
not yet been reported. AI media generation, video and dedicated practice remain
deferred. No Indigenous-community suitability or learning-effectiveness result
is claimed.

## Repository and deployment evidence

- The implementation and repair are committed as
  `692e44d38da85b39593a2fc71afc171e46224458` and are now on `main`.
- The subsequent archive-only commit is
  `88118493ffe809c64ef341d313619516bddb914d`.
- `a7e88702dff965ff1cacac7fd2a8a366f49291c4` changes only `DEBUG = True` to
  `DEBUG = False` in the shared settings. It is the reviewed `main` tip for this
  documentation update. Manny confirmed redeployment and effective `DEBUG = False`
  on 26 September.
- The supplied nginx preflight has HTTPS, a 200 MB request limit, public aliases
  for `staticfiles/` and `media/`, and a valid configuration. Gunicorn runs as
  `ubuntu:www-data`. The complete redirect/header configuration was not supplied.
- The 26 September `check --deploy` output contains `security.W004` (HSTS),
  `security.W008` (Django SSL redirect), `security.W012` (secure session cookie)
  and `security.W016` (secure CSRF cookie). Their remediation is pending; nginx
  may already implement part of the HTTPS policy. The wildcard `ALLOWED_HOSTS`
  also remains in the reviewed settings although this trace does not flag it.
- Read-only external HEAD requests by the assistant on 26 September returned
  HTTP 301 from the dictionary's HTTP URL to its HTTPS URL, and HTTP 302 from
  that HTTPS URL to the login page. No HSTS header was present on that HTTPS
  response. This confirms redirection for this public path; it does not verify
  all routes, nginx's handling of forwarded headers or authenticated responses.

## Development-method evidence

Manny estimates the first functional cut at 45 minutes and the initial
implementation and repair at under two hours. These are human estimates, not
independent timing/cost measurements. Specification, existing infrastructure,
installation, evaluation and future maintenance must not be silently treated as
free or included in a precise measured total. The documented implementation
iterations contain multiple tool calls, checks and repairs.

The earlier 21 passing app tests and controlled Chromium checks remain the
recorded automated evidence. No new runtime test pass is claimed by this
documentation-only update. Prior iteration and laptop-trial records retain
their historical wording. Original material human reports are archived with
global-workspace revision 15; the live assessment and current status summaries
are updated so the repository Assistant can retrieve the new evidence.

## Next evidence to collect

1. Close the production configuration items with the actual nginx setup in view.
2. Record phone/browser details, and exercise additional capture/playback paths.
3. Let the Icelandic testers create a few personally useful entries and report
   friction, collaboration issues and whether they choose to return.
4. Revisit features after feedback; retain human camera/voice input as the core.
