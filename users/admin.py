from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string

from .models import User, UserProfile, TwoFactorSession, TwoFactorAttempt
from .forms import AdminUserCreationForm


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profil'
    fields = ('avatar', 'phone', 'address', 'city', 'postal_code', 'country', 'birth_date', 'bio')
    readonly_fields = ('created_at', 'updated_at')
    
    def get_queryset(self, request):
        """S'assurer que le profil existe avant de l'afficher"""
        qs = super().get_queryset(request)
        return qs


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = AdminUserCreationForm
    inlines = (UserProfileInline,)
    
    list_display = ('email', 'get_full_name', 'user_type', 'is_active', 'is_staff', 'must_change_password', 'date_joined')
    list_filter = ('user_type', 'is_active', 'is_staff', 'is_superuser', 'must_change_password', 'date_joined')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Informations personnelles', {'fields': ('first_name', 'last_name', 'user_type')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Gestion des mots de passe', {
            'fields': ('must_change_password', 'temporary_password', 'password_changed_at'),
            'classes': ('collapse',)
        }),
        ('Authentification à deux facteurs', {
            'fields': ('two_factor_enabled', 'two_factor_method', 'phone_number'),
            'classes': ('collapse',)
        }),
        ('Dates importantes', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'user_type', 'is_active', 'is_staff'),
        }),
    )
    
    readonly_fields = ('password_changed_at', 'last_login', 'date_joined')
    
    def get_fieldsets(self, request, obj=None):
        """Personnalise les fieldsets selon le type d'utilisateur"""
        if obj and obj.user_type == 'manager':
            # Pour les gestionnaires, masquer les champs de mot de passe
            fieldsets = list(super().get_fieldsets(request, obj))
            for i, (title, options) in enumerate(fieldsets):
                if title == (None, {'fields': ('email', 'password')}):
                    fieldsets[i] = (None, {'fields': ('email',)})
                elif title == 'Gestion des mots de passe':
                    fieldsets[i] = ('Gestion des mots de passe', {
                        'fields': ('must_change_password', 'temporary_password', 'password_changed_at'),
                        'classes': ('collapse',),
                        'description': 'Le mot de passe sera généré automatiquement et envoyé par email.'
                    })
            return fieldsets
        return super().get_fieldsets(request, obj)
    
    def get_form(self, request, obj=None, **kwargs):
        """Personnalise le formulaire selon le contexte"""
        if not obj:  # Création d'un nouvel utilisateur
            # Utiliser le formulaire d'ajout personnalisé
            kwargs['form'] = self.add_form
        return super().get_form(request, obj, **kwargs)
    
    def get_readonly_fields(self, request, obj=None):
        """Rend certains champs en lecture seule selon le contexte"""
        readonly = list(self.readonly_fields)
        if obj and obj.user_type == 'manager':
            readonly.extend(['password'])
        return readonly
    
    def save_model(self, request, obj, form, change):
        """Gère la sauvegarde spéciale pour les gestionnaires"""
        if obj.user_type == 'manager' and not change:
            # Nouveau gestionnaire - générer mot de passe temporaire
            temp_password = obj.set_temporary_password()
            obj.is_active = True
            obj.is_staff = True
            obj.must_change_password = True  # Forcer le changement de mot de passe
            
            # Envoyer l'email avec les identifiants
            self.send_manager_credentials(request, obj, temp_password)
            
            messages.success(
                request, 
                f'Gestionnaire créé avec succès. Les identifiants ont été envoyés à {obj.email}'
            )
        
        super().save_model(request, obj, form, change)
        
        # S'assurer que le profil existe après la sauvegarde
        if not hasattr(obj, 'profile'):
            UserProfile.objects.create(user=obj)
    
    def send_manager_credentials(self, request, user, password):
        """Envoie les identifiants de connexion au gestionnaire"""
        try:
            subject = 'Vos identifiants de connexion - Gestionnaire'
            context = {
                'user': user,
                'password': password,
                'login_url': request.build_absolute_uri(reverse('users:login')),
                'site_name': getattr(settings, 'SITE_NAME', 'Plateforme E-commerce')
            }
            
            html_message = render_to_string('users/emails/manager_credentials.html', context)
            plain_message = render_to_string('users/emails/manager_credentials.txt', context)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )
        except Exception as e:
            messages.error(request, f'Erreur lors de l\'envoi de l\'email: {str(e)}')
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    get_full_name.short_description = 'Nom complet'


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'city', 'country', 'created_at')
    list_filter = ('country', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'phone', 'city')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(TwoFactorSession)
class TwoFactorSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_verified', 'created_at', 'expires_at')
    list_filter = ('is_verified', 'created_at')
    search_fields = ('user__email', 'session_key')
    readonly_fields = ('session_key', 'created_at', 'expires_at')


@admin.register(TwoFactorAttempt)
class TwoFactorAttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'ip_address', 'success', 'method', 'created_at')
    list_filter = ('success', 'method', 'created_at')
    search_fields = ('user__email', 'ip_address')
    readonly_fields = ('created_at',)
