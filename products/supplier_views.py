"""
Vues pour la gestion des fournisseurs (dropshipping)
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View, TemplateView
from django.http import JsonResponse, HttpResponse
import csv
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q, F, Sum, Count, Avg
from django.core.paginator import Paginator
from django.db import transaction
from .models import Supplier, DropshipProduct, SupplierSale, SupplierInvoice
from .forms import SupplierForm, DropshipProductForm
from .dropshipping_services import DropshippingService
import json


class ManagerRequiredMixin(UserPassesTestMixin):
    """Mixin pour vérifier que l'utilisateur est un manager"""
    
    def test_func(self):
        return self.request.user.is_staff and self.request.user.is_active
    
    def handle_no_permission(self):
        messages.error(self.request, "Accès refusé. Seuls les managers peuvent accéder à cette page.")
        return redirect('home')


class SupplierListView(LoginRequiredMixin, ManagerRequiredMixin, ListView):
    """Liste des fournisseurs"""
    model = Supplier
    template_name = 'products/supplier_list.html'
    context_object_name = 'suppliers'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Supplier.objects.all()
        
        # Filtres
        status = self.request.GET.get('status')
        is_verified = self.request.GET.get('verified')
        search = self.request.GET.get('search')
        
        if status:
            queryset = queryset.filter(status=status)
        if is_verified is not None:
            queryset = queryset.filter(is_verified=is_verified == 'true')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(company_name__icontains=search) |
                Q(email__icontains=search)
            )
        
        return queryset.order_by('name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = Supplier.STATUS_CHOICES
        return context


class SupplierDetailView(LoginRequiredMixin, ManagerRequiredMixin, DetailView):
    """Détail d'un fournisseur"""
    model = Supplier
    template_name = 'products/supplier_detail.html'
    context_object_name = 'supplier'
    pk_url_kwarg = 'supplier_uid'
    
    def get_object(self):
        return get_object_or_404(Supplier, uid=self.kwargs['supplier_uid'])
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        supplier = self.get_object()
        
        # Statistiques du fournisseur
        context['stats'] = {
            'total_products': supplier.total_products,
            'active_products': supplier.active_products,
            'total_sales_value': supplier.total_sales_value,
            'total_commission_earned': supplier.total_commission_earned,
        }
        
        # Produits du fournisseur
        context['dropship_products'] = supplier.dropship_products.select_related('product').all()[:10]
        
        # Ventes récentes
        context['recent_sales'] = supplier.supplier_sales.select_related(
            'dropship_product__product', 'order'
        ).order_by('-created_at')[:10]
        
        # Factures récentes
        context['recent_invoices'] = supplier.invoices.order_by('-invoice_date')[:5]
        
        return context


class SupplierCreateView(LoginRequiredMixin, ManagerRequiredMixin, CreateView):
    """Création d'un nouveau fournisseur"""
    model = Supplier
    form_class = SupplierForm
    template_name = 'products/supplier_form.html'
    
    def get_success_url(self):
        messages.success(self.request, f"Fournisseur '{self.object.name}' créé avec succès.")
        return reverse('products:suppliers:supplier_detail', kwargs={'supplier_uid': self.object.uid})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Créer un nouveau fournisseur'
        context['submit_text'] = 'Créer le fournisseur'
        return context


class SupplierUpdateView(LoginRequiredMixin, ManagerRequiredMixin, UpdateView):
    """Modification d'un fournisseur"""
    model = Supplier
    form_class = SupplierForm
    template_name = 'products/supplier_form.html'
    pk_url_kwarg = 'supplier_uid'
    
    def get_object(self):
        return get_object_or_404(Supplier, uid=self.kwargs['supplier_uid'])
    
    def get_success_url(self):
        messages.success(self.request, f"Fournisseur '{self.object.name}' modifié avec succès.")
        return reverse('products:suppliers:supplier_detail', kwargs={'supplier_uid': self.object.uid})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Modifier le fournisseur "{self.object.name}"'
        context['submit_text'] = 'Modifier le fournisseur'
        return context


class SupplierDeleteView(LoginRequiredMixin, ManagerRequiredMixin, DeleteView):
    """Suppression d'un fournisseur"""
    model = Supplier
    template_name = 'products/supplier_confirm_delete.html'
    pk_url_kwarg = 'supplier_uid'
    
    def get_object(self):
        return get_object_or_404(Supplier, uid=self.kwargs['supplier_uid'])
    
    def get_success_url(self):
        messages.success(self.request, f"Fournisseur '{self.object.name}' supprimé avec succès.")
        return reverse('products:suppliers:supplier_list')


class SupplierVerificationView(LoginRequiredMixin, ManagerRequiredMixin, View):
    """Vérification d'un fournisseur"""
    
    def post(self, request, supplier_uid):
        supplier = get_object_or_404(Supplier, uid=supplier_uid)
        
        if supplier.is_verified:
            supplier.is_verified = False
            supplier.verified_at = None
            supplier.verified_by = None
            messages.info(request, f"Fournisseur '{supplier.name}' non vérifié.")
        else:
            supplier.is_verified = True
            supplier.verified_at = timezone.now()
            supplier.verified_by = request.user
            messages.success(request, f"Fournisseur '{supplier.name}' vérifié avec succès.")
        
        supplier.save()
        return redirect('products:suppliers:supplier_detail', supplier_uid=supplier.uid)


class SupplierStatusUpdateView(LoginRequiredMixin, ManagerRequiredMixin, View):
    """Mise à jour du statut d'un fournisseur"""
    
    def post(self, request, supplier_uid):
        supplier = get_object_or_404(Supplier, uid=supplier_uid)
        new_status = request.POST.get('status')
        
        if new_status in [choice[0] for choice in Supplier.STATUS_CHOICES]:
            old_status = supplier.get_status_display()
            supplier.status = new_status
            supplier.save()
            messages.success(
                request, 
                f"Statut du fournisseur '{supplier.name}' changé de '{old_status}' à '{supplier.get_status_display()}'."
            )
        else:
            messages.error(request, "Statut invalide.")
        
        return redirect('products:suppliers:supplier_detail', supplier_uid=supplier.uid)


class DropshipProductListView(LoginRequiredMixin, ManagerRequiredMixin, ListView):
    """Liste des produits dropshipping"""
    model = DropshipProduct
    template_name = 'products/dropship_product_list.html'
    context_object_name = 'dropship_products'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = DropshipProduct.objects.select_related('supplier', 'product').all()
        
        # Filtres
        supplier_id = self.request.GET.get('supplier')
        is_active = self.request.GET.get('active')
        stock_status = self.request.GET.get('stock_status')
        search = self.request.GET.get('search')
        
        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active == 'true')
        if stock_status:
            if stock_status == 'out_of_stock':
                queryset = queryset.filter(virtual_stock=0)
            elif stock_status == 'low_stock':
                queryset = queryset.filter(virtual_stock__lte=F('reorder_threshold'), virtual_stock__gt=0)
        if search:
            queryset = queryset.filter(
                Q(product__name__icontains=search) |
                Q(supplier__name__icontains=search) |
                Q(supplier_sku__icontains=search)
            )
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['suppliers'] = Supplier.objects.filter(status='active').order_by('name')
        return context


