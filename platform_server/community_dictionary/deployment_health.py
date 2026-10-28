"""Content-free readiness and optional deployment admission control."""
import re
import subprocess

from django.conf import settings
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe
from core import deployment_activity

HEALTH_PATH = '/community-dictionaries/deployment-health/'
RELEASE = ''


def capture_release():
    """Freeze identity at Django startup, not when somebody later moves HEAD."""
    global RELEASE
    if deployment_activity.directory() is None:
        return
    try:
        repo = settings.BASE_DIR.parent.resolve()
        # AWS's service user differs from the checkout owner. Trust only this
        # configured checkout for this read; do not change global Git policy.
        result = subprocess.run(['git', '-c', 'safe.directory=' + str(repo), 'rev-parse', 'HEAD'], cwd=repo,
                                capture_output=True, text=True, check=True, timeout=5)
        value = result.stdout.strip()
        RELEASE = value if re.fullmatch(r'[0-9a-f]{40}', value) else ''
    except (OSError, subprocess.SubprocessError):
        RELEASE = ''


@never_cache
@require_safe
def health(request):
    if deployment_activity.directory() is None:
        return HttpResponse(status=404)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            healthy = cursor.fetchone()[0] == 1 and bool(RELEASE)
    except Exception:
        healthy = False
    response = JsonResponse({'ready': healthy, 'release': RELEASE,
                             'maintenance': deployment_activity.paused()}, status=200 if healthy else 503)
    response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    return response


class DeploymentMiddleware:
    """When opted in, cover both applications and every in-flight HTTP request."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == HEALTH_PATH or deployment_activity.directory() is None:
            return self.get_response(request)
        try:
            lease = deployment_activity.acquire('request')
        except deployment_activity.Maintenance:
            response = HttpResponse('A short update is in progress. Please try again shortly.', status=503)
            response['Retry-After'] = '30'
            response['Cache-Control'] = 'no-store'
            return response
        try:
            response = self.get_response(request)
        except BaseException:
            deployment_activity.release(lease)
            raise
        if response.streaming:
            # Streaming responses continue after middleware returns. Django calls
            # close even on client disconnect; FileResponse already relies on it.
            response._resource_closers.append(lambda: deployment_activity.release(lease))
        else:
            deployment_activity.release(lease)
        return response
