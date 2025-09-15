"""
Services de cache optimisés pour l'application
"""
from django.core.cache import cache
from django.conf import settings
import hashlib
import json
from typing import Any, Optional, Dict
import logging

logger = logging.getLogger(__name__)


class CacheService:
    """Service de cache centralisé avec optimisations"""
    
    @classmethod
    def get_cache_key(cls, prefix: str, *args, **kwargs) -> str:
        """Génère une clé de cache unique et sécurisée"""
        key_parts = [prefix]
        
        for arg in args:
            key_parts.append(str(arg))
        
        for key, value in sorted(kwargs.items()):
            key_parts.append(f"{key}:{value}")
        
        key_string = ":".join(key_parts)
        
        if len(key_string) > 200:
            key_hash = hashlib.md5(key_string.encode()).hexdigest()
            key_string = f"{prefix}:{key_hash}"
        
        return key_string
    
    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """Récupère une valeur du cache"""
        try:
            return cache.get(key, default)
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {e}")
            return default
    
    @classmethod
    def set(cls, key: str, value: Any, timeout: Optional[int] = None) -> bool:
        """Stocke une valeur dans le cache"""
        try:
            cache.set(key, value, timeout)
            return True
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            return False
    
    @classmethod
    def delete(cls, key: str) -> bool:
        """Supprime une valeur du cache"""
        try:
            cache.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            return False


class ProductCacheService(CacheService):
    """Service de cache spécialisé pour les produits"""
    
    @classmethod
    def get_product_list_key(cls, category_id: Optional[int] = None, 
                           search_query: Optional[str] = None,
                           page: int = 1) -> str:
        """Génère une clé de cache pour la liste des produits"""
        return cls.get_cache_key(
            'product_list',
            category_id=category_id,
            search=search_query,
            page=page
        )
    
    @classmethod
    def get_product_detail_key(cls, product_uid: str) -> str:
        """Génère une clé de cache pour le détail d'un produit"""
        return cls.get_cache_key('product_detail', product_uid)
    
    @classmethod
    def invalidate_product_cache(cls, product_uid: str):
        """Invalide le cache d'un produit spécifique"""
        detail_key = cls.get_product_detail_key(product_uid)
        cls.delete(detail_key)