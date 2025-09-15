"""
Vues pour les analytics et rapports avancés
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse, HttpResponse
from django.views.generic import ListView, DetailView, TemplateView
from django.core.paginator import Paginator
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime, timedelta, date
import json
import csv

from .models import (
    AnalyticsEvent, AnalyticsMetric, UserSession, ConversionFunnel,
    ABTest, ReportTemplate, ScheduledReport
)
from .analytics_services import AnalyticsService, ReportGenerator


class AnalyticsDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Vue principale du dashboard analytics"""
    template_name = 'products/analytics_dashboard.html'
    
    def test_func(self):
        """Vérifier que l'utilisateur est un administrateur"""
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Période par défaut (30 derniers jours)
        days = int(self.request.GET.get('days', 30))
        
        # Obtenir les données du dashboard
        analytics_service = AnalyticsService()
        dashboard_data = analytics_service.get_dashboard_data(days)
        
        context.update({
            'dashboard_data': dashboard_data,
            'selected_days': days,
            'date_range': self._get_date_range(days),
        })
        
        return context
    
    def _get_date_range(self, days: int) -> dict:
        """Obtenir la plage de dates"""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        return {
            'start_date': start_date,
            'end_date': end_date,
            'days': days,
        }


class AnalyticsEventsView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Vue pour lister les événements d'analytics"""
    model = AnalyticsEvent
    template_name = 'products/analytics_events.html'
    context_object_name = 'events'
    paginate_by = 50
    
    def test_func(self):
        """Vérifier que l'utilisateur est un administrateur"""
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_queryset(self):
        """Filtrer les événements selon les critères"""
        queryset = AnalyticsEvent.objects.select_related('user')
        
        # Filtres
        event_type = self.request.GET.get('event_type')
        user_id = self.request.GET.get('user')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Statistiques
        total_events = AnalyticsEvent.objects.count()
        unique_users = AnalyticsEvent.objects.filter(
            user__isnull=False
        ).values('user').distinct().count()
        
        # Types d'événements
        event_types = AnalyticsEvent.EVENT_TYPES
        
        context.update({
            'total_events': total_events,
            'unique_users': unique_users,
            'event_types': event_types,
        })
        
        return context


class ConversionFunnelView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Vue pour analyser les entonnoirs de conversion"""
    template_name = 'products/conversion_funnel.html'
    
    def test_func(self):
        """Vérifier que l'utilisateur est un administrateur"""
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Période par défaut (7 derniers jours)
        days = int(self.request.GET.get('days', 7))
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Analyser l'entonnoir principal
        analytics_service = AnalyticsService()
        funnel_data = analytics_service.analyze_conversion_funnel('main_funnel', end_date)
        
        # Obtenir les données historiques
        historical_data = ConversionFunnel.objects.filter(
            name='main_funnel',
            date__range=[start_date, end_date]
        ).order_by('date', 'order')
        
        context.update({
            'funnel_data': funnel_data,
            'historical_data': historical_data,
            'selected_days': days,
            'date_range': {
                'start_date': start_date,
                'end_date': end_date,
            },
        })
        
        return context


class ABTestListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Vue pour lister les tests A/B"""
    model = ABTest
    template_name = 'products/ab_test_list.html'
    context_object_name = 'tests'
    paginate_by = 20
    
    def test_func(self):
        """Vérifier que l'utilisateur est un administrateur"""
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_queryset(self):
        """Filtrer les tests selon le statut"""
        queryset = ABTest.objects.all()
        
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Statistiques
        total_tests = ABTest.objects.count()
        active_tests = ABTest.objects.filter(status='active').count()
        completed_tests = ABTest.objects.filter(status='completed').count()
        
        context.update({
            'total_tests': total_tests,
            'active_tests': active_tests,
            'completed_tests': completed_tests,
            'status_choices': ABTest.STATUS_CHOICES,
        })
        
        return context


class ABTestDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Vue pour afficher le détail d'un test A/B"""
    model = ABTest
    template_name = 'products/ab_test_detail.html'
    context_object_name = 'test'
    
    def test_func(self):
        """Vérifier que l'utilisateur est un administrateur"""
        return self.request.user.is_staff or self.request.user.is_superuser


class ReportTemplateListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Vue pour lister les templates de rapports"""
    model = ReportTemplate
    template_name = 'products/report_template_list.html'
    context_object_name = 'templates'
    paginate_by = 20
    
    def test_func(self):
        """Vérifier que l'utilisateur est un administrateur"""
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_queryset(self):
        """Filtrer les templates selon le type"""
        queryset = ReportTemplate.objects.select_related('created_by')
        
        report_type = self.request.GET.get('type')
        if report_type:
            queryset = queryset.filter(report_type=report_type)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['report_types'] = ReportTemplate.REPORT_TYPES
        return context


class ScheduledReportListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Vue pour lister les rapports programmés"""
    model = ScheduledReport
    template_name = 'products/scheduled_report_list.html'
    context_object_name = 'reports'
    paginate_by = 20
    
    def test_func(self):
        """Vérifier que l'utilisateur est un administrateur"""
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_queryset(self):
        """Filtrer les rapports selon l'état"""
        queryset = ScheduledReport.objects.select_related('template', 'created_by')
        
        is_active = self.request.GET.get('active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active == 'true')
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['frequency_choices'] = ScheduledReport.FREQUENCY_CHOICES
        return context


# Vues AJAX pour les données en temps réel
@login_required
@require_http_methods(["GET"])
def analytics_data_api(request):
    """API pour obtenir les données d'analytics"""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'error': 'Permission refusée'}, status=403)
    
    try:
        days = int(request.GET.get('days', 30))
        analytics_service = AnalyticsService()
        data = analytics_service.get_dashboard_data(days)
        
        return JsonResponse(data)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def conversion_funnel_api(request):
    """API pour obtenir les données d'entonnoir de conversion"""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'error': 'Permission refusée'}, status=403)
    
    try:
        funnel_name = request.GET.get('funnel_name', 'main_funnel')
        days = int(request.GET.get('days', 7))
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        analytics_service = AnalyticsService()
        funnel_data = analytics_service.analyze_conversion_funnel(funnel_name, end_date)
        
        return JsonResponse(funnel_data)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def ab_test_results_api(request, test_id):
    """API pour obtenir les résultats d'un test A/B"""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'error': 'Permission refusée'}, status=403)
    
    try:
        test = get_object_or_404(ABTest, id=test_id)
        
        from .analytics_services import ABTestManager
        ab_test_manager = ABTestManager()
        results = ab_test_manager.get_test_results(test_id)
        
        return JsonResponse(results)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def start_ab_test(request, test_id):
    """Démarrer un test A/B"""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'error': 'Permission refusée'}, status=403)
    
    try:
        from .analytics_services import ABTestManager
        ab_test_manager = ABTestManager()
        success = ab_test_manager.start_test(test_id)
        
        if success:
            return JsonResponse({'success': True, 'message': 'Test démarré avec succès'})
        else:
            return JsonResponse({'success': False, 'message': 'Erreur lors du démarrage du test'})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def stop_ab_test(request, test_id):
    """Arrêter un test A/B"""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'error': 'Permission refusée'}, status=403)
    
    try:
        from .analytics_services import ABTestManager
        ab_test_manager = ABTestManager()
        success = ab_test_manager.stop_test(test_id)
        
        if success:
            return JsonResponse({'success': True, 'message': 'Test arrêté avec succès'})
        else:
            return JsonResponse({'success': False, 'message': 'Erreur lors de l\'arrêt du test'})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# Vues pour les rapports
@login_required
@require_http_methods(["GET"])
def sales_report(request):
    """Générer un rapport de ventes"""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'error': 'Permission refusée'}, status=403)
    
    try:
        # Période par défaut (30 derniers jours)
        days = int(request.GET.get('days', 30))
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        report_generator = ReportGenerator()
        report_data = report_generator.generate_sales_report(start_date, end_date)
        
        return JsonResponse(report_data)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def inventory_report(request):
    """Générer un rapport d'inventaire"""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'error': 'Permission refusée'}, status=403)
    
    try:
        report_generator = ReportGenerator()
        report_data = report_generator.generate_inventory_report()
        
        return JsonResponse(report_data)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def customer_report(request):
    """Générer un rapport client"""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'error': 'Permission refusée'}, status=403)
    
    try:
        # Période par défaut (30 derniers jours)
        days = int(request.GET.get('days', 30))
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        report_generator = ReportGenerator()
        report_data = report_generator.generate_customer_report(start_date, end_date)
        
        return JsonResponse(report_data)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def export_analytics_data(request):
    """Exporter les données d'analytics en CSV"""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'error': 'Permission refusée'}, status=403)
    
    try:
        # Paramètres d'export
        event_type = request.GET.get('event_type')
        days = int(request.GET.get('days', 30))
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Filtrer les événements
        events = AnalyticsEvent.objects.filter(
            created_at__date__range=[start_date, end_date]
        ).select_related('user')
        
        if event_type:
            events = events.filter(event_type=event_type)
        
        # Créer la réponse CSV
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="analytics_data_{start_date}_{end_date}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Date', 'Type d\'événement', 'Utilisateur', 'Session ID', 
            'Adresse IP', 'Données de l\'événement'
        ])
        
        for event in events:
            writer.writerow([
                event.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                event.get_event_type_display(),
                event.user.username if event.user else 'Anonyme',
                event.session_id,
                event.ip_address or '',
                json.dumps(event.event_data, ensure_ascii=False)
            ])
        
        return response
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# Vue pour tracker les événements
@csrf_exempt
@require_http_methods(["POST"])
def track_event(request):
    """Endpoint pour tracker les événements d'analytics"""
    try:
        data = json.loads(request.body)
        
        event_type = data.get('event_type')
        event_data = data.get('event_data', {})
        session_id = data.get('session_id')
        
        if not event_type:
            return JsonResponse({'error': 'event_type requis'}, status=400)
        
        # Obtenir l'utilisateur si authentifié
        user = request.user if request.user.is_authenticated else None
        
        # Tracker l'événement
        analytics_service = AnalyticsService()
        event = analytics_service.track_event(
            event_type=event_type,
            user=user,
            session_id=session_id,
            event_data=event_data,
            request=request
        )
        
        return JsonResponse({
            'success': True,
            'event_id': str(event.uid),
            'message': 'Événement tracké avec succès'
        })
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON invalide'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
