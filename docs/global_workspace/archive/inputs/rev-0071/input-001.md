Oh good! Your revised version looks fine:

$ clara_manage community_queue_check --tasks 20
Queue implementation: /srv/C-LARA-2/src/django_q/tasks.py
Connection cleanup version: 1
Active task limit in this process: 2
Completed SELECT probes: 20/20
Peak simultaneous probe bodies: 2 (limit 2)
Task connections still open after completion: 0
Queue check passed. No app data changed and no AI requests sent.

Proceed to next step?