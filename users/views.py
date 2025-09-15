from django.contrib.auth.views import LoginView
from django.views.generic.edit import CreateView, View, UpdateView
from django.views.generic import ListView, TemplateView
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect, render
from django.utils.http import urlsafe_base64_decode
from django.contrib import messages
from django.db import transaction
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import logout, login, authenticate
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta

from .forms import CustomAuthenticationForm, CustomUserCreationForm, ChangePasswordForm, ProfileUpdateForm
from users.models import User, UserProfile
from .utils.send_emails import send_activation_email
from orders.models import Order
from products.models import Product
from .mixins import ManagerRequiredMixin, ClientRequiredMixin, AdminRequiredMixin


class CustomLoginView(LoginView):
    authentication_form = CustomAuthenticationForm
    template_name = 'registration/login.html'
    
    def form_valid(self, form):
        """Redirige vers le changement de mot de passe si nécessaire"""
        user = form.get_user()
        
        # Vérifier que l'utilisateur existe
        if user is None:
            print("DEBUG: User is None")
            return super().form_valid(form)
        
        print(f"DEBUG: User found: {user.email}")
        print(f"DEBUG: Must change password: {user.must_change_password}")
        print(f"DEBUG: User type: {user.user_type}")
        
        # Authentifier l'utilisateur D'ABORD
        login(self.request, user)
        print("DEBUG: User logged in successfully")
        
        # Vérifier si l'utilisateur doit changer son mot de passe
        if user.must_change_password:
            print("DEBUG: Redirecting to password change")
            return redirect('users:change_password_required')
        
        # Rediriger selon le type d'utilisateur
        if user.is_admin():
            print("DEBUG: Redirecting to admin")
            return redirect('/admin/')
        elif user.is_manager():
            print("DEBUG: Redirecting to manager dashboard")
            return redirect('manager:dashboard')
        else:
            print("DEBUG: Redirecting to client dashboard")
            return redirect('users:client_dashboard')


class CustomUserCreationView(CreateView):
    template_name = 'registration/register.html'
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('register')

    def form_valid(self, form):
        with transaction.atomic():
            user = form.save(commit=False)
            user.is_active = False
            user.save()
            send_activation_email(user)
        messages.success(
            self.request,
            ("Votre compte compte a ete cree, consulter "
                "votre boite email pour activer votre compte")
        )
        return redirect(self.success_url)


class ActivationUserView(View):
    login_url = reverse_lazy('users:login')

    def get(self, request, uidb64, token):
        id = urlsafe_base64_decode(uidb64)
        try:
            user = User.objects.get(id=id)
        except User.DoesNotExist:
            return render(request, 'registration/activation_invalid.html')

        if default_token_generator.check_token(user, token):
            user.is_active = True
            user.save()
            messages.success(
                self.request,
                "Votre compte a ete active. Vous pouvez vous connecter "
            )
            return redirect(self.login_url)
        return render(request, 'registration/activation_invalid.html')



class ProfileUserView(ListView):
    template_name = 'registration/user_profile.html'
    model = User


class LogoutView(View):
    login_url = reverse_lazy('users:login')

    def get(self, request):
        logout(request)
        messages.success(
            self.request,
            "Votre a ete deconnecte"
        )
        return redirect(self.login_url)


class ChangePasswordRequiredView(LoginRequiredMixin, View):
    """Vue pour forcer le changement de mot de passe"""
    template_name = 'registration/change_password_required.html'
    login_url = reverse_lazy('users:login')
    
    def get(self, request):
        if not request.user.must_change_password:
            return redirect('products:home')
        form = ChangePasswordForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        if not request.user.must_change_password:
            return redirect('products:home')
        
        form = ChangePasswordForm(request.POST)
        if form.is_valid():
            new_password = form.cleaned_data['new_password1']
            request.user.change_password(new_password)
            
            messages.success(
                request,
                "Votre mot de passe a été changé avec succès. Vous pouvez maintenant accéder à votre compte."
            )
            
            # Rediriger selon le type d'utilisateur
            if request.user.is_admin():
                return redirect('/admin/')
            elif request.user.is_manager():
                return redirect('manager:dashboard')
            else:
                return redirect('products:home')
        
        return render(request, self.template_name, {'form': form})


