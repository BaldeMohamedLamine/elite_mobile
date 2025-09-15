"""
Formulaires pour la gestion des fournisseurs et dropshipping
"""
from django import forms
from django.core.exceptions import ValidationError
from .models import Supplier, DropshipProduct, Product


class SupplierForm(forms.ModelForm):
    """Formulaire pour créer/modifier un fournisseur"""
    
    class Meta:
        model = Supplier
        fields = [
            'name', 'company_name', 'contact_person', 'email', 'phone', 'website',
            'address_line1', 'address_line2', 'city', 'state_province', 'postal_code', 'country',
            'tax_id', 'business_license', 'payment_terms', 'credit_limit', 'discount_percentage',
            'status', 'is_verified', 'notes'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom du fournisseur'
            }),
            'company_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom de l\'entreprise'
            }),
            'contact_person': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Personne de contact'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@exemple.com'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+224 XXX XX XX XX'
            }),
            'website': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://www.exemple.com'
            }),
            'address_line1': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Adresse ligne 1'
            }),
            'address_line2': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Adresse ligne 2 (optionnel)'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ville'
            }),
            'state_province': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Région/Province'
            }),
            'postal_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Code postal'
            }),
            'country': forms.TextInput(attrs={
                'class': 'form-control',
                'value': 'Guinée'
            }),
            'tax_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Numéro de TVA/Impôt'
            }),
            'business_license': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Numéro de licence'
            }),
            'payment_terms': forms.Select(attrs={'class': 'form-select'}),
            'credit_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'discount_percentage': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '100'
            }),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'is_verified': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Notes internes sur ce fournisseur...'
            }),
        }
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        
        if email:
            # Vérifier l'unicité de l'email
            existing = Supplier.objects.filter(email=email).exclude(
                pk=self.instance.pk if self.instance else None
            )
            
            if existing.exists():
                raise ValidationError("Un fournisseur avec cet email existe déjà.")
        
        return email
    
    def clean_credit_limit(self):
        credit_limit = self.cleaned_data.get('credit_limit')
        
        if credit_limit is not None and credit_limit < 0:
            raise ValidationError("La limite de crédit ne peut pas être négative.")
        
        return credit_limit
    
    def clean_discount_percentage(self):
        discount = self.cleaned_data.get('discount_percentage')
        
        if discount is not None and (discount < 0 or discount > 100):
            raise ValidationError("Le pourcentage de remise doit être entre 0 et 100.")
        
        return discount


class DropshipProductForm(forms.ModelForm):
    """Formulaire pour créer/modifier un produit dropshipping"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filtrer les fournisseurs actifs
        self.fields['supplier'].queryset = Supplier.objects.filter(status='active')
        
        # Filtrer les produits actifs
        self.fields['product'].queryset = Product.objects.filter(is_active=True)
    
    class Meta:
        model = DropshipProduct
        fields = [
            'supplier', 'product', 'supplier_price', 'selling_price', 'virtual_stock',
            'min_order_quantity', 'max_order_quantity', 'estimated_delivery_days',
            'shipping_cost', 'is_active', 'is_featured', 'auto_reorder',
            'reorder_threshold', 'supplier_sku', 'supplier_url', 'notes'
        ]
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'product': forms.Select(attrs={'class': 'form-select'}),
            'supplier_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'selling_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'virtual_stock': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'min_order_quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'max_order_quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'estimated_delivery_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'shipping_cost': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'auto_reorder': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'reorder_threshold': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'supplier_sku': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'SKU du fournisseur'
            }),
            'supplier_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://www.exemple.com/produit'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Notes sur ce produit...'
            }),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        supplier = cleaned_data.get('supplier')
        product = cleaned_data.get('product')
        supplier_price = cleaned_data.get('supplier_price')
        selling_price = cleaned_data.get('selling_price')
        
        # Vérifier l'unicité de la combinaison fournisseur + produit
        if supplier and product:
            existing = DropshipProduct.objects.filter(
                supplier=supplier,
                product=product
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing.exists():
                raise ValidationError(
                    f"Ce produit est déjà associé à ce fournisseur."
                )
        
        # Vérifier que le prix de vente est supérieur au prix fournisseur
        if supplier_price and selling_price:
            if selling_price <= supplier_price:
                raise ValidationError(
                    "Le prix de vente doit être supérieur au prix fournisseur."
                )
        
        return cleaned_data
    
    def clean_supplier_price(self):
        price = self.cleaned_data.get('supplier_price')
        
        if price is not None and price < 0:
            raise ValidationError("Le prix fournisseur ne peut pas être négatif.")
        
        return price
    
    def clean_selling_price(self):
        price = self.cleaned_data.get('selling_price')
        
        if price is not None and price < 0:
            raise ValidationError("Le prix de vente ne peut pas être négatif.")
        
        return price
    
    def clean_virtual_stock(self):
        stock = self.cleaned_data.get('virtual_stock')
        
        if stock is not None and stock < 0:
            raise ValidationError("Le stock virtuel ne peut pas être négatif.")
        
        return stock
    
    def clean_min_order_quantity(self):
        quantity = self.cleaned_data.get('min_order_quantity')
        
        if quantity is not None and quantity < 1:
            raise ValidationError("La quantité minimum doit être au moins 1.")
        
        return quantity
    
    def clean_max_order_quantity(self):
        quantity = self.cleaned_data.get('max_order_quantity')
        min_quantity = self.cleaned_data.get('min_order_quantity')
        
        if quantity is not None and quantity < 1:
            raise ValidationError("La quantité maximum doit être au moins 1.")
        
        if quantity and min_quantity and quantity < min_quantity:
            raise ValidationError(
                "La quantité maximum doit être supérieure à la quantité minimum."
            )
        
        return quantity


class SupplierBulkImportForm(forms.Form):
    """Formulaire pour l'import en masse de fournisseurs"""
    
    csv_file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv'
        }),
        help_text="Fichier CSV avec les colonnes: name,company_name,email,phone,address_line1,city,country"
    )
    
    def clean_csv_file(self):
        file = self.cleaned_data.get('csv_file')
        
        if file:
            if not file.name.endswith('.csv'):
                raise ValidationError("Le fichier doit être au format CSV.")
            
            # Vérifier la taille du fichier (max 5MB)
            if file.size > 5 * 1024 * 1024:
                raise ValidationError("Le fichier ne doit pas dépasser 5MB.")
        
        return file


class DropshipProductBulkImportForm(forms.Form):
    """Formulaire pour l'import en masse de produits dropshipping"""
    
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.filter(status='active'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Fournisseur pour les produits à importer"
    )
    
    csv_file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv'
        }),
        help_text="Fichier CSV avec les colonnes: product_id,supplier_price,selling_price,virtual_stock,supplier_sku"
    )
    
    def clean_csv_file(self):
        file = self.cleaned_data.get('csv_file')
        
        if file:
            if not file.name.endswith('.csv'):
                raise ValidationError("Le fichier doit être au format CSV.")
            
            # Vérifier la taille du fichier (max 5MB)
            if file.size > 5 * 1024 * 1024:
                raise ValidationError("Le fichier ne doit pas dépasser 5MB.")
        
        return file
