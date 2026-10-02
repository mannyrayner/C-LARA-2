Here are the results:

(.venv) $ /usr/lib/postgresql/18/bin/pg_dump --version
pg_dump (PostgreSQL) 18.6 (Ubuntu 18.6-1.pgdg24.04+2)
(.venv) $ /usr/lib/postgresql/18/bin/pg_restore --version
pg_restore (PostgreSQL) 18.6 (Ubuntu 18.6-1.pgdg24.04+2)
(.venv) $ ps -C tar,gzip,pg_dump -o pid,etime,pcpu,stat,comm
    PID     ELAPSED %CPU STAT COMMAND
(.venv) $ df -h /srv/C-LARA-2 "$HOME"
Filesystem      Size  Used Avail Use% Mounted on
/dev/root        96G   49G   48G  51% /
/dev/root        96G   49G   48G  51% /
(.venv) $ sudo du -sh /srv/C-LARA-2/platform_server/media \
  /srv/C-LARA-2/platform_server/private_uploads/community_dictionary \
  "$HOME/clara2-backups"> > 
22G     /srv/C-LARA-2/platform_server/media
23M     /srv/C-LARA-2/platform_server/private_uploads/community_dictionary
5.1G    /home/ssm-user/clara2-backups

I mailed Sophie, Kate and Axel to say we would be offline for a while. I am not sure there are any people using C-LARA-2 right now.
