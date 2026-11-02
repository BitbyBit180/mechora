"""
URL configuration for mechora project.

Routes:
- /admin/ : Django Unfold Administration and Authentication Portal
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path


def root_redirect(request):
    """Convenience redirect from root to admin panel."""
    return redirect("admin:index")


urlpatterns = [
    path("", root_redirect, name="root_redirect"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("assistant/", include("assistant.urls")),
    path("api/assistant/", include("assistant.api_urls")),
    path("api/manuals/", include("manuals.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
