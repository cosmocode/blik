"""Log in with the email address as well as the username."""
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User


class EmailBackend(ModelBackend):
    """
    Accept the email address in the username field; ModelBackend before it handles the username.

    Email addresses are not unique in the database, so each user with that address is tried.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not (username and password):
            return None

        for user in User.objects.filter(email__iexact=username):
            if user.check_password(password) and self.user_can_authenticate(user):
                return user

        return None
