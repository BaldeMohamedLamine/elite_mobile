from django.urls import path
from . import views
from orders.views import ManagerInvoicePDFView, ManagerReceiptPDFView

app_name = 'manager'

urlpatterns = [
    # Dashboard
    path('', views.ManagerDashboardView.as_view(), name='dashboard'),
    
    # Commandes
    path('orders/', views.OrderListView.as_view(), name='order_list'),
    path('orders/<str:order_uid>/', views.OrderDetailView.as_view(), name='order_detail'),
    path('orders/<str:order_uid>/update-status/', views.OrderStatusUpdateView.as_view(), name='order_status_update'),
    path('orders/<str:order_uid>/cash-payment/', views.CashPaymentConfirmationView.as_view(), name='cash_payment_confirmation'),
    
    # PDF pour les managers
    path('orders/<str:order_uid>/invoice/', ManagerInvoicePDFView.as_view(), name='order_invoice_pdf'),
    path('orders/<str:order_uid>/receipt/', ManagerReceiptPDFView.as_view(), name='order_receipt_pdf'),
    
    # Produits
    path('products/', views.ProductListView.as_view(), name='product_list'),
    path('products/<str:product_uid>/', views.ProductDetailView.as_view(), name='product_detail'),
    
    # Clients
    path('customers/', views.CustomerListView.as_view(), name='customer_list'),
    path('customers/<int:customer_id>/', views.CustomerDetailView.as_view(), name='customer_detail'),
    
]
