from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, ListView, DetailView, UpdateView, CreateView, DeleteView
from django.contrib import messages
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from django.urls import reverse_lazy

from orders.models import Order, OrderItem, Payment
from products.models import Product, Category, Stock
from users.models import User
from users.mixins import ManagerRequiredMixin
from .models import CompanySettings


class ManagerDashboardView(LoginRequiredMixin, ManagerRequiredMixin, TemplateView):
    """Dashboard principal du gestionnaire"""
    template_name = 'manager/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Statistiques générales
        today = timezone.now().date()
        this_month = today.replace(day=1)
        last_month = (this_month - timedelta(days=1)).replace(day=1)
        
        # Commandes
        total_orders = Order.objects.count()
        pending_orders = Order.objects.filter(status='pending').count()
        paid_orders = Order.objects.filter(payment_status='paid').count()
        delivered_orders = Order.objects.filter(status='delivered').count()
        
        # Ventes
        total_sales = Order.objects.filter(payment_status='paid').aggregate(
            total=Sum('total_amount')
        )['total'] or Decimal('0')
        
        monthly_sales = Order.objects.filter(
            payment_status='paid',
            created_at__gte=this_month
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        
        # Produits
        total_products = Product.objects.count()
        low_stock_products = Stock.objects.filter(
            current_quantity__lt=10,
            current_quantity__gt=0
        ).count()
        
        # Clients
        total_customers = User.objects.filter(is_staff=False).count()
        new_customers_this_month = User.objects.filter(
            date_joined__gte=this_month,
            is_staff=False
        ).count()
        
        # Commandes récentes
        recent_orders = Order.objects.select_related('customer').order_by('-created_at')[:10]
        
        # Top produits
        top_products = Product.objects.annotate(
            total_sold=Sum('orderitem__quantity')
        ).order_by('-total_sold')[:5]
        
        # Commandes par statut
        orders_by_status = Order.objects.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        # Ventes par mois (6 derniers mois)
        sales_by_month = []
        for i in range(6):
            month_start = (this_month - timedelta(days=30*i)).replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            month_sales = Order.objects.filter(
                payment_status='paid',
                created_at__gte=month_start,
                created_at__lte=month_end
            ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
            
            sales_by_month.append({
                'month': month_start.strftime('%B %Y'),
                'sales': month_sales
            })
        
        sales_by_month.reverse()
        
        context.update({
            # Statistiques générales
            'total_orders': total_orders,
            'pending_orders': pending_orders,
            'paid_orders': paid_orders,
            'delivered_orders': delivered_orders,
            'total_sales': total_sales,
            'monthly_sales': monthly_sales,
            'total_products': total_products,
            'low_stock_products': low_stock_products,
            'total_customers': total_customers,
            'new_customers_this_month': new_customers_this_month,
            
            # Données pour les graphiques
            'recent_orders': recent_orders,
            'top_products': top_products,
            'orders_by_status': orders_by_status,
            'sales_by_month': sales_by_month,
        })
        
        return context


class OrderListView(LoginRequiredMixin, ManagerRequiredMixin, ListView):
    """Liste des commandes pour le gestionnaire"""
    model = Order
    template_name = 'manager/orders/order_list.html'
    context_object_name = 'orders'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Order.objects.select_related('customer').order_by('-created_at')
        
        # Filtres
        status = self.request.GET.get('status')
        payment_status = self.request.GET.get('payment_status')
        search = self.request.GET.get('search')
        
        if status:
            queryset = queryset.filter(status=status)
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)
        if search:
            queryset = queryset.filter(
                Q(uid__icontains=search) |
                Q(customer__first_name__icontains=search) |
                Q(customer__last_name__icontains=search) |
                Q(customer__email__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = Order.STATUS_CHOICES
        context['payment_status_choices'] = [
            ('pending', 'En attente'),
            ('paid', 'Payé'),
            ('failed', 'Échoué'),
            ('refunded', 'Remboursé'),
        ]
        return context


class OrderDetailView(LoginRequiredMixin, ManagerRequiredMixin, DetailView):
    """Détails d'une commande pour le gestionnaire"""
    model = Order
    template_name = 'manager/orders/order_detail.html'
    context_object_name = 'order'
    pk_url_kwarg = 'order_uid'
    
    def get_object(self):
        return get_object_or_404(Order, uid=self.kwargs['order_uid'])


class OrderStatusUpdateView(LoginRequiredMixin, ManagerRequiredMixin, UpdateView):
    """Mise à jour du statut d'une commande"""
    model = Order
    fields = ['status']
    template_name = 'manager/orders/order_status_update.html'
    pk_url_kwarg = 'order_uid'
    
    def get_object(self):
        return get_object_or_404(Order, uid=self.kwargs['order_uid'])
    
    def form_valid(self, form):
        old_status = self.object.status
        order = form.save()
        
        # Si la commande est annulée et qu'elle était payée, restaurer les stocks
        if order.status == 'cancelled' and old_status in ['paid', 'processing']:
            order.restore_stock_quantities()
            messages.success(
                self.request, 
                f"Statut de la commande {order.uid} mis à jour: {order.get_status_display()}. "
                f"Les quantités en stock ont été restaurées."
            )
        else:
            messages.success(
                self.request, 
                f"Statut de la commande {order.uid} mis à jour: {order.get_status_display()}"
            )
        
        return redirect('manager:order_detail', order_uid=order.uid)


class ProductListView(LoginRequiredMixin, ManagerRequiredMixin, ListView):
    """Liste des produits pour le gestionnaire"""
    model = Product
    template_name = 'products/product_list_manager.html'
    context_object_name = 'products'
    paginate_by = 20
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_manager_view'] = True  # Flag pour identifier la vue manager
        context['categories'] = Category.objects.all()
        return context
    
    def get_queryset(self):
        queryset = Product.objects.select_related('category').order_by('-created_at')
        
        # Filtres
        category = self.request.GET.get('category')
        low_stock = self.request.GET.get('low_stock')
        search = self.request.GET.get('search')
        
        if category:
            queryset = queryset.filter(category_id=category)
        if low_stock:
            # Filtrer les produits avec stock faible
            low_stock_product_ids = Stock.objects.filter(
                current_quantity__lt=10,
                current_quantity__gt=0
            ).values_list('product_id', flat=True)
            queryset = queryset.filter(id__in=low_stock_product_ids)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        return context


class ProductDetailView(LoginRequiredMixin, ManagerRequiredMixin, DetailView):
    """Détails d'un produit pour le gestionnaire"""
    model = Product
    template_name = 'manager/products/product_detail.html'
    context_object_name = 'product'
    pk_url_kwarg = 'product_uid'
    
    def get_object(self):
        return get_object_or_404(Product, uid=self.kwargs['product_uid'])


class CustomerListView(LoginRequiredMixin, ManagerRequiredMixin, ListView):
    """Liste des clients pour le gestionnaire"""
    model = User
    template_name = 'manager/customers/customer_list.html'
    context_object_name = 'customers'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = User.objects.filter(is_staff=False).order_by('-date_joined')
        
        # Filtres
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search)
            )
        
        return queryset


class CustomerDetailView(LoginRequiredMixin, ManagerRequiredMixin, DetailView):
    """Détails d'un client pour le gestionnaire"""
    model = User
    template_name = 'manager/customers/customer_detail.html'
    context_object_name = 'customer'
    pk_url_kwarg = 'customer_id'
    
    def get_object(self):
        return get_object_or_404(User, id=self.kwargs['customer_id'], is_staff=False)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = self.get_object()
        
        # Commandes du client
        context['orders'] = Order.objects.filter(customer=customer).order_by('-created_at')
        
        # Statistiques du client
        context['total_orders'] = context['orders'].count()
        context['total_spent'] = context['orders'].filter(
            payment_status='paid'
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        
        return context


class CashPaymentConfirmationView(LoginRequiredMixin, ManagerRequiredMixin, DetailView):
    """Confirmation de paiement à la livraison pour le gestionnaire"""
    model = Order
    template_name = 'manager/orders/cash_payment_confirmation.html'
    context_object_name = 'order'
    pk_url_kwarg = 'order_uid'
    
    def get_object(self):
        return get_object_or_404(Order, uid=self.kwargs['order_uid'])
    
    def post(self, request, *args, **kwargs):
        order = self.get_object()
        
        # Récupérer le montant reçu
        amount_received_str = request.POST.get('amount_received', '0')
        try:
            cash_received = Decimal(amount_received_str)
        except (ValueError, InvalidOperation):
            messages.error(request, "Montant invalide. Veuillez entrer un nombre valide.")
            return self.get(request, *args, **kwargs)
        
        if cash_received <= 0:
            messages.error(request, "Le montant reçu doit être supérieur à 0.")
            return self.get(request, *args, **kwargs)
        
        if cash_received >= order.total_amount:
            # Créer le paiement
            payment = Payment.objects.create(
                order=order,
                amount=order.total_amount,
                method='cash_on_delivery',
                status='completed',
                cash_received=cash_received,
                cash_change=cash_received - order.total_amount
            )
            
            # Mettre à jour la commande
            order.payment_status = 'paid'
            order.paid_amount = order.total_amount
            order.cash_payment_confirmed = True
            order.cash_payment_confirmed_by = request.user
            order.cash_payment_confirmed_at = timezone.now()
            order.paid_at = timezone.now()
            order.status = 'paid'
            order.save()
            
            # Mettre à jour les quantités en stock
            order.update_stock_quantities()
            
            messages.success(
                request, 
                f"Paiement confirmé! Montant reçu: {cash_received} GNF, "
                f"Monnaie rendue: {cash_received - order.total_amount} GNF. "
                f"Les quantités en stock ont été mises à jour."
            )
            return redirect('manager:order_detail', order_uid=order.uid)
        else:
            messages.error(
                request, 
                f"Le montant reçu ({cash_received} GNF) est inférieur au montant attendu "
                f"({order.total_amount} GNF)"
            )
        
        return self.get(request, *args, **kwargs)


# Vues pour la gestion des catégories
class CategoryListView(LoginRequiredMixin, ManagerRequiredMixin, ListView):
    """Liste des catégories"""
    model = Category
    template_name = 'products/category_list.html'
    context_object_name = 'categories'
    
    def get_queryset(self):
        return Category.objects.annotate(
            product_count=Count('products')
        ).order_by('name')


class CategoryCreateView(LoginRequiredMixin, ManagerRequiredMixin, CreateView):
    """Créer une nouvelle catégorie"""
    model = Category
    template_name = 'products/category_form.html'
    fields = ['name']
    success_url = reverse_lazy('manager:category_list')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['name'].widget.attrs.update({
            'class': 'input input-bordered w-full',
            'placeholder': 'Ex: Électronique, Vêtements, Maison...'
        })
        return form
    
    def form_valid(self, form):
        messages.success(self.request, 'Catégorie créée avec succès!')
        return super().form_valid(form)


class CategoryUpdateView(LoginRequiredMixin, ManagerRequiredMixin, UpdateView):
    """Modifier une catégorie"""
    model = Category
    template_name = 'products/category_form.html'
    fields = ['name']
    success_url = reverse_lazy('manager:category_list')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['name'].widget.attrs.update({
            'class': 'input input-bordered w-full',
            'placeholder': 'Ex: Électronique, Vêtements, Maison...'
        })
        return form
    
    def form_valid(self, form):
        messages.success(self.request, 'Catégorie modifiée avec succès!')
        return super().form_valid(form)


class CategoryDeleteView(LoginRequiredMixin, ManagerRequiredMixin, DeleteView):
    """Supprimer une catégorie"""
    model = Category
    template_name = 'products/category_confirm_delete.html'
    success_url = reverse_lazy('manager:category_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Catégorie supprimée avec succès!')
        return super().delete(request, *args, **kwargs)


# Vues pour les paramètres de l'entreprise
class CompanySettingsView(LoginRequiredMixin, ManagerRequiredMixin, UpdateView):
    """Gestion des paramètres de l'entreprise"""
    model = CompanySettings
    template_name = 'manager/company_settings.html'
    fields = [
        'company_name', 'company_description', 'logo', 'address', 
        'phone', 'email', 'website', 'tax_number', 'registration_number',
        'show_logo_on_invoices', 'show_logo_on_receipts', 'show_logo_on_reports'
    ]
    success_url = reverse_lazy('manager:company_settings')
    
    def get_object(self):
        return CompanySettings.get_settings()
    
    def form_valid(self, form):
        messages.success(self.request, 'Paramètres de l\'entreprise mis à jour avec succès!')
        return super().form_valid(form)
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        
        # Appliquer les classes CSS aux champs
        for field_name, field in form.fields.items():
            if field_name == 'logo':
                field.widget.attrs.update({
                    'class': 'file-input file-input-bordered w-full',
                    'accept': 'image/*'
                })
            elif field_name == 'company_description':
                field.widget.attrs.update({
                    'class': 'textarea textarea-bordered w-full',
                    'rows': '3',
                    'placeholder': 'Décrivez votre entreprise en quelques mots...'
                })
            elif field_name in ['show_logo_on_invoices', 'show_logo_on_receipts', 'show_logo_on_reports']:
                field.widget.attrs.update({
                    'class': 'toggle toggle-primary'
                })
            else:
                field.widget.attrs.update({
                    'class': 'input input-bordered w-full',
                    'placeholder': f'Entrez {field.label.lower()}...'
                })
        
        return form
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Paramètres de l\'entreprise'
        context['page_description'] = 'Configurez les informations et le logo de votre entreprise'
        return context