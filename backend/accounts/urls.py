from django.urls import path

from .views import register_choice, register_customer, register_producer

urlpatterns = [
    path("register/", register_choice, name="register_choice"),
    path("register/customer/", register_customer, name="register_customer"),
    path("register/producer/", register_producer, name="register_producer"),
]