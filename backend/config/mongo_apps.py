# config/mongo_apps.py
# These classes replace Django's default "auth" and "contenttypes" app configs.
# We force them to use MongoDB's ObjectId primary key instead of AutoField.

from django.contrib.auth.apps import AuthConfig
from django.contrib.contenttypes.apps import ContentTypesConfig

class MongoAuthConfig(AuthConfig):
    default_auto_field = "django_mongodb_backend.fields.ObjectIdAutoField"

class MongoContentTypesConfig(ContentTypesConfig):
    default_auto_field = "django_mongodb_backend.fields.ObjectIdAutoField"