"""
Mixins pour la gestion des droits d'accès
"""
from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse_lazy


class ClientRequiredMixin(UserPassesTestMixin):
    """
    Mixin pour s'assurer que seuls les clients peuvent accéder à la vue
    """
    login_url = reverse_lazy('users:login')
    
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_client()
    
    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            messages.warning(self.request, "Vous devez être connecté pour accéder à cette page.")
            return redirect(self.login_url)
        else:
            messages.error(self.request, "Accès refusé. Cette page est réservée aux clients.")
            return redirect('users:client_dashboard')


class ManagerRequiredMixin(UserPassesTestMixin):
    """
    Mixin pour s'assurer que seuls les gestionnaires peuvent accéder à la vue
    """
    login_url = reverse_lazy('users:login')
    
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_manager()
    
    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            messages.warning(self.request, "Vous devez être connecté pour accéder à cette page.")
            return redirect(self.login_url)
        else:
            messages.error(self.request, "Accès refusé. Cette page est réservée aux gestionnaires.")
            if self.request.user.is_client():
                return redirect('users:client_dashboard')
            else:
                return redirect('theme:home')


class AdminRequiredMixin(UserPassesTestMixin):
    """
    Mixin pour s'assurer que seuls les administrateurs peuvent accéder à la vue
    """
    login_url = reverse_lazy('users:login')
    
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_admin()
    
    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            messages.warning(self.request, "Vous devez être connecté pour accéder à cette page.")
            return redirect(self.login_url)
        else:
            messages.error(self.request, "Accès refusé. Cette page est réservée aux administrateurs.")
            if self.request.user.is_client():
                return redirect('users:client_dashboard')
            elif self.request.user.is_manager():
                return redirect('manager:dashboard')
            else:
                return redirect('theme:home')


class StaffRequiredMixin(UserPassesTestMixin):
    """
    Mixin pour s'assurer que seuls les membres du staff (gestionnaires + admins) peuvent accéder à la vue
    """
    login_url = reverse_lazy('users:login')
    
    def test_func(self):
        return self.request.user.is_authenticated and (self.request.user.is_manager() or self.request.user.is_admin())
    
    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            messages.warning(self.request, "Vous devez être connecté pour accéder à cette page.")
            return redirect(self.login_url)
        else:
            messages.error(self.request, "Accès refusé. Cette page est réservée au personnel.")
            if self.request.user.is_client():
                return redirect('users:client_dashboard')
            else:
                return redirect('theme:home')


class OwnerOrStaffRequiredMixin(UserPassesTestMixin):
    """
    Mixin pour s'assurer que seuls le propriétaire de l'objet ou le staff peuvent accéder à la vue
    """
    login_url = reverse_lazy('users:login')
    owner_field = 'user'  # Champ qui contient le propriétaire de l'objet
    
    def test_func(self):
        if not self.request.user.is_authenticated:
            return False
        
        # Le staff peut toujours accéder
        if self.request.user.is_manager() or self.request.user.is_admin():
            return True
        
        # Vérifier si l'utilisateur est le propriétaire de l'objet
        obj = self.get_object()
        owner = getattr(obj, self.owner_field, None)
        return owner == self.request.user
    
    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            messages.warning(self.request, "Vous devez être connecté pour accéder à cette page.")
            return redirect(self.login_url)
        else:
            messages.error(self.request, "Accès refusé. Vous ne pouvez accéder qu'à vos propres données.")
            if self.request.user.is_client():
                return redirect('users:client_dashboard')
            elif self.request.user.is_manager():
                return redirect('manager:dashboard')
            else:
                return redirect('theme:home')


class PublicAccessMixin:
    """
    Mixin pour les vues publiques (pas de restriction d'accès)
    """
    pass


class LoginRequiredMixin:
    """
    Mixin simple pour exiger une authentification
    """
    login_url = reverse_lazy('users:login')
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, "Vous devez être connecté pour accéder à cette page.")
            return redirect(self.login_url)
        return super().dispatch(request, *args, **kwargs)
