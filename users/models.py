from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db.models.signals import post_save
from django.dispatch import receiver
import uuid
import secrets
import string

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    # Types d'utilisateurs
    USER_TYPE_CHOICES = [
        ('admin', 'Administrateur Général'),
        ('manager', 'Gestionnaire'),
        ('client', 'Client'),
    ]
    
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='client')
    is_active = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    username = None
    
    # Gestion des mots de passe
    must_change_password = models.BooleanField(default=False)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    temporary_password = models.BooleanField(default=False)
    
    # Authentification à deux facteurs
    two_factor_enabled = models.BooleanField(default=False)
    two_factor_method = models.CharField(
        max_length=10,
        choices=[
            ('email', 'Email'),
            ('sms', 'SMS'),
        ],
        default='email'
    )
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    two_factor_backup_codes = models.JSONField(default=list, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    EMAIL_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_user_type_display()})"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self):
        return self.first_name

    def is_admin(self):
        return self.user_type == 'admin' or self.is_superuser

    def is_manager(self):
        return self.user_type == 'manager'

    def is_client(self):
        return self.user_type == 'client'

    @staticmethod
    def generate_temporary_password(length=12):
        """Génère un mot de passe temporaire sécurisé"""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        return password

    def set_temporary_password(self, password=None):
        """Définit un mot de passe temporaire"""
        if password is None:
            password = self.generate_temporary_password()
        
        self.set_password(password)
        self.must_change_password = True
        self.temporary_password = True
        self.password_changed_at = None
        self.save()
        return password

    def change_password(self, new_password):
        """Change le mot de passe et met à jour les flags"""
        self.set_password(new_password)
        self.must_change_password = False
        self.temporary_password = False
        self.password_changed_at = timezone.now()
        self.save()


class UserProfile(models.Model):
    """Profil utilisateur avec informations supplémentaires"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=10, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    birth_date = models.DateField(blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Profil Utilisateur'
        verbose_name_plural = 'Profils Utilisateurs'

    def __str__(self):
        return f"Profil de {self.user.get_full_name()}"

    def get_full_address(self):
        """Retourne l'adresse complète formatée"""
        parts = [self.address, self.city, self.postal_code, self.country]
        return ', '.join(filter(None, parts))


class TwoFactorSession(models.Model):
    """
    Modèle pour gérer les sessions 2FA
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='two_factor_sessions')
    session_key = models.CharField(max_length=100, unique=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    
    def __str__(self):
        return f"2FA Session for {self.user.email}"
    
    def is_expired(self):
        return timezone.now() > self.expires_at


class TwoFactorAttempt(models.Model):
    """
    Modèle pour tracer les tentatives 2FA
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='two_factor_attempts')
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    success = models.BooleanField(default=False)
    method = models.CharField(max_length=10, choices=[('email', 'Email'), ('sms', 'SMS'), ('backup', 'Code de sauvegarde')])
    created_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"2FA Attempt for {self.user.email} - {'Success' if self.success else 'Failed'}"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Crée automatiquement un profil utilisateur lors de la création d'un utilisateur"""
    if created:
        # Vérifier si le profil n'existe pas déjà
        if not hasattr(instance, 'profile'):
            UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Sauvegarde automatiquement le profil utilisateur"""
    if hasattr(instance, 'profile'):
        instance.profile.save()
