"""
Vues pour le système de notifications et alertes
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.views.generic import ListView, DetailView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy, reverse
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json

from .models import (
    Notification, NotificationTemplate, NotificationPreference, 
    NotificationLog, AlertRule, Alert
)
from .notification_services import NotificationService, AlertService


class NotificationListView(LoginRequiredMixin, ListView):
    """Vue pour lister les notifications de l'utilisateur"""
    model = Notification
    template_name = 'products/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 20
    
    def get_queryset(self):
        """Filtrer les notifications de l'utilisateur"""
        queryset = Notification.objects.filter(user=self.request.user)
        
        # Filtres
        notification_type = self.request.GET.get('type')
        status = self.request.GET.get('status')
        
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
        
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Statistiques
        user_notifications = Notification.objects.filter(user=self.request.user)
        context['total_notifications'] = user_notifications.count()
        context['unread_count'] = user_notifications.filter(status='sent').count()
        context['notification_types'] = NotificationTemplate.NOTIFICATION_TYPES
        
        return context


class NotificationDetailView(LoginRequiredMixin, DetailView):
    """Vue pour afficher le détail d'une notification"""
    model = Notification
    template_name = 'products/notification_detail.html'
    context_object_name = 'notification'
    
    def get_object(self):
        """Récupérer la notification et vérifier les permissions"""
        notification = get_object_or_404(
            Notification, 
            uid=self.kwargs['notification_uid']
        )
        
        # Vérifier que l'utilisateur peut voir cette notification
        if notification.user != self.request.user:
            raise PermissionDenied
        
        # Marquer comme lue si c'est une notification in-app
        if notification.notification_type == 'in_app' and notification.status == 'sent':
            notification.mark_as_read()
        
        return notification


@login_required
@require_http_methods(["POST"])
def mark_notification_read(request, notification_uid):
    """Vue AJAX pour marquer une notification comme lue"""
    notification = get_object_or_404(
        Notification, 
        uid=notification_uid,
        user=request.user
    )
    
    notification.mark_as_read()
    
    return JsonResponse({
        'success': True,
        'message': 'Notification marquée comme lue'
    })


@login_required
@require_http_methods(["POST"])
def mark_all_notifications_read(request):
    """Vue AJAX pour marquer toutes les notifications comme lues"""
    notifications = Notification.objects.filter(
        user=request.user,
        status='sent'
    )
    
    count = 0
    for notification in notifications:
        notification.mark_as_read()
        count += 1
    
    return JsonResponse({
        'success': True,
        'message': f'{count} notifications marquées comme lues'
    })


class NotificationPreferenceView(LoginRequiredMixin, UpdateView):
    """Vue pour gérer les préférences de notification"""
    model = NotificationPreference
    template_name = 'products/notification_preferences.html'
    fields = [
        'email_enabled', 'sms_enabled', 'push_enabled', 'in_app_enabled',
        'order_notifications', 'payment_notifications', 'stock_notifications',
        'price_notifications', 'review_notifications', 'promotion_notifications',
        'quiet_hours_start', 'quiet_hours_end', 'timezone'
    ]
    
    def get_object(self):
        """Récupérer ou créer les préférences de l'utilisateur"""
        preferences, created = NotificationPreference.objects.get_or_create(
            user=self.request.user,
            defaults={
                'email_enabled': True,
                'sms_enabled': False,
                'push_enabled': True,
                'in_app_enabled': True,
                'order_notifications': True,
                'payment_notifications': True,
                'stock_notifications': True,
                'price_notifications': True,
                'review_notifications': True,
                'promotion_notifications': True,
            }
        )
        return preferences
    
    def get_success_url(self):
        return reverse('notifications:preferences')
    
    def form_valid(self, form):
        """Sauvegarder les préférences"""
        response = super().form_valid(form)
        messages.success(self.request, 'Vos préférences de notification ont été mises à jour.')
        return response


class AlertListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Vue pour lister les alertes (admin)"""
    model = Alert
    template_name = 'products/alert_list.html'
    context_object_name = 'alerts'
    paginate_by = 20
    
    def test_func(self):
        """Vérifier que l'utilisateur est un administrateur"""
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_queryset(self):
        """Filtrer les alertes selon le statut"""
        queryset = Alert.objects.select_related('rule')
        
        status = self.request.GET.get('status')
        severity = self.request.GET.get('severity')
        
        if status:
            queryset = queryset.filter(status=status)
        
        if severity:
            queryset = queryset.filter(severity=severity)
        
        return queryset.order_by('-triggered_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Statistiques
        all_alerts = Alert.objects.all()
        context['total_alerts'] = all_alerts.count()
        context['active_alerts'] = all_alerts.filter(status='active').count()
        context['severity_choices'] = AlertRule.SEVERITY_CHOICES
        context['status_choices'] = Alert.STATUS_CHOICES
        
        return context


class AlertDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Vue pour afficher le détail d'une alerte (admin)"""
    model = Alert
    template_name = 'products/alert_detail.html'
    context_object_name = 'alert'
    
    def test_func(self):
        """Vérifier que l'utilisateur est un administrateur"""
        return self.request.user.is_staff or self.request.user.is_superuser


@login_required
@require_http_methods(["POST"])
def acknowledge_alert(request, alert_uid):
    """Vue AJAX pour reconnaître une alerte (admin)"""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'error': 'Permission refusée'}, status=403)
    
    alert = get_object_or_404(Alert, uid=alert_uid)
    alert.acknowledge(request.user)
    
    return JsonResponse({
        'success': True,
        'message': 'Alerte reconnue'
    })


