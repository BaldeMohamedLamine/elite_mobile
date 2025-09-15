"""
URLs pour les analytics de stock
"""
from django.urls import path
from .stock_analytics_views import (
    StockAnalyticsDashboardView,
    StockAnalyticsAPIView,
    StockForecastingView,
    StockTrendsAPIView,
    StockOptimizationView,
    stock_export_api,
)

app_name = 'stock_analytics'

urlpatterns = [
    # Dashboard
    path('', StockAnalyticsDashboardView.as_view(), name='dashboard'),
    
    # API
    path('api/', StockAnalyticsAPIView.as_view(), name='api'),
    path('api/trends/', StockTrendsAPIView.as_view(), name='trends_api'),
    path('api/export/', stock_export_api, name='export_api'),
    
    # Prévisions
    path('forecast/<int:product_id>/', StockForecastingView.as_view(), name='forecast'),
    
    # Optimisation
    path('optimization/', StockOptimizationView.as_view(), name='optimization'),
]
