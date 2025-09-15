from django.contrib import admin
from .models import Cart, CartItem, Order, OrderItem, Payment, Refund, SupportTicket, SupportMessage
from .audit import AuditLog, SecurityEvent


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['uid', 'owner', 'created_at', 'nb_cart_items', 'amount']
    list_filter = ['created_at']
    search_fields = ['owner__first_name', 'owner__last_name', 'owner__email']
    readonly_fields = ['uid', 'created_at', 'amount', 'nb_cart_items']


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ['product', 'cart', 'quantity']
    list_filter = ['cart__created_at']
    search_fields = ['product__name', 'cart__owner__first_name']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'uid', 'customer', 'status', 'payment_method', 'payment_status', 
        'total_amount', 'created_at', 'is_paid'
    ]
    list_filter = [
        'status', 'payment_method', 'payment_status', 'created_at', 
        'cash_payment_confirmed'
    ]
    search_fields = [
        'uid', 'customer__first_name', 'customer__last_name', 
        'customer__email', 'delivery_phone'
    ]
    readonly_fields = [
        'uid', 'created_at', 'updated_at', 'paid_at', 'delivered_at',
        'cash_payment_confirmed_at', 'is_paid'
    ]
    fieldsets = (
        ('Informations générales', {
            'fields': ('uid', 'customer', 'status', 'created_at', 'updated_at')
        }),
        ('Paiement', {
            'fields': ('payment_method', 'payment_status', 'paid_at', 'is_paid')
        }),
        ('Livraison', {
            'fields': ('delivery_address', 'delivery_phone', 'delivery_notes')
        }),
        ('Montants', {
            'fields': ('subtotal', 'delivery_fee', 'total_amount', 'paid_amount')
        }),
        ('Paiement à la livraison', {
            'fields': (
                'cash_payment_confirmed', 'cash_payment_confirmed_by', 
                'cash_payment_confirmed_at'
            ),
            'classes': ('collapse',)
        }),
        ('Livraison', {
            'fields': ('delivered_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('customer')


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product', 'quantity', 'price_at_time']
    list_filter = ['order__created_at', 'order__status']
    search_fields = ['product__name', 'order__uid']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'uid', 'order', 'method', 'amount', 'status', 'created_at', 'completed_at'
    ]
    list_filter = ['method', 'status', 'created_at']
    search_fields = [
        'uid', 'order__uid', 'order__customer__first_name', 
        'orange_money_phone', 'transaction_id'
    ]
    readonly_fields = ['uid', 'created_at', 'completed_at']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('uid', 'order', 'method', 'amount', 'status', 'created_at', 'completed_at')
        }),
        ('Orange Money', {
            'fields': ('orange_money_transaction_id', 'orange_money_phone'),
            'classes': ('collapse',)
        }),
        ('Carte Visa/Mastercard', {
            'fields': ('card_last_four', 'card_brand', 'transaction_id'),
            'classes': ('collapse',)
        }),
        ('Paiement à la livraison', {
            'fields': ('cash_received', 'cash_change'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ['uid', 'order', 'amount', 'reason', 'status', 'requested_by', 'created_at']
    list_filter = ['status', 'reason', 'refund_method', 'created_at']
    search_fields = ['uid', 'order__uid', 'requested_by__email', 'requested_by__first_name', 'requested_by__last_name']
    readonly_fields = ['uid', 'created_at', 'processed_at', 'completed_at']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('uid', 'order', 'amount', 'reason', 'reason_description')
        }),
        ('Statut et traitement', {
            'fields': ('status', 'refund_method', 'refund_transaction_id')
        }),
        ('Gestion', {
            'fields': ('requested_by', 'processed_by', 'created_at', 'processed_at', 'completed_at')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('order__customer', 'requested_by', 'processed_by')


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ['uid', 'customer', 'subject', 'category', 'priority', 'status', 'assigned_to', 'created_at']
    list_filter = ['status', 'category', 'priority', 'created_at']
    search_fields = ['uid', 'subject', 'customer__email', 'customer__first_name', 'customer__last_name']
    readonly_fields = ['uid', 'created_at', 'updated_at', 'resolved_at']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('uid', 'customer', 'order', 'subject', 'description')
        }),
        ('Classification', {
            'fields': ('category', 'priority', 'status')
        }),
        ('Gestion', {
            'fields': ('assigned_to', 'created_at', 'updated_at', 'resolved_at')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('customer', 'order', 'assigned_to')


@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ['ticket', 'author', 'is_internal', 'created_at']
    list_filter = ['is_internal', 'created_at']
    search_fields = ['ticket__uid', 'author__email', 'author__first_name', 'author__last_name', 'message']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Message', {
            'fields': ('ticket', 'author', 'message', 'is_internal')
        }),
        ('Métadonnées', {
            'fields': ('created_at',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('ticket', 'author')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['uid', 'action_type', 'user', 'severity', 'success', 'created_at']
    list_filter = ['action_type', 'severity', 'success', 'created_at']
    search_fields = ['uid', 'description', 'user__email', 'ip_address', 'object_id']
    readonly_fields = ['uid', 'created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('uid', 'user', 'action_type', 'severity', 'description', 'created_at')
        }),
        ('Contexte de la requête', {
            'fields': ('ip_address', 'user_agent', 'request_path', 'request_method'),
            'classes': ('collapse',)
        }),
        ('Objet concerné', {
            'fields': ('object_type', 'object_id'),
            'classes': ('collapse',)
        }),
        ('Changements', {
            'fields': ('old_values', 'new_values'),
            'classes': ('collapse',)
        }),
        ('Résultat', {
            'fields': ('success', 'error_message', 'metadata'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def has_add_permission(self, request):
        return False  # Les logs d'audit ne doivent pas être créés manuellement


@admin.register(SecurityEvent)
class SecurityEventAdmin(admin.ModelAdmin):
    list_display = ['uid', 'event_type', 'severity', 'ip_address', 'blocked', 'created_at']
    list_filter = ['event_type', 'severity', 'blocked', 'created_at']
    search_fields = ['uid', 'description', 'ip_address', 'user__email', 'request_path']
    readonly_fields = ['uid', 'created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('uid', 'event_type', 'severity', 'description', 'created_at')
        }),
        ('Contexte de l\'événement', {
            'fields': ('ip_address', 'user_agent', 'user', 'request_path', 'request_method'),
            'classes': ('collapse',)
        }),
        ('Données de la requête', {
            'fields': ('request_data', 'response_status'),
            'classes': ('collapse',)
        }),
        ('Action et statut', {
            'fields': ('blocked', 'action_taken', 'metadata'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def has_add_permission(self, request):
        return False  # Les événements de sécurité ne doivent pas être créés manuellement
