#!/usr/bin/env python
import os
import sys

def main():
    # Force the platform settings module so host-level DJANGO_SETTINGS_MODULE
    # values (e.g., from other Django projects) cannot leak into this server.
    os.environ["DJANGO_SETTINGS_MODULE"] = "platform_server.settings"
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
