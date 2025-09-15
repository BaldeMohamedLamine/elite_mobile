from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import redirect
from django.db.models import F, Q
from django.http import JsonResponse
from django.views import View
from django.urls import reverse
from django.db import models
import json

from .models import Product, Category, Stock
from .forms import ProductForm
from users.mixins import ManagerRequiredMixin
from orders.services import CartService


class ProductView(ListView):
    model = Product
    template_name = 'products/product_list_modern.html'
    context_object_name = 'products'
    paginate_by = 12  # 12 produits par page

    def get_queryset(self):
        queryset = self.model.objects.select_related('category', 'stock').order_by('-created_at')
        
        # Filtrage par recherche
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(description__icontains=search) |
                Q(sku__icontains=search)
            )
        
        # Filtrage par catégorie
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category_id=category)
        
        # Filtrage par prix
        price = self.request.GET.get('price')
        if price:
            if price == '0-50000':
                queryset = queryset.filter(price__lte=50000)
            elif price == '50000-100000':
                queryset = queryset.filter(price__gte=50000, price__lte=100000)
            elif price == '100000-500000':
                queryset = queryset.filter(price__gte=100000, price__lte=500000)
            elif price == '500000+':
                queryset = queryset.filter(price__gte=500000)
        
        # Tri
        sort = self.request.GET.get('sort')
        if sort:
            queryset = queryset.order_by(sort)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        return context


class ProductDetailView(DetailView):
    template_name = 'products/product_detail.html'
    context_object_name = 'product'

    def get_object(self):
        identifier = self.kwargs.get('identifier')
        try:
            # Essayer d'abord avec l'ID numérique
            if identifier.isdigit():
                return Product.objects.select_related('category').get(id=int(identifier))
            # Sinon, essayer avec l'UUID
            else:
                return Product.objects.select_related('category').get(uid=identifier)
        except (Product.DoesNotExist, ValueError):
            from django.http import Http404
            raise Http404("Produit non trouvé")

# Le mixin ManagerRequiredMixin est maintenant importé depuis users.mixins

# Vues de gestion des produits pour les managers
class ProductCreateView(LoginRequiredMixin, ManagerRequiredMixin, CreateView):
    """Création d'un nouveau produit"""
    model = Product
    form_class = ProductForm
    template_name = 'products/product_form.html'
    
    def get_success_url(self):
        messages.success(self.request, f"Produit '{self.object.name}' créé avec succès.")
        return reverse('products:home')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Créer un nouveau produit'
        context['submit_text'] = 'Créer le produit'
        context['object'] = None
        return context


class ProductUpdateView(LoginRequiredMixin, ManagerRequiredMixin, UpdateView):
    """Modification d'un produit"""
    model = Product
    form_class = ProductForm
    template_name = 'products/product_form.html'
    pk_url_kwarg = 'uid'
    
    def get_object(self):
        return Product.objects.get(uid=self.kwargs['uid'])
    
    def get_success_url(self):
        messages.success(self.request, f"Produit '{self.object.name}' modifié avec succès.")
        return reverse('products:home')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Modifier le produit "{self.object.name}"'
        context['submit_text'] = 'Modifier le produit'
        context['object'] = self.object
        return context


class ProductManagerListView(LoginRequiredMixin, ManagerRequiredMixin, ListView):
    """Liste des produits pour les managers"""
    model = Product
    template_name = 'products/product_list_manager_modern.html'
    context_object_name = 'products'
    paginate_by = 20

    def get_queryset(self):
        queryset = self.model.objects.select_related('category', 'stock').order_by('-created_at')
        
        # Filtrage par recherche
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(description__icontains=search) |
                Q(sku__icontains=search)
            )
        
        # Filtrage par catégorie
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category_id=category)
        
        # Filtrage par statut de stock
        stock_status = self.request.GET.get('stock_status')
        if stock_status:
            queryset = queryset.filter(stock__status=stock_status)
        
        # Tri
        sort = self.request.GET.get('sort')
        if sort:
            queryset = queryset.order_by(sort)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        
        # Statistiques
        total_products = Product.objects.count()
        available_products = Stock.objects.filter(status='available').count()
        low_stock_products = Stock.objects.filter(status='low_stock').count()
        out_of_stock_products = Stock.objects.filter(status='out_of_stock').count()
        
        context['stats'] = {
            'total_products': total_products,
            'available_products': available_products,
            'low_stock_products': low_stock_products,
            'out_of_stock_products': out_of_stock_products,
        }
        
        return context


