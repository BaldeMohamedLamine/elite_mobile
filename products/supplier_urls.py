from django.urls import path
from . import views

app_name = 'suppliers'

urlpatterns = [
    path('', views.SupplierListView.as_view(), name='supplier_list'),
    path('dashboard/', views.SupplierDashboardView.as_view(), name='dashboard'),
    path('create/', views.SupplierCreateView.as_view(), name='supplier_create'),
    path('<str:supplier_uid>/', views.SupplierDetailView.as_view(), name='supplier_detail'),
    path('<str:supplier_uid>/edit/', views.SupplierUpdateView.as_view(), name='supplier_edit'),
    path('<str:supplier_uid>/delete/', views.SupplierDeleteView.as_view(), name='supplier_delete'),
]