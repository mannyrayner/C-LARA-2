from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.templatetags.static import static as static_url
from django.urls import include, path
from django.views.generic.base import RedirectView
from projects import views as project_views

urlpatterns = [
    path("favicon.ico", project_views.favicon, name="favicon"),
    path("admin/", admin.site.urls),
    path("accounts/register/", project_views.register, name="register"),
    path("", include("projects.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
