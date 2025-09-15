"""
Services de notification pour le système e-commerce
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from django.conf import settings
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction

from .models import (
    Notification, NotificationTemplate, NotificationPreference, 
    NotificationLog, AlertRule, Alert
)

User = get_user_model()
logger = logging.getLogger(__name__)


class NotificationService:
    """Service principal pour la gestion des notifications"""
    
    def __init__(self):
        self.email_service = EmailNotificationService()
        self.sms_service = SMSNotificationService()
        self.push_service = PushNotificationService()
        self.in_app_service = InAppNotificationService()
    
    def send_notification(
        self, 
        user: User, 
        template: NotificationTemplate, 
        context: Dict[str, Any] = None,
        priority: str = 'normal',
        scheduled_at: datetime = None
    ) -> Notification:
        """Envoyer une notification à un utilisateur"""
        if context is None:
            context = {}
        
        # Vérifier les préférences de l'utilisateur
        preferences = self._get_user_preferences(user)
        if not self._should_send_notification(preferences, template):
            logger.info(f"Notification non envoyée pour {user.username} - préférences")
            return None
        
        # Créer la notification
        notification = self._create_notification(
            user, template, context, priority, scheduled_at
        )
        
        # Programmer l'envoi
        if scheduled_at and scheduled_at > timezone.now():
            # Notification programmée
            notification.scheduled_at = scheduled_at
            notification.save()
        else:
            # Envoi immédiat
            self._send_notification_immediately(notification)
        
        return notification
    
    def send_bulk_notifications(
        self, 
        users: List[User], 
        template: NotificationTemplate, 
        context: Dict[str, Any] = None,
        priority: str = 'normal'
    ) -> List[Notification]:
        """Envoyer des notifications en masse"""
        notifications = []
        
        for user in users:
            notification = self.send_notification(
                user, template, context, priority
            )
            if notification:
                notifications.append(notification)
        
        return notifications
    
    def _get_user_preferences(self, user: User) -> NotificationPreference:
        """Récupérer les préférences de notification de l'utilisateur"""
        preferences, created = NotificationPreference.objects.get_or_create(
            user=user,
            defaults={
                'email_enabled': True,
                'sms_enabled': False,
                'push_enabled': True,
                'in_app_enabled': True,
            }
        )
        return preferences
    
    def _should_send_notification(
        self, 
        preferences: NotificationPreference, 
        template: NotificationTemplate
    ) -> bool:
        """Vérifier si la notification doit être envoyée selon les préférences"""
        # Vérifier les heures silencieuses
        if preferences.is_quiet_time():
            return False
        
        # Vérifier le type de notification
        if template.notification_type == 'email' and not preferences.email_enabled:
            return False
        elif template.notification_type == 'sms' and not preferences.sms_enabled:
            return False
        elif template.notification_type == 'push' and not preferences.push_enabled:
            return False
        elif template.notification_type == 'in_app' and not preferences.in_app_enabled:
            return False
        
        # Vérifier les préférences par déclencheur
        trigger_mapping = {
            'order_created': preferences.order_notifications,
            'order_shipped': preferences.order_notifications,
            'order_delivered': preferences.order_notifications,
            'payment_received': preferences.payment_notifications,
            'stock_low': preferences.stock_notifications,
            'price_drop': preferences.price_notifications,
            'new_review': preferences.review_notifications,
            'promotion': preferences.promotion_notifications,
        }
        
        return trigger_mapping.get(template.trigger_type, True)
    
    def _create_notification(
        self, 
        user: User, 
        template: NotificationTemplate, 
        context: Dict[str, Any],
        priority: str,
        scheduled_at: datetime
    ) -> Notification:
        """Créer une notification"""
        # Rendre le contenu avec le contexte
        subject = self._render_template(template.subject, context)
        message = self._render_template(template.content, context)
        
        notification = Notification.objects.create(
            user=user,
            template=template,
            title=subject,
            message=message,
            notification_type=template.notification_type,
            priority=priority,
            scheduled_at=scheduled_at,
            context_data=context
        )
        
        return notification
    
    def _render_template(self, template_content: str, context: Dict[str, Any]) -> str:
        """Rendre un template avec le contexte"""
        try:
            from django.template import Template, Context
            template = Template(template_content)
            return template.render(Context(context))
        except Exception as e:
            logger.error(f"Erreur lors du rendu du template: {e}")
            return template_content
    
    def _send_notification_immediately(self, notification: Notification):
        """Envoyer une notification immédiatement"""
        try:
            if notification.notification_type == 'email':
                self.email_service.send(notification)
            elif notification.notification_type == 'sms':
                self.sms_service.send(notification)
            elif notification.notification_type == 'push':
                self.push_service.send(notification)
            elif notification.notification_type == 'in_app':
                self.in_app_service.send(notification)
            
            notification.mark_as_sent()
            
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de la notification {notification.uid}: {e}")
            notification.status = 'failed'
            notification.save()
    
    def process_scheduled_notifications(self):
        """Traiter les notifications programmées"""
        now = timezone.now()
        scheduled_notifications = Notification.objects.filter(
            status='pending',
            scheduled_at__lte=now
        )
        
        for notification in scheduled_notifications:
            self._send_notification_immediately(notification)


