It looked like it was going to work, but to my surprise the processes failed to restart:

(.venv) $ python manage.py migrate community_dictionary 0008_dictionary_participation
Operations to perform:
  Target specific migration: 0008_dictionary_participation, from community_dictionary
Running migrations:
  Applying community_dictionary.0006_contribution_control... OK
  Applying community_dictionary.0007_split_text_provenance... OK
  Applying community_dictionary.0008_dictionary_participation... OK
(.venv) $ python manage.py community_withdrawal_audit --expect-empty
Private contributions: 0
Private entries: 0
No content, files or participation states were changed.
(.venv) $ python manage.py migrate
Operations to perform:
  Apply all migrations: admin, auth, community_dictionary, contenttypes, projects, sessions
Running migrations:
  Applying community_dictionary.0009_restore_experimental_collections... OK
(.venv) $ python manage.py collectstatic --noinput
Found another file with the destination path 'projects/favicon.svg'. It will be ignored since only the first encountered file is collected. If this is not what you want, make sure every static file has a unique path.

1 static file copied to '/srv/C-LARA-2/platform_server/staticfiles', 133 unmodified.
(.venv) $ python manage.py check
System check identified no issues (0 silenced).
(.venv) $ sudo systemctl start gunicorn-clara2 djangoq-clara2 project-understanding-worker
(.venv) $ sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
● gunicorn-clara2.service - Gunicorn service for C-LARA-2 Django
     Loaded: loaded (/etc/systemd/system/gunicorn-clara2.service; enabled; preset: enabled)
     Active: activating (auto-restart) (Result: exit-code) since Fri 2026-10-02 10:00:29 UTC; 2s ago
    Process: 882414 ExecStart=/srv/C-LARA-2/.venv/bin/gunicorn --workers 3 --bind unix:/run/gunicorn-clara2/gunicorn.sock --umask 007 --timeout 600 --access-logfile - --error-logfile - platform_server.wsgi:application (code=exited, status=3)
   Main PID: 882414 (code=exited, status=3)
        CPU: 2.066s

● djangoq-clara2.service - Django Q worker for C-LARA-2
     Loaded: loaded (/etc/systemd/system/djangoq-clara2.service; enabled; preset: enabled)
     Active: activating (auto-restart) (Result: exit-code) since Fri 2026-10-02 10:00:27 UTC; 3s ago
    Process: 882412 ExecStart=/srv/C-LARA-2/.venv/bin/python manage.py qcluster (code=exited, status=1/FAILURE)
   Main PID: 882412 (code=exited, status=1/FAILURE)
        CPU: 748ms

● project-understanding-worker.service - C-LARA-2 project-understanding Codex worker
     Loaded: loaded (/etc/systemd/system/project-understanding-worker.service; disabled; preset: enabled)
     Active: activating (auto-restart) (Result: exit-code) since Fri 2026-10-02 10:00:27 UTC; 3s ago
    Process: 882413 ExecStart=/srv/C-LARA-2/.venv/bin/python manage.py process_project_understanding_queue (code=exited, status=1/FAILURE)
   Main PID: 882413 (code=exited, status=1/FAILURE)
        CPU: 752ms
