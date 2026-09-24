from django.urls import path

from . import views

app_name = 'community_dictionary'
urlpatterns = [
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
    path('<int:pk>/entries/<int:entry_id>/comment/', views.comment, name='comment'),
    path('<int:pk>/entries/<int:entry_id>/ask/', views.ask, name='ask'),
    path('<int:pk>/entries/<int:entry_id>/remove/', views.remove_entry, name='remove-entry'),
    path('<int:pk>/contributions/<int:contribution_id>/review/', views.review, name='review'),
    path('<int:pk>/media/<int:contribution_id>/', views.media, name='media'),
    path('<int:pk>/export/', views.export_dictionary, name='export'),
]
