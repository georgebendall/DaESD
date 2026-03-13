from django.urls import path

from .views import after_login, register_choice, register_customer, register_producer

urlpatterns = [
    path("after-login/", after_login, name="after_login"),
    path("register/", register_choice, name="register_choice"),
    path("register/customer/", register_customer, name="register_customer"),
    path("register/producer/", register_producer, name="register_producer"),
]