from django.urls import path
from django.contrib.auth import views as auth_views

from . import audio_views, photo_views, views

app_name = 'community_dictionary'
urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='community_dictionary/login.html', next_page='community_dictionary:home'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='community_dictionary:login'), name='logout'),
    path('<int:pk>/entries/<int:entry_id>/pictures/<int:image_id>/learn/', photo_views.start, name='entry-photo'),
    path('<int:pk>/entries/<int:entry_id>/create-audio/', audio_views.start, name='audio-start'),
    path('<int:pk>/audio-preview/<uuid:study_id>/', audio_views.detail, name='audio-study'),
    path('<int:pk>/audio-preview/<uuid:study_id>/media/', audio_views.media, name='audio-media'),
    path('<int:pk>/audio-preview/<uuid:study_id>/action/', audio_views.action, name='audio-action'),
    path('<int:pk>/learn-photo/', photo_views.start, name='photo-start'),
    path('<int:pk>/learn-photo/<uuid:study_id>/', photo_views.detail, name='photo-study'),
    path('<int:pk>/learn-photo/<uuid:study_id>/image/', photo_views.media, name='photo-media'),
    path('<int:pk>/learn-photo/<uuid:study_id>/action/', photo_views.action, name='photo-action'),
    path('', views.home, name='home'),
    path('<int:pk>/join/', views.join_dictionary, name='join'),
    path('<int:pk>/', views.dictionary, name='dictionary'),
    path('<int:pk>/people/', views.people, name='people'),
    path('<int:pk>/requests/', views.queue, name='queue'),
    path('<int:pk>/requests/<int:request_id>/respond/', views.contribute, name='respond'),
    path('<int:pk>/requests/<int:request_id>/action/', views.request_action, name='request-action'),
    path('<int:pk>/new/', views.contribute, name='new'),
    path('<int:pk>/entries/<int:entry_id>/', views.entry_detail, name='entry'),
    path('<int:pk>/entries/<int:entry_id>/contribute/', views.contribute, name='contribute'),
    path('<int:pk>/entries/<int:entry_id>/record/', views.contribute, {'audio_only': True}, name='record-audio'),
    path('<int:pk>/entries/<int:entry_id>/comment/', views.comment, name='comment'),
    path('<int:pk>/entries/<int:entry_id>/ask/', views.ask, name='ask'),
    path('<int:pk>/entries/<int:entry_id>/remove/', views.remove_entry, name='remove-entry'),
    path('<int:pk>/contributions/<int:contribution_id>/review/', views.review, name='review'),
    path('<int:pk>/media/<int:contribution_id>/', views.media, name='media'),
    path('<int:pk>/export/', views.export_dictionary, name='export'),
]
