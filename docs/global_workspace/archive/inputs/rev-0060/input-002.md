For (1), I see this:

ubuntu@ip-172-31-5-210:~$ sudo journalctl -u gunicorn-clara2 -u djangoq-clara2 \
  --since "10 minutes ago" -n 180 --no-pager
Oct 09 09:27:16 ip-172-31-5-210 gunicorn[932265]:  - - [09/Oct/2026:09:27:16 +0000] "GET /community-dictionaries/10/new/ HTTP/1.0" 500 145 "https://c-lara-2.c-lara.org/community-dictionaries/10/entries/1982/" "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36"
Oct 09 09:27:19 ip-172-31-5-210 gunicorn[932266]:  - - [09/Oct/2026:09:27:19 +0000] "GET /community-dictionaries/10/entries/1982/ HTTP/1.0" 500 145 "https://c-lara-2.c-lara.org/community-dictionaries/10/new/" "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36"
Oct 09 09:27:22 ip-172-31-5-210 gunicorn[932264]:  - - [09/Oct/2026:09:27:22 +0000] "GET /community-dictionaries/10/new/ HTTP/1.0" 500 145 "https://c-lara-2.c-lara.org/community-dictionaries/10/entries/1981/" "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36"
Oct 09 09:27:27 ip-172-31-5-210 gunicorn[932264]:  - - [09/Oct/2026:09:27:27 +0000] "GET /community-dictionaries/ HTTP/1.0" 500 145 "-" "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36"
Oct 09 09:27:33 ip-172-31-5-210 gunicorn[932266]:  - - [09/Oct/2026:09:27:33 +0000] "GET /community-dictionaries/ HTTP/1.0" 500 145 "-" "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36"
Oct 09 09:29:25 ip-172-31-5-210 gunicorn[932264]:  - - [09/Oct/2026:09:29:25 +0000] "GET /admin-tools/ HTTP/1.0" 500 145 "https://c-lara-2.c-lara.org/admin-tools/" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
Oct 09 09:29:25 ip-172-31-5-210 gunicorn[932264]:  - - [09/Oct/2026:09:29:25 +0000] "GET /favicon.ico HTTP/1.0" 200 0 "https://c-lara-2.c-lara.org/admin-tools/" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
Oct 09 09:33:54 ip-172-31-5-210 gunicorn[932265]:  - - [09/Oct/2026:09:33:54 +0000] "GET / HTTP/1.0" 500 145 "-" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
