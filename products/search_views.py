"""
Vues pour la recherche et les filtres
"""
import json
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.generic import TemplateView
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers

from .models import Product, Category
from .search_services import SearchService, FilterService, SearchAnalyticsService


class SearchView(TemplateView):
    """Vue principale de recherche"""
    template_name = 'products/search_results.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Récupérer les paramètres de recherche
        query = self.request.GET.get('q', '').strip()
        page = int(self.request.GET.get('page', 1))
        sort_by = self.request.GET.get('sort', 'relevance')
        per_page = int(self.request.GET.get('per_page', 20))
        
        # Construire les filtres
        filters = {}
        if self.request.GET.get('category'):
            filters['category'] = self.request.GET.get('category')
        if self.request.GET.get('min_price'):
            filters['min_price'] = float(self.request.GET.get('min_price'))
        if self.request.GET.get('max_price'):
            filters['max_price'] = float(self.request.GET.get('max_price'))
        if self.request.GET.get('in_stock'):
            filters['in_stock'] = True
        if self.request.GET.get('min_rating'):
            filters['min_rating'] = float(self.request.GET.get('min_rating'))
        
        # Utiliser le service de recherche
        search_results = SearchService.search_products(
            query=query,
            filters=filters,
            sort_by=sort_by,
            page=page,
            per_page=per_page
        )
        
        # Enregistrer la recherche pour les analytics
        if query:
            SearchAnalyticsService.track_search(
                query=query,
                results_count=search_results['total_count'],
                user=self.request.user if self.request.user.is_authenticated else None
            )
        
        # Obtenir les options de filtrage
        filter_options = SearchService.get_filter_options()
        
        context.update({
            'search_results': search_results,
            'query': query,
            'page': page,
            'per_page': per_page,
            'sort_by': sort_by,
            'available_filters': filter_options,
            'current_filters': filters,
            'sort_options': filter_options['sort_options'],
        })
        
        return context
    
    def _get_filters_from_request(self):
        """Extraire les filtres de la requête"""
        filters = {}
        
        # Filtres par catégorie
        categories = self.request.GET.getlist('category')
        if categories:
            filters['category'] = categories
        
        # Filtres par prix
        price_min = self.request.GET.get('price_min')
        if price_min:
            try:
                filters['price_min'] = int(price_min)
            except ValueError:
                pass
        
        price_max = self.request.GET.get('price_max')
        if price_max:
            try:
                filters['price_max'] = int(price_max)
            except ValueError:
                pass
        
        # Filtre par disponibilité
        availability = self.request.GET.get('availability')
        if availability:
            filters['availability'] = availability
        
        # Filtre par produits vedettes
        featured = self.request.GET.get('featured')
        if featured == 'true':
            filters['featured'] = True
        
        # Filtre par promotions
        discount = self.request.GET.get('discount')
        if discount == 'true':
            filters['discount'] = True
        
        return filters


class SearchSuggestionsView(View):
    """Vue pour les suggestions de recherche (AJAX)"""
    
    def get(self, request, *args, **kwargs):
        query = request.GET.get('q', '').strip()
        
        if len(query) < 2:
            suggestions = search_service.get_popular_suggestions()
        else:
            suggestions = search_service.get_suggestions(query)
        
        return JsonResponse({
            'suggestions': suggestions,
            'query': query
        })


class SearchHistoryView(LoginRequiredMixin, View):
    """Vue pour l'historique de recherche de l'utilisateur"""
    
    def get(self, request, *args, **kwargs):
        history = search_service.get_search_history(user=request.user, limit=20)
        
        return JsonResponse({
            'history': history
        })
    
    def delete(self, request, *args, **kwargs):
        """Supprimer l'historique de recherche"""
        SearchHistory.objects.filter(user=request.user).delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Historique supprimé avec succès'
        })


class AdvancedSearchView(TemplateView):
    """Vue pour la recherche avancée"""
    template_name = 'products/advanced_search.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtenir toutes les catégories
        categories = Category.objects.annotate(
            product_count=Count('products')
        ).filter(product_count__gt=0)
        
        # Obtenir les gammes de prix
        products = Product.objects.all()
        if products.exists():
            prices = products.values_list('price', flat=True)
            min_price = min(prices)
            max_price = max(prices)
        else:
            min_price = max_price = 0
        
        context.update({
            'categories': categories,
            'min_price': min_price,
            'max_price': max_price,
            'sort_options': [
                {'value': 'relevance', 'label': 'Pertinence'},
                {'value': 'price_asc', 'label': 'Prix croissant'},
                {'value': 'price_desc', 'label': 'Prix décroissant'},
                {'value': 'name', 'label': 'Nom A-Z'},
                {'value': 'popularity', 'label': 'Popularité'},
            ]
        })
        
        return context


