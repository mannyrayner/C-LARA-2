from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    path("accounts/login/", auth_views.LoginView.as_view(template_name="projects/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),
    path("accounts/profile/", views.profile, name="profile"),
    path("", views.ProjectListView.as_view(), name="project-list"),
    path("projects/new/", views.ProjectCreateView.as_view(), name="project-create"),
    path("projects/<int:pk>/", views.ProjectDetailView.as_view(), name="project-detail"),
    path("projects/<int:pk>/images/style/", views.project_image_style, name="project-image-style"),
    path("projects/<int:pk>/images/elements/", views.project_image_elements, name="project-image-elements"),
    path("projects/<int:pk>/images/pages/", views.project_image_pages, name="project-image-pages"),
    path("projects/<int:pk>/image-placement/", views.set_page_image_placement, name="project-image-placement"),
    path("projects/<int:pk>/processing-options/", views.set_processing_options, name="project-processing-options"),
    path("projects/<int:pk>/compile/", views.compile_project, name="project-compile"),
    path(
        "projects/<int:pk>/compile/monitor/<uuid:report_id>/",
        views.compile_monitor,
        name="project-compile-monitor",
    ),
    path(
        "projects/<int:pk>/compile/status/<uuid:report_id>/",
        views.compile_status,
        name="project-compile-status",
    ),
    path("projects/<int:pk>/publish/", views.toggle_publish, name="project-publish"),
    path("projects/<int:pk>/delete/", views.delete_project, name="project-delete"),
    path("projects/<int:pk>/compiled/<path:path>", views.serve_compiled, name="project-compiled"),
]
