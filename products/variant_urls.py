"""
URLs pour la gestion des variantes de produits
"""
from django.urls import path
from .variant_views import (
    VariantListView,
    VariantCreateView,
    VariantUpdateView,
    VariantDeleteView,
    ProductVariantManagementView,
    ProductVariantOptionCreateView,
    ProductVariantOptionUpdateView,
    ProductVariantOptionDeleteView,
    VariantStockAdjustmentView,
    VariantAPIView,
)

app_name = 'variants'

urlpatterns = [
    # Gestion des variantes
    path('', VariantListView.as_view(), name='variant_list'),
    path('create/', VariantCreateView.as_view(), name='variant_create'),
    path('<str:variant_uid>/edit/', VariantUpdateView.as_view(), name='variant_edit'),
    path('<str:variant_uid>/delete/', VariantDeleteView.as_view(), name='variant_delete'),
    
    # Gestion des variantes de produits
    path('product/<str:product_uid>/', ProductVariantManagementView.as_view(), name='product_variant_management'),
    path('product/<str:product_uid>/option/create/', ProductVariantOptionCreateView.as_view(), name='variant_option_create'),
    path('option/<str:option_uid>/edit/', ProductVariantOptionUpdateView.as_view(), name='variant_option_edit'),
    path('option/<str:option_uid>/delete/', ProductVariantOptionDeleteView.as_view(), name='variant_option_delete'),
    path('option/<str:option_uid>/stock/', VariantStockAdjustmentView.as_view(), name='variant_stock_adjust'),
    
    # API
    path('api/product/<str:product_uid>/', VariantAPIView.as_view(), name='variant_api'),
]
