Before I go further, here's the output from the first block:

$ ls -ld "$CLARA_STATIC_ROOT" \
  "$CLARA_STATIC_ROOT/community_dictionary"
> drwxr-xr-x 5 ssm-user ssm-user 4096 Sep 25 05:54 /srv/C-LARA-2/platform_server/staticfiles
drwxrwxr-x 2 ssm-user ssm-user 4096 Oct  8 10:20 /srv/C-LARA-2/platform_server/staticfiles/community_dictionary
$ ls -l "$CLARA_STATIC_ROOT/community_dictionary/practice.js"
-rw-r--r-- 1 ssm-user ssm-user 18274 Oct  4 02:32 /srv/C-LARA-2/platform_server/staticfiles/community_dictionary/practice.js
$ ls -l "$CLARA_STATIC_ROOT/community_dictionary/practice.js"
-rw-r--r-- 1 ssm-user ssm-user 18274 Oct  4 02:32 /srv/C-LARA-2/platform_server/staticfiles/community_dictionary/practice.js
$ 

Proceed to the next one?
