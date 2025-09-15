from django.contrib import admin
from django.contrib.admin import AdminSite
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import Product, Category, Stock, StockMovement


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'stock_status', 'created_at')
    list_filter = ('category', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('uid', 'created_at', 'stock_status')
    fieldsets = (
        ('Informations générales', {
            'fields': ('uid', 'name', 'description', 'category')
        }),
        ('Prix', {
            'fields': ('price',)
        }),
        ('Stock', {
            'fields': ('stock_status',),
            'description': 'Le stock est géré séparément dans la section Stock'
        }),
        ('Médias', {
            'fields': ('image',)
        }),
        ('Métadonnées', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def stock_status(self, obj):
        """Affiche le statut du stock"""
        try:
            stock = obj.stock
            status_colors = {
                'available': 'green',
                'low_stock': 'orange',
                'out_of_stock': 'red',
                'discontinued': 'gray'
            }
            color = status_colors.get(stock.status, 'black')
            return format_html(
                '<span style="color: {};">{} ({} unités)</span>',
                color,
                stock.get_status_display(),
                stock.current_quantity
            )
        except:
            return format_html('<span style="color: red;">Aucun stock</span>')
    stock_status.short_description = 'Statut du stock'


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ('product', 'current_quantity', 'available_quantity', 'status', 'last_updated')
    list_filter = ('status', 'is_active', 'auto_reorder')
    search_fields = ('product__name', 'product__description')
    readonly_fields = ('last_updated', 'last_movement', 'available_quantity')
    
    fieldsets = (
        ('Produit', {
            'fields': ('product',)
        }),
        ('Quantités', {
            'fields': ('current_quantity', 'reserved_quantity', 'available_quantity')
        }),
        ('Seuils', {
            'fields': ('min_quantity', 'max_quantity', 'reorder_quantity')
        }),
        ('Statut', {
            'fields': ('status', 'is_active', 'auto_reorder')
        }),
        ('Métadonnées', {
            'fields': ('last_updated', 'last_movement'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product')


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('stock', 'movement_type', 'quantity', 'quantity_before', 'quantity_after', 'reason', 'created_at')
    list_filter = ('movement_type', 'created_at')
    search_fields = ('stock__product__name', 'reason')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('Mouvement', {
            'fields': ('stock', 'movement_type', 'quantity', 'reason')
        }),
        ('Quantités', {
            'fields': ('quantity_before', 'quantity_after')
        }),
        ('Utilisateur', {
            'fields': ('user',)
        }),
        ('Métadonnées', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('stock__product', 'user')


