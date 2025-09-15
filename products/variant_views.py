"""
Vues pour la gestion des variantes de produits
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, F, Sum, Count
from django.core.paginator import Paginator
from .models import Product, ProductVariant, ProductVariantOption, ProductVariantImage
from .forms import ProductVariantForm, ProductVariantOptionForm, ProductVariantImageForm
import json


class ManagerRequiredMixin(UserPassesTestMixin):
    """Mixin pour vérifier que l'utilisateur est un manager"""
    
    def test_func(self):
        return self.request.user.is_staff and self.request.user.is_active
    
    def handle_no_permission(self):
        messages.error(self.request, "Accès refusé. Seuls les managers peuvent accéder à cette page.")
        return redirect('home')


class VariantListView(LoginRequiredMixin, ManagerRequiredMixin, ListView):
    """Liste des variantes disponibles"""
    model = ProductVariant
    template_name = 'products/variant_list.html'
    context_object_name = 'variants'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = ProductVariant.objects.all()
        
        # Filtres
        variant_type = self.request.GET.get('type')
        is_active = self.request.GET.get('active')
        search = self.request.GET.get('search')
        
        if variant_type:
            queryset = queryset.filter(variant_type=variant_type)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active == 'true')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(value__icontains=search)
            )
        
        return queryset.order_by('variant_type', 'display_order', 'name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['variant_types'] = ProductVariant.VARIANT_TYPES
        return context


class VariantCreateView(LoginRequiredMixin, ManagerRequiredMixin, CreateView):
    """Création d'une nouvelle variante"""
    model = ProductVariant
    form_class = ProductVariantForm
    template_name = 'products/variant_form.html'
    
    def get_success_url(self):
        messages.success(self.request, f"Variante '{self.object.name}' créée avec succès.")
        return redirect('/products/variants/')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Créer une nouvelle variante'
        context['submit_text'] = 'Créer la variante'
        return context


class VariantUpdateView(LoginRequiredMixin, ManagerRequiredMixin, UpdateView):
    """Modification d'une variante"""
    model = ProductVariant
    form_class = ProductVariantForm
    template_name = 'products/variant_form.html'
    pk_url_kwarg = 'variant_uid'
    
    def get_object(self):
        return get_object_or_404(ProductVariant, uid=self.kwargs['variant_uid'])
    
    def get_success_url(self):
        messages.success(self.request, f"Variante '{self.object.name}' modifiée avec succès.")
        return redirect('/products/variants/')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Modifier la variante "{self.object.name}"'
        context['submit_text'] = 'Modifier la variante'
        return context


class VariantDeleteView(LoginRequiredMixin, ManagerRequiredMixin, DeleteView):
    """Suppression d'une variante"""
    model = ProductVariant
    template_name = 'products/variant_confirm_delete.html'
    pk_url_kwarg = 'variant_uid'
    
    def get_object(self):
        return get_object_or_404(ProductVariant, uid=self.kwargs['variant_uid'])
    
    def get_success_url(self):
        messages.success(self.request, f"Variante '{self.object.name}' supprimée avec succès.")
        return redirect('/products/variants/')


class ProductVariantManagementView(LoginRequiredMixin, ManagerRequiredMixin, DetailView):
    """Gestion des variantes d'un produit"""
    model = Product
    template_name = 'products/product_variant_management.html'
    context_object_name = 'product'
    pk_url_kwarg = 'product_uid'
    
    def get_object(self):
        return get_object_or_404(Product, uid=self.kwargs['product_uid'])
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.get_object()
        
        # Variantes existantes du produit
        context['variant_options'] = product.variant_options.select_related('variant').all()
        
        # Variantes disponibles par type
        context['available_variants'] = ProductVariant.objects.filter(is_active=True).order_by('variant_type', 'display_order')
        
        # Statistiques
        context['stats'] = {
            'total_variants': product.variant_options.count(),
            'active_variants': product.variant_options.filter(is_active=True).count(),
            'low_stock_variants': product.variant_options.filter(
                stock_quantity__lte=F('min_stock_level')
            ).count(),
            'out_of_stock_variants': product.variant_options.filter(stock_quantity=0).count(),
        }
        
        return context


class ProductVariantOptionCreateView(LoginRequiredMixin, ManagerRequiredMixin, CreateView):
    """Création d'une option de variante pour un produit"""
    model = ProductVariantOption
    form_class = ProductVariantOptionForm
    template_name = 'products/variant_option_form.html'
    
    def dispatch(self, request, *args, **kwargs):
        self.product = get_object_or_404(Product, uid=kwargs['product_uid'])
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['product'] = self.product
        return kwargs
    
    def form_valid(self, form):
        form.instance.product = self.product
        return super().form_valid(form)
    
    def get_success_url(self):
        messages.success(self.request, f"Option de variante créée avec succès.")
        return redirect('/products/variants/product/{}/'.format(self.product.uid))
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['product'] = self.product
        context['title'] = f'Ajouter une variante à "{self.product.name}"'
        context['submit_text'] = 'Créer l\'option'
        return context


class ProductVariantOptionUpdateView(LoginRequiredMixin, ManagerRequiredMixin, UpdateView):
    """Modification d'une option de variante"""
    model = ProductVariantOption
    form_class = ProductVariantOptionForm
    template_name = 'products/variant_option_form.html'
    pk_url_kwarg = 'option_uid'
    
    def get_object(self):
        return get_object_or_404(ProductVariantOption, uid=self.kwargs['option_uid'])
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['product'] = self.object.product
        return kwargs
    
    def get_success_url(self):
        messages.success(self.request, f"Option de variante modifiée avec succès.")
        return redirect('/products/variants/product/{}/'.format(self.object.product.uid))
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['product'] = self.object.product
        context['title'] = f'Modifier l\'option "{self.object.variant.name}"'
        context['submit_text'] = 'Modifier l\'option'
        return context


class ProductVariantOptionDeleteView(LoginRequiredMixin, ManagerRequiredMixin, DeleteView):
    """Suppression d'une option de variante"""
    model = ProductVariantOption
    template_name = 'products/variant_option_confirm_delete.html'
    pk_url_kwarg = 'option_uid'
    
    def get_object(self):
        return get_object_or_404(ProductVariantOption, uid=self.kwargs['option_uid'])
    
    def get_success_url(self):
        messages.success(self.request, f"Option de variante supprimée avec succès.")
        return redirect('/products/variants/product/{}/'.format(self.object.product.uid))


class VariantStockAdjustmentView(LoginRequiredMixin, ManagerRequiredMixin, UpdateView):
    """Ajustement du stock d'une variante"""
    model = ProductVariantOption
    fields = ['stock_quantity']
    template_name = 'products/variant_stock_adjustment.html'
    pk_url_kwarg = 'option_uid'
    
    def get_object(self):
        return get_object_or_404(ProductVariantOption, uid=self.kwargs['option_uid'])
    
    def get_success_url(self):
        messages.success(self.request, f"Stock de la variante ajusté avec succès.")
        return redirect('/products/variants/product/{}/'.format(self.object.product.uid))
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['product'] = self.object.product
        return context


class VariantAPIView(LoginRequiredMixin, ManagerRequiredMixin, View):
    """API pour les variantes (AJAX)"""
    
    def get(self, request, product_uid):
        """Récupère les variantes d'un produit"""
        product = get_object_or_404(Product, uid=product_uid)
        variant_options = product.variant_options.select_related('variant').filter(is_active=True)
        
        data = []
        for option in variant_options:
            data.append({
                'id': str(option.uid),
                'variant_name': option.variant.name,
                'variant_type': option.variant.get_variant_type_display(),
                'sku': option.sku,
                'price': float(option.final_price),
                'stock_quantity': option.stock_quantity,
                'available_quantity': option.available_quantity,
                'stock_status': option.stock_status,
                'is_low_stock': option.is_low_stock,
                'is_out_of_stock': option.is_out_of_stock,
            })
        
        return JsonResponse({'variants': data})
    
    def post(self, request, product_uid):
        """Actions sur les variantes"""
        try:
            data = json.loads(request.body)
            action = data.get('action')
            option_uid = data.get('option_uid')
            
            if action == 'toggle_active':
                option = get_object_or_404(ProductVariantOption, uid=option_uid)
                option.is_active = not option.is_active
                option.save()
                return JsonResponse({'success': True, 'is_active': option.is_active})
            
            elif action == 'adjust_stock':
                option = get_object_or_404(ProductVariantOption, uid=option_uid)
                new_quantity = int(data.get('quantity', 0))
                option.stock_quantity = new_quantity
                option.save()
                return JsonResponse({
                    'success': True, 
                    'stock_quantity': option.stock_quantity,
                    'available_quantity': option.available_quantity,
                    'stock_status': option.stock_status
                })
            
            else:
                return JsonResponse({'error': 'Action invalide'}, status=400)
                
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
