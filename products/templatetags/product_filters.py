"""
Filtres personnalisés pour les templates de produits
"""
from django import template

register = template.Library()


@register.filter
def dict_key(dictionary, key):
    """
    Filtre pour accéder à une clé d'un dictionnaire dans un template
    Usage: {{ dictionary|dict_key:key }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key, None)


@register.filter
def get_item(dictionary, key):
    """
    Alias pour dict_key
    Usage: {{ dictionary|get_item:key }}
    """
    return dict_key(dictionary, key)


@register.filter
def percentage(value, total):
    """
    Calcule le pourcentage d'une valeur par rapport à un total
    Usage: {{ value|percentage:total }}
    """
    if not total or total == 0:
        return 0
    return (value / total) * 100


@register.filter
def rating_percentage(rating_distribution, rating):
    """
    Calcule le pourcentage pour une note spécifique
    Usage: {{ rating_distribution|rating_percentage:rating }}
    """
    if not rating_distribution:
        return 0
    
    total = sum(rating_distribution.values()) if rating_distribution else 0
    if total == 0:
        return 0
    
    count = rating_distribution.get(str(rating), 0)
    return (count / total) * 100


@register.filter
def mul(value, arg):
    """
    Multiplie value par arg
    Usage: {{ value|mul:arg }}
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0