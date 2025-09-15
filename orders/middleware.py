from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponseForbidden
from django.core.cache import cache
from django.conf import settings
import time
import hashlib


class RateLimitMiddleware(MiddlewareMixin):
    """Middleware pour limiter le taux de requêtes par IP"""
    
    def process_request(self, request):
        # Obtenir l'IP du client
        ip = self.get_client_ip(request)
        
        # Clé de cache pour cette IP
        cache_key = f"rate_limit_{ip}"
        
        # Récupérer le nombre de requêtes actuelles
        current_requests = cache.get(cache_key, 0)
        
        # Limite: 100 requêtes par minute
        max_requests = getattr(settings, 'RATE_LIMIT_MAX_REQUESTS', 100)
        time_window = getattr(settings, 'RATE_LIMIT_TIME_WINDOW', 60)
        
        if current_requests >= max_requests:
            # Logger la tentative de rate limiting
            self.log_rate_limit_exceeded(request, ip, current_requests, max_requests)
            return HttpResponseForbidden("Trop de requêtes. Veuillez patienter.")
        
        # Incrémenter le compteur
        cache.set(cache_key, current_requests + 1, time_window)
        
        return None
    
    def get_client_ip(self, request):
        """Obtenir l'IP réelle du client"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def log_rate_limit_exceeded(self, request, ip, current_requests, max_requests):
        """Logger les tentatives de rate limiting"""
        try:
            from orders.audit import SecurityEvent
            SecurityEvent.log_security_event(
                event_type='rate_limit_exceeded',
                severity='medium',
                description=f"Rate limit exceeded for IP {ip}: {current_requests}/{max_requests} requests",
                ip_address=ip,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                request_path=request.get_full_path(),
                request_method=request.method,
                blocked=True,
                action_taken="Request blocked due to rate limiting"
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error logging rate limit event: {e}")


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Middleware pour ajouter des en-têtes de sécurité"""
    
    def process_response(self, request, response):
        # En-têtes de sécurité
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Content Security Policy
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "img-src 'self' data: https:; "
            "font-src 'self' https://cdnjs.cloudflare.com; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        response['Content-Security-Policy'] = csp
        
        return response


class RequestLoggingMiddleware(MiddlewareMixin):
    """Middleware pour logger les requêtes suspectes"""
    
    def process_request(self, request):
        # Vérifier les patterns suspects
        suspicious_patterns = [
            '<script', 'javascript:', 'onload=', 'onerror=',
            'union select', 'drop table', 'delete from',
            '../../../', '..\\..\\..\\',
        ]
        
        # Vérifier l'URL
        url = request.get_full_path().lower()
        for pattern in suspicious_patterns:
            if pattern in url:
                self.log_suspicious_request(request, f"Suspicious URL pattern: {pattern}")
                break
        
        # Vérifier les paramètres POST
        if request.method == 'POST':
            for key, value in request.POST.items():
                if isinstance(value, str):
                    for pattern in suspicious_patterns:
                        if pattern in value.lower():
                            self.log_suspicious_request(request, f"Suspicious POST data: {pattern}")
                            break
        
        return None
    
    def log_suspicious_request(self, request, reason):
        """Logger une requête suspecte"""
        import logging
        logger = logging.getLogger('security')
        
        log_data = {
            'ip': self.get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'url': request.get_full_path(),
            'method': request.method,
            'reason': reason,
            'timestamp': time.time(),
        }
        
        logger.warning(f"Suspicious request detected: {log_data}")


class IPWhitelistMiddleware(MiddlewareMixin):
    """Middleware pour whitelist d'IPs (optionnel)"""
    
    def process_request(self, request):
        # Liste des IPs autorisées (pour l'admin par exemple)
        whitelist_ips = getattr(settings, 'ADMIN_IP_WHITELIST', [])
        
        if whitelist_ips:
            client_ip = self.get_client_ip(request)
            
            # Vérifier si c'est une page admin
            if request.path.startswith('/admin/'):
                if client_ip not in whitelist_ips:
                    return HttpResponseForbidden("Accès non autorisé depuis cette IP.")
        
        return None
    
    def get_client_ip(self, request):
        """Obtenir l'IP réelle du client"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
