"""
Commande pour initialiser les données de recherche
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from products.models import Product, SearchSuggestion, ProductSearchIndex


class Command(BaseCommand):
    help = 'Initialise les données de recherche (suggestions et index)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forcer la réinitialisation des données existantes',
        )

    def handle(self, *args, **options):
        force = options['force']
        
        self.stdout.write('Initialisation des données de recherche...')
        
        with transaction.atomic():
            # Créer les suggestions de recherche populaires
            self.create_search_suggestions(force)
            
            # Créer les index de recherche pour les produits
            self.create_product_search_indexes(force)
        
        self.stdout.write(
            self.style.SUCCESS('Données de recherche initialisées avec succès!')
        )

    def create_search_suggestions(self, force=False):
        """Créer les suggestions de recherche populaires"""
        if force:
            SearchSuggestion.objects.all().delete()
            self.stdout.write('Suggestions existantes supprimées.')
        
        suggestions = [
            'iPhone', 'Samsung', 'Ordinateur', 'Laptop', 'Téléphone',
            'Écouteurs', 'Casque', 'Chaussures', 'Vêtements', 'Sac',
            'Montre', 'Tablette', 'Caméra', 'Jeux', 'Livre',
            'Maison', 'Décoration', 'Cuisine', 'Sport', 'Fitness',
            'Beauté', 'Santé', 'Bébé', 'Jouets', 'Électronique',
            'Informatique', 'Téléphonie', 'Audio', 'Vidéo', 'Gaming'
        ]
        
        created_count = 0
        for suggestion in suggestions:
            suggestion_obj, created = SearchSuggestion.objects.get_or_create(
                query=suggestion,
                defaults={
                    'popularity_score': 1,
                    'is_active': True
                }
            )
            if created:
                created_count += 1
        
        self.stdout.write(f'{created_count} suggestions créées.')

    def create_product_search_indexes(self, force=False):
        """Créer les index de recherche pour les produits"""
        if force:
            ProductSearchIndex.objects.all().delete()
            self.stdout.write('Index existants supprimés.')
        
        products = Product.objects.all()
        created_count = 0
        
        for product in products:
            # Créer l'index de recherche si il n'existe pas
            index, created = ProductSearchIndex.objects.get_or_create(
                product=product,
                defaults={
                    'search_vector': self.generate_search_vector(product)
                }
            )
            
            if created:
                created_count += 1
            else:
                # Mettre à jour l'index existant
                index.search_vector = self.generate_search_vector(product)
                index.save()
        
        self.stdout.write(f'{created_count} index de recherche créés/mis à jour.')

    def generate_search_vector(self, product):
        """Générer le vecteur de recherche pour un produit"""
        search_terms = []
        
        # Ajouter le nom du produit
        search_terms.append(product.name.lower())
        
        # Ajouter la description
        search_terms.append(product.description.lower())
        
        # Ajouter la catégorie
        if product.category:
            search_terms.append(product.category.name.lower())
        
        # Ajouter des mots-clés basés sur le nom
        name_words = product.name.lower().split()
        for word in name_words:
            if len(word) > 2:  # Ignorer les mots trop courts
                search_terms.append(word)
        
        # Joindre tous les termes
        return ' '.join(set(search_terms))  # Utiliser set pour éviter les doublons
