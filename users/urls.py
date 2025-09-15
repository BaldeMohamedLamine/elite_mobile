from django.urls import path
from . import views
from .two_factor_views import (
    TwoFactorSetupView, TwoFactorVerifyView, TwoFactorStatusView,
    TwoFactorDisableView, TwoFactorRegenerateBackupCodesView, send_verification_code
)

app_name = 'users'

urlpatterns = [
    # Authentification de base
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('register/', views.ClientRegistrationView.as_view(), name='register'),
    path('activate/<str:uidb64>/<str:token>/', views.ActivationUserView.as_view(), name='activate_account'),
    
    # Dashboard client
    path('dashboard/', views.ClientDashboardView.as_view(), name='client_dashboard'),
    
    # Gestion des profils et mots de passe
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    path('change-password-required/', views.ChangePasswordRequiredView.as_view(), name='change_password_required'),
    
    # Authentification 2FA
    path('two-factor/setup/', TwoFactorSetupView.as_view(), name='two_factor_setup'),
    path('two-factor/verify/<str:session_key>/', TwoFactorVerifyView.as_view(), name='two_factor_verify'),
    path('two-factor/status/', TwoFactorStatusView.as_view(), name='two_factor_status'),
    path('two-factor/disable/', TwoFactorDisableView.as_view(), name='two_factor_disable'),
    path('two-factor/regenerate-backup-codes/', TwoFactorRegenerateBackupCodesView.as_view(), name='two_factor_regenerate_backup_codes'),
    path('api/send-verification-code/', send_verification_code, name='send_verification_code'),
    
    # Pages de test pour les contrôles d'accès (commentées temporairement)
    # path('test/manager-only/', views.ManagerOnlyTestView.as_view(), name='manager_only_test'),
    # path('test/client-only/', views.ClientOnlyTestView.as_view(), name='client_only_test'),
    # path('test/admin-only/', views.AdminOnlyTestView.as_view(), name='admin_only_test'),
]
