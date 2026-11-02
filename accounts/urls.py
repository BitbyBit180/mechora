from django.urls import path

from .views import login_view, logout_view, signup_view


urlpatterns = [
    path("login/", login_view, name="login"),
    path("signin/", login_view, name="signin"),
    path("signup/", signup_view, name="signup"),
    path("logout/", logout_view, name="logout"),
]