class EmailNotificationService:
    """Service d'envoi d'emails"""
    
    def send(self, notification: Notification) -> bool:
        """Envoyer un email"""
        try:
            user = notification.user
            context = notification.context_data
            context.update({
                'user': user,
                'notification': notification,
            })
            
            # Rendre le contenu HTML si disponible
            html_content = None
            if notification.template and notification.template.html_content:
                html_content = self._render_template(
                    notification.template.html_content, context
                )
            
            # Envoyer l'email
            if html_content:
                msg = EmailMultiAlternatives(
                    subject=notification.title,
                    body=notification.message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[user.email]
                )
                msg.attach_alternative(html_content, "text/html")
                msg.send()
            else:
                send_mail(
                    subject=notification.title,
                    message=notification.message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False
                )
            
            # Log de l'envoi
            NotificationLog.objects.create(
                notification=notification,
                provider='django_email',
                status='sent',
                response_data={'email': user.email}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de l'email: {e}")
            
            # Log de l'erreur
            NotificationLog.objects.create(
                notification=notification,
                provider='django_email',
                status='failed',
                error_message=str(e)
            )
            
            return False
    
    def _render_template(self, template_content: str, context: Dict[str, Any]) -> str:
        """Rendre un template HTML"""
        try:
            from django.template import Template, Context
            template = Template(template_content)
            return template.render(Context(context))
        except Exception as e:
            logger.error(f"Erreur lors du rendu du template HTML: {e}")
            return template_content


class SMSNotificationService:
    """Service d'envoi de SMS"""
    
    def send(self, notification: Notification) -> bool:
        """Envoyer un SMS"""
        try:
            # Ici, vous intégreriez avec un service SMS comme Twilio, Orange, etc.
            # Pour l'instant, on simule l'envoi
            
            user = notification.user
            phone_number = getattr(user, 'phone_number', None)
            
            if not phone_number:
                logger.warning(f"Pas de numéro de téléphone pour {user.username}")
                return False
            
            # Simulation d'envoi SMS
            logger.info(f"SMS envoyé à {phone_number}: {notification.message}")
            
            # Log de l'envoi
            NotificationLog.objects.create(
                notification=notification,
                provider='sms_simulator',
                status='sent',
                response_data={'phone': phone_number}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi du SMS: {e}")
            
            # Log de l'erreur
            NotificationLog.objects.create(
                notification=notification,
                provider='sms_simulator',
                status='failed',
                error_message=str(e)
            )
            
            return False


class PushNotificationService:
    """Service de notifications push"""
    
    def send(self, notification: Notification) -> bool:
        """Envoyer une notification push"""
        try:
            # Ici, vous intégreriez avec Firebase, OneSignal, etc.
            # Pour l'instant, on simule l'envoi
            
            user = notification.user
            
            # Simulation d'envoi push
            logger.info(f"Push notification envoyée à {user.username}: {notification.title}")
            
            # Log de l'envoi
            NotificationLog.objects.create(
                notification=notification,
                provider='push_simulator',
                status='sent',
                response_data={'user_id': user.id}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de la notification push: {e}")
            
            # Log de l'erreur
            NotificationLog.objects.create(
                notification=notification,
                provider='push_simulator',
                status='failed',
                error_message=str(e)
            )
            
            return False


class InAppNotificationService:
    """Service de notifications in-app"""
    
    def send(self, notification: Notification) -> bool:
        """Créer une notification in-app"""
        try:
            # Les notifications in-app sont stockées en base
            # et affichées dans l'interface utilisateur
            
            notification.status = 'sent'
            notification.save()
            
            # Log de l'envoi
            NotificationLog.objects.create(
                notification=notification,
                provider='in_app',
                status='sent',
                response_data={'user_id': notification.user.id}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la création de la notification in-app: {e}")
            
            # Log de l'erreur
            NotificationLog.objects.create(
                notification=notification,
                provider='in_app',
                status='failed',
                error_message=str(e)
            )
            
            return False


class AlertService:
    """Service de gestion des alertes"""
    
    def check_alert_rules(self):
        """Vérifier toutes les règles d'alerte"""
        active_rules = AlertRule.objects.filter(is_active=True)
        
        for rule in active_rules:
            if rule.can_trigger():
                if self._evaluate_rule(rule):
                    self._trigger_alert(rule)
    
    def _evaluate_rule(self, rule: AlertRule) -> bool:
        """Évaluer une règle d'alerte"""
        try:
            alert_type = rule.alert_type
            
            if alert_type == 'stock_low':
                return self._check_stock_low(rule)
            elif alert_type == 'stock_out':
                return self._check_stock_out(rule)
            elif alert_type == 'price_change':
                return self._check_price_change(rule)
            elif alert_type == 'order_high_value':
                return self._check_high_value_order(rule)
            elif alert_type == 'payment_failed':
                return self._check_payment_failed(rule)
            elif alert_type == 'review_negative':
                return self._check_negative_review(rule)
            # Ajouter d'autres types d'alertes selon les besoins
            
            return False
            
        except Exception as e:
            logger.error(f"Erreur lors de l'évaluation de la règle {rule.name}: {e}")
            return False
    
    def _check_stock_low(self, rule: AlertRule) -> bool:
        """Vérifier les stocks faibles"""
        from .models import Product
        
        threshold = rule.threshold_value or 10
        low_stock_products = Product.objects.filter(
            stock_quantity__lte=threshold,
            stock_quantity__gt=0
        )
        
        return low_stock_products.exists()
    
    def _check_stock_out(self, rule: AlertRule) -> bool:
        """Vérifier les ruptures de stock"""
        from .models import Product
        
        out_of_stock_products = Product.objects.filter(stock_quantity=0)
        return out_of_stock_products.exists()
    
    def _check_price_change(self, rule: AlertRule) -> bool:
        """Vérifier les changements de prix"""
        # Implémentation selon vos besoins
        return False
    
    def _check_high_value_order(self, rule: AlertRule) -> bool:
        """Vérifier les commandes de forte valeur"""
        from orders.models import Order
        
        threshold = rule.threshold_value or 1000000  # 1M GNF
        recent_high_value_orders = Order.objects.filter(
            total_amount__gte=threshold,
            created_at__gte=timezone.now() - timedelta(hours=1)
        )
        
        return recent_high_value_orders.exists()
    
    def _check_payment_failed(self, rule: AlertRule) -> bool:
        """Vérifier les échecs de paiement"""
        from orders.models import Order
        
        recent_failed_payments = Order.objects.filter(
            status='payment_failed',
            created_at__gte=timezone.now() - timedelta(hours=1)
        )
        
        return recent_failed_payments.exists()
    
    def _check_negative_review(self, rule: AlertRule) -> bool:
        """Vérifier les avis négatifs"""
        from .models import ProductReview
        
        recent_negative_reviews = ProductReview.objects.filter(
            rating__lte=2,
            created_at__gte=timezone.now() - timedelta(hours=24)
        )
        
        return recent_negative_reviews.exists()
    
    def _trigger_alert(self, rule: AlertRule):
        """Déclencher une alerte"""
        try:
            # Créer l'alerte
            alert = Alert.objects.create(
                rule=rule,
                title=f"Alerte: {rule.name}",
                message=self._generate_alert_message(rule),
                severity=rule.severity,
                context_data={'rule_id': rule.id}
            )
            
            # Marquer la règle comme déclenchée
            rule.mark_triggered()
            
            # Notifier les utilisateurs concernés
            self._notify_alert_recipients(alert, rule)
            
            logger.info(f"Alerte déclenchée: {alert.title}")
            
        except Exception as e:
            logger.error(f"Erreur lors du déclenchement de l'alerte: {e}")
    
    def _generate_alert_message(self, rule: AlertRule) -> str:
        """Générer le message d'alerte"""
        messages = {
            'stock_low': f"Stock faible détecté. Seuil: {rule.threshold_value}",
            'stock_out': "Rupture de stock détectée",
            'price_change': "Changement de prix détecté",
            'order_high_value': f"Commande de forte valeur détectée. Seuil: {rule.threshold_value} GNF",
            'payment_failed': "Échecs de paiement détectés",
            'review_negative': "Avis négatifs récents détectés",
        }
        
        return messages.get(rule.alert_type, f"Alerte: {rule.name}")
    
    def _notify_alert_recipients(self, alert: Alert, rule: AlertRule):
        """Notifier les destinataires de l'alerte"""
        # Notifier les utilisateurs
        for user in rule.notify_users.all():
            # Créer une notification in-app
            Notification.objects.create(
                user=user,
                title=alert.title,
                message=alert.message,
                notification_type='in_app',
                priority='high',
                context_data={'alert_id': alert.uid}
            )
        
        # Notifier par email si configuré
        if rule.notify_emails:
            # Ici, vous pourriez envoyer des emails aux adresses configurées
            pass
