from django.urls import path
from . import views
from .views import after_login

urlpatterns = [
    path("after-login/", after_login, name="after_login"),
    path("register/", views.register, name="register"),
]