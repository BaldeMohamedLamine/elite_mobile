"""
Vues pour la gestion du stock
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.views.generic import ListView, DetailView, UpdateView, TemplateView
from django.http import JsonResponse
from django.db.models import Q, F, Sum, Count
from django.core.paginator import Paginator
from django.utils import timezone
from .models import Stock, StockMovement, Product
from .stock_forms import StockAdjustmentForm
import json


class ManagerRequiredMixin(UserPassesTestMixin):
    """Mixin pour vérifier que l'utilisateur est un manager"""
    
    def test_func(self):
        return self.request.user.is_staff and self.request.user.is_active
    
    def handle_no_permission(self):
        messages.error(self.request, "Accès refusé. Seuls les managers peuvent accéder à cette page.")
        return redirect('products:home')


class StockListView(LoginRequiredMixin, ManagerRequiredMixin, ListView):
    """Liste des stocks"""
    model = Stock
    template_name = 'products/stock_list.html'
    context_object_name = 'stocks'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Stock.objects.select_related('product', 'product__category').all()
        
        # Filtres
        status = self.request.GET.get('status')
        category = self.request.GET.get('category')
        search = self.request.GET.get('search')
        stock_type = self.request.GET.get('stock_type')
        
        if status:
            queryset = queryset.filter(status=status)
        if category:
            queryset = queryset.filter(product__category_id=category)
        if search:
            queryset = queryset.filter(
                Q(product__name__icontains=search) |
                Q(product__description__icontains=search)
            )
        if stock_type:
            if stock_type == 'low_stock':
                queryset = queryset.filter(current_quantity__lte=F('min_quantity'), current_quantity__gt=0)
            elif stock_type == 'out_of_stock':
                queryset = queryset.filter(current_quantity=0)
            elif stock_type == 'available':
                queryset = queryset.filter(current_quantity__gt=F('min_quantity'))
        
        return queryset.order_by('-last_updated')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = Stock.STATUS_CHOICES
        context['categories'] = Product.objects.values_list('category__id', 'category__name').distinct()
        
        # Statistiques
        context['stats'] = {
            'total_products': Stock.objects.count(),
            'available_products': Stock.objects.filter(status='available').count(),
            'low_stock_products': Stock.objects.filter(status='low_stock').count(),
            'out_of_stock_products': Stock.objects.filter(status='out_of_stock').count(),
            'total_quantity': Stock.objects.aggregate(total=Sum('current_quantity'))['total'] or 0,
        }
        
        return context


class StockDetailView(LoginRequiredMixin, ManagerRequiredMixin, DetailView):
    """Détail d'un stock"""
    model = Stock
    template_name = 'products/stock_detail.html'
    context_object_name = 'stock'
    pk_url_kwarg = 'stock_id'
    
    def get_object(self):
        return get_object_or_404(Stock, id=self.kwargs['stock_id'])
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        stock = self.get_object()
        
        # Mouvements récents
        context['recent_movements'] = stock.movements.select_related('user').order_by('-created_at')[:10]
        
        # Statistiques du produit
        context['movement_stats'] = {
            'total_movements': stock.movements.count(),
            'total_in': stock.movements.filter(movement_type='in').aggregate(total=Sum('quantity'))['total'] or 0,
            'total_out': stock.movements.filter(movement_type='out').aggregate(total=Sum('quantity'))['total'] or 0,
        }
        
        return context


class StockAdjustmentView(LoginRequiredMixin, ManagerRequiredMixin, UpdateView):
    """Ajustement du stock"""
    model = Stock
    form_class = StockAdjustmentForm
    template_name = 'products/stock_adjustment.html'
    pk_url_kwarg = 'stock_id'
    
    def get_object(self):
        return get_object_or_404(Stock, id=self.kwargs['stock_id'])
    
    def get_success_url(self):
        messages.success(self.request, f"Stock ajusté avec succès pour {self.object.product.name}")
        return reverse('products:stock:stock_detail', kwargs={'stock_id': self.object.id})
    
    def form_valid(self, form):
        stock = self.object
        new_quantity = form.cleaned_data['new_quantity']
        reason = form.cleaned_data['reason']
        
        # Ajuster le stock
        stock.adjust_stock(new_quantity, reason)
        
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Ajuster le stock - {self.object.product.name}'
        return context