class ProductDeleteView(LoginRequiredMixin, ManagerRequiredMixin, DeleteView):
    """Suppression d'un produit"""
    model = Product
    template_name = 'products/product_confirm_delete.html'
    pk_url_kwarg = 'uid'
    
    def get_object(self):
        return Product.objects.get(uid=self.kwargs['uid'])
    
    def get_success_url(self):
        messages.success(self.request, f"Produit supprimé avec succès.")
        return reverse('products:home')


class ProductToggleStatusView(LoginRequiredMixin, ManagerRequiredMixin, View):
    """Activation/Désactivation d'un produit"""
    
    def post(self, request, uid):
        product = Product.objects.get(uid=uid)
        product.is_active = not product.is_active
        product.save()
        
        status = "activé" if product.is_active else "désactivé"
        messages.success(request, f"Produit '{product.name}' {status} avec succès.")
        
        return JsonResponse({
            'success': True,
            'is_active': product.is_active,
            'message': f"Produit {status} avec succès"
        })


class CategoryListView(LoginRequiredMixin, ManagerRequiredMixin, ListView):
    """Liste des catégories pour le manager"""
    model = Category
    template_name = 'products/category_list.html'
    context_object_name = 'categories'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_manager_view'] = True
        return context


# Vues pour la gestion des stocks
class StockListView(ManagerRequiredMixin, ListView):
    model = Product
    template_name = 'products/stock_dashboard.html'
    context_object_name = 'products'
    
    def get_queryset(self):
        return self.model.objects.select_related('category').all()


class StockDashboardView(ManagerRequiredMixin, ListView):
    model = Product
    template_name = 'products/stock_dashboard.html'
    context_object_name = 'products'
    
    def get_queryset(self):
        return self.model.objects.select_related('category').all()


class StockAlertListView(ManagerRequiredMixin, ListView):
    model = Product
    template_name = 'products/stock_alert_list.html'
    context_object_name = 'products'
    
    def get_queryset(self):
        # Produits avec stock faible (quantité < 10)
        return self.model.objects.filter(stock__current_quantity__lt=10).select_related('category', 'stock')


class StockMovementListView(ManagerRequiredMixin, ListView):
    model = Product
    template_name = 'products/stock_movement_list.html'
    context_object_name = 'products'
    
    def get_queryset(self):
        return self.model.objects.select_related('category').all()


class ProductStockDetailView(ManagerRequiredMixin, DetailView):
    model = Product
    template_name = 'products/product_stock_detail.html'
    context_object_name = 'product'
    pk_url_kwarg = 'product_uid'
    slug_field = 'uid'
    slug_url_kwarg = 'product_uid'


class StockAdjustmentView(ManagerRequiredMixin, UpdateView):
    model = Stock
    template_name = 'products/stock_adjustment.html'
    fields = ['current_quantity']
    pk_url_kwarg = 'stock_id'
    
    def get_success_url(self):
        return reverse('products:stock:stock_detail', kwargs={'stock_id': self.object.id})


# Vues pour la gestion des fournisseurs
class SupplierListView(ManagerRequiredMixin, ListView):
    model = Product
    template_name = 'products/supplier_list.html'
    context_object_name = 'products'
    
    def get_queryset(self):
        return self.model.objects.select_related('category').all()


class SupplierDashboardView(ManagerRequiredMixin, ListView):
    model = Product
    template_name = 'products/supplier_dashboard.html'
    context_object_name = 'products'
    
    def get_queryset(self):
        return self.model.objects.select_related('category').all()


