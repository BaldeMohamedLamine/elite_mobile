"""
Services d'analytics pour la gestion des stocks
"""
from django.db.models import Sum, Count, Avg, F, Q
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
import logging

from .models import Product, StockMovement, StockAlert, Category

logger = logging.getLogger(__name__)


class StockAnalyticsService:
    """Service d'analytics pour les stocks"""
    
    @staticmethod
    def get_stock_overview():
        """Retourne un aperçu général des stocks"""
        total_products = Product.objects.filter(is_active=True).count()
        total_stock_value = Product.objects.filter(is_active=True).aggregate(
            total=Sum(F('quantity') * F('price'))
        )['total'] or Decimal('0')
        
        low_stock_count = Product.objects.filter(
            is_active=True,
            quantity__lte=F('min_stock_level')
        ).count()
        
        out_of_stock_count = Product.objects.filter(
            is_active=True,
            quantity=0
        ).count()
        
        overstock_count = Product.objects.filter(
            is_active=True,
            quantity__gte=F('max_stock_level')
        ).count()
        
        return {
            'total_products': total_products,
            'total_stock_value': total_stock_value,
            'low_stock_count': low_stock_count,
            'out_of_stock_count': out_of_stock_count,
            'overstock_count': overstock_count,
            'stock_health_percentage': round(
                ((total_products - low_stock_count - out_of_stock_count) / total_products * 100) 
                if total_products > 0 else 0, 2
            )
        }
    
    @staticmethod
    def get_stock_trends(days=30):
        """Analyse les tendances de stock sur une période"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Mouvements de stock par jour
        daily_movements = StockMovement.objects.filter(
            created_at__range=[start_date, end_date]
        ).extra(
            select={'day': 'date(created_at)'}
        ).values('day').annotate(
            total_in=Sum('quantity', filter=Q(movement_type='in')),
            total_out=Sum('quantity', filter=Q(movement_type='out')),
            total_adjustment=Sum('quantity', filter=Q(movement_type='adjustment'))
        ).order_by('day')
        
        # Alertes par jour
        daily_alerts = StockAlert.objects.filter(
            created_at__range=[start_date, end_date]
        ).extra(
            select={'day': 'date(created_at)'}
        ).values('day', 'alert_type').annotate(
            count=Count('id')
        ).order_by('day')
        
        return {
            'daily_movements': list(daily_movements),
            'daily_alerts': list(daily_alerts),
            'period_days': days
        }
    
    @staticmethod
    def get_category_stock_analysis():
        """Analyse des stocks par catégorie"""
        categories = Category.objects.annotate(
            product_count=Count('products', filter=Q(products__is_active=True)),
            total_stock=Sum('products__quantity', filter=Q(products__is_active=True)),
            total_value=Sum(
                F('products__quantity') * F('products__price'),
                filter=Q(products__is_active=True)
            ),
            low_stock_count=Count(
                'products',
                filter=Q(
                    products__is_active=True,
                    products__quantity__lte=F('products__min_stock_level')
                )
            ),
            out_of_stock_count=Count(
                'products',
                filter=Q(
                    products__is_active=True,
                    products__quantity=0
                )
            )
        ).order_by('-total_value')
        
        return list(categories)
    
    @staticmethod
    def get_top_moving_products(limit=10, days=30):
        """Retourne les produits avec le plus de mouvements"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        products = Product.objects.filter(
            is_active=True,
            stock_movements__created_at__range=[start_date, end_date]
        ).annotate(
            total_movements=Count('stock_movements'),
            total_in=Sum('stock_movements__quantity', filter=Q(stock_movements__movement_type='in')),
            total_out=Sum('stock_movements__quantity', filter=Q(stock_movements__movement_type='out')),
            last_movement_date=models.Max('stock_movements__created_at')
        ).order_by('-total_movements')[:limit]
        
        return list(products)
    
    @staticmethod
    def get_stock_velocity_analysis():
        """Analyse la vélocité des stocks (rotation)"""
        products = Product.objects.filter(
            is_active=True,
            quantity__gt=0
        ).annotate(
            stock_velocity=Sum(
                'stock_movements__quantity',
                filter=Q(stock_movements__movement_type='out')
            ) / F('quantity')
        ).order_by('-stock_velocity')
        
        return {
            'fast_moving': products.filter(stock_velocity__gte=2)[:10],
            'slow_moving': products.filter(stock_velocity__lt=0.5)[:10],
            'average_velocity': products.aggregate(
                avg=Avg('stock_velocity')
            )['avg'] or 0
        }
    
    @staticmethod
    def get_stock_forecasting(product_id, days=30):
        """Prévision des stocks basée sur l'historique"""
        product = Product.objects.get(id=product_id)
        
        # Calculer la consommation moyenne par jour
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        daily_consumption = StockMovement.objects.filter(
            product=product,
            movement_type='out',
            created_at__range=[start_date, end_date]
        ).aggregate(
            total=Sum('quantity')
        )['total'] or 0
        
        avg_daily_consumption = daily_consumption / days if days > 0 else 0
        
        # Calculer les jours restants
        days_remaining = product.quantity / avg_daily_consumption if avg_daily_consumption > 0 else float('inf')
        
        # Recommandations
        recommendations = []
        if days_remaining < 7:
            recommendations.append("Commande urgente recommandée")
        elif days_remaining < 14:
            recommendations.append("Planifier une commande prochainement")
        elif days_remaining > 90:
            recommendations.append("Stock élevé, surveiller la rotation")
        
        return {
            'product': product,
            'current_stock': product.quantity,
            'avg_daily_consumption': round(avg_daily_consumption, 2),
            'days_remaining': round(days_remaining, 1) if days_remaining != float('inf') else None,
            'recommendations': recommendations,
            'forecast_date': end_date + timedelta(days=days_remaining) if days_remaining != float('inf') else None
        }
    
    @staticmethod
    def get_stock_optimization_suggestions():
        """Suggestions d'optimisation des stocks"""
        suggestions = []
        
        # Produits en surstock
        overstock_products = Product.objects.filter(
            is_active=True,
            quantity__gte=F('max_stock_level')
        )[:5]
        
        if overstock_products:
            suggestions.append({
                'type': 'overstock',
                'title': 'Produits en surstock',
                'description': f'{overstock_products.count()} produits dépassent leur stock maximum',
                'products': list(overstock_products),
                'action': 'Considérer des promotions ou des ajustements de stock'
            })
        
        # Produits avec stock faible
        low_stock_products = Product.objects.filter(
            is_active=True,
            quantity__lte=F('min_stock_level')
        )[:5]
        
        if low_stock_products:
            suggestions.append({
                'type': 'low_stock',
                'title': 'Produits avec stock faible',
                'description': f'{low_stock_products.count()} produits ont un stock faible',
                'products': list(low_stock_products),
                'action': 'Planifier des commandes de réapprovisionnement'
            })
        
        # Produits avec rotation lente
        slow_moving = StockAnalyticsService.get_stock_velocity_analysis()['slow_moving']
        if slow_moving:
            suggestions.append({
                'type': 'slow_moving',
                'title': 'Produits à rotation lente',
                'description': f'{len(slow_moving)} produits ont une rotation lente',
                'products': list(slow_moving),
                'action': 'Analyser la demande et considérer des promotions'
            })
        
        return suggestions


class StockReportingService:
    """Service de génération de rapports de stock"""
    
    @staticmethod
    def generate_stock_report(report_type='summary', filters=None):
        """Génère un rapport de stock"""
        if report_type == 'summary':
            return StockAnalyticsService.get_stock_overview()
        elif report_type == 'trends':
            days = filters.get('days', 30) if filters else 30
            return StockAnalyticsService.get_stock_trends(days)
        elif report_type == 'category':
            return StockAnalyticsService.get_category_stock_analysis()
        elif report_type == 'velocity':
            return StockAnalyticsService.get_stock_velocity_analysis()
        elif report_type == 'optimization':
            return StockAnalyticsService.get_stock_optimization_suggestions()
        else:
            return {}
    
    @staticmethod
    def export_stock_data(format='csv', filters=None):
        """Exporte les données de stock dans différents formats"""
        # TODO: Implémenter l'export CSV/Excel
        pass
