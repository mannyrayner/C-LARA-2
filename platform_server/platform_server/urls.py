from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from projects import views as project_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/register/", project_views.register, name="register"),
    path("", include("projects.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