class SupplierCreateView(ManagerRequiredMixin, CreateView):
    model = Product
    template_name = 'products/supplier_form.html'
    fields = ['name', 'description', 'price', 'category', 'image', 'sku', 'barcode', 'weight', 'dimensions', 'is_active']
    
    def get_success_url(self):
        return reverse('products:suppliers:supplier_list')


class SupplierDetailView(ManagerRequiredMixin, DetailView):
    model = Product
    template_name = 'products/supplier_detail.html'
    context_object_name = 'product'
    pk_url_kwarg = 'supplier_uid'
    slug_field = 'uid'
    slug_url_kwarg = 'supplier_uid'


class SupplierUpdateView(ManagerRequiredMixin, UpdateView):
    model = Product
    template_name = 'products/supplier_form.html'
    fields = ['name', 'description', 'price', 'category', 'image', 'sku', 'barcode', 'weight', 'dimensions', 'is_active']
    pk_url_kwarg = 'supplier_uid'
    slug_field = 'uid'
    slug_url_kwarg = 'supplier_uid'
    
    def get_success_url(self):
        return reverse('products:suppliers:supplier_detail', kwargs={'supplier_uid': self.object.uid})


class SupplierDeleteView(ManagerRequiredMixin, DeleteView):
    model = Product
    template_name = 'products/supplier_confirm_delete.html'
    pk_url_kwarg = 'supplier_uid'
    slug_field = 'uid'
    slug_url_kwarg = 'supplier_uid'
    
    def get_success_url(self):
        return reverse('products:suppliers:supplier_list')


# Vues AJAX pour l'ajout au panier
class AddToCartView(LoginRequiredMixin, View):
    """Vue AJAX pour ajouter un produit au panier"""
    
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': "Données JSON invalides."
            }, status=400)

        # Validation des données
        product_id = data.get('product_id')
        quantity = data.get('quantity', 1)

        if not product_id:
            return JsonResponse({
                'success': False,
                'message': "ID du produit manquant."
            }, status=400)

        if not isinstance(quantity, int) or quantity <= 0:
            return JsonResponse({
                'success': False,
                'message': "Quantité invalide."
            }, status=400)

        try:
            # Récupérer le produit
            product = Product.objects.get(id=product_id)
            
            # Vérifier le stock
            if hasattr(product, 'stock') and product.stock:
                if product.stock.available_quantity < quantity:
                    return JsonResponse({
                        'success': False,
                        'message': f"Stock insuffisant. Disponible: {product.stock.available_quantity}"
                    }, status=400)
            else:
                # Si pas de stock, utiliser la quantité du produit directement
                if hasattr(product, 'quantity') and product.quantity < quantity:
                    return JsonResponse({
                        'success': False,
                        'message': f"Stock insuffisant. Disponible: {product.quantity}"
                    }, status=400)

            # Ajouter au panier
            result = CartService.add_to_cart(
                user=request.user,
                product=product,
                quantity=quantity
            )

            if result['success']:
                return JsonResponse({
                    'success': True,
                    'message': f"Produit '{product.name}' ajouté au panier avec succès.",
                    'cart_count': result.get('cart_count', 0),
                    'cart_item_id': result.get('cart_item_id'),
                    'quantity': result.get('quantity')
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': result.get('message', 'Erreur lors de l\'ajout au panier.')
                }, status=400)

        except Product.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': "Produit non trouvé."
            }, status=404)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Unexpected error in AddToCartView: {e}")
            return JsonResponse({
                'success': False,
                'message': "Une erreur inattendue s'est produite."
            }, status=500)


class GetCartCountView(LoginRequiredMixin, View):
    """Vue AJAX pour obtenir le nombre d'articles dans le panier"""
    
    def get(self, request, *args, **kwargs):
        try:
            cart_count = CartService.get_cart_count(request.user)
            
            return JsonResponse({
                'success': True,
                'cart_count': cart_count
            })
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Unexpected error in GetCartCountView: {e}")
            return JsonResponse({
                'success': False,
                'message': "Erreur lors de la récupération du panier."
            }, status=500)
