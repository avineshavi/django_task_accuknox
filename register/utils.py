from django.conf import settings
from django.utils import timezone
from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
import hashlib


class User(AbstractUser):

    email = models.EmailField(unique=True)

    groups = models.ManyToManyField(
        Group,
        related_name='custom_user_set',  # Change the related name
        blank=True,
    )
    
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='custom_user_set',  # Change the related name
        blank=True,
    )

    def save(self, *args, **kwargs):
        """Override the save method to encrypt the email before saving."""
        if self.email:
            self.email = encrypt_email(email=self.email)
        super().save(*args, **kwargs)
    
def encrypt_email(email):
    """Encrypt the email using Fernet encryption."""
    if email:
        return hashlib.sha256(email.encode()).hexdigest()
    return email

 
def set_jwt_token_cookie(response, refresh_token=None):
    """
    Util method to set the access token in cookie
    """
    if refresh_token:
        key = settings.AUTH_COOKIE_REFRESH
        expires_in = timezone.now() + settings.SIMPLE_JWT[
            'REFRESH_TOKEN_LIFETIME']
        response.set_signed_cookie(
            key=key,
            value=refresh_token,
            salt=settings.AUTH_COOKIE_SALT,
            domain=settings.TOKEN_COOKIE_DOMAIN,
            expires=expires_in,
            secure=settings.SESSION_COOKIE_SECURE,
            httponly=settings.SESSION_COOKIE_HTTPONLY,
            samesite=settings.SESSION_COOKIE_SAMESITE
        )

def add_access_token_validity_cookie(response, is_yc_user=False):
    """
    Method for updating access token expiry cookie
    """
    key = 'access_token_expiry'
    expires_in = timezone.now() + settings.SIMPLE_JWT[
        'ACCESS_TOKEN_LIFETIME']

    response.set_cookie(
        key=key,
        value=expires_in,
        expires=expires_in,
        domain=settings.TOKEN_COOKIE_DOMAIN,
        secure=settings.SESSION_COOKIE_SECURE,
    )
