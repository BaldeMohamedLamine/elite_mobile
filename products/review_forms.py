"""
Formulaires pour le système de reviews et avis
"""
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.validators import FileExtensionValidator

from .models import ProductReview, ReviewImage, ReviewReport, ReviewHelpfulness


class ProductReviewForm(forms.ModelForm):
    """Formulaire pour créer ou modifier un avis produit"""
    
    class Meta:
        model = ProductReview
        fields = ['title', 'content', 'rating']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'Titre de votre avis...',
                'maxlength': 200
            }),
            'content': forms.Textarea(attrs={
                'class': 'textarea textarea-bordered w-full h-32',
                'placeholder': 'Partagez votre expérience avec ce produit...',
                'rows': 6
            }),
            'rating': forms.RadioSelect(attrs={
                'class': 'rating rating-lg'
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.product = kwargs.pop('product', None)
        super().__init__(*args, **kwargs)
        
        # Personnaliser les choix de rating
        self.fields['rating'].widget = forms.RadioSelect(
            choices=ProductReview.RATING_CHOICES,
            attrs={'class': 'rating rating-lg'}
        )
        
        # Ajouter des classes CSS
        self.fields['title'].widget.attrs.update({
            'class': 'input input-bordered w-full focus:ring-2 focus:ring-primary',
            'required': True
        })
        self.fields['content'].widget.attrs.update({
            'class': 'textarea textarea-bordered w-full h-32 focus:ring-2 focus:ring-primary',
            'required': True
        })
    
    def clean_rating(self):
        """Validation de la note"""
        rating = self.cleaned_data.get('rating')
        if not rating or rating < 1 or rating > 5:
            raise ValidationError('Veuillez sélectionner une note entre 1 et 5 étoiles.')
        return rating
    
    def clean_title(self):
        """Validation du titre"""
        title = self.cleaned_data.get('title')
        if not title or len(title.strip()) < 5:
            raise ValidationError('Le titre doit contenir au moins 5 caractères.')
        return title.strip()
    
    def clean_content(self):
        """Validation du contenu"""
        content = self.cleaned_data.get('content')
        if not content or len(content.strip()) < 20:
            raise ValidationError('Le contenu doit contenir au moins 20 caractères.')
        return content.strip()
    
    def save(self, commit=True):
        """Sauvegarder l'avis avec l'utilisateur et le produit"""
        review = super().save(commit=False)
        if self.user:
            review.user = self.user
        if self.product:
            review.product = self.product
        
        # Vérifier si l'utilisateur a acheté ce produit
        if self.user and self.product:
            # Ici, vous pourriez vérifier dans les commandes
            # review.is_verified_purchase = self._check_verified_purchase()
            pass
        
        if commit:
            review.save()
        return review
    
    def _check_verified_purchase(self):
        """Vérifier si l'utilisateur a acheté ce produit"""
        # Cette méthode devrait vérifier dans les commandes
        # Pour l'instant, on retourne False
        return False


class ReviewImageForm(forms.ModelForm):
    """Formulaire pour ajouter des images à un avis"""
    
    class Meta:
        model = ReviewImage
        fields = ['image', 'caption']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'file-input file-input-bordered w-full',
                'accept': 'image/*'
            }),
            'caption': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'Légende de l\'image (optionnel)',
                'maxlength': 200
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['image'].validators.append(
            FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif', 'webp'])
        )
        self.fields['image'].widget.attrs.update({
            'class': 'file-input file-input-bordered w-full focus:ring-2 focus:ring-primary'
        })
        self.fields['caption'].widget.attrs.update({
            'class': 'input input-bordered w-full focus:ring-2 focus:ring-primary'
        })
    
    def clean_image(self):
        """Validation de l'image"""
        image = self.cleaned_data.get('image')
        if image:
            # Vérifier la taille (max 5MB)
            if image.size > 5 * 1024 * 1024:
                raise ValidationError('L\'image ne doit pas dépasser 5MB.')
            
            # Vérifier les dimensions (max 2000x2000)
            from PIL import Image
            try:
                img = Image.open(image)
                if img.width > 2000 or img.height > 2000:
                    raise ValidationError('L\'image ne doit pas dépasser 2000x2000 pixels.')
            except Exception:
                raise ValidationError('Format d\'image non supporté.')
        
        return image


