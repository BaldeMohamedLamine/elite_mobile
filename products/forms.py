from django import forms
from .models import Product


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'cost_price', 'category', 'image', 'sku', 'barcode', 'weight', 'dimensions', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'input input-bordered w-full focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Nom du produit'
            }),
            'description': forms.Textarea(attrs={
                'class': 'textarea textarea-bordered w-full focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'rows': 4,
                'placeholder': 'Description du produit'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'input input-bordered w-full focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'step': '0.01',
                'placeholder': '0.00'
            }),
            'cost_price': forms.NumberInput(attrs={
                'class': 'input input-bordered w-full focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'step': '0.01',
                'placeholder': '0.00'
            }),
            'category': forms.Select(attrs={
                'class': 'select select-bordered w-full focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
            }),
            'image': forms.FileInput(attrs={
                'class': 'file-input file-input-bordered w-full focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
            }),
            'sku': forms.TextInput(attrs={
                'class': 'input input-bordered w-full focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Code SKU unique'
            }),
            'barcode': forms.TextInput(attrs={
                'class': 'input input-bordered w-full focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Code-barres'
            }),
            'weight': forms.NumberInput(attrs={
                'class': 'input input-bordered w-full focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'step': '0.01',
                'placeholder': '0.00'
            }),
            'dimensions': forms.TextInput(attrs={
                'class': 'input input-bordered w-full focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'L x l x H (cm)'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'checkbox checkbox-primary'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Rendre le champ SKU obligatoire
        self.fields['sku'].required = True
        self.fields['name'].required = True
        self.fields['description'].required = True
        self.fields['price'].required = True
        self.fields['category'].required = True
        
        # Ajouter des labels personnalisés
        self.fields['cost_price'].label = 'Prix d\'achat (optionnel)'
        self.fields['weight'].label = 'Poids (kg)'
        self.fields['dimensions'].label = 'Dimensions (L x l x H)'
        self.fields['is_active'].label = 'Produit actif'
        self.fields['is_active'].initial = True