class DropshipProductCreateView(LoginRequiredMixin, ManagerRequiredMixin, CreateView):
    """Création d'un produit dropshipping"""
    model = DropshipProduct
    form_class = DropshipProductForm
    template_name = 'products/dropship_product_form.html'
    
    def get_success_url(self):
        messages.success(self.request, f"Produit dropshipping créé avec succès.")
        return reverse('products:suppliers:dropship_product_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Ajouter un produit dropshipping'
        context['submit_text'] = 'Créer le produit'
        return context


class DropshipProductUpdateView(LoginRequiredMixin, ManagerRequiredMixin, UpdateView):
    """Modification d'un produit dropshipping"""
    model = DropshipProduct
    form_class = DropshipProductForm
    template_name = 'products/dropship_product_form.html'
    pk_url_kwarg = 'dropship_product_uid'
    
    def get_object(self):
        return get_object_or_404(DropshipProduct, uid=self.kwargs['dropship_product_uid'])
    
    def get_success_url(self):
        messages.success(self.request, f"Produit dropshipping modifié avec succès.")
        return reverse('products:suppliers:dropship_product_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Modifier le produit "{self.object.product.name}"'
        context['submit_text'] = 'Modifier le produit'
        return context


class DropshipProductDeleteView(LoginRequiredMixin, ManagerRequiredMixin, DeleteView):
    """Suppression d'un produit dropshipping"""
    model = DropshipProduct
    template_name = 'products/dropship_product_confirm_delete.html'
    pk_url_kwarg = 'dropship_product_uid'
    
    def get_object(self):
        return get_object_or_404(DropshipProduct, uid=self.kwargs['dropship_product_uid'])
    
    def get_success_url(self):
        messages.success(self.request, f"Produit dropshipping supprimé avec succès.")
        return reverse('products:suppliers:dropship_product_list')


class SupplierDashboardView(LoginRequiredMixin, ManagerRequiredMixin, TemplateView):
    """Dashboard des fournisseurs"""
    template_name = 'products/supplier_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Statistiques générales
        context['summary'] = {
            'total_suppliers': Supplier.objects.count(),
            'active_suppliers': Supplier.objects.filter(status='active').count(),
            'verified_suppliers': Supplier.objects.filter(is_verified=True).count(),
            'total_dropship_products': DropshipProduct.objects.count(),
            'active_dropship_products': DropshipProduct.objects.filter(is_active=True).count(),
            'low_stock_products': DropshipProduct.objects.filter(
                virtual_stock__lte=F('reorder_threshold')
            ).count(),
            'out_of_stock_products': DropshipProduct.objects.filter(virtual_stock=0).count(),
        }
        
        # Top fournisseurs par nombre de produits
        context['top_suppliers_by_products'] = Supplier.objects.annotate(
            product_count=Count('dropship_products')
        ).order_by('-product_count')[:10]
        
        # Top fournisseurs par valeur des ventes
        context['top_suppliers_by_sales'] = Supplier.objects.annotate(
            sales_value=Sum(F('supplier_sales__quantity') * F('supplier_sales__selling_price'))
        ).order_by('-sales_value')[:10]
        
        # Produits avec stock faible
        context['low_stock_products'] = DropshipProduct.objects.filter(
            virtual_stock__lte=F('reorder_threshold'),
            is_active=True
        ).select_related('supplier', 'product')[:10]
        
        # Ventes récentes
        context['recent_sales'] = SupplierSale.objects.select_related(
            'supplier', 'dropship_product__product', 'order'
        ).order_by('-created_at')[:10]
        
        return context


class SupplierAPIView(LoginRequiredMixin, ManagerRequiredMixin, View):
    """API pour les fournisseurs (AJAX)"""
    
    def get(self, request):
        """Récupère les fournisseurs"""
        suppliers = Supplier.objects.filter(status='active')
        
        data = []
        for supplier in suppliers:
            data.append({
                'id': str(supplier.uid),
                'name': supplier.name,
                'company_name': supplier.company_name,
                'email': supplier.email,
                'phone': supplier.phone,
                'total_products': supplier.total_products,
                'active_products': supplier.active_products,
                'is_verified': supplier.is_verified,
            })
        
        return JsonResponse({'suppliers': data})
    
    def post(self, request):
        """Actions sur les fournisseurs"""
        try:
            data = json.loads(request.body)
            action = data.get('action')
            supplier_uid = data.get('supplier_uid')
            
            supplier = get_object_or_404(Supplier, uid=supplier_uid)
            
            if action == 'toggle_verification':
                supplier.is_verified = not supplier.is_verified
                if supplier.is_verified:
                    supplier.verified_at = timezone.now()
                    supplier.verified_by = request.user
                else:
                    supplier.verified_at = None
                    supplier.verified_by = None
                supplier.save()
                
                return JsonResponse({
                    'success': True, 
                    'is_verified': supplier.is_verified
                })
            
            elif action == 'update_status':
                new_status = data.get('status')
                if new_status in [choice[0] for choice in Supplier.STATUS_CHOICES]:
                    supplier.status = new_status
                    supplier.save()
                    return JsonResponse({
                        'success': True, 
                        'status': supplier.status,
                        'status_display': supplier.get_status_display()
                    })
                else:
                    return JsonResponse({'error': 'Statut invalide'}, status=400)
            
            else:
                return JsonResponse({'error': 'Action invalide'}, status=400)
                
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class DropshipOrderTrackingView(LoginRequiredMixin, ManagerRequiredMixin, ListView):
    """Suivi des commandes dropshipping"""
    model = SupplierSale
    template_name = 'products/dropship_order_tracking.html'
    context_object_name = 'supplier_sales'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = SupplierSale.objects.select_related(
            'supplier', 'dropship_product__product', 'order__user'
        ).all()
        
        # Filtres
        supplier_id = self.request.GET.get('supplier')
        status = self.request.GET.get('status')
        search = self.request.GET.get('search')
        
        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)
        if status:
            queryset = queryset.filter(status=status)
        if search:
            queryset = queryset.filter(
                Q(dropship_product__product__name__icontains=search) |
                Q(order__uid__icontains=search) |
                Q(supplier__name__icontains=search)
            )
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['suppliers'] = Supplier.objects.filter(status='active').order_by('name')
        context['status_choices'] = SupplierSale.STATUS_CHOICES
        return context


class DropshipOrderDetailView(LoginRequiredMixin, ManagerRequiredMixin, DetailView):
    """Détail d'une commande dropshipping"""
    model = SupplierSale
    template_name = 'products/dropship_order_detail.html'
    context_object_name = 'supplier_sale'
    pk_url_kwarg = 'sale_uid'
    
    def get_object(self):
        return get_object_or_404(SupplierSale, uid=self.kwargs['sale_uid'])


class DropshipOrderStatusUpdateView(LoginRequiredMixin, ManagerRequiredMixin, View):
    """Mise à jour du statut d'une commande dropshipping"""
    
    def post(self, request, sale_uid):
        supplier_sale = get_object_or_404(SupplierSale, uid=sale_uid)
        action = request.POST.get('action')
        
        try:
            if action == 'confirm':
                DropshippingService.confirm_dropship_sale(supplier_sale)
                messages.success(request, "Commande dropshipping confirmée avec succès.")
            elif action == 'ship':
                tracking_number = request.POST.get('tracking_number', '')
                DropshippingService.ship_dropship_sale(supplier_sale, tracking_number)
                messages.success(request, "Commande dropshipping marquée comme expédiée.")
            elif action == 'deliver':
                DropshippingService.deliver_dropship_sale(supplier_sale)
                messages.success(request, "Commande dropshipping marquée comme livrée.")
            elif action == 'cancel':
                reason = request.POST.get('reason', '')
                DropshippingService.cancel_dropship_sale(supplier_sale, reason)
                messages.success(request, "Commande dropshipping annulée.")
            else:
                messages.error(request, "Action invalide.")
        except Exception as e:
            messages.error(request, f"Erreur lors de la mise à jour: {str(e)}")
        
        return redirect('products:suppliers:dropship_order_detail', sale_uid=supplier_sale.uid)


class SupplierInvoiceListView(LoginRequiredMixin, ManagerRequiredMixin, ListView):
    """Liste des factures fournisseur"""
    model = SupplierInvoice
    template_name = 'products/supplier_invoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = SupplierInvoice.objects.select_related('supplier').all()
        
        # Filtres
        supplier_id = self.request.GET.get('supplier')
        status = self.request.GET.get('status')
        
        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset.order_by('-invoice_date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['suppliers'] = Supplier.objects.filter(status='active').order_by('name')
        context['status_choices'] = SupplierInvoice.STATUS_CHOICES
        return context


class SupplierInvoiceDetailView(LoginRequiredMixin, ManagerRequiredMixin, DetailView):
    """Détail d'une facture fournisseur"""
    model = SupplierInvoice
    template_name = 'products/supplier_invoice_detail.html'
    context_object_name = 'invoice'
    pk_url_kwarg = 'invoice_uid'
    
    def get_object(self):
        return get_object_or_404(SupplierInvoice, uid=self.kwargs['invoice_uid'])


class GenerateSupplierInvoiceView(LoginRequiredMixin, ManagerRequiredMixin, View):
    """Génération de factures fournisseur"""
    
    def post(self, request, supplier_uid):
        supplier = get_object_or_404(Supplier, uid=supplier_uid)
        
        # Période par défaut (30 derniers jours)
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        try:
            invoice = DropshippingService.generate_supplier_invoice(supplier, start_date, end_date)
            
            if invoice:
                messages.success(request, f"Facture générée avec succès: {invoice.invoice_number}")
                return redirect('products:suppliers:supplier_invoice_detail', invoice_uid=invoice.uid)
            else:
                messages.info(request, "Aucune vente à facturer pour cette période.")
                return redirect('products:suppliers:supplier_detail', supplier_uid=supplier.uid)
                
        except Exception as e:
            messages.error(request, f"Erreur lors de la génération de la facture: {str(e)}")
            return redirect('products:suppliers:supplier_detail', supplier_uid=supplier.uid)


class DropshipAnalyticsView(LoginRequiredMixin, ManagerRequiredMixin, TemplateView):
    """Analytics et rapports dropshipping"""
    template_name = 'products/dropship_analytics.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Période par défaut (30 derniers jours)
        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)
        
        # Statistiques générales
        context['summary'] = {
            'total_suppliers': Supplier.objects.count(),
            'active_suppliers': Supplier.objects.filter(status='active').count(),
            'total_dropship_products': DropshipProduct.objects.count(),
            'active_dropship_products': DropshipProduct.objects.filter(is_active=True).count(),
            'total_sales': SupplierSale.objects.count(),
            'sales_this_period': SupplierSale.objects.filter(created_at__gte=start_date).count(),
            'total_revenue': SupplierSale.objects.aggregate(
                total=Sum(F('quantity') * F('selling_price'))
            )['total'] or 0,
            'total_commission': SupplierSale.objects.aggregate(
                total=Sum('commission_earned')
            )['total'] or 0,
        }
        
        # Top fournisseurs par ventes
        context['top_suppliers_by_sales'] = Supplier.objects.annotate(
            sales_count=Count('supplier_sales'),
            total_revenue=Sum(F('supplier_sales__quantity') * F('supplier_sales__selling_price')),
            total_commission=Sum('supplier_sales__commission_earned')
        ).order_by('-total_revenue')[:10]
        
        # Top produits dropshipping
        context['top_dropship_products'] = DropshipProduct.objects.annotate(
            sales_count=Count('sales'),
            total_revenue=Sum(F('sales__quantity') * F('sales__selling_price')),
            total_commission=Sum('sales__commission_earned')
        ).order_by('-total_revenue')[:10]
        
        # Ventes par statut
        context['sales_by_status'] = SupplierSale.objects.values('status').annotate(
            count=Count('id'),
            total_revenue=Sum(F('quantity') * F('selling_price'))
        ).order_by('-count')
        
        # Ventes par mois (12 derniers mois)
        context['monthly_sales'] = SupplierSale.objects.filter(
            created_at__gte=end_date - timedelta(days=365)
        ).extra(
            select={'month': 'strftime("%Y-%m", created_at)'}
        ).values('month').annotate(
            count=Count('id'),
            total_revenue=Sum(F('quantity') * F('selling_price')),
            total_commission=Sum('commission_earned')
        ).order_by('month')
        
        # Fournisseurs avec stock faible
        context['suppliers_low_stock'] = Supplier.objects.annotate(
            low_stock_products=Count(
                'dropship_products',
                filter=Q(dropship_products__virtual_stock__lte=F('dropship_products__reorder_threshold'))
            )
        ).filter(low_stock_products__gt=0).order_by('-low_stock_products')[:10]
        
        return context


class DropshipReportView(LoginRequiredMixin, ManagerRequiredMixin, View):
    """Génération de rapports dropshipping"""
    
    def get(self, request):
        report_type = request.GET.get('type', 'sales')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        supplier_id = request.GET.get('supplier')
        
        # Période par défaut
        if not start_date:
            start_date = (timezone.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = timezone.now().strftime('%Y-%m-%d')
        
        start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Base queryset
        sales = SupplierSale.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).select_related('supplier', 'dropship_product__product', 'order')
        
        if supplier_id:
            sales = sales.filter(supplier_id=supplier_id)
        
        context = {
            'report_type': report_type,
            'start_date': start_date,
            'end_date': end_date,
            'supplier_id': supplier_id,
            'suppliers': Supplier.objects.filter(status='active').order_by('name'),
            'sales': sales.order_by('-created_at'),
            'summary': {
                'total_sales': sales.count(),
                'total_revenue': sales.aggregate(total=Sum(F('quantity') * F('selling_price')))['total'] or 0,
                'total_commission': sales.aggregate(total=Sum('commission_earned'))['total'] or 0,
                'total_supplier_amount': sales.aggregate(total=Sum(F('quantity') * F('supplier_price')))['total'] or 0,
            }
        }
        
        return render(request, 'products/dropship_report.html', context)


class DropshipExportView(LoginRequiredMixin, ManagerRequiredMixin, View):
    """Export des données dropshipping"""
    
    def get(self, request):
        export_type = request.GET.get('type', 'csv')
        data_type = request.GET.get('data', 'sales')
        
        if export_type == 'csv':
            return self.export_csv(data_type)
        elif export_type == 'json':
            return self.export_json(data_type)
        else:
            messages.error(request, "Type d'export non supporté")
            return redirect('products:suppliers:dropship_analytics')
    
    def export_csv(self, data_type):
        """Export CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="dropship_{data_type}_{timezone.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        
        if data_type == 'sales':
            writer.writerow(['Date', 'Fournisseur', 'Produit', 'Quantité', 'Prix Vente', 'Prix Fournisseur', 'Commission', 'Statut'])
            
            sales = SupplierSale.objects.select_related('supplier', 'dropship_product__product').order_by('-created_at')
            for sale in sales:
                writer.writerow([
                    sale.created_at.strftime('%Y-%m-%d %H:%M'),
                    sale.supplier.name,
                    sale.dropship_product.product.name,
                    sale.quantity,
                    sale.selling_price,
                    sale.supplier_price,
                    sale.commission_earned,
                    sale.get_status_display()
                ])
        
        elif data_type == 'suppliers':
            writer.writerow(['Nom', 'Entreprise', 'Email', 'Téléphone', 'Statut', 'Vérifié', 'Produits', 'Ventes'])
            
            suppliers = Supplier.objects.annotate(
                product_count=Count('dropship_products'),
                sales_count=Count('supplier_sales')
            )
            for supplier in suppliers:
                writer.writerow([
                    supplier.name,
                    supplier.company_name,
                    supplier.email,
                    supplier.phone,
                    supplier.get_status_display(),
                    'Oui' if supplier.is_verified else 'Non',
                    supplier.product_count,
                    supplier.sales_count
                ])
        
        return response
    
    def export_json(self, data_type):
        """Export JSON"""
        data = {}
        
        if data_type == 'sales':
            sales = SupplierSale.objects.select_related('supplier', 'dropship_product__product')
            data['sales'] = []
            for sale in sales:
                data['sales'].append({
                    'date': sale.created_at.isoformat(),
                    'supplier': sale.supplier.name,
                    'product': sale.dropship_product.product.name,
                    'quantity': sale.quantity,
                    'selling_price': float(sale.selling_price),
                    'supplier_price': float(sale.supplier_price),
                    'commission': float(sale.commission_earned),
                    'status': sale.status
                })
        
        response = JsonResponse(data, json_dumps_params={'indent': 2})
        response['Content-Disposition'] = f'attachment; filename="dropship_{data_type}_{timezone.now().strftime("%Y%m%d")}.json"'
        return response
