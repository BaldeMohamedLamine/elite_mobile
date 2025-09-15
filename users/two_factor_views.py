from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import View, TemplateView
from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
import uuid
import json

from .models import User, TwoFactorSession, TwoFactorAttempt
from .forms import (
    TwoFactorSetupForm, TwoFactorVerificationForm, 
    TwoFactorBackupCodeForm, TwoFactorDisableForm
)
from .two_factor import TwoFactorAuth, TwoFactorBackupCodes
from orders.audit import AuditLog


class TwoFactorSetupView(LoginRequiredMixin, View):
    """Vue pour configurer l'authentification 2FA"""
    
    def get(self, request):
        if request.user.two_factor_enabled:
            messages.info(request, "L'authentification 2FA est déjà activée.")
            return redirect('users:two_factor_status')
        
        form = TwoFactorSetupForm()
        return render(request, 'users/two_factor/setup.html', {'form': form})
    
    def post(self, request):
        form = TwoFactorSetupForm(request.POST)
        
        if form.is_valid():
            method = form.cleaned_data['method']
            phone_number = form.cleaned_data.get('phone_number')
            
            # Mettre à jour le profil utilisateur
            request.user.two_factor_method = method
            if method == 'sms' and phone_number:
                request.user.phone_number = phone_number
            request.user.save()
            
            # Générer et envoyer le code de vérification
            two_factor = TwoFactorAuth()
            code = two_factor.generate_code()
            
            # Envoyer le code
            if method == 'email':
                success = two_factor.send_email_code(request.user, code)
            else:  # SMS
                success = two_factor.send_sms_code(phone_number, code)
            
            if success:
                # Stocker le code
                two_factor.store_code(request.user, code, method)
                
                # Créer une session 2FA temporaire
                session_key = str(uuid.uuid4())
                TwoFactorSession.objects.create(
                    user=request.user,
                    session_key=session_key,
                    expires_at=timezone.now() + timezone.timedelta(minutes=10)
                )
                
                # Enregistrer l'action d'audit
                AuditLog.log_action(
                    user=request.user,
                    action_type='user_password_change',  # Utiliser un type existant
                    severity='medium',
                    description=f'Configuration de l\'authentification 2FA ({method})',
                    ip_address=self.get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    request_path=request.path,
                    request_method=request.method,
                    metadata={'2fa_method': method}
                )
                
                messages.success(request, f"Code de vérification envoyé par {method}.")
                return redirect('users:two_factor_verify', session_key=session_key)
            else:
                messages.error(request, "Erreur lors de l'envoi du code de vérification.")
        
        return render(request, 'users/two_factor/setup.html', {'form': form})
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class TwoFactorVerifyView(View):
    """Vue pour vérifier le code 2FA lors de la configuration"""
    
    def get(self, request, session_key):
        session = get_object_or_404(TwoFactorSession, session_key=session_key)
        
        if session.is_expired():
            messages.error(request, "La session a expiré. Veuillez recommencer.")
            return redirect('users:two_factor_setup')
        
        form = TwoFactorVerificationForm()
        return render(request, 'users/two_factor/verify.html', {
            'form': form,
            'session_key': session_key,
            'method': session.user.two_factor_method
        })
    
    def post(self, request, session_key):
        session = get_object_or_404(TwoFactorSession, session_key=session_key)
        
        if session.is_expired():
            messages.error(request, "La session a expiré. Veuillez recommencer.")
            return redirect('users:two_factor_setup')
        
        form = TwoFactorVerificationForm(request.POST)
        
        if form.is_valid():
            code = form.cleaned_data['code']
            two_factor = TwoFactorAuth()
            
            # Vérifier le code
            is_valid, message = two_factor.verify_code(session.user, code, session.user.two_factor_method)
            
            if is_valid:
                # Activer l'authentification 2FA
                session.user.two_factor_enabled = True
                session.user.save()
                
                # Marquer la session comme vérifiée
                session.is_verified = True
                session.save()
                
                # Générer les codes de sauvegarde
                backup_codes = TwoFactorBackupCodes().generate_backup_codes()
                session.user.two_factor_backup_codes = backup_codes
                session.user.save()
                
                # Enregistrer l'action d'audit
                AuditLog.log_action(
                    user=session.user,
                    action_type='user_password_change',
                    severity='high',
                    description='Authentification 2FA activée avec succès',
                    ip_address=self.get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    request_path=request.path,
                    request_method=request.method,
                    metadata={'2fa_method': session.user.two_factor_method}
                )
                
                messages.success(request, "Authentification 2FA activée avec succès !")
                return render(request, 'users/two_factor/backup_codes.html', {
                    'backup_codes': backup_codes
                })
            else:
                messages.error(request, message)
        
        return render(request, 'users/two_factor/verify.html', {
            'form': form,
            'session_key': session_key,
            'method': session.user.two_factor_method
        })
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class TwoFactorStatusView(LoginRequiredMixin, TemplateView):
    """Vue pour afficher le statut de l'authentification 2FA"""
    template_name = 'users/two_factor/status.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        context['backup_codes_count'] = len(self.request.user.two_factor_backup_codes)
        return context