class SearchAnalyticsView(LoginRequiredMixin, TemplateView):
    """Vue pour les analytics de recherche (admin)"""
    template_name = 'products/search_analytics.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Statistiques générales
        total_searches = SearchHistory.objects.count()
        unique_queries = SearchHistory.objects.values('query').distinct().count()
        
        # Recherches populaires
        popular_searches = SearchHistory.objects.values('query').annotate(
            search_count=Count('query')
        ).order_by('-search_count')[:10]
        
        # Recherches récentes
        recent_searches = SearchHistory.objects.select_related('user').order_by('-created_at')[:20]
        
        # Suggestions populaires
        popular_suggestions = SearchSuggestion.objects.filter(
            is_active=True
        ).order_by('-popularity_score')[:10]
        
        context.update({
            'total_searches': total_searches,
            'unique_queries': unique_queries,
            'popular_searches': popular_searches,
            'recent_searches': recent_searches,
            'popular_suggestions': popular_suggestions,
        })
        
        return context


class FilterOptionsView(View):
    """Vue pour obtenir les options de filtres disponibles (AJAX)"""
    
    @method_decorator(cache_page(60 * 15))  # Cache 15 minutes
    @method_decorator(vary_on_headers('X-Requested-With'))
    def get(self, request, *args, **kwargs):
        # Obtenir les filtres disponibles
        available_filters = filter_service.get_available_filters(
            Product.objects.all()
        )
        
        return JsonResponse({
            'filters': available_filters
        })


class SearchAPIView(View):
    """API pour la recherche (AJAX)"""
    
    def get(self, request, *args, **kwargs):
        # Récupérer les paramètres
        query = request.GET.get('q', '').strip()
        page = int(request.GET.get('page', 1))
        sort_by = request.GET.get('sort', 'relevance')
        per_page = int(request.GET.get('per_page', 20))
        
        # Récupérer les filtres
        filters = {}
        for key, value in request.GET.items():
            if key.startswith('filter_'):
                filter_key = key.replace('filter_', '')
                if value:
                    filters[filter_key] = value.split(',') if ',' in value else value
        
        # Effectuer la recherche
        search_results = search_service.search_products(
            query=query,
            user=request.user,
            filters=filters,
            sort_by=sort_by,
            page=page,
            per_page=per_page
        )
        
        # Préparer la réponse
        products_data = []
        for product in search_results['products']:
            products_data.append({
                'uid': str(product.uid),
                'name': product.name,
                'description': product.description,
                'price': product.price,
                'quantity': product.quantity,
                'image_url': product.image.url if product.image else None,
                'category': {
                    'name': product.category.name,
                    'uid': str(product.category.uid)
                } if product.category else None,
                'is_featured': getattr(product, 'is_featured', False),
                'discount_price': getattr(product, 'discount_price', None),
            })
        
        return JsonResponse({
            'success': True,
            'products': products_data,
            'pagination': {
                'page': search_results['page'],
                'per_page': search_results['per_page'],
                'total_count': search_results['total_count'],
                'total_pages': search_results['total_pages'],
                'has_next': search_results['has_next'],
                'has_previous': search_results['has_previous'],
            },
            'suggestions': search_results['suggestions']
        })


class QuickSearchView(View):
    """Vue pour la recherche rapide (autocomplétion)"""
    
    def get(self, request, *args, **kwargs):
        query = request.GET.get('q', '').strip()
        
        if len(query) < 2:
            return JsonResponse({'results': []})
        
        # Recherche rapide dans les noms de produits
        products = Product.objects.filter(
            name__icontains=query
        ).select_related('category')[:5]
        
        results = []
        for product in products:
            results.append({
                'uid': str(product.uid),
                'name': product.name,
                'price': product.price,
                'image_url': product.image.url if product.image else None,
                'category': product.category.name if product.category else None,
                'url': f'/products/{product.uid}/'
            })
        
        return JsonResponse({
            'results': results,
            'query': query
        })
