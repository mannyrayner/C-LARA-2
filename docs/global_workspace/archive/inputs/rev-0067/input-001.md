Very unexpectedly, I get an error in AWS installation, in collectstatic:

$ clara_manage collectstatic --noinput
Found another file with the destination path 'projects/favicon.svg'. It will be ignored since only the first encountered file is collected. If this is not what you want, make sure every static file has a unique path.
Traceback (most recent call last):
  File "/srv/C-LARA-2/platform_server/manage.py", line 13, in <module>
    main()
  File "/srv/C-LARA-2/platform_server/manage.py", line 10, in main
    execute_from_command_line(sys.argv)
  File "/srv/C-LARA-2/.venv/lib/python3.12/site-packages/django/core/management/__init__.py", line 442, in execute_from_command_line
    utility.execute()
  File "/srv/C-LARA-2/.venv/lib/python3.12/site-packages/django/core/management/__init__.py", line 436, in execute
    self.fetch_command(subcommand).run_from_argv(self.argv)
  File "/srv/C-LARA-2/.venv/lib/python3.12/site-packages/django/core/management/base.py", line 420, in run_from_argv
    self.execute(*args, **cmd_options)
  File "/srv/C-LARA-2/.venv/lib/python3.12/site-packages/django/core/management/base.py", line 464, in execute
    output = self.handle(*args, **options)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/srv/C-LARA-2/.venv/lib/python3.12/site-packages/django/contrib/staticfiles/management/commands/collectstatic.py", line 209, in handle
    collected = self.collect()
                ^^^^^^^^^^^^^^
  File "/srv/C-LARA-2/.venv/lib/python3.12/site-packages/django/contrib/staticfiles/management/commands/collectstatic.py", line 135, in collect
    handler(path, prefixed_path, storage)
  File "/srv/C-LARA-2/.venv/lib/python3.12/site-packages/django/contrib/staticfiles/management/commands/collectstatic.py", line 368, in copy_file
    if not self.delete_file(path, prefixed_path, source_storage):
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/srv/C-LARA-2/.venv/lib/python3.12/site-packages/django/contrib/staticfiles/management/commands/collectstatic.py", line 322, in delete_file
    self.storage.delete(prefixed_path)
  File "/srv/C-LARA-2/.venv/lib/python3.12/site-packages/django/core/files/storage/filesystem.py", line 184, in delete
    os.remove(name)
PermissionError: [Errno 13] Permission denied: '/srv/C-LARA-2/platform_server/staticfiles/community_dictionary/practice.js'

This has never happened before. Can you advise?
