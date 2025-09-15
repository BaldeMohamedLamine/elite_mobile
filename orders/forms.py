from django import forms
from django.core.exceptions import ValidationError
from .models import Order, Payment, Refund, SupportTicket, SupportMessage
from .validators import (
    validate_phone_number, validate_card_number, validate_positive_decimal
)


class CheckoutForm(forms.Form):
    """Formulaire pour finaliser la commande"""
    
    PAYMENT_METHOD_CHOICES = [
        ('orange_money', 'Orange Money'),
        ('visa', 'Carte Visa/Mastercard'),
        ('cash_on_delivery', 'Paiement à la livraison'),
    ]
    
    # Informations de livraison
    delivery_address = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Adresse complète de livraison',
            'rows': 3
        }),
        label='Adresse de livraison',
        # Validation basique pour l'adresse
    )
    
    delivery_phone = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+224 XXX XX XX XX'
        }),
        label='Téléphone de livraison',
        max_length=20,
        validators=[validate_phone_number]
    )
    
    delivery_notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Instructions spéciales pour la livraison (optionnel)',
            'rows': 2
        }),
        label='Notes de livraison',
        required=False,
        # Validation basique pour les notes
    )
    
    # Méthode de paiement
    payment_method = forms.ChoiceField(
        choices=PAYMENT_METHOD_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label='Méthode de paiement'
    )
    
    # Conditions générales
    accept_terms = forms.BooleanField(
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='J\'accepte les conditions générales de vente',
        required=True
    )


class OrangeMoneyPaymentForm(forms.Form):
    """Formulaire pour paiement Orange Money"""
    
    phone_number = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '6XX XXX XXX',
        }),
        label='Numéro Orange Money',
        max_length=15,
        help_text='Format: 6XX XXX XXX',
        validators=[validate_phone_number]
    )


class VisaPaymentForm(forms.Form):
    """Formulaire pour paiement par carte Visa/Mastercard"""
    
    card_number = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '1234 5678 9012 3456',
            'maxlength': 19
        }),
        label='Numéro de carte',
        max_length=19,
        validators=[validate_card_number]
    )
    
    expiry_month = forms.ChoiceField(
        choices=[(i, f'{i:02d}') for i in range(1, 13)],
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Mois d\'expiration'
    )
    
    expiry_year = forms.ChoiceField(
        choices=[(i, i) for i in range(2024, 2035)],
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Année d\'expiration'
    )
    
    cvv = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '123',
            'maxlength': 4
        }),
        label='CVV',
        max_length=4,
        # Validation basique pour le CVC
    )
    
    cardholder_name = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nom du titulaire de la carte'
        }),
        label='Nom du titulaire',
        max_length=100
    )


class CashPaymentConfirmationForm(forms.Form):
    """Formulaire pour confirmer le paiement à la livraison (admin)"""
    
    cash_received = forms.DecimalField(
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0'
        }),
        label='Montant reçu (GNF)',
        max_digits=10,
        decimal_places=2
    )
    
    notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Notes sur le paiement (optionnel)',
            'rows': 3
        }),
        label='Notes',
        required=False
    )
    
    def __init__(self, *args, **kwargs):
        self.order = kwargs.pop('order', None)
        super().__init__(*args, **kwargs)
        
        if self.order:
            self.fields['cash_received'].initial = self.order.total_amount
            self.fields['cash_received'].help_text = f'Montant attendu: {self.order.total_amount} GNF'
    
    def clean_cash_received(self):
        cash_received = self.cleaned_data.get('cash_received')
        if self.order and cash_received < self.order.total_amount:
            raise ValidationError(
                f'Le montant reçu ({cash_received} GNF) est inférieur au montant attendu '
                f'({self.order.total_amount} GNF)'
            )
        return cash_received


class RefundRequestForm(forms.ModelForm):
    """Formulaire pour demander un remboursement"""
    
    class Meta:
        model = Refund
        fields = ['reason', 'reason_description', 'amount']
        widgets = {
            'reason': forms.Select(attrs={'class': 'form-select'}),
            'reason_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Décrivez la raison du remboursement...'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.order = kwargs.pop('order', None)
        super().__init__(*args, **kwargs)
        
        if self.order:
            self.fields['amount'].initial = self.order.total_amount
            self.fields['amount'].help_text = f'Montant maximum: {self.order.total_amount} GNF'
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if self.order and amount > self.order.total_amount:
            raise ValidationError(
                f'Le montant du remboursement ({amount} GNF) ne peut pas dépasser '
                f'le montant de la commande ({self.order.total_amount} GNF)'
            )
        if amount <= 0:
            raise ValidationError('Le montant du remboursement doit être positif')
        if amount > 1000000:  # Limite raisonnable
            raise ValidationError("Le montant semble trop élevé")
        
        return amount


class RefundProcessForm(forms.ModelForm):
    """Formulaire pour traiter un remboursement (admin)"""
    
    class Meta:
        model = Refund
        fields = ['status', 'refund_method', 'refund_transaction_id']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'refund_method': forms.Select(attrs={'class': 'form-select'}),
            'refund_transaction_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ID de transaction du remboursement'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrer les statuts disponibles selon l'état actuel
        if self.instance and self.instance.status:
            if self.instance.status == 'pending':
                self.fields['status'].choices = [
                    ('processing', 'En cours'),
                    ('completed', 'Terminé'),
                    ('cancelled', 'Annulé'),
                ]
            elif self.instance.status == 'processing':
                self.fields['status'].choices = [
                    ('completed', 'Terminé'),
                    ('failed', 'Échoué'),
                ]


class SupportTicketForm(forms.ModelForm):
    """Formulaire pour créer un ticket de support"""
    
    class Meta:
        model = SupportTicket
        fields = ['subject', 'description', 'category', 'priority', 'order']
        widgets = {
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Sujet de votre demande'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Décrivez votre problème en détail...'
            }),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'order': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user:
            # Filtrer les commandes de l'utilisateur
            self.fields['order'].queryset = Order.objects.filter(customer=self.user)
            self.fields['order'].required = False
            self.fields['order'].empty_label = "Aucune commande spécifique"


class SupportMessageForm(forms.ModelForm):
    """Formulaire pour ajouter un message à un ticket"""
    
    class Meta:
        model = SupportMessage
        fields = ['message', 'is_internal']
        widgets = {
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Votre message...'
            }),
            'is_internal': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Seuls les staff peuvent marquer un message comme interne
        if not (self.user and self.user.is_staff):
            self.fields['is_internal'].widget = forms.HiddenInput()
            self.fields['is_internal'].initial = False
