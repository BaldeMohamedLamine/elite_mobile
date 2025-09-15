"""
Middleware de cache pour optimiser les performances
"""
from django.core.cache import cache
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponse
from django.utils.cache import get_cache_key, learn_cache_key
from django.conf import settings
import logging
import time

logger = logging.getLogger(__name__)


class CacheMiddleware(MiddlewareMixin):
    """Middleware de cache pour les pages statiques"""
    
    def process_request(self, request):
        """Vérifie si la page est en cache"""
        # Ne pas mettre en cache les requêtes POST, PUT, DELETE
        if request.method not in ['GET', 'HEAD']:
            return None
        
        # Ne pas mettre en cache les pages d'administration
        if request.path.startswith('/admin/'):
            return None
        
        # Ne pas mettre en cache les pages d'API
        if request.path.startswith('/api/'):
            return None
        
        # Ne pas mettre en cache les pages d'authentification
        if request.path.startswith('/users/login/') or request.path.startswith('/users/logout/'):
            return None
        
        # Vérifier le cache
        cache_key = self.get_cache_key(request)
        if cache_key:
            cached_response = cache.get(cache_key)
            if cached_response:
                logger.debug(f"Cache hit for: {request.path}")
                return cached_response
        
        return None
    
    def process_response(self, request, response):
        """Met en cache la réponse si approprié"""
        # Ne pas mettre en cache les requêtes non-GET
        if request.method not in ['GET', 'HEAD']:
            return response
        
        # Ne pas mettre en cache les réponses d'erreur
        if response.status_code != 200:
            return response
        
        # Ne pas mettre en cache les pages d'administration
        if request.path.startswith('/admin/'):
            return response
        
        # Ne pas mettre en cache les pages d'API
        if request.path.startswith('/api/'):
            return response
        
        # Ne pas mettre en cache les pages d'authentification
        if request.path.startswith('/users/login/') or request.path.startswith('/users/logout/'):
            return response
        
        # Ne pas mettre en cache les pages avec des messages
        if hasattr(request, '_messages') and request._messages:
            return response
        
        # Déterminer le timeout de cache
        timeout = self.get_cache_timeout(request)
        if timeout > 0:
            cache_key = self.get_cache_key(request)
            if cache_key:
                cache.set(cache_key, response, timeout)
                logger.debug(f"Cached response for: {request.path} (timeout: {timeout}s)")
        
        return response
    
    def get_cache_key(self, request):
        """Génère une clé de cache pour la requête"""
        try:
            # Utiliser l'URL et les paramètres de requête
            cache_key = f"page:{request.path}:{hash(str(sorted(request.GET.items())))}"
            return cache_key
        except Exception as e:
            logger.error(f"Error generating cache key: {e}")
            return None
    
    def get_cache_timeout(self, request):
        """Détermine le timeout de cache pour la requête"""
        # Ne pas mettre en cache si l'utilisateur est authentifié
        if hasattr(request, 'user') and request.user.is_authenticated:
            return 0
        
        # Pages d'accueil et de produits : 15 minutes
        if request.path in ['/', '/products/']:
            return 900
        
        # Pages de détail de produits : 30 minutes
        if request.path.startswith('/products/produit/'):
            return 1800
        
        # Pages de recherche : 5 minutes
        if request.path.startswith('/products/search/'):
            return 300
        
        # Pages de catégories : 15 minutes
        if request.path.startswith('/products/categories/'):
            return 900
        
        # Pages d'avis : 10 minutes
        if request.path.startswith('/products/reviews/'):
            return 600
        
        # Pages statiques : 1 heure
        if request.path.startswith('/static/') or request.path.startswith('/media/'):
            return 3600
        
        # Autres pages : 5 minutes
        return 300


class DatabaseQueryCacheMiddleware(MiddlewareMixin):
    """Middleware pour mettre en cache les requêtes de base de données"""
    
    def process_request(self, request):
        """Initialise le cache des requêtes"""
        request._query_cache = {}
        return None
    
    def process_response(self, request, response):
        """Nettoie le cache des requêtes"""
        if hasattr(request, '_query_cache'):
            del request._query_cache
        return response


class StaticFileCacheMiddleware(MiddlewareMixin):
    """Middleware pour optimiser le cache des fichiers statiques"""
    
    def process_response(self, request, response):
        """Ajoute des en-têtes de cache pour les fichiers statiques"""
        if request.path.startswith('/static/') or request.path.startswith('/media/'):
            # Cache les fichiers statiques pendant 1 an
            response['Cache-Control'] = 'public, max-age=31536000'
            response['Expires'] = 'Thu, 31 Dec 2025 23:59:59 GMT'
        elif request.path.startswith('/products/') and request.method == 'GET':
            # Cache les pages de produits pendant 15 minutes
            response['Cache-Control'] = 'public, max-age=900'
        
        return response


class PerformanceMonitoringMiddleware(MiddlewareMixin):
    """Middleware pour surveiller les performances"""
    
    def process_request(self, request):
        """Enregistre le début de la requête"""
        import time
        request._start_time = time.time()
        return None
    
    def process_response(self, request, response):
        """Enregistre la durée de la requête"""
        if hasattr(request, '_start_time'):
            duration = time.time() - request._start_time
            
            # Enregistrer les requêtes lentes (> 1 seconde)
            if duration > 1.0:
                logger.warning(f"Slow request: {request.path} took {duration:.2f}s")
            
            # Ajouter l'en-tête de durée
            response['X-Response-Time'] = f"{duration:.3f}s"
        
        return response