class TwoFactorDisableView(LoginRequiredMixin, View):
    """Vue pour désactiver l'authentification 2FA"""
    
    def get(self, request):
        if not request.user.two_factor_enabled:
            messages.info(request, "L'authentification 2FA n'est pas activée.")
            return redirect('users:two_factor_status')
        
        form = TwoFactorDisableForm(user=request.user)
        return render(request, 'users/two_factor/disable.html', {'form': form})
    
    def post(self, request):
        form = TwoFactorDisableForm(user=request.user, data=request.POST)
        
        if form.is_valid():
            # Désactiver l'authentification 2FA
            request.user.two_factor_enabled = False
            request.user.two_factor_method = 'email'
            request.user.phone_number = None
            request.user.two_factor_backup_codes = []
            request.user.save()
            
            # Supprimer les sessions 2FA actives
            TwoFactorSession.objects.filter(user=request.user).delete()
            
            # Enregistrer l'action d'audit
            AuditLog.log_action(
                user=request.user,
                action_type='user_password_change',
                severity='high',
                description='Authentification 2FA désactivée',
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                request_path=request.path,
                request_method=request.method
            )
            
            messages.success(request, "Authentification 2FA désactivée avec succès.")
            return redirect('users:two_factor_status')
        
        return render(request, 'users/two_factor/disable.html', {'form': form})
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class TwoFactorRegenerateBackupCodesView(LoginRequiredMixin, View):
    """Vue pour régénérer les codes de sauvegarde"""
    
    def post(self, request):
        if not request.user.two_factor_enabled:
            messages.error(request, "L'authentification 2FA n'est pas activée.")
            return redirect('users:two_factor_status')
        
        # Générer de nouveaux codes de sauvegarde
        backup_codes = TwoFactorBackupCodes().generate_backup_codes()
        request.user.two_factor_backup_codes = backup_codes
        request.user.save()
        
        # Enregistrer l'action d'audit
        AuditLog.log_action(
            user=request.user,
            action_type='user_password_change',
            severity='medium',
            description='Codes de sauvegarde 2FA régénérés',
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            request_path=request.path,
            request_method=request.method
        )
        
        messages.success(request, "Nouveaux codes de sauvegarde générés.")
        return render(request, 'users/two_factor/backup_codes.html', {
            'backup_codes': backup_codes
        })
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


@require_http_methods(["POST"])
@csrf_exempt
def send_verification_code(request):
    """API pour renvoyer un code de vérification"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Non authentifié'}, status=401)
    
    if not request.user.two_factor_enabled:
        return JsonResponse({'error': '2FA non activé'}, status=400)
    
    two_factor = TwoFactorAuth()
    code = two_factor.generate_code()
    
    # Envoyer le code
    if request.user.two_factor_method == 'email':
        success = two_factor.send_email_code(request.user, code)
    else:  # SMS
        success = two_factor.send_sms_code(request.user.phone_number, code)
    
    if success:
        two_factor.store_code(request.user, code, request.user.two_factor_method)
        return JsonResponse({'success': True, 'message': 'Code envoyé'})
    else:
        return JsonResponse({'error': 'Erreur lors de l\'envoi'}, status=500)
