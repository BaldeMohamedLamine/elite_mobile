from django.urls import path
from . import stock_views

app_name = 'stock'

urlpatterns = [
    path('', stock_views.StockListView.as_view(), name='stock_list'),
    path('dashboard/', stock_views.StockDashboardView.as_view(), name='stock_dashboard'),
    path('movements/', stock_views.StockMovementListView.as_view(), name='stock_movement_list'),
    path('<int:stock_id>/', stock_views.StockDetailView.as_view(), name='stock_detail'),
    path('<int:stock_id>/adjust/', stock_views.StockAdjustmentView.as_view(), name='stock_adjustment'),
    path('api/', stock_views.StockAPIView.as_view(), name='stock_api'),
]
