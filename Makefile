.PHONY: run-platform

# Launch the Django dev server (runs migrations first)
run-platform:
	cd platform_server && python manage.py migrate && python manage.py runserver