class StockDashboardView(LoginRequiredMixin, ManagerRequiredMixin, TemplateView):
    """Dashboard du stock"""
    template_name = 'products/stock_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Statistiques générales
        context['summary'] = {
            'total_products': Stock.objects.count(),
            'available_products': Stock.objects.filter(status='available').count(),
            'low_stock_products': Stock.objects.filter(status='low_stock').count(),
            'out_of_stock_products': Stock.objects.filter(status='out_of_stock').count(),
            'discontinued_products': Stock.objects.filter(status='discontinued').count(),
            'total_quantity': Stock.objects.aggregate(total=Sum('current_quantity'))['total'] or 0,
            'total_value': Stock.objects.aggregate(
                total=Sum(F('current_quantity') * F('product__price'))
            )['total'] or 0,
        }
        
        # Produits avec stock faible
        context['low_stock_products'] = Stock.objects.filter(
            status='low_stock'
        ).select_related('product', 'product__category')[:10]
        
        # Produits en rupture
        context['out_of_stock_products'] = Stock.objects.filter(
            status='out_of_stock'
        ).select_related('product', 'product__category')[:10]
        
        # Mouvements récents
        context['recent_movements'] = StockMovement.objects.select_related(
            'stock__product', 'user'
        ).order_by('-created_at')[:10]
        
        # Top produits par quantité
        context['top_products_by_quantity'] = Stock.objects.select_related(
            'product', 'product__category'
        ).order_by('-current_quantity')[:10]
        
        # Mouvements par type (30 derniers jours)
        from datetime import timedelta
        thirty_days_ago = timezone.now() - timedelta(days=30)
        context['movements_by_type'] = StockMovement.objects.filter(
            created_at__gte=thirty_days_ago
        ).values('movement_type').annotate(
            count=Count('id'),
            total_quantity=Sum('quantity')
        ).order_by('-count')
        
        return context


class StockMovementListView(LoginRequiredMixin, ManagerRequiredMixin, ListView):
    """Liste des mouvements de stock"""
    model = StockMovement
    template_name = 'products/stock_movement_list.html'
    context_object_name = 'movements'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = StockMovement.objects.select_related(
            'stock__product', 'user'
        ).all()
        
        # Filtres
        movement_type = self.request.GET.get('movement_type')
        product_id = self.request.GET.get('product')
        user_id = self.request.GET.get('user')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        
        if movement_type:
            queryset = queryset.filter(movement_type=movement_type)
        if product_id:
            queryset = queryset.filter(stock__product_id=product_id)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['movement_types'] = StockMovement._meta.get_field('movement_type').choices
        context['products'] = Product.objects.all()
        context['users'] = StockMovement.objects.values_list('user__id', 'user__first_name', 'user__last_name').distinct()
        return context


class StockAPIView(LoginRequiredMixin, ManagerRequiredMixin, TemplateView):
    """API pour les opérations de stock"""
    
    def post(self, request):
        """Effectue une opération sur le stock"""
        try:
            data = json.loads(request.body)
            action = data.get('action')
            stock_id = data.get('stock_id')
            quantity = data.get('quantity', 0)
            reason = data.get('reason', 'Opération via API')
            
            stock = get_object_or_404(Stock, id=stock_id)
            
            if action == 'add':
                stock.add_stock(quantity, reason)
                return JsonResponse({
                    'success': True,
                    'message': f'{quantity} unités ajoutées au stock',
                    'new_quantity': stock.current_quantity
                })
            
            elif action == 'remove':
                stock.remove_stock(quantity, reason)
                return JsonResponse({
                    'success': True,
                    'message': f'{quantity} unités retirées du stock',
                    'new_quantity': stock.current_quantity
                })
            
            elif action == 'adjust':
                stock.adjust_stock(quantity, reason)
                return JsonResponse({
                    'success': True,
                    'message': f'Stock ajusté à {quantity} unités',
                    'new_quantity': stock.current_quantity
                })
            
            else:
                return JsonResponse({'error': 'Action invalide'}, status=400)
                
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def get(self, request):
        """Récupère les informations du stock"""
        stock_id = request.GET.get('stock_id')
        if stock_id:
            try:
                stock = Stock.objects.select_related('product').get(id=stock_id)
                return JsonResponse({
                    'success': True,
                    'stock': {
                        'id': stock.id,
                        'product_name': stock.product.name,
                        'current_quantity': stock.current_quantity,
                        'available_quantity': stock.available_quantity,
                        'status': stock.status,
                        'status_display': stock.get_status_display()
                    }
                })
            except Stock.DoesNotExist:
                return JsonResponse({'error': 'Stock non trouvé'}, status=404)
        
        return JsonResponse({'error': 'ID du stock requis'}, status=400)
