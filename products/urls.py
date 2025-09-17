from django.urls import path, include

from .views import (
    ProductView, ProductDetailView, ProductCreateView, 
    ProductUpdateView, ProductDeleteView, ProductToggleStatusView,
    ProductManagerListView, CategoryListView, StockListView, StockDashboardView, StockAlertListView,
    StockMovementListView, ProductStockDetailView, StockAdjustmentView,
    AddToCartView, GetCartCountView
)

app_name = 'products'

urlpatterns = [
    path('', ProductView.as_view(), name='home'),
    path('produit/<str:identifier>', ProductDetailView.as_view(), name='product_detail'),
    
    # AJAX pour le panier
    path('add-to-cart/', AddToCartView.as_view(), name='add_to_cart'),
    path('cart-count/', GetCartCountView.as_view(), name='cart_count'),
    
    # Gestion des produits (pour les managers)
    path('manager/', ProductManagerListView.as_view(), name='product_manager_list'),
    path('create/', ProductCreateView.as_view(), name='product_create'),
    path('update/<str:uid>/', ProductUpdateView.as_view(), name='product_update'),
    path('delete/<str:uid>/', ProductDeleteView.as_view(), name='product_delete'),
    path('toggle-status/<str:uid>/', ProductToggleStatusView.as_view(), name='product_toggle_status'),
    
    # Gestion des catégories
    path('categories/', CategoryListView.as_view(), name='category_list'),
    
    # Gestion des stocks
    path('stock/', include('products.stock_urls')),
    
    # Variants (sera ajouté plus tard)
    # path('variants/', include('products.variant_urls')),
    
    # Suppliers
    path('suppliers/', include('products.supplier_urls')),
]