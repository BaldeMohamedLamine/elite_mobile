"""
Services d'analytics pour la collecte et l'analyse de données
"""
import logging
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q, F
from django.contrib.auth import get_user_model
from django.core.cache import cache

from .models import (
    AnalyticsEvent, AnalyticsMetric, UserSession, ConversionFunnel,
    ABTest, ReportTemplate, ScheduledReport, Product
)
from orders.models import Order

User = get_user_model()
logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service principal pour la collecte et l'analyse de données"""
    
    def __init__(self):
        self.event_collector = EventCollector()
        self.metric_calculator = MetricCalculator()
        self.funnel_analyzer = FunnelAnalyzer()
        self.ab_test_manager = ABTestManager()
    
    def track_event(
        self, 
        event_type: str, 
        user: User = None, 
        session_id: str = None,
        event_data: Dict[str, Any] = None,
        request=None
    ) -> AnalyticsEvent:
        """Traquer un événement d'analytics"""
        return self.event_collector.track_event(
            event_type, user, session_id, event_data, request
        )
    
    def calculate_daily_metrics(self, target_date: date = None) -> Dict[str, Any]:
        """Calculer les métriques quotidiennes"""
        if target_date is None:
            target_date = timezone.now().date()
        
        return self.metric_calculator.calculate_daily_metrics(target_date)
    
    def analyze_conversion_funnel(self, funnel_name: str, target_date: date = None) -> Dict[str, Any]:
        """Analyser un entonnoir de conversion"""
        if target_date is None:
            target_date = timezone.now().date()
        
        return self.funnel_analyzer.analyze_funnel(funnel_name, target_date)
    
    def get_dashboard_data(self, days: int = 30) -> Dict[str, Any]:
        """Obtenir les données pour le dashboard analytics"""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        return {
            'overview': self._get_overview_metrics(start_date, end_date),
            'traffic': self._get_traffic_metrics(start_date, end_date),
            'conversions': self._get_conversion_metrics(start_date, end_date),
            'products': self._get_product_metrics(start_date, end_date),
            'users': self._get_user_metrics(start_date, end_date),
            'revenue': self._get_revenue_metrics(start_date, end_date),
        }
    
    def _get_overview_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Métriques générales"""
        total_visitors = UserSession.objects.filter(
            started_at__date__range=[start_date, end_date]
        ).values('session_id').distinct().count()
        
        total_orders = Order.objects.filter(
            created_at__date__range=[start_date, end_date]
        ).count()
        
        total_revenue = Order.objects.filter(
            created_at__date__range=[start_date, end_date],
            status='completed'
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        conversion_rate = (total_orders / total_visitors * 100) if total_visitors > 0 else 0
        
        return {
            'total_visitors': total_visitors,
            'total_orders': total_orders,
            'total_revenue': total_revenue,
            'conversion_rate': round(conversion_rate, 2),
        }
    
    def _get_traffic_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Métriques de trafic"""
        page_views = AnalyticsEvent.objects.filter(
            event_type='page_view',
            created_at__date__range=[start_date, end_date]
        ).count()
        
        unique_visitors = UserSession.objects.filter(
            started_at__date__range=[start_date, end_date]
        ).values('session_id').distinct().count()
        
        avg_session_duration = UserSession.objects.filter(
            started_at__date__range=[start_date, end_date],
            session_duration__isnull=False
        ).aggregate(avg=Avg('session_duration'))['avg']
        
        bounce_rate = UserSession.objects.filter(
            started_at__date__range=[start_date, end_date],
            is_bounce=True
        ).count() / max(unique_visitors, 1) * 100
        
        return {
            'page_views': page_views,
            'unique_visitors': unique_visitors,
            'avg_session_duration': avg_session_duration,
            'bounce_rate': round(bounce_rate, 2),
        }
    
    def _get_conversion_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Métriques de conversion"""
        funnel_data = self.funnel_analyzer.get_funnel_summary(start_date, end_date)
        
        cart_abandonment = self._calculate_cart_abandonment(start_date, end_date)
        
        return {
            'funnel_data': funnel_data,
            'cart_abandonment_rate': cart_abandonment,
        }
    
    def _get_product_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Métriques des produits"""
        top_products = AnalyticsEvent.objects.filter(
            event_type='product_view',
            created_at__date__range=[start_date, end_date]
        ).values('event_data__product_id').annotate(
            views=Count('id')
        ).order_by('-views')[:10]
        
        return {
            'top_products': list(top_products),
        }
    
    def _get_user_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Métriques des utilisateurs"""
        new_users = User.objects.filter(
            date_joined__date__range=[start_date, end_date]
        ).count()
        
        returning_users = UserSession.objects.filter(
            started_at__date__range=[start_date, end_date],
            user__isnull=False
        ).values('user').distinct().count()
        
        return {
            'new_users': new_users,
            'returning_users': returning_users,
        }
    
    def _get_revenue_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Métriques de revenus"""
        daily_revenue = Order.objects.filter(
            created_at__date__range=[start_date, end_date],
            status='completed'
        ).extra(
            select={'day': 'date(created_at)'}
        ).values('day').annotate(
            revenue=Sum('total_amount')
        ).order_by('day')
        
        avg_order_value = Order.objects.filter(
            created_at__date__range=[start_date, end_date],
            status='completed'
        ).aggregate(avg=Avg('total_amount'))['avg'] or 0
        
        return {
            'daily_revenue': list(daily_revenue),
            'avg_order_value': avg_order_value,
        }
    
    def _calculate_cart_abandonment(self, start_date: date, end_date: date) -> float:
        """Calculer le taux d'abandon de panier"""
        cart_adds = AnalyticsEvent.objects.filter(
            event_type='add_to_cart',
            created_at__date__range=[start_date, end_date]
        ).count()
        
        checkouts = AnalyticsEvent.objects.filter(
            event_type='checkout_start',
            created_at__date__range=[start_date, end_date]
        ).count()
        
        if cart_adds == 0:
            return 0
        
        abandonment_rate = ((cart_adds - checkouts) / cart_adds) * 100
        return round(abandonment_rate, 2)


