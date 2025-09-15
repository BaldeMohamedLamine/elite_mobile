from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class CustomAuthentication(ModelBackend):
    """
    Backend d'authentification personnalisé avec vérifications de sécurité
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authentifie un utilisateur avec des vérifications de sécurité
        """
        if username is None or password is None:
            return None
            
        try:
            # Rechercher l'utilisateur par email
            user = User.objects.get(email=username)
        except User.DoesNotExist:
            # Enregistrer la tentative de connexion échouée
            self._log_failed_attempt(request, username, "User not found")
            return None
        except User.MultipleObjectsReturned:
            # En cas de doublons (ne devrait pas arriver avec unique=True)
            logger.error(f"Multiple users found with email: {username}")
            return None
        
        # Vérifier si l'utilisateur est actif
        if not user.is_active:
            self._log_failed_attempt(request, username, "Inactive user")
            return None
            
        # Vérifier le mot de passe
        if not user.check_password(password):
            self._log_failed_attempt(request, username, "Invalid password")
            return None
            
        # Vérifier si l'utilisateur doit changer son mot de passe
        if user.must_change_password:
            # Permettre la connexion mais forcer le changement de mot de passe
            logger.info(f"User {username} must change password")
            
        # Enregistrer la connexion réussie
        self._log_successful_attempt(request, user)
        
        return user
    
    def _log_failed_attempt(self, request, username, reason):
        """Enregistre une tentative de connexion échouée"""
        try:
            from orders.audit import AuditLog
            AuditLog.log_action(
                user=None,
                action_type='user_login',
                severity='medium',
                description=f"Failed login attempt for {username}: {reason}",
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                request_path=request.get_full_path(),
                request_method=request.method,
                success=False,
                error_message=reason
            )
        except Exception as e:
            logger.error(f"Error logging failed attempt: {e}")
    
    def _log_successful_attempt(self, request, user):
        """Enregistre une connexion réussie"""
        try:
            from orders.audit import AuditLog
            AuditLog.log_action(
                user=user,
                action_type='user_login',
                severity='low',
                description=f"Successful login for {user.email}",
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                request_path=request.get_full_path(),
                request_method=request.method,
                success=True
            )
        except Exception as e:
            logger.error(f"Error logging successful attempt: {e}")
    
    def _get_client_ip(self, request):
        """Récupère l'IP réelle du client"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def get_user(self, user_id):
        """Récupère un utilisateur par son ID"""
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
