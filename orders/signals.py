from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Order, OrderItem, Payment, Refund, SupportTicket, SupportMessage
from .audit import AuditLog, SecurityEvent
import json

User = get_user_model()


def get_client_ip(request):
    """Récupère l'adresse IP du client"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_user_agent(request):
    """Récupère le User-Agent du client"""
    return request.META.get('HTTP_USER_AGENT', '')


# Signaux pour les utilisateurs
@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """Enregistre la connexion d'un utilisateur"""
    AuditLog.log_action(
        user=user,
        action_type='user_login',
        severity='low',
        description=f'Connexion de l\'utilisateur {user.email}',
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        request_path=request.path,
        request_method=request.method,
        metadata={'login_time': timezone.now().isoformat()}
    )


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """Enregistre la déconnexion d'un utilisateur"""
    if user is None:
        return
    
    AuditLog.log_action(
        user=user,
        action_type='user_logout',
        severity='low',
        description=f'Déconnexion de l\'utilisateur {user.email}',
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        request_path=request.path,
        request_method=request.method,
        metadata={'logout_time': timezone.now().isoformat()}
    )


# Signaux pour les commandes
@receiver(post_save, sender=Order)
def log_order_changes(sender, instance, created, **kwargs):
    """Enregistre les changements sur les commandes"""
    if created:
        # Nouvelle commande
        AuditLog.log_action(
            user=instance.customer,
            action_type='order_create',
            severity='medium',
            description=f'Création de la commande {instance.uid}',
            object_type='Order',
            object_id=str(instance.uid),
            new_values={
                'status': instance.status,
                'total_amount': str(instance.total_amount),
                'payment_method': instance.payment_method,
                'delivery_address': instance.delivery_address[:50] + '...' if len(instance.delivery_address) > 50 else instance.delivery_address
            },
            metadata={'order_uid': str(instance.uid)}
        )
    else:
        # Modification de commande
        if hasattr(instance, '_old_status'):
            if instance._old_status != instance.status:
                AuditLog.log_action(
                    user=instance.customer,
                    action_type='order_update',
                    severity='medium',
                    description=f'Changement de statut de la commande {instance.uid}: {instance._old_status} → {instance.status}',
                    object_type='Order',
                    object_id=str(instance.uid),
                    old_values={'status': instance._old_status},
                    new_values={'status': instance.status},
                    metadata={'order_uid': str(instance.uid)}
                )


@receiver(pre_save, sender=Order)
def capture_order_old_values(sender, instance, **kwargs):
    """Capture les anciennes valeurs avant sauvegarde"""
    if instance.pk:
        try:
            old_instance = Order.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except Order.DoesNotExist:
            pass


# Signaux pour les paiements
@receiver(post_save, sender=Payment)
def log_payment_changes(sender, instance, created, **kwargs):
    """Enregistre les changements sur les paiements"""
    if created:
        AuditLog.log_action(
            user=instance.order.customer,
            action_type='payment_create',
            severity='high',
            description=f'Création du paiement {instance.uid} pour la commande {instance.order.uid}',
            object_type='Payment',
            object_id=str(instance.uid),
            new_values={
                'amount': str(instance.amount),
                'payment_method': instance.method,
                'status': instance.status
            },
            metadata={
                'payment_uid': str(instance.uid),
                'order_uid': str(instance.order.uid)
            }
        )