@login_required
@require_http_methods(["POST"])
def resolve_alert(request, alert_uid):
    """Vue AJAX pour résoudre une alerte (admin)"""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'error': 'Permission refusée'}, status=403)
    
    alert = get_object_or_404(Alert, uid=alert_uid)
    alert.resolve()
    
    return JsonResponse({
        'success': True,
        'message': 'Alerte résolue'
    })


class AlertRuleListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Vue pour lister les règles d'alerte (admin)"""
    model = AlertRule
    template_name = 'products/alert_rule_list.html'
    context_object_name = 'rules'
    paginate_by = 20
    
    def test_func(self):
        """Vérifier que l'utilisateur est un administrateur"""
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_queryset(self):
        """Filtrer les règles selon le type"""
        queryset = AlertRule.objects.all()
        
        alert_type = self.request.GET.get('type')
        is_active = self.request.GET.get('active')
        
        if alert_type:
            queryset = queryset.filter(alert_type=alert_type)
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active == 'true')
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['alert_types'] = AlertRule.ALERT_TYPES
        return context


class NotificationTemplateListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Vue pour lister les templates de notification (admin)"""
    model = NotificationTemplate
    template_name = 'products/notification_template_list.html'
    context_object_name = 'templates'
    paginate_by = 20
    
    def test_func(self):
        """Vérifier que l'utilisateur est un administrateur"""
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_queryset(self):
        """Filtrer les templates selon le type"""
        queryset = NotificationTemplate.objects.all()
        
        notification_type = self.request.GET.get('type')
        trigger_type = self.request.GET.get('trigger')
        
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
        
        if trigger_type:
            queryset = queryset.filter(trigger_type=trigger_type)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['notification_types'] = NotificationTemplate.NOTIFICATION_TYPES
        context['trigger_types'] = NotificationTemplate.TRIGGER_TYPES
        return context


@login_required
@require_http_methods(["GET"])
def notification_count_api(request):
    """API pour obtenir le nombre de notifications non lues"""
    if not request.user.is_authenticated:
        return JsonResponse({'count': 0})
    
    count = Notification.objects.filter(
        user=request.user,
        status='sent',
        notification_type='in_app'
    ).count()
    
    return JsonResponse({'count': count})


@login_required
@require_http_methods(["GET"])
def recent_notifications_api(request):
    """API pour obtenir les notifications récentes"""
    if not request.user.is_authenticated:
        return JsonResponse({'notifications': []})
    
    notifications = Notification.objects.filter(
        user=request.user,
        notification_type='in_app'
    ).order_by('-created_at')[:5]
    
    notifications_data = []
    for notification in notifications:
        notifications_data.append({
            'id': str(notification.uid),
            'title': notification.title,
            'message': notification.message[:100] + '...' if len(notification.message) > 100 else notification.message,
            'created_at': notification.created_at.isoformat(),
            'is_read': notification.status == 'read',
            'priority': notification.priority
        })
    
    return JsonResponse({'notifications': notifications_data})


@login_required
@require_http_methods(["POST"])
def send_test_notification(request):
    """Vue pour envoyer une notification de test (admin)"""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'error': 'Permission refusée'}, status=403)
    
    try:
        data = json.loads(request.body)
        template_id = data.get('template_id')
        user_id = data.get('user_id')
        
        if not template_id or not user_id:
            return JsonResponse({'error': 'Template ID et User ID requis'}, status=400)
        
        template = get_object_or_404(NotificationTemplate, id=template_id)
        user = get_object_or_404(User, id=user_id)
        
        # Envoyer la notification de test
        notification_service = NotificationService()
        notification = notification_service.send_notification(
            user=user,
            template=template,
            context={'test': True},
            priority='normal'
        )
        
        if notification:
            return JsonResponse({
                'success': True,
                'message': 'Notification de test envoyée',
                'notification_id': str(notification.uid)
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Notification non envoyée (préférences utilisateur)'
            })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def trigger_alert_test(request):
    """Vue pour déclencher un test d'alerte (admin)"""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'error': 'Permission refusée'}, status=403)
    
    try:
        data = json.loads(request.body)
        rule_id = data.get('rule_id')
        
        if not rule_id:
            return JsonResponse({'error': 'Rule ID requis'}, status=400)
        
        rule = get_object_or_404(AlertRule, id=rule_id)
        
        # Déclencher l'alerte de test
        alert_service = AlertService()
        alert_service._trigger_alert(rule)
        
        return JsonResponse({
            'success': True,
            'message': 'Alerte de test déclenchée'
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


class NotificationAnalyticsView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Vue pour les analytics des notifications (admin)"""
    template_name = 'products/notification_analytics.html'
    
    def test_func(self):
        """Vérifier que l'utilisateur est un administrateur"""
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Statistiques générales
        total_notifications = Notification.objects.count()
        sent_notifications = Notification.objects.filter(status='sent').count()
        failed_notifications = Notification.objects.filter(status='failed').count()
        
        # Statistiques par type
        notifications_by_type = Notification.objects.values('notification_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Statistiques par statut
        notifications_by_status = Notification.objects.values('status').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Statistiques récentes (7 derniers jours)
        from datetime import timedelta
        recent_date = timezone.now() - timedelta(days=7)
        recent_notifications = Notification.objects.filter(
            created_at__gte=recent_date
        ).count()
        
        context.update({
            'total_notifications': total_notifications,
            'sent_notifications': sent_notifications,
            'failed_notifications': failed_notifications,
            'success_rate': (sent_notifications / total_notifications * 100) if total_notifications > 0 else 0,
            'notifications_by_type': notifications_by_type,
            'notifications_by_status': notifications_by_status,
            'recent_notifications': recent_notifications,
        })
        
        return context
