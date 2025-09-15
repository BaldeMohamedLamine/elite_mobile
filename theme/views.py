"""
Vues pour l'application theme
"""
from django.shortcuts import redirect, render
from django.views.generic import RedirectView


class HomeView(RedirectView):
    """Vue pour la page d'accueil - redirige vers la liste des produits"""
    permanent = False
    url = '/products/'


def custom_404(request, exception=None):
    """Page d'erreur 404 personnalisée"""
    return render(request, '404.html', status=404)


def custom_403(request, exception=None):
    """Page d'erreur 403 personnalisée"""
    return render(request, '403.html', status=403)


def custom_500(request):
    """Page d'erreur 500 personnalisée"""
    return render(request, '500.html', status=500)
