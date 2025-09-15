from django.shortcuts import render, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta
from .audit import AuditLog as AuditLogModel, SecurityEvent as SecurityEventModel


class AuditLogListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """
    Vue pour lister les logs d'audit
    Accessible uniquement aux staff et superusers
    """
    model = AuditLogModel
    template_name = 'orders/audit/audit_log_list.html'
    context_object_name = 'audit_logs'
    paginate_by = 50
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_queryset(self):
        queryset = AuditLogModel.objects.all()
        
        # Filtres
        action_type = self.request.GET.get('action_type')
        severity = self.request.GET.get('severity')
        user_id = self.request.GET.get('user')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        search = self.request.GET.get('search')
        
        if action_type:
            queryset = queryset.filter(action_type=action_type)
        
        if severity:
            queryset = queryset.filter(severity=severity)
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        if date_from:
            try:
                date_from = timezone.datetime.strptime(date_from, '%Y-%m-%d').date()
                queryset = queryset.filter(created_at__date__gte=date_from)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to = timezone.datetime.strptime(date_to, '%Y-%m-%d').date()
                queryset = queryset.filter(created_at__date__lte=date_to)
            except ValueError:
                pass
        
        if search:
            queryset = queryset.filter(
                Q(description__icontains=search) |
                Q(user__email__icontains=search) |
                Q(object_id__icontains=search) |
                Q(ip_address__icontains=search)
            )
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action_types'] = AuditLogModel.ACTION_TYPES
        context['severity_levels'] = AuditLogModel.SEVERITY_LEVELS
        context['current_filters'] = {
            'action_type': self.request.GET.get('action_type', ''),
            'severity': self.request.GET.get('severity', ''),
            'user': self.request.GET.get('user', ''),
            'date_from': self.request.GET.get('date_from', ''),
            'date_to': self.request.GET.get('date_to', ''),
            'search': self.request.GET.get('search', ''),
        }
        return context


class AuditLogDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """
    Vue pour afficher les détails d'un log d'audit
    """
    model = AuditLogModel
    template_name = 'orders/audit/audit_log_detail.html'
    context_object_name = 'audit_log'
    pk_url_kwarg = 'uid'
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_object(self):
        return get_object_or_404(AuditLogModel, uid=self.kwargs['uid'])


class SecurityEventListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """
    Vue pour lister les événements de sécurité
    Accessible uniquement aux staff et superusers
    """
    model = SecurityEventModel
    template_name = 'orders/audit/security_event_list.html'
    context_object_name = 'security_events'
    paginate_by = 50
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_queryset(self):
        queryset = SecurityEventModel.objects.all()
        
        # Filtres
        event_type = self.request.GET.get('event_type')
        severity = self.request.GET.get('severity')
        blocked = self.request.GET.get('blocked')
        ip_address = self.request.GET.get('ip_address')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        
        if severity:
            queryset = queryset.filter(severity=severity)
        
        if blocked is not None:
            queryset = queryset.filter(blocked=blocked == 'true')
        
        if ip_address:
            queryset = queryset.filter(ip_address__icontains=ip_address)
        
        if date_from:
            try:
                date_from = timezone.datetime.strptime(date_from, '%Y-%m-%d').date()
                queryset = queryset.filter(created_at__date__gte=date_from)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to = timezone.datetime.strptime(date_to, '%Y-%m-%d').date()
                queryset = queryset.filter(created_at__date__lte=date_to)
            except ValueError:
                pass
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['event_types'] = SecurityEventModel.EVENT_TYPES
        context['severity_levels'] = SecurityEventModel.SEVERITY_LEVELS
        context['current_filters'] = {
            'event_type': self.request.GET.get('event_type', ''),
            'severity': self.request.GET.get('severity', ''),
            'blocked': self.request.GET.get('blocked', ''),
            'ip_address': self.request.GET.get('ip_address', ''),
            'date_from': self.request.GET.get('date_from', ''),
            'date_to': self.request.GET.get('date_to', ''),
        }
        
        # Statistiques
        context['stats'] = {
            'total_events': SecurityEventModel.objects.count(),
            'blocked_events': SecurityEventModel.objects.filter(blocked=True).count(),
            'critical_events': SecurityEventModel.objects.filter(severity='critical').count(),
            'events_today': SecurityEventModel.objects.filter(
                created_at__date=timezone.now().date()
            ).count(),
            'events_last_7_days': SecurityEventModel.objects.filter(
                created_at__gte=timezone.now() - timedelta(days=7)
            ).count(),
        }
        
        return context


class SecurityEventDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """
    Vue pour afficher les détails d'un événement de sécurité
    """
    model = SecurityEventModel
    template_name = 'orders/audit/security_event_detail.html'
    context_object_name = 'security_event'
    pk_url_kwarg = 'uid'
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_object(self):
        return get_object_or_404(SecurityEventModel, uid=self.kwargs['uid'])


class AuditDashboardView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """
    Vue pour le tableau de bord d'audit
    """
    template_name = 'orders/audit/audit_dashboard.html'
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get(self, request, *args, **kwargs):
        # Statistiques générales
        stats = {
            'total_audit_logs': AuditLogModel.objects.count(),
            'total_security_events': SecurityEventModel.objects.count(),
            'critical_events': SecurityEventModel.objects.filter(severity='critical').count(),
            'blocked_events': SecurityEventModel.objects.filter(blocked=True).count(),
        }
        
        # Événements récents
        recent_audit_logs = AuditLogModel.objects.order_by('-created_at')[:10]
        recent_security_events = SecurityEventModel.objects.order_by('-created_at')[:10]
        
        # Événements par type (derniers 30 jours)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        audit_by_type = AuditLogModel.objects.filter(
            created_at__gte=thirty_days_ago
        ).values('action_type').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        security_by_type = SecurityEventModel.objects.filter(
            created_at__gte=thirty_days_ago
        ).values('event_type').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        context = {
            'stats': stats,
            'recent_audit_logs': recent_audit_logs,
            'recent_security_events': recent_security_events,
            'audit_by_type': audit_by_type,
            'security_by_type': security_by_type,
        }
        
        return render(request, self.template_name, context)
