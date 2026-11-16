from django.http import HttpResponseNotFound
from django.urls import path
from .urls import urlpatterns as normal_patterns


urlpatterns = [path('accounts/register/', lambda request: HttpResponseNotFound())] + normal_patterns
