I don't have the right permissions to do the first part as ubuntu:

buntu@ip-172-31-5-210:~$ sudo -iu ubuntu
ubuntu@ip-172-31-5-210:~$ cd /srv/C-LARA-2
ubuntu@ip-172-31-5-210:/srv/C-LARA-2$ . .venv/bin/activate
(.venv) ubuntu@ip-172-31-5-210:/srv/C-LARA-2$ set -a && . /etc/clara2.env && set +a
-bash: /etc/clara2.env: Permission denied
