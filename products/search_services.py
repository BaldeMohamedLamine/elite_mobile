"""
Services de recherche et filtrage pour les produits
"""
from django.db.models import Q, Count, Avg, F
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
import re

from .models import Product, Category


class SearchService:
    """Service de recherche pour les produits"""
    
    @staticmethod
    def search_products(query, filters=None, sort_by='relevance', page=1, per_page=20):
        """
        Recherche de produits avec filtres et tri
        
        Args:
            query (str): Terme de recherche
            filters (dict): Filtres à appliquer
            sort_by (str): Critère de tri
            page (int): Numéro de page
            per_page (int): Nombre d'éléments par page
            
        Returns:
            dict: Résultats de recherche avec pagination
        """
        # Construction de la requête de base
        products = Product.objects.filter(is_active=True)
        
        # Recherche textuelle
        if query:
            products = SearchService._apply_text_search(products, query)
        
        # Application des filtres
        if filters:
            products = SearchService._apply_filters(products, filters)
        
        # Tri
        products = SearchService._apply_sorting(products, sort_by)
        
        # Pagination
        paginator = Paginator(products, per_page)
        page_obj = paginator.get_page(page)
        
        return {
            'products': page_obj,
            'total_count': paginator.count,
            'query': query,
            'filters': filters or {},
            'sort_by': sort_by,
            'page': page,
            'per_page': per_page,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
            'num_pages': paginator.num_pages,
        }
    
    @staticmethod
    def _apply_text_search(products, query):
        """Applique la recherche textuelle"""
        # Nettoyage de la requête
        query = query.strip()
        if not query:
            return products
        
        # Recherche dans le nom et la description
        search_terms = re.findall(r'\b\w+\b', query.lower())
        
        q_objects = Q()
        for term in search_terms:
            q_objects |= (
                Q(name__icontains=term) |
                Q(description__icontains=term) |
                Q(category__name__icontains=term)
            )
        
        return products.filter(q_objects).distinct()
    
    @staticmethod
    def _apply_filters(products, filters):
        """Applique les filtres de recherche"""
        # Filtre par catégorie
        if filters.get('category'):
            products = products.filter(category_id=filters['category'])
        
        # Filtre par prix
        if filters.get('min_price'):
            products = products.filter(price__gte=filters['min_price'])
        
        if filters.get('max_price'):
            products = products.filter(price__lte=filters['max_price'])
        
        # Filtre par disponibilité
        if filters.get('in_stock'):
            products = products.filter(quantity__gt=0)
        
        # Filtre par note moyenne
        if filters.get('min_rating'):
            products = products.annotate(
                avg_rating=Avg('reviews__rating')
            ).filter(avg_rating__gte=filters['min_rating'])
        
        return products
    
    @staticmethod
    def _apply_sorting(products, sort_by):
        """Applique le tri des résultats"""
        if sort_by == 'price_asc':
            return products.order_by('price')
        elif sort_by == 'price_desc':
            return products.order_by('-price')
        elif sort_by == 'name_asc':
            return products.order_by('name')
        elif sort_by == 'name_desc':
            return products.order_by('-name')
        elif sort_by == 'newest':
            return products.order_by('-created_at')
        elif sort_by == 'oldest':
            return products.order_by('created_at')
        elif sort_by == 'popularity':
            return products.annotate(
                order_count=Count('order_items')
            ).order_by('-order_count')
        elif sort_by == 'rating':
            return products.annotate(
                avg_rating=Avg('reviews__rating')
            ).order_by('-avg_rating')
        else:  # relevance par défaut
            return products.order_by('-created_at')
    
    @staticmethod
    def get_search_suggestions(query, limit=10):
        """Génère des suggestions de recherche"""
        if not query or len(query) < 2:
            return []
        
        suggestions = []
        
        # Suggestions basées sur les noms de produits
        products = Product.objects.filter(
            name__icontains=query,
            is_active=True
        ).values_list('name', flat=True)[:limit//2]
        
        suggestions.extend(products)
        
        # Suggestions basées sur les catégories
        categories = Category.objects.filter(
            name__icontains=query
        ).values_list('name', flat=True)[:limit//2]
        
        suggestions.extend(categories)
        
        return list(set(suggestions))[:limit]
    
    @staticmethod
    def get_filter_options():
        """Retourne les options de filtrage disponibles"""
        return {
            'categories': Category.objects.all(),
            'price_ranges': [
                {'label': '0 - 10,000 GNF', 'min': 0, 'max': 10000},
                {'label': '10,000 - 50,000 GNF', 'min': 10000, 'max': 50000},
                {'label': '50,000 - 100,000 GNF', 'min': 50000, 'max': 100000},
                {'label': '100,000+ GNF', 'min': 100000, 'max': None},
            ],
            'sort_options': [
                {'value': 'relevance', 'label': 'Pertinence'},
                {'value': 'price_asc', 'label': 'Prix croissant'},
                {'value': 'price_desc', 'label': 'Prix décroissant'},
                {'value': 'name_asc', 'label': 'Nom A-Z'},
                {'value': 'name_desc', 'label': 'Nom Z-A'},
                {'value': 'newest', 'label': 'Plus récents'},
                {'value': 'oldest', 'label': 'Plus anciens'},
                {'value': 'popularity', 'label': 'Plus populaires'},
                {'value': 'rating', 'label': 'Mieux notés'},
            ]
        }


class FilterService:
    """Service de filtrage avancé"""
    
    @staticmethod
    def get_advanced_filters():
        """Retourne les filtres avancés disponibles"""
        return {
            'availability': [
                {'value': 'in_stock', 'label': 'En stock'},
                {'value': 'out_of_stock', 'label': 'Rupture de stock'},
                {'value': 'low_stock', 'label': 'Stock faible'},
            ],
            'ratings': [
                {'value': 5, 'label': '5 étoiles'},
                {'value': 4, 'label': '4 étoiles et plus'},
                {'value': 3, 'label': '3 étoiles et plus'},
                {'value': 2, 'label': '2 étoiles et plus'},
                {'value': 1, 'label': '1 étoile et plus'},
            ],
            'date_ranges': [
                {'value': 'today', 'label': 'Aujourd\'hui'},
                {'value': 'week', 'label': 'Cette semaine'},
                {'value': 'month', 'label': 'Ce mois'},
                {'value': 'year', 'label': 'Cette année'},
            ]
        }
    
    @staticmethod
    def apply_advanced_filters(products, filters):
        """Applique les filtres avancés"""
        # Filtre par disponibilité
        if filters.get('availability') == 'in_stock':
            products = products.filter(quantity__gt=0)
        elif filters.get('availability') == 'out_of_stock':
            products = products.filter(quantity=0)
        elif filters.get('availability') == 'low_stock':
            products = products.filter(quantity__lte=F('min_stock_level'))
        
        # Filtre par note
        if filters.get('min_rating'):
            products = products.annotate(
                avg_rating=Avg('reviews__rating')
            ).filter(avg_rating__gte=filters['min_rating'])
        
        # Filtre par date
        if filters.get('date_range'):
            now = timezone.now()
            if filters['date_range'] == 'today':
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif filters['date_range'] == 'week':
                start_date = now - timedelta(days=7)
            elif filters['date_range'] == 'month':
                start_date = now - timedelta(days=30)
            elif filters['date_range'] == 'year':
                start_date = now - timedelta(days=365)
            else:
                start_date = None
            
            if start_date:
                products = products.filter(created_at__gte=start_date)
        
        return products


class SearchAnalyticsService:
    """Service d'analytics pour la recherche"""
    
    @staticmethod
    def track_search(query, results_count, user=None):
        """Enregistre une recherche pour les analytics"""
        # TODO: Implémenter le tracking des recherches
        pass
    
    @staticmethod
    def get_popular_searches(limit=10):
        """Retourne les recherches populaires"""
        # TODO: Implémenter la récupération des recherches populaires
        return []
    
    @staticmethod
    def get_search_analytics():
        """Retourne les analytics de recherche"""
        # TODO: Implémenter les analytics de recherche
        return {
            'total_searches': 0,
            'popular_queries': [],
            'no_results_queries': [],
            'conversion_rate': 0,
        }