class EventCollector:
    """Collecteur d'événements d'analytics"""
    
    def track_event(
        self, 
        event_type: str, 
        user: User = None, 
        session_id: str = None,
        event_data: Dict[str, Any] = None,
        request=None
    ) -> AnalyticsEvent:
        """Collecter un événement d'analytics"""
        if event_data is None:
            event_data = {}
        
        # Extraire les informations de la requête
        ip_address = None
        user_agent = None
        referrer = None
        
        if request:
            ip_address = self._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            referrer = request.META.get('HTTP_REFERER', '')
        
        # Créer l'événement
        event = AnalyticsEvent.objects.create(
            event_type=event_type,
            user=user,
            session_id=session_id or '',
            event_data=event_data,
            ip_address=ip_address,
            user_agent=user_agent,
            referrer=referrer
        )
        
        # Mettre à jour la session si nécessaire
        if session_id:
            self._update_session(session_id, event_type, user, request)
        
        logger.info(f"Event tracked: {event_type} for user {user}")
        return event
    
    def _get_client_ip(self, request) -> str:
        """Obtenir l'adresse IP du client"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _update_session(self, session_id: str, event_type: str, user: User, request):
        """Mettre à jour les informations de session"""
        session, created = UserSession.objects.get_or_create(
            session_id=session_id,
            defaults={
                'user': user,
                'ip_address': self._get_client_ip(request) if request else None,
                'user_agent': request.META.get('HTTP_USER_AGENT', '') if request else '',
                'referrer': request.META.get('HTTP_REFERER', '') if request else '',
            }
        )
        
        if not created:
            session.pages_visited += 1
            session.save()


class MetricCalculator:
    """Calculateur de métriques d'analytics"""
    
    def calculate_daily_metrics(self, target_date: date) -> Dict[str, Any]:
        """Calculer les métriques pour une date donnée"""
        metrics = {}
        
        # Visiteurs quotidiens
        daily_visitors = UserSession.objects.filter(
            started_at__date=target_date
        ).values('session_id').distinct().count()
        
        # Vues de pages quotidiennes
        daily_page_views = AnalyticsEvent.objects.filter(
            event_type='page_view',
            created_at__date=target_date
        ).count()
        
        # Commandes quotidiennes
        daily_orders = Order.objects.filter(
            created_at__date=target_date
        ).count()
        
        # Revenus quotidiens
        daily_revenue = Order.objects.filter(
            created_at__date=target_date,
            status='completed'
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        # Taux de conversion
        conversion_rate = (daily_orders / daily_visitors * 100) if daily_visitors > 0 else 0
        
        # Taux de rebond
        bounce_rate = UserSession.objects.filter(
            started_at__date=target_date,
            is_bounce=True
        ).count() / max(daily_visitors, 1) * 100
        
        # Durée moyenne de session
        avg_session_duration = UserSession.objects.filter(
            started_at__date=target_date,
            session_duration__isnull=False
        ).aggregate(avg=Avg('session_duration'))['avg']
        
        # Sauvegarder les métriques
        metrics_data = [
            ('daily_visitors', daily_visitors),
            ('daily_page_views', daily_page_views),
            ('daily_orders', daily_orders),
            ('daily_revenue', daily_revenue),
            ('conversion_rate', conversion_rate),
            ('bounce_rate', bounce_rate),
            ('avg_session_duration', avg_session_duration.total_seconds() if avg_session_duration else 0),
        ]
        
        for metric_type, value in metrics_data:
            AnalyticsMetric.objects.update_or_create(
                metric_type=metric_type,
                date=target_date,
                defaults={'value': value}
            )
        
        return {
            'date': target_date,
            'visitors': daily_visitors,
            'page_views': daily_page_views,
            'orders': daily_orders,
            'revenue': daily_revenue,
            'conversion_rate': round(conversion_rate, 2),
            'bounce_rate': round(bounce_rate, 2),
            'avg_session_duration': avg_session_duration,
        }


class FunnelAnalyzer:
    """Analyseur d'entonnoirs de conversion"""
    
    def analyze_funnel(self, funnel_name: str, target_date: date) -> Dict[str, Any]:
        """Analyser un entonnoir de conversion"""
        funnel_steps = ConversionFunnel.FUNNEL_STEPS
        
        funnel_data = []
        previous_visitors = 0
        
        for step_order, (step_code, step_name) in enumerate(funnel_steps):
            # Compter les visiteurs pour cette étape
            visitors = self._count_step_visitors(step_code, target_date)
            
            # Calculer le taux de conversion
            if step_order == 0:
                conversion_rate = 100.0
                previous_visitors = visitors
            else:
                conversion_rate = (visitors / previous_visitors * 100) if previous_visitors > 0 else 0
                previous_visitors = visitors
            
            # Créer ou mettre à jour l'entrée de l'entonnoir
            ConversionFunnel.objects.update_or_create(
                name=funnel_name,
                step=step_code,
                date=target_date,
                defaults={
                    'order': step_order,
                    'total_visitors': visitors,
                    'conversions': visitors,
                    'conversion_rate': conversion_rate,
                }
            )
            
            funnel_data.append({
                'step': step_code,
                'step_name': step_name,
                'visitors': visitors,
                'conversion_rate': round(conversion_rate, 2),
            })
        
        return {
            'funnel_name': funnel_name,
            'date': target_date,
            'steps': funnel_data,
        }
    
    def _count_step_visitors(self, step_code: str, target_date: date) -> int:
        """Compter les visiteurs pour une étape donnée"""
        event_type_mapping = {
            'landing': 'page_view',
            'product_view': 'product_view',
            'add_to_cart': 'add_to_cart',
            'checkout_start': 'checkout_start',
            'checkout_complete': 'checkout_complete',
            'payment_success': 'payment_success',
        }
        
        event_type = event_type_mapping.get(step_code)
        if not event_type:
            return 0
        
        return AnalyticsEvent.objects.filter(
            event_type=event_type,
            created_at__date=target_date
        ).values('session_id').distinct().count()
    
    def get_funnel_summary(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Obtenir un résumé des entonnoirs"""
        funnels = ConversionFunnel.objects.filter(
            date__range=[start_date, end_date]
        ).values('name', 'step').annotate(
            avg_conversion_rate=Avg('conversion_rate'),
            total_visitors=Sum('total_visitors')
        )
        
        return list(funnels)


class ABTestManager:
    """Gestionnaire de tests A/B"""
    
    def create_test(
        self, 
        name: str, 
        test_type: str, 
        target_url: str,
        control_variant: Dict[str, Any],
        test_variant: Dict[str, Any],
        traffic_percentage: int = 50
    ) -> ABTest:
        """Créer un nouveau test A/B"""
        test = ABTest.objects.create(
            name=name,
            test_type=test_type,
            target_url=target_url,
            control_variant=control_variant,
            test_variant=test_variant,
            traffic_percentage=traffic_percentage
        )
        
        logger.info(f"AB Test created: {name}")
        return test
    
    def start_test(self, test_id: int) -> bool:
        """Démarrer un test A/B"""
        try:
            test = ABTest.objects.get(id=test_id)
            test.status = 'active'
            test.started_at = timezone.now()
            test.save()
            
            logger.info(f"AB Test started: {test.name}")
            return True
        except ABTest.DoesNotExist:
            return False
    
    def stop_test(self, test_id: int) -> bool:
        """Arrêter un test A/B"""
        try:
            test = ABTest.objects.get(id=test_id)
            test.status = 'completed'
            test.ended_at = timezone.now()
            test.save()
            
            logger.info(f"AB Test stopped: {test.name}")
            return True
        except ABTest.DoesNotExist:
            return False
    
    def get_test_results(self, test_id: int) -> Dict[str, Any]:
        """Obtenir les résultats d'un test A/B"""
        try:
            test = ABTest.objects.get(id=test_id)
            
            return {
                'test_name': test.name,
                'status': test.status,
                'control_conversion_rate': test.control_conversion_rate,
                'test_conversion_rate': test.test_conversion_rate,
                'improvement_percentage': test.improvement_percentage,
                'control_visitors': test.control_visitors,
                'test_visitors': test.test_visitors,
                'control_conversions': test.control_conversions,
                'test_conversions': test.test_conversions,
            }
        except ABTest.DoesNotExist:
            return {}
    
    def assign_variant(self, test_id: int, user_id: int) -> str:
        """Assigner une variante à un utilisateur"""
        # Logique simple d'assignation basée sur l'ID utilisateur
        # En production, vous pourriez utiliser une logique plus sophistiquée
        if user_id % 2 == 0:
            return 'control'
        else:
            return 'test'


class ReportGenerator:
    """Générateur de rapports"""
    
    def generate_sales_report(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Générer un rapport de ventes"""
        orders = Order.objects.filter(
            created_at__date__range=[start_date, end_date]
        )
        
        total_orders = orders.count()
        total_revenue = orders.filter(status='completed').aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        avg_order_value = orders.filter(status='completed').aggregate(
            avg=Avg('total_amount')
        )['avg'] or 0
        
        # Ventes par jour
        daily_sales = orders.filter(status='completed').extra(
            select={'day': 'date(created_at)'}
        ).values('day').annotate(
            revenue=Sum('total_amount'),
            orders=Count('id')
        ).order_by('day')
        
        return {
            'period': f"{start_date} to {end_date}",
            'total_orders': total_orders,
            'total_revenue': total_revenue,
            'avg_order_value': avg_order_value,
            'daily_sales': list(daily_sales),
        }
    
    def generate_inventory_report(self) -> Dict[str, Any]:
        """Générer un rapport d'inventaire"""
        products = Product.objects.all()
        
        total_products = products.count()
        low_stock_products = products.filter(stock_quantity__lte=10).count()
        out_of_stock_products = products.filter(stock_quantity=0).count()
        
        # Valeur totale de l'inventaire
        total_inventory_value = products.aggregate(
            total=Sum(F('stock_quantity') * F('price'))
        )['total'] or 0
        
        return {
            'total_products': total_products,
            'low_stock_products': low_stock_products,
            'out_of_stock_products': out_of_stock_products,
            'total_inventory_value': total_inventory_value,
        }
    
    def generate_customer_report(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Générer un rapport client"""
        new_customers = User.objects.filter(
            date_joined__date__range=[start_date, end_date]
        ).count()
        
        total_customers = User.objects.count()
        
        # Clients actifs (ayant passé une commande)
        active_customers = User.objects.filter(
            orders__created_at__date__range=[start_date, end_date]
        ).distinct().count()
        
        return {
            'new_customers': new_customers,
            'total_customers': total_customers,
            'active_customers': active_customers,
        }
