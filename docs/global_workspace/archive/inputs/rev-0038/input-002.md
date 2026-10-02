When I killed, I got this:

^CTraceback (most recent call last):
  File "/srv/C-LARA-2/platform_server/manage.py", line 13, in <module>
    main()
  File "/srv/C-LARA-2/platform_server/manage.py", line 10, in main
    execute_from_command_line(sys.argv)

I restarted and checked that Community Dictionaries is running normally.

Going to go and help make dinner, okay? 
  File "/srv/C-LARA-2/.venv/lib/python3.12/site-packages/django/core/management/__init__.py", line 442, in execute_from_command_line 
    utility.execute() 
  File "/srv/C-LARA-2/.venv/lib/python3.12/site-packages/django/core/management/__init__.py", line 436, in execute 
    self.fetch_command(subcommand).run_from_argv(self.argv) 
  File "/srv/C-LARA-2/.venv/lib/python3.12/site-packages/django/core/management/base.py", line 420, in run_from_argv 
    self.execute(*args, **cmd_options) 
  File "/srv/C-LARA-2/.venv/lib/python3.12/site-packages/django/core/management/base.py", line 464, in execute 
    output = self.handle(*args, **options) 
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^ 
  File "/srv/C-LARA-2/.venv/lib/python3.12/site-packages/django/core/management/commands/shell.py", line 257, in handle 
    exec(sys.stdin.read(), {**globals(), **self.get_namespace(**options)}) 
  File "<string>", line 15, in <module> 
  File "/usr/lib/python3.12/subprocess.py", line 550, in run 
    stdout, stderr = process.communicate(input, timeout=timeout) 
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ 
  File "/usr/lib/python3.12/subprocess.py", line 1201, in communicate 
    self.wait() 
  File "/usr/lib/python3.12/subprocess.py", line 1264, in wait 
    return self._wait(timeout=timeout) 
           ^^^^^^^^^^^^^^^^^^^^^^^^^^ 
  File "/usr/lib/python3.12/subprocess.py", line 2053, in _wait 
    (pid, sts) = self._try_wait(0) 
                 ^^^^^^^^^^^^^^^^^ 
  File "/usr/lib/python3.12/subprocess.py", line 2011, in _try_wait 
    (pid, sts) = os.waitpid(self.pid, wait_flags) 
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ 
KeyboardInterrupt
