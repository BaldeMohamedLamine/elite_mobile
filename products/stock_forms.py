"""
Formulaires pour la gestion du stock
"""
from django import forms
from django.core.exceptions import ValidationError
from .models import Stock, StockMovement


class StockAdjustmentForm(forms.ModelForm):
    """Formulaire pour ajuster le stock"""
    
    new_quantity = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nouvelle quantité'
        }),
        label='Nouvelle quantité'
    )
    
    reason = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Raison de l\'ajustement'
        }),
        label='Raison de l\'ajustement',
        help_text='Ex: Réception de marchandise, Inventaire, Ajustement manuel, etc.'
    )
    
    class Meta:
        model = Stock
        fields = ['min_quantity', 'max_quantity', 'reorder_quantity', 'auto_reorder']
        widgets = {
            'min_quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'max_quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'reorder_quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'auto_reorder': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def clean_new_quantity(self):
        new_quantity = self.cleaned_data.get('new_quantity')
        if new_quantity is None:
            raise ValidationError("La quantité est requise")
        return new_quantity
    
    def clean_reason(self):
        reason = self.cleaned_data.get('reason')
        if not reason or len(reason.strip()) < 3:
            raise ValidationError("Veuillez fournir une raison valide (au moins 3 caractères)")
        return reason.strip()


class StockMovementForm(forms.ModelForm):
    """Formulaire pour créer un mouvement de stock"""
    
    class Meta:
        model = StockMovement
        fields = ['stock', 'movement_type', 'quantity', 'reason']
        widgets = {
            'stock': forms.Select(attrs={
                'class': 'form-select'
            }),
            'movement_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'reason': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Raison du mouvement'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrer les stocks actifs
        self.fields['stock'].queryset = Stock.objects.filter(is_active=True).select_related('product')
    
    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if quantity is None or quantity <= 0:
            raise ValidationError("La quantité doit être positive")
        return quantity
    
    def clean(self):
        cleaned_data = super().clean()
        stock = cleaned_data.get('stock')
        movement_type = cleaned_data.get('movement_type')
        quantity = cleaned_data.get('quantity')
        
        if stock and movement_type and quantity:
            if movement_type == 'out' and quantity > stock.available_quantity:
                raise ValidationError(
                    f"Quantité insuffisante. Stock disponible: {stock.available_quantity} unités"
                )
        
        return cleaned_data


class StockBulkAdjustmentForm(forms.Form):
    """Formulaire pour ajuster plusieurs stocks en masse"""
    
    stocks = forms.ModelMultipleChoiceField(
        queryset=Stock.objects.filter(is_active=True).select_related('product'),
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        }),
        label='Produits à ajuster'
    )
    
    adjustment_type = forms.ChoiceField(
        choices=[
            ('set', 'Définir la quantité'),
            ('add', 'Ajouter la quantité'),
            ('remove', 'Retirer la quantité'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Type d\'ajustement'
    )
    
    quantity = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Quantité'
        }),
        label='Quantité'
    )
    
    reason = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Raison de l\'ajustement'
        }),
        label='Raison de l\'ajustement'
    )
    
    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if quantity is None:
            raise ValidationError("La quantité est requise")
        return quantity
    
    def clean_reason(self):
        reason = self.cleaned_data.get('reason')
        if not reason or len(reason.strip()) < 3:
            raise ValidationError("Veuillez fournir une raison valide (au moins 3 caractères)")
        return reason.strip()