# Signaux pour les remboursements
@receiver(post_save, sender=Refund)
def log_refund_changes(sender, instance, created, **kwargs):
    """Enregistre les changements sur les remboursements"""
    if created:
        AuditLog.log_action(
            user=instance.requested_by,
            action_type='payment_refund',
            severity='high',
            description=f'Demande de remboursement {instance.uid} pour la commande {instance.order.uid}',
            object_type='Refund',
            object_id=str(instance.uid),
            new_values={
                'amount': str(instance.amount),
                'reason': instance.reason,
                'status': instance.status
            },
            metadata={
                'refund_uid': str(instance.uid),
                'order_uid': str(instance.order.uid)
            }
        )
    else:
        # Modification de statut de remboursement
        if hasattr(instance, '_old_status') and instance._old_status != instance.status:
            AuditLog.log_action(
                user=instance.processed_by or instance.requested_by,
                action_type='payment_refund',
                severity='high',
                description=f'Changement de statut du remboursement {instance.uid}: {instance._old_status} → {instance.status}',
                object_type='Refund',
                object_id=str(instance.uid),
                old_values={'status': instance._old_status},
                new_values={'status': instance.status},
                metadata={
                    'refund_uid': str(instance.uid),
                    'order_uid': str(instance.order.uid)
                }
            )


@receiver(pre_save, sender=Refund)
def capture_refund_old_values(sender, instance, **kwargs):
    """Capture les anciennes valeurs avant sauvegarde"""
    if instance.pk:
        try:
            old_instance = Refund.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except Refund.DoesNotExist:
            pass


# Signaux pour les tickets de support
@receiver(post_save, sender=SupportTicket)
def log_support_ticket_changes(sender, instance, created, **kwargs):
    """Enregistre les changements sur les tickets de support"""
    if created:
        AuditLog.log_action(
            user=instance.customer,
            action_type='support_ticket_create',
            severity='medium',
            description=f'Création du ticket de support {instance.uid}',
            object_type='SupportTicket',
            object_id=str(instance.uid),
            new_values={
                'category': instance.category,
                'priority': instance.priority,
                'status': instance.status
            },
            metadata={'ticket_uid': str(instance.uid)}
        )
    else:
        # Modification de statut de ticket
        if hasattr(instance, '_old_status') and instance._old_status != instance.status:
            AuditLog.log_action(
                user=instance.assigned_to or instance.customer,
                action_type='support_ticket_update',
                severity='medium',
                description=f'Changement de statut du ticket {instance.uid}: {instance._old_status} → {instance.status}',
                object_type='SupportTicket',
                object_id=str(instance.uid),
                old_values={'status': instance._old_status},
                new_values={'status': instance.status},
                metadata={'ticket_uid': str(instance.uid)}
            )


@receiver(pre_save, sender=SupportTicket)
def capture_support_ticket_old_values(sender, instance, **kwargs):
    """Capture les anciennes valeurs avant sauvegarde"""
    if instance.pk:
        try:
            old_instance = SupportTicket.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except SupportTicket.DoesNotExist:
            pass


# Signaux pour les messages de support
@receiver(post_save, sender=SupportMessage)
def log_support_message_creation(sender, instance, created, **kwargs):
    """Enregistre la création de messages de support"""
    if created:
        AuditLog.log_action(
            user=instance.author,
            action_type='support_ticket_update',
            severity='low',
            description=f'Ajout d\'un message au ticket {instance.ticket.uid}',
            object_type='SupportMessage',
            object_id=str(instance.pk),
            metadata={
                'ticket_uid': str(instance.ticket.uid),
                'is_internal': instance.is_internal
            }
        )


# Signaux pour les suppressions
@receiver(post_delete, sender=Order)
def log_order_deletion(sender, instance, **kwargs):
    """Enregistre la suppression d'une commande"""
    AuditLog.log_action(
        user=None,  # L'utilisateur peut ne plus exister
        action_type='order_delete',
        severity='critical',
        description=f'Suppression de la commande {instance.uid}',
        object_type='Order',
        object_id=str(instance.uid),
        metadata={'deleted_order_uid': str(instance.uid)}
    )


@receiver(post_delete, sender=Payment)
def log_payment_deletion(sender, instance, **kwargs):
    """Enregistre la suppression d'un paiement"""
    AuditLog.log_action(
        user=None,
        action_type='payment_update',
        severity='critical',
        description=f'Suppression du paiement {instance.uid}',
        object_type='Payment',
        object_id=str(instance.uid),
        metadata={'deleted_payment_uid': str(instance.uid)}
    )
