from django.urls import path

from .views import (
    AddToCardView, UpdateCartItemView, RemoveFromCartView, CartOrderView, CheckoutView, PaymentProcessView,
    OrderDetailView, OrderListView, CashPaymentConfirmationView,
    InvoicePDFView, ReceiptPDFView, RefundRequestView, RefundListView, RefundDetailView,
    OrderStatusUpdateView, SupportTicketListView, SupportTicketCreateView, SupportTicketDetailView,
    CartCountView
)
from .audit_views import (
    AuditDashboardView, AuditLogListView, AuditLogDetailView,
    SecurityEventListView, SecurityEventDetailView
)

app_name = 'orders'

urlpatterns = [
    # Panier
    path('carts', AddToCardView.as_view(), name='add_to_cart'),
    path('carts/update', UpdateCartItemView.as_view(), name='update_cart_item'),
    path('carts/remove', RemoveFromCartView.as_view(), name='remove_from_cart'),
    path('carts/orders', CartOrderView.as_view(), name='list_cart_orders'),
    path('carts/count', CartCountView.as_view(), name='cart_count'),
    
    # Commande et paiement
    path('checkout', CheckoutView.as_view(), name='checkout'),
    path('payment/<str:order_uid>', PaymentProcessView.as_view(), name='payment_process'),
    
    # Commandes
    path('', OrderListView.as_view(), name='order_list'),
    path('<str:order_uid>', OrderDetailView.as_view(), name='order_detail'),
    
    # PDF
    path('<str:order_uid>/invoice', InvoicePDFView.as_view(), name='order_invoice_pdf'),
    path('<str:order_uid>/receipt', ReceiptPDFView.as_view(), name='order_receipt_pdf'),
    
    # Remboursements
    path('<str:order_uid>/refund', RefundRequestView.as_view(), name='refund_request'),
    path('refunds', RefundListView.as_view(), name='refund_list'),
    path('refunds/<str:refund_uid>', RefundDetailView.as_view(), name='refund_detail'),
    
    # Mise à jour statut commande
    path('<str:order_uid>/update-status', OrderStatusUpdateView.as_view(), name='order_status_update'),
    
    # Support client
    path('support', SupportTicketListView.as_view(), name='support_ticket_list'),
    path('support/create', SupportTicketCreateView.as_view(), name='support_ticket_create'),
    path('support/<str:ticket_uid>', SupportTicketDetailView.as_view(), name='support_ticket_detail'),
    
    # Confirmation paiement à la livraison (admin)
    path('admin/cash-payment/<str:order_uid>', CashPaymentConfirmationView.as_view(), name='cash_payment_confirmation'),
    
    # Audit et sécurité
    path('audit', AuditDashboardView.as_view(), name='audit_dashboard'),
    path('audit/logs', AuditLogListView.as_view(), name='audit_log_list'),
    path('audit/logs/<str:uid>', AuditLogDetailView.as_view(), name='audit_log_detail'),
    path('audit/security-events', SecurityEventListView.as_view(), name='security_event_list'),
    path('audit/security-events/<str:uid>', SecurityEventDetailView.as_view(), name='security_event_detail'),
]