class ProfileView(LoginRequiredMixin, UpdateView):
    """Vue pour afficher et modifier le profil utilisateur"""
    model = User
    form_class = ProfileUpdateForm
    template_name = 'registration/profile.html'
    success_url = reverse_lazy('users:profile')
    
    def get_object(self):
        return self.request.user
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile'] = self.request.user.profile
        return context
    
    def form_valid(self, form):
        messages.success(self.request, "Votre profil a été mis à jour avec succès.")
        return super().form_valid(form)


class ChangePasswordView(LoginRequiredMixin, View):
    """Vue pour changer le mot de passe (optionnel)"""
    template_name = 'registration/change_password.html'
    
    def get(self, request):
        form = ChangePasswordForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = ChangePasswordForm(request.POST)
        if form.is_valid():
            new_password = form.cleaned_data['new_password1']
            request.user.change_password(new_password)
            
            messages.success(
                request,
                "Votre mot de passe a été changé avec succès."
            )
            return redirect('users:profile')
        
        return render(request, self.template_name, {'form': form})


class ClientRegistrationView(CreateView):
    """Vue pour l'inscription des clients"""
    template_name = 'registration/client_register.html'
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('users:login')
    
    def form_valid(self, form):
        with transaction.atomic():
            user = form.save(commit=False)
            user.user_type = 'client'  # Forcer le type client
            user.is_active = False
            user.save()
            send_activation_email(user)
        
        messages.success(
            self.request,
            "Votre compte client a été créé avec succès. Consultez votre boîte email pour activer votre compte."
        )
        return redirect(self.success_url)


class ClientDashboardView(LoginRequiredMixin, TemplateView):
    """Dashboard pour les clients"""
    template_name = 'users/client_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Statistiques du client
        total_orders = Order.objects.filter(customer=user).count()
        pending_orders = Order.objects.filter(customer=user, status='pending').count()
        delivered_orders = Order.objects.filter(customer=user, status='delivered').count()
        
        # Total dépensé
        total_spent = Order.objects.filter(
            customer=user, 
            payment_status='paid'
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        # Commandes récentes
        recent_orders = Order.objects.filter(customer=user).order_by('-created_at')[:5]
        
        # Produits populaires (pour suggestions)
        popular_products = Product.objects.filter(is_active=True).order_by('?')[:6]
        
        # Statistiques mensuelles
        this_month = timezone.now().replace(day=1)
        monthly_orders = Order.objects.filter(
            customer=user,
            created_at__gte=this_month
        ).count()
        
        context.update({
            'total_orders': total_orders,
            'pending_orders': pending_orders,
            'delivered_orders': delivered_orders,
            'total_spent': total_spent,
            'recent_orders': recent_orders,
            'popular_products': popular_products,
            'monthly_orders': monthly_orders,
        })
        
        return context


# Vues de test pour les contrôles d'accès
class ManagerOnlyTestView(LoginRequiredMixin, ManagerRequiredMixin, TemplateView):
    """Vue de test accessible uniquement aux gestionnaires"""
    template_name = 'users/test_access.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['access_type'] = 'Gestionnaire'
        context['message'] = 'Félicitations ! Vous avez accès à cette page car vous êtes un gestionnaire.'
        return context


class ClientOnlyTestView(LoginRequiredMixin, ClientRequiredMixin, TemplateView):
    """Vue de test accessible uniquement aux clients"""
    template_name = 'users/test_access.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['access_type'] = 'Client'
        context['message'] = 'Félicitations ! Vous avez accès à cette page car vous êtes un client.'
        return context


class AdminOnlyTestView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    """Vue de test accessible uniquement aux administrateurs"""
    template_name = 'users/test_access.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['access_type'] = 'Administrateur'
        context['message'] = 'Félicitations ! Vous avez accès à cette page car vous êtes un administrateur.'
        return context
