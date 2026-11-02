"""
URL configuration for mechora project.

Routes:
- / : Role-based Engineer/Supervisor sign-in page
- /admin/ : Django Unfold Administration and Authentication Portal
"""

from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.shortcuts import redirect
from django.urls import include, path



def root_redirect(request):
    """Make the role-based sign-in screen the public landing page."""
    return redirect("login")


urlpatterns = [
    path("", root_redirect, name="root_redirect"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("api/auth/", include("accounts.api_urls")),
    path("assistant/", include("assistant.urls")),
    path("engineer/", include("machines.urls")),
    path("api/machines/", include("machines.api_urls")),
    path("api/assistant/", include("assistant.api_urls")),
    path("api/manuals/", include("manuals.urls")),
]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
