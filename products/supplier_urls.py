from django.urls import path
from . import supplier_views

app_name = 'suppliers'

urlpatterns = [
    # URLs spécifiques (doivent être avant les URLs génériques)
    path('', supplier_views.SupplierListView.as_view(), name='supplier_list'),
    path('dashboard/', supplier_views.SupplierDashboardView.as_view(), name='dashboard'),
    path('create/', supplier_views.SupplierCreateView.as_view(), name='supplier_create'),
    
    # Dropship Products
    path('dropship-products/create/', supplier_views.DropshipProductCreateView.as_view(), name='dropship_product_create'),
    path('dropship-products/', supplier_views.DropshipProductListView.as_view(), name='dropship_product_list'),
    path('dropship-products/<str:product_uid>/', supplier_views.DropshipProductDetailView.as_view(), name='dropship_product_detail'),
    path('dropship-products/<str:product_uid>/edit/', supplier_views.DropshipProductUpdateView.as_view(), name='dropship_product_edit'),
    path('dropship-products/<str:product_uid>/delete/', supplier_views.DropshipProductDeleteView.as_view(), name='dropship_product_delete'),
    
    # Supplier Sales
    path('sales/', supplier_views.SupplierSaleListView.as_view(), name='supplier_sale_list'),
    path('sales/<str:sale_uid>/', supplier_views.SupplierSaleDetailView.as_view(), name='supplier_sale_detail'),
    path('sales/<str:sale_uid>/update/', supplier_views.SupplierSaleUpdateView.as_view(), name='supplier_sale_update'),
    
    # Supplier Invoices
    path('invoices/', supplier_views.SupplierInvoiceListView.as_view(), name='supplier_invoice_list'),
    path('invoices/<str:invoice_uid>/', supplier_views.SupplierInvoiceDetailView.as_view(), name='supplier_invoice_detail'),
    
    # URLs génériques (doivent être à la fin)
    path('<str:supplier_uid>/', supplier_views.SupplierDetailView.as_view(), name='supplier_detail'),
    path('<str:supplier_uid>/edit/', supplier_views.SupplierUpdateView.as_view(), name='supplier_edit'),
    path('<str:supplier_uid>/delete/', supplier_views.SupplierDeleteView.as_view(), name='supplier_delete'),
    path('<str:supplier_uid>/generate-invoice/', supplier_views.SupplierInvoiceGenerateView.as_view(), name='supplier_invoice_generate'),
    
    # Rapports fournisseurs
    path('<str:supplier_uid>/reports/sold/', supplier_views.SupplierSoldProductsReportView.as_view(), name='supplier_sold_products_report'),
    path('<str:supplier_uid>/reports/unsold/', supplier_views.SupplierUnsoldProductsReportView.as_view(), name='supplier_unsold_products_report'),
    path('<str:supplier_uid>/reports/sold/pdf/', supplier_views.SupplierSoldProductsPDFView.as_view(), name='supplier_sold_products_pdf'),
    path('<str:supplier_uid>/reports/unsold/pdf/', supplier_views.SupplierUnsoldProductsPDFView.as_view(), name='supplier_unsold_products_pdf'),
]