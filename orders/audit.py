from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid
import json

User = get_user_model()


class AuditLog(models.Model):
    """
    Modèle pour tracer toutes les actions sensibles dans l'application
    """
    ACTION_TYPES = [
        ('user_login', 'Connexion utilisateur'),
        ('user_logout', 'Déconnexion utilisateur'),
        ('user_register', 'Inscription utilisateur'),
        ('user_activate', 'Activation compte utilisateur'),
        ('user_deactivate', 'Désactivation compte utilisateur'),
        ('user_password_change', 'Changement mot de passe'),
        ('user_password_reset', 'Réinitialisation mot de passe'),
        ('order_create', 'Création commande'),
        ('order_update', 'Modification commande'),
        ('order_cancel', 'Annulation commande'),
        ('order_delete', 'Suppression commande'),
        ('payment_create', 'Création paiement'),
        ('payment_update', 'Modification paiement'),
        ('payment_refund', 'Remboursement'),
        ('product_create', 'Création produit'),
        ('product_update', 'Modification produit'),
        ('product_delete', 'Suppression produit'),
        ('category_create', 'Création catégorie'),
        ('category_update', 'Modification catégorie'),
        ('category_delete', 'Suppression catégorie'),
        ('support_ticket_create', 'Création ticket support'),
        ('support_ticket_update', 'Modification ticket support'),
        ('support_ticket_close', 'Fermeture ticket support'),
        ('admin_access', 'Accès admin'),
        ('manager_access', 'Accès gestionnaire'),
        ('data_export', 'Export données'),
        ('data_import', 'Import données'),
        ('system_config_change', 'Modification configuration système'),
        ('security_event', 'Événement sécurité'),
        ('other', 'Autre'),
    ]
    
    SEVERITY_LEVELS = [
        ('low', 'Faible'),
        ('medium', 'Moyen'),
        ('high', 'Élevé'),
        ('critical', 'Critique'),
    ]
    
    uid = models.UUIDField(default=uuid.uuid4, unique=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action_type = models.CharField(max_length=30, choices=ACTION_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS, default='medium')
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    request_path = models.CharField(max_length=500, blank=True, null=True)
    request_method = models.CharField(max_length=10, blank=True, null=True)
    object_type = models.CharField(max_length=100, blank=True, null=True)
    object_id = models.CharField(max_length=100, blank=True, null=True)
    old_values = models.JSONField(blank=True, null=True)
    new_values = models.JSONField(blank=True, null=True)
    metadata = models.JSONField(blank=True, null=True)
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['action_type', 'created_at']),
            models.Index(fields=['severity', 'created_at']),
            models.Index(fields=['object_type', 'object_id']),
            models.Index(fields=['ip_address', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_action_type_display()} - {self.user or 'Système'} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
    @classmethod
    def log_action(cls, user=None, action_type='other', severity='medium', description='', 
                   ip_address=None, user_agent=None, request_path=None, request_method=None,
                   object_type=None, object_id=None, old_values=None, new_values=None,
                   metadata=None, success=True, error_message=None):
        """
        Méthode utilitaire pour enregistrer une action d'audit
        """
        return cls.objects.create(
            user=user,
            action_type=action_type,
            severity=severity,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            request_path=request_path,
            request_method=request_method,
            object_type=object_type,
            object_id=object_id,
            old_values=old_values,
            new_values=new_values,
            metadata=metadata,
            success=success,
            error_message=error_message
        )
    
    def get_changes_summary(self):
        """
        Retourne un résumé des changements effectués
        """
        if not self.old_values or not self.new_values:
            return "Aucun changement détecté"
        
        changes = []
        for key, new_value in self.new_values.items():
            old_value = self.old_values.get(key)
            if old_value != new_value:
                changes.append(f"{key}: {old_value} → {new_value}")
        
        return "; ".join(changes) if changes else "Aucun changement détecté"


class SecurityEvent(models.Model):
    """
    Modèle pour tracer les événements de sécurité spécifiques
    """
    EVENT_TYPES = [
        ('failed_login', 'Tentative de connexion échouée'),
        ('brute_force_attempt', 'Tentative de force brute'),
        ('suspicious_activity', 'Activité suspecte'),
        ('unauthorized_access', 'Tentative d\'accès non autorisé'),
        ('data_breach_attempt', 'Tentative de violation de données'),
        ('malicious_request', 'Requête malveillante'),
        ('rate_limit_exceeded', 'Limite de taux dépassée'),
        ('ip_blocked', 'IP bloquée'),
        ('account_locked', 'Compte verrouillé'),
        ('password_compromise', 'Compromission de mot de passe'),
        ('session_hijack', 'Tentative de détournement de session'),
        ('csrf_attack', 'Attaque CSRF'),
        ('xss_attempt', 'Tentative XSS'),
        ('sql_injection_attempt', 'Tentative d\'injection SQL'),
        ('file_upload_attack', 'Attaque par upload de fichier'),
        ('other', 'Autre'),
    ]
    
    SEVERITY_LEVELS = [
        ('low', 'Faible'),
        ('medium', 'Moyen'),
        ('high', 'Élevé'),
        ('critical', 'Critique'),
    ]
    
    uid = models.UUIDField(default=uuid.uuid4, unique=True)
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS, default='medium')
    description = models.TextField()
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='security_events')
    request_path = models.CharField(max_length=500, blank=True, null=True)
    request_method = models.CharField(max_length=10, blank=True, null=True)
    request_data = models.JSONField(blank=True, null=True)
    response_status = models.IntegerField(blank=True, null=True)
    blocked = models.BooleanField(default=False)
    action_taken = models.TextField(blank=True, null=True)
    metadata = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_type', 'created_at']),
            models.Index(fields=['severity', 'created_at']),
            models.Index(fields=['ip_address', 'created_at']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['blocked', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_event_type_display()} - {self.ip_address} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
    @classmethod
    def log_security_event(cls, event_type='other', severity='medium', description='',
                          ip_address=None, user_agent=None, user=None, request_path=None,
                          request_method=None, request_data=None, response_status=None,
                          blocked=False, action_taken=None, metadata=None):
        """
        Méthode utilitaire pour enregistrer un événement de sécurité
        """
        return cls.objects.create(
            event_type=event_type,
            severity=severity,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            user=user,
            request_path=request_path,
            request_method=request_method,
            request_data=request_data,
            response_status=response_status,
            blocked=blocked,
            action_taken=action_taken,
            metadata=metadata
        )
