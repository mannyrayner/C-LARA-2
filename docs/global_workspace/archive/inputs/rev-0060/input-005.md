Your diagnosis sounds like it would explain things! Here's what I see when I run your test:

(.venv) ubuntu@ip-172-31-5-210:/srv/C-LARA-2$ sudo systemd-run --wait --pipe --collect \
  --property=User=ubuntu \
  --property=Group=www-data \
  --property=WorkingDirectory=/srv/C-LARA-2/platform_server \
  --property=EnvironmentFile=/etc/clara2.env \
  /srv/C-LARA-2/.venv/bin/python manage.py shell -v 0 -c '
import django_q.tasks
from django.conf import settings
from django.core.management import call_command
from django.db import connection

print("Queue implementation:", django_q.tasks.__file__)
print("Real Django Q selected:", settings.USE_REAL_DJANGO_Q)
print("Configured workers:", settings.Q_CLUSTER.get("workers"))

with connection.cursor() as cursor:
    cursor.execute("SHOW max_connections")
    print("Database connection limit:", cursor.fetchone()[0])
    cursor.execute("""
        SELECT datname, application_name, state, count(*)
        FROM pg_stat_activity
        GROUP BY datname, application_name, state
        ORDER BY count(*) DESC
    """)
    print("Connections: database, application, state, count")
    for row in cursor.fetchall():
        print(row)

call_command("showmigrations", "community_dictionary")
'
Running as unit: run-u9350.service
Queue implementation: /srv/C-LARA-2/src/django_q/tasks.py
Real Django Q selected: False
Configured workers: 2
Database connection limit: 79
Connections: database, application, state, count
(None, '', None, 6)
('rdsadmin', '', 'idle', 1)
('rdsadmin', 'PostgreSQL JDBC Driver', 'idle', 1)
('clara2', '', 'active', 1)
community_dictionary
 [X] 0001_initial
 [X] 0002_photo_learning
 [X] 0003_entry_photo_and_saved_audio
 [X] 0004_ai_defaults_and_voices
 [X] 0005_image_word_links
 [X] 0006_contribution_control
 [X] 0007_split_text_provenance
 [X] 0008_dictionary_participation
 [X] 0009_restore_experimental_collections
 [X] 0010_image_generation
 [X] 0011_languageport_portrun_contributiondependency_and_more
 [X] 0012_port_category_context
 [X] 0013_tts_pronunciation_guidance
 [X] 0014_port_review_attention
 [X] 0015_picture_descriptions
 [X] 0016_capture_daily_limit
 [X] 0017_dictionary_visibility
 [X] 0018_port_vocabulary_stages
Finished with result: success
Main processes terminated with: code=exited/status=0
Service runtime: 676ms
CPU time consumed: 617ms
Memory peak: 2.5M
Memory swap peak: 0B
