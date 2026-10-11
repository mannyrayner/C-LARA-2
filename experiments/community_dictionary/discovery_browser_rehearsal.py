"""Disposable discovery/profile/member-request rehearsal; no email or AI calls."""
from public_browsing_browser_rehearsal import main

if __name__ == '__main__':
    main('discovery_browser_workflow.cjs', "\nget_user_model().objects.create_user('learner', 'learner@example.org', 'browser-test-password-948')\n")
