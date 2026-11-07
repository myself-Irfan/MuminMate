from django.http import HttpRequest

from users.models import User


# django-stubs' pattern: ConsumerLoginRequiredMiddleware guarantees a logged-in user here.
class AuthenticatedHttpRequest(HttpRequest):
    user: User
