We are making good progress. I could batch-compile all the imported project (I checked a few, they looked good), then I was able to batch-publish the first five:



$ sudo bash -lc '\n  set -a\n  . /etc/clara2.env\n  set +a\n  cd /srv/C-LARA-2/platform_server\n  exec runuser -u ubuntu -- \\n    /srv/C-LARA-2/.venv/bin/python manage.py publish_legacy_projects \\n  --source-system clara_adelaide \\n  --limit 5 \\n>   --report /tmp/legacy-publish-dry-run.jsonl\n'
> > > > > > > > > 
[1/5] 1 published
[2/5] 100 published
[3/5] 101 published
[4/5] 102 published
[5/5] 103 published
Legacy publish batch complete: published=5



I will run the full batch-publish tomorrow.



Some general news:



- Unfortunately, we never heard back from the Sprint. I think they were oversubscribed and we didn't make the cut, alternately there was some misunderstanding. 
- We have still heard nothing from EuroCALL.  I just sent this brief mail to Yazdan, who told us last week that Ana would be back at work on Thursday after returning from her annual leave:



Dear Yazdan,

We have still heard nothing from Ana. Is she in fact back from her leave? We really have no idea what is going on here.

Thank you,

Manny