class ReviewReportForm(forms.ModelForm):
    """Formulaire pour signaler un avis"""
    
    class Meta:
        model = ReviewReport
        fields = ['reason', 'description']
        widgets = {
            'reason': forms.Select(attrs={
                'class': 'select select-bordered w-full focus:ring-2 focus:ring-primary'
            }),
            'description': forms.Textarea(attrs={
                'class': 'textarea textarea-bordered w-full h-24 focus:ring-2 focus:ring-primary',
                'placeholder': 'Décrivez pourquoi vous signalez cet avis...',
                'rows': 3
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['reason'].widget.attrs.update({
            'class': 'select select-bordered w-full focus:ring-2 focus:ring-primary'
        })
        self.fields['description'].widget.attrs.update({
            'class': 'textarea textarea-bordered w-full h-24 focus:ring-2 focus:ring-primary'
        })
    
    def clean_description(self):
        """Validation de la description"""
        description = self.cleaned_data.get('description', '')
        if description and len(description.strip()) < 10:
            raise ValidationError('La description doit contenir au moins 10 caractères.')
        return description.strip()


class ReviewHelpfulnessForm(forms.ModelForm):
    """Formulaire pour voter sur l'utilité d'un avis"""
    
    class Meta:
        model = ReviewHelpfulness
        fields = ['is_helpful']
        widgets = {
            'is_helpful': forms.HiddenInput()
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['is_helpful'].required = True


class ReviewModerationForm(forms.ModelForm):
    """Formulaire pour la modération des avis (admin)"""
    
    class Meta:
        model = ProductReview
        fields = ['status', 'moderation_notes']
        widgets = {
            'status': forms.Select(attrs={
                'class': 'select select-bordered w-full focus:ring-2 focus:ring-primary'
            }),
            'moderation_notes': forms.Textarea(attrs={
                'class': 'textarea textarea-bordered w-full h-24 focus:ring-2 focus:ring-primary',
                'placeholder': 'Notes de modération (optionnel)',
                'rows': 3
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status'].widget.attrs.update({
            'class': 'select select-bordered w-full focus:ring-2 focus:ring-primary'
        })
        self.fields['moderation_notes'].widget.attrs.update({
            'class': 'textarea textarea-bordered w-full h-24 focus:ring-2 focus:ring-primary'
        })


class ReviewFilterForm(forms.Form):
    """Formulaire pour filtrer les avis"""
    
    RATING_CHOICES = [
        ('', 'Toutes les notes'),
        ('5', '5 étoiles'),
        ('4', '4 étoiles'),
        ('3', '3 étoiles'),
        ('2', '2 étoiles'),
        ('1', '1 étoile'),
    ]
    
    SORT_CHOICES = [
        ('newest', 'Plus récents'),
        ('oldest', 'Plus anciens'),
        ('highest_rating', 'Note la plus élevée'),
        ('lowest_rating', 'Note la plus basse'),
        ('most_helpful', 'Plus utiles'),
        ('verified_only', 'Achats vérifiés uniquement'),
    ]
    
    rating = forms.ChoiceField(
        choices=RATING_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'select select-bordered w-full focus:ring-2 focus:ring-primary'
        })
    )
    
    sort_by = forms.ChoiceField(
        choices=SORT_CHOICES,
        required=False,
        initial='newest',
        widget=forms.Select(attrs={
            'class': 'select select-bordered w-full focus:ring-2 focus:ring-primary'
        })
    )
    
    verified_only = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'checkbox checkbox-primary'
        })
    )
    
    with_images = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'checkbox checkbox-primary'
        })
    )


class ReviewSearchForm(forms.Form):
    """Formulaire pour rechercher dans les avis"""
    
    query = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'input input-bordered w-full focus:ring-2 focus:ring-primary',
            'placeholder': 'Rechercher dans les avis...'
        })
    )
    
    def clean_query(self):
        """Validation de la requête de recherche"""
        query = self.cleaned_data.get('query', '').strip()
        if query and len(query) < 2:
            raise ValidationError('La recherche doit contenir au moins 2 caractères.')
        return query
