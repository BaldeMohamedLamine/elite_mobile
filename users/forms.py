from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, PasswordChangeForm
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
import re

from .models import User, TwoFactorSession, UserProfile
from .utils.send_emails import send_activation_email
from .two_factor import TwoFactorAuth


class CustomAuthenticationForm(AuthenticationForm):
    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        user = authenticate(
            self.request, username=username, password=password
        )
        if user is None:
            raise ValidationError(
                "Email ou Mot de passe incorrect."
            )
        if not user.is_active:
            send_activation_email(user)
            raise ValidationError(
                ("Votre compte n'est pas ete actif, consulter votre boite "
                    "email pour activer votre compte")
            )
        
        # Stocker l'utilisateur pour get_user()
        self.user_cache = user
        return self.cleaned_data


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        help_text="Requis. Entrez une adresse email valide."
    )
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("Cette adresse email existe deja.")
        return email


class TwoFactorSetupForm(forms.Form):
    """Formulaire pour configurer l'authentification 2FA"""
    method = forms.ChoiceField(
        choices=[
            ('email', 'Email'),
            ('sms', 'SMS'),
        ],
        widget=forms.RadioSelect,
        initial='email'
    )
    phone_number = forms.CharField(
        max_length=20,
        required=False,
        help_text="Numéro de téléphone requis pour l'authentification SMS"
    )
    
    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        method = self.cleaned_data.get('method')
        
        if method == 'sms' and not phone_number:
            raise ValidationError("Le numéro de téléphone est requis pour l'authentification SMS.")
        
        if phone_number:
            # Validation basique du numéro de téléphone
            phone_pattern = r'^\+?[1-9]\d{1,14}$'
            if not re.match(phone_pattern, phone_number.replace(' ', '').replace('-', '')):
                raise ValidationError("Format de numéro de téléphone invalide.")
        
        return phone_number


class TwoFactorVerificationForm(forms.Form):
    """Formulaire pour la vérification 2FA"""
    code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control text-center',
            'placeholder': '000000',
            'maxlength': '6',
            'pattern': '[0-9]{6}'
        }),
        help_text="Entrez le code de vérification à 6 chiffres"
    )
    
    def clean_code(self):
        code = self.cleaned_data.get('code')
        if not code.isdigit() or len(code) != 6:
            raise ValidationError("Le code doit contenir exactement 6 chiffres.")
        return code


class TwoFactorBackupCodeForm(forms.Form):
    """Formulaire pour utiliser un code de sauvegarde"""
    backup_code = forms.CharField(
        max_length=8,
        min_length=8,
        widget=forms.TextInput(attrs={
            'class': 'form-control text-center',
            'placeholder': 'XXXXXXXX',
            'maxlength': '8'
        }),
        help_text="Entrez un code de sauvegarde à 8 caractères"
    )
    
    def clean_backup_code(self):
        backup_code = self.cleaned_data.get('backup_code')
        if len(backup_code) != 8:
            raise ValidationError("Le code de sauvegarde doit contenir exactement 8 caractères.")
        return backup_code.upper()


class TwoFactorDisableForm(forms.Form):
    """Formulaire pour désactiver l'authentification 2FA"""
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text="Confirmez votre mot de passe pour désactiver l'authentification 2FA"
    )
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_password(self):
        password = self.cleaned_data.get('password')
        if not self.user.check_password(password):
            raise ValidationError("Mot de passe incorrect.")
        return password


class ChangePasswordForm(forms.Form):
    """Formulaire pour changer le mot de passe"""
    new_password1 = forms.CharField(
        label="Nouveau mot de passe",
        widget=forms.PasswordInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'Nouveau mot de passe'
        }),
        help_text="Votre mot de passe doit contenir au moins 8 caractères."
    )
    new_password2 = forms.CharField(
        label="Confirmer le nouveau mot de passe",
        widget=forms.PasswordInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'Confirmer le nouveau mot de passe'
        })
    )
    
    def clean_new_password1(self):
        password1 = self.cleaned_data.get('new_password1')
        if len(password1) < 8:
            raise ValidationError("Le mot de passe doit contenir au moins 8 caractères.")
        return password1
    
    def clean(self):
        password1 = self.cleaned_data.get('new_password1')
        password2 = self.cleaned_data.get('new_password2')
        
        if password1 and password2 and password1 != password2:
            raise ValidationError("Les mots de passe ne correspondent pas.")
        
        return self.cleaned_data


class ProfileUpdateForm(forms.ModelForm):
    """Formulaire pour mettre à jour le profil utilisateur"""
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'Prénom'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'Nom'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'Email'
            }),
        }
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Cette adresse email est déjà utilisée.")
        return email


class UserProfileForm(forms.ModelForm):
    """Formulaire pour le profil utilisateur étendu"""
    class Meta:
        model = UserProfile
        fields = ['phone', 'address', 'city', 'postal_code', 'country', 'birth_date', 'bio', 'avatar']
        widgets = {
            'phone': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'Numéro de téléphone'
            }),
            'address': forms.Textarea(attrs={
                'class': 'textarea textarea-bordered w-full',
                'placeholder': 'Adresse complète',
                'rows': 3
            }),
            'city': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'Ville'
            }),
            'postal_code': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'Code postal'
            }),
            'country': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'Pays'
            }),
            'birth_date': forms.DateInput(attrs={
                'class': 'input input-bordered w-full',
                'type': 'date'
            }),
            'bio': forms.Textarea(attrs={
                'class': 'textarea textarea-bordered w-full',
                'placeholder': 'Biographie',
                'rows': 4
            }),
            'avatar': forms.FileInput(attrs={
                'class': 'file-input file-input-bordered w-full'
            }),
        }


class AdminUserCreationForm(forms.ModelForm):
    """Formulaire personnalisé pour l'ajout d'utilisateurs dans l'admin Django"""
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'user_type', 'is_active', 'is_staff')
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'vTextField',
                'placeholder': 'Adresse email'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'vTextField',
                'placeholder': 'Prénom'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'vTextField',
                'placeholder': 'Nom'
            }),
            'user_type': forms.Select(attrs={
                'class': 'vSelectField'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ajouter une note d'information pour les gestionnaires
        if 'user_type' in self.fields:
            self.fields['user_type'].help_text = (
                "Pour les gestionnaires, le mot de passe sera généré automatiquement et envoyé par email."
            )
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("Cette adresse email existe déjà.")
        return email
    
    def save(self, commit=True):
        user = super().save(commit=False)
        # Le mot de passe sera géré dans UserAdmin.save_model()
        if commit:
            user.save()
        return user
