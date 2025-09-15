"""
Vues pour les rapports de stock et inventaire
"""
from django.shortcuts import render, get_object_or_404,redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.views.generic import View, TemplateView
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Q, F, Sum, Count, Avg, Min, Max
from django.db.models.functions import TruncMonth, TruncDay
from django.template.loader import render_to_string
from django.core.paginator import Paginator
from datetime import datetime, timedelta
from .models import Product, StockMovement, StockAlert, ProductVariantOption
from .stock_services import StockMovementService
import json
import csv
from io import StringIO


class ManagerRequiredMixin(UserPassesTestMixin):
    """Mixin pour vérifier que l'utilisateur est un manager"""
    
    def test_func(self):
        return self.request.user.is_staff and self.request.user.is_active
    
    def handle_no_permission(self):
        messages.error(self.request, "Accès refusé. Seuls les managers peuvent accéder à cette page.")
        return redirect('home')


class StockReportDashboardView(LoginRequiredMixin, ManagerRequiredMixin, TemplateView):
    """Dashboard des rapports de stock"""
    template_name = 'products/stock_report_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Période par défaut (30 derniers jours)
        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)
        
        # Statistiques générales
        context['summary'] = StockMovementService.get_stock_summary()
        
        # Top produits par valeur de stock
        context['top_products_by_value'] = Product.objects.filter(
            is_active=True
        ).annotate(
            stock_value=F('quantity') * F('price')
        ).order_by('-stock_value')[:10]
        
        # Top produits par mouvements
        context['top_products_by_movements'] = Product.objects.filter(
            is_active=True,
            stock_movements__created_at__gte=start_date
        ).annotate(
            movement_count=Count('stock_movements')
        ).order_by('-movement_count')[:10]
        
        # Mouvements par type (30 derniers jours)
        context['movements_by_type'] = StockMovement.objects.filter(
            created_at__gte=start_date
        ).values('movement_type').annotate(
            count=Count('id'),
            total_quantity=Sum('quantity')
        ).order_by('-count')
        
        # Mouvements par jour (7 derniers jours)
        context['daily_movements'] = StockMovement.objects.filter(
            created_at__gte=end_date - timedelta(days=7)
        ).extra(
            select={'day': 'date(created_at)'}
        ).values('day').annotate(
            count=Count('id'),
            total_quantity=Sum('quantity')
        ).order_by('day')
        
        # Alertes par type
        context['alerts_by_type'] = StockAlert.objects.filter(
            status='active'
        ).values('alert_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        return context


class StockValueReportView(LoginRequiredMixin, ManagerRequiredMixin, View):
    """Rapport de valeur des stocks"""
    
    def get(self, request):
        # Filtres
        category_id = request.GET.get('category')
        min_value = request.GET.get('min_value')
        max_value = request.GET.get('max_value')
        sort_by = request.GET.get('sort', 'stock_value')
        
        # Base queryset
        products = Product.objects.filter(is_active=True).select_related('category')
        
        # Appliquer les filtres
        if category_id:
            products = products.filter(category_id=category_id)
        
        # Annoter avec la valeur du stock
        products = products.annotate(
            stock_value=F('quantity') * F('price'),
            margin_value=F('quantity') * (F('price') - F('cost_price')) if F('cost_price') else 0
        )
        
        # Filtres de valeur
        if min_value:
            products = products.filter(stock_value__gte=min_value)
        if max_value:
            products = products.filter(stock_value__lte=max_value)
        
        # Tri
        if sort_by == 'stock_value':
            products = products.order_by('-stock_value')
        elif sort_by == 'quantity':
            products = products.order_by('-quantity')
        elif sort_by == 'name':
            products = products.order_by('name')
        
        # Pagination
        paginator = Paginator(products, 50)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Statistiques
        total_value = products.aggregate(total=Sum('stock_value'))['total'] or 0
        total_products = products.count()
        avg_value = total_value / total_products if total_products > 0 else 0
        
        context = {
            'products': page_obj,
            'total_value': total_value,
            'total_products': total_products,
            'avg_value': avg_value,
            'categories': Product.objects.values_list('category_id', 'category__name').distinct(),
        }
        
        return render(request, 'products/stock_value_report.html', context)


class StockMovementReportView(LoginRequiredMixin, ManagerRequiredMixin, View):
    """Rapport des mouvements de stock"""
    
    def get(self, request):
        # Période
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        if not start_date:
            start_date = (timezone.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = timezone.now().strftime('%Y-%m-%d')
        
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Filtres
        product_id = request.GET.get('product')
        movement_type = request.GET.get('movement_type')
        user_id = request.GET.get('user')
        
        # Base queryset
        movements = StockMovement.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).select_related('product', 'created_by')
        
        # Appliquer les filtres
        if product_id:
            movements = movements.filter(product_id=product_id)
        if movement_type:
            movements = movements.filter(movement_type=movement_type)
        if user_id:
            movements = movements.filter(created_by_id=user_id)
        
        # Pagination
        paginator = Paginator(movements.order_by('-created_at'), 100)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Statistiques
        stats = movements.aggregate(
            total_movements=Count('id'),
            total_quantity=Sum('quantity'),
            avg_quantity=Avg('quantity')
        )
        
        # Mouvements par type
        movements_by_type = movements.values('movement_type').annotate(
            count=Count('id'),
            total_quantity=Sum('quantity')
        ).order_by('-count')
        
        # Mouvements par produit
        movements_by_product = movements.values(
            'product__name', 'product__sku'
        ).annotate(
            count=Count('id'),
            total_quantity=Sum('quantity')
        ).order_by('-count')[:20]
        
        context = {
            'movements': page_obj,
            'stats': stats,
            'movements_by_type': movements_by_type,
            'movements_by_product': movements_by_product,
            'start_date': start_date,
            'end_date': end_date,
            'products': Product.objects.filter(is_active=True).order_by('name'),
            'movement_types': StockMovement.MOVEMENT_TYPES,
        }
        
        return render(request, 'products/stock_movement_report.html', context)


class LowStockReportView(LoginRequiredMixin, ManagerRequiredMixin, View):
    """Rapport des stocks faibles"""
    
    def get(self, request):
        # Filtres
        category_id = request.GET.get('category')
        alert_level = request.GET.get('alert_level', 'all')
        
        # Base queryset
        products = Product.objects.filter(is_active=True).select_related('category')
        
        # Appliquer les filtres
        if category_id:
            products = products.filter(category_id=category_id)
        
        # Filtrer par niveau d'alerte
        if alert_level == 'out_of_stock':
            products = products.filter(quantity=0)
        elif alert_level == 'low_stock':
            products = products.filter(quantity__lte=F('min_stock_level'), quantity__gt=0)
        elif alert_level == 'critical':
            products = products.filter(quantity__lte=F('min_stock_level') * 0.5, quantity__gt=0)
        
        # Annoter avec les informations de stock
        products = products.annotate(
            stock_value=F('quantity') * F('price'),
            days_remaining=0  # À calculer selon la vitesse de vente
        )
        
        # Pagination
        paginator = Paginator(products.order_by('quantity'), 50)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Statistiques
        stats = {
            'total_products': products.count(),
            'out_of_stock': products.filter(quantity=0).count(),
            'low_stock': products.filter(quantity__lte=F('min_stock_level'), quantity__gt=0).count(),
            'total_value_at_risk': products.aggregate(total=Sum('stock_value'))['total'] or 0,
        }
        
        context = {
            'products': page_obj,
            'stats': stats,
            'categories': Product.objects.values_list('category_id', 'category__name').distinct(),
            'alert_level': alert_level,
        }
        
        return render(request, 'products/low_stock_report.html', context)


class StockExportView(LoginRequiredMixin, ManagerRequiredMixin, View):
    """Export des données de stock"""
    
    def get(self, request):
        export_type = request.GET.get('type', 'csv')
        report_type = request.GET.get('report', 'products')
        
        if export_type == 'csv':
            return self.export_csv(report_type)
        elif export_type == 'json':
            return self.export_json(report_type)
        else:
            messages.error(request, "Type d'export non supporté")
            return redirect('stock:report_dashboard')
    
    def export_csv(self, report_type):
        """Export CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="stock_report_{report_type}_{timezone.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        
        if report_type == 'products':
            writer.writerow(['Nom', 'SKU', 'Catégorie', 'Prix', 'Stock', 'Stock Réservé', 'Stock Disponible', 'Valeur Stock', 'Statut'])
            
            products = Product.objects.filter(is_active=True).select_related('category')
            for product in products:
                writer.writerow([
                    product.name,
                    product.sku or '',
                    product.category.name,
                    product.price,
                    product.quantity,
                    product.reserved_quantity,
                    product.available_quantity,
                    product.quantity * product.price,
                    product.stock_status
                ])
        
        elif report_type == 'movements':
            writer.writerow(['Date', 'Produit', 'Type', 'Quantité', 'Avant', 'Après', 'Raison', 'Utilisateur'])
            
            movements = StockMovement.objects.select_related('product', 'created_by').order_by('-created_at')
            for movement in movements:
                writer.writerow([
                    movement.created_at.strftime('%Y-%m-%d %H:%M'),
                    movement.product.name,
                    movement.get_movement_type_display(),
                    movement.quantity,
                    movement.quantity_before,
                    movement.quantity_after,
                    movement.reason,
                    movement.created_by.get_full_name() if movement.created_by else 'Système'
                ])
        
        return response
    
    def export_json(self, report_type):
        """Export JSON"""
        data = {}
        
        if report_type == 'products':
            products = Product.objects.filter(is_active=True).select_related('category')
            data['products'] = []
            for product in products:
                data['products'].append({
                    'name': product.name,
                    'sku': product.sku,
                    'category': product.category.name,
                    'price': float(product.price),
                    'quantity': product.quantity,
                    'reserved_quantity': product.reserved_quantity,
                    'available_quantity': product.available_quantity,
                    'stock_value': float(product.quantity * product.price),
                    'stock_status': product.stock_status
                })
        
        response = JsonResponse(data, json_dumps_params={'indent': 2})
        response['Content-Disposition'] = f'attachment; filename="stock_report_{report_type}_{timezone.now().strftime("%Y%m%d")}.json"'
        return response


class StockAnalyticsAPIView(LoginRequiredMixin, ManagerRequiredMixin, View):
    """API pour les analytics de stock"""
    
    def get(self, request):
        chart_type = request.GET.get('chart', 'stock_value')
        period = request.GET.get('period', '30')  # jours
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=int(period))
        
        data = {}
        
        if chart_type == 'stock_value':
            # Évolution de la valeur du stock
            products = Product.objects.filter(is_active=True)
            data['labels'] = [product.name for product in products[:10]]
            data['values'] = [float(product.quantity * product.price) for product in products[:10]]
        
        elif chart_type == 'movements_trend':
            # Tendance des mouvements
            movements = StockMovement.objects.filter(
                created_at__gte=start_date
            ).extra(
                select={'day': 'date(created_at)'}
            ).values('day').annotate(
                count=Count('id')
            ).order_by('day')
            
            data['labels'] = [m['day'].strftime('%d/%m') for m in movements]
            data['values'] = [m['count'] for m in movements]
        
        elif chart_type == 'stock_status':
            # Répartition par statut
            products = Product.objects.filter(is_active=True)
            status_counts = {}
            for product in products:
                status = product.stock_status
                status_counts[status] = status_counts.get(status, 0) + 1
            
            data['labels'] = list(status_counts.keys())
            data['values'] = list(status_counts.values())
        
        return JsonResponse(data)
