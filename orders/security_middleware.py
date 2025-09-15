from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponseForbidden
from django.conf import settings
from django.core.cache import cache
from .audit import SecurityEvent
import re
import time
from collections import defaultdict


class SecurityEventMiddleware(MiddlewareMixin):
    """
    Middleware pour détecter et enregistrer automatiquement les événements de sécurité
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
        
        # Patterns suspects à détecter
        self.suspicious_patterns = {
            'sql_injection': [
                r"union\s+select", r"drop\s+table", r"delete\s+from", r"insert\s+into",
                r"update\s+set", r"exec\s*\(", r"script\s*>", r"<script",
                r"javascript:", r"vbscript:", r"onload\s*=", r"onerror\s*="
            ],
            'xss_attempt': [
                r"<script", r"javascript:", r"vbscript:", r"onload\s*=", r"onerror\s*=",
                r"<iframe", r"<object", r"<embed", r"<link", r"<meta"
            ],
            'path_traversal': [
                r"\.\./", r"\.\.\\", r"%2e%2e%2f", r"%2e%2e%5c",
                r"\.\.%2f", r"\.\.%5c", r"\.\.%252f", r"\.\.%255c"
            ],
            'command_injection': [
                r";\s*cat\s+", r";\s*ls\s+", r";\s*dir\s+", r";\s*type\s+",
                r"|\s*cat\s+", r"|\s*ls\s+", r"|\s*dir\s+", r"|\s*type\s+",
                r"`.*`", r"\$\(.*\)"
            ]
        }
        
        # IPs suspectes (à étendre selon les besoins)
        self.suspicious_ips = set()
        
        # Limites de taux pour détecter les attaques par force brute
        self.rate_limits = {
            'login_attempts': 5,  # 5 tentatives par minute
            'api_requests': 100,  # 100 requêtes par minute
            'general_requests': 200  # 200 requêtes par minute
        }
    
    def get_client_ip(self, request):
        """Récupère l'adresse IP du client"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def get_user_agent(self, request):
        """Récupère le User-Agent du client"""
        return request.META.get('HTTP_USER_AGENT', '')
    
    def check_suspicious_patterns(self, request):
        """Vérifie les patterns suspects dans la requête"""
        suspicious_content = []
        
        # Vérifier l'URL
        url = request.get_full_path()
        for pattern_type, patterns in self.suspicious_patterns.items():
            for pattern in patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    suspicious_content.append(f"{pattern_type}: {pattern}")
        
        # Vérifier les paramètres GET
        for key, value in request.GET.items():
            if isinstance(value, str):
                for pattern_type, patterns in self.suspicious_patterns.items():
                    for pattern in patterns:
                        if re.search(pattern, value, re.IGNORECASE):
                            suspicious_content.append(f"{pattern_type} in GET[{key}]: {pattern}")
        
        # Vérifier les paramètres POST
        if request.method == 'POST':
            for key, value in request.POST.items():
                if isinstance(value, str):
                    for pattern_type, patterns in self.suspicious_patterns.items():
                        for pattern in patterns:
                            if re.search(pattern, value, re.IGNORECASE):
                                suspicious_content.append(f"{pattern_type} in POST[{key}]: {pattern}")
        
        return suspicious_content
    
    def check_rate_limiting(self, request):
        """Vérifie les limites de taux"""
        ip = self.get_client_ip(request)
        current_time = int(time.time())
        
        # Clés de cache pour différents types de requêtes
        cache_keys = {
            'login': f"rate_limit_login_{ip}",
            'api': f"rate_limit_api_{ip}",
            'general': f"rate_limit_general_{ip}"
        }
        
        # Déterminer le type de requête
        request_type = 'general'
        if '/login/' in request.path or '/auth/' in request.path:
            request_type = 'login'
        elif '/api/' in request.path:
            request_type = 'api'
        
        cache_key = cache_keys[request_type]
        limit = self.rate_limits[f"{request_type}_requests" if request_type != 'login' else 'login_attempts']
        
        # Récupérer le nombre de requêtes actuelles
        current_requests = cache.get(cache_key, 0)
        
        # Vérifier si la limite est dépassée
        if current_requests >= limit:
            return True, f"Rate limit exceeded: {current_requests}/{limit} requests"
        
        # Incrémenter le compteur
        cache.set(cache_key, current_requests + 1, 60)  # Expire après 60 secondes
        
        return False, None
    
    def check_suspicious_headers(self, request):
        """Vérifie les en-têtes suspects"""
        suspicious_headers = []
        
        # Vérifier les en-têtes suspects
        suspicious_header_patterns = {
            'x_forwarded_for': r"^(\d{1,3}\.){3}\d{1,3}$",
            'user_agent': r"bot|crawler|spider|scraper",
            'referer': r"javascript:|data:|vbscript:"
        }
        
        for header_name, pattern in suspicious_header_patterns.items():
            header_value = request.META.get(f'HTTP_{header_name.upper().replace("-", "_")}', '')
            if header_value and not re.match(pattern, header_value, re.IGNORECASE):
                suspicious_headers.append(f"Suspicious {header_name}: {header_value}")
        
        return suspicious_headers
    
    def log_security_event(self, request, event_type, severity, description, blocked=False, action_taken=None):
        """Enregistre un événement de sécurité"""
        try:
            SecurityEvent.log_security_event(
                event_type=event_type,
                severity=severity,
                description=description,
                ip_address=self.get_client_ip(request),
                user_agent=self.get_user_agent(request),
                user=getattr(request, 'user', None) if hasattr(request, 'user') and request.user.is_authenticated else None,
                request_path=request.get_full_path(),
                request_method=request.method,
                request_data={
                    'GET': dict(request.GET),
                    'POST': dict(request.POST) if request.method == 'POST' else None,
                    'headers': {k: v for k, v in request.META.items() if k.startswith('HTTP_')}
                },
                blocked=blocked,
                action_taken=action_taken,
                metadata={
                    'timestamp': time.time(),
                    'session_key': getattr(request, 'session', {}).get('_session_key', None)
                }
            )
        except Exception as e:
            # En cas d'erreur, on ne veut pas bloquer la requête
            print(f"Erreur lors de l'enregistrement de l'événement de sécurité: {e}")
    
    def process_request(self, request):
        """Traite la requête entrante"""
        # Désactiver le middleware de sécurité pendant les tests
        if getattr(settings, 'TESTING', False):
            return None
            
        ip = self.get_client_ip(request)
        
        # Vérifier si l'IP est bloquée
        if ip in self.suspicious_ips:
            self.log_security_event(
                request, 'ip_blocked', 'high',
                f"Request from blocked IP: {ip}",
                blocked=True,
                action_taken="Request blocked due to previous security violations"
            )
            return HttpResponseForbidden("Access denied")
        
        # Vérifier les patterns suspects
        suspicious_patterns = self.check_suspicious_patterns(request)
        if suspicious_patterns:
            event_type = 'malicious_request'
            severity = 'high'
            
            # Déterminer le type d'attaque
            if any('sql_injection' in pattern for pattern in suspicious_patterns):
                event_type = 'sql_injection_attempt'
                severity = 'critical'
            elif any('xss' in pattern for pattern in suspicious_patterns):
                event_type = 'xss_attempt'
                severity = 'high'
            elif any('path_traversal' in pattern for pattern in suspicious_patterns):
                event_type = 'unauthorized_access'
                severity = 'high'
            elif any('command_injection' in pattern for pattern in suspicious_patterns):
                event_type = 'malicious_request'
                severity = 'critical'
            
            self.log_security_event(
                request, event_type, severity,
                f"Suspicious patterns detected: {', '.join(suspicious_patterns)}",
                blocked=True,
                action_taken="Request blocked due to suspicious content"
            )
            return HttpResponseForbidden("Access denied")
        
        # Vérifier les limites de taux
        rate_limited, rate_message = self.check_rate_limiting(request)
        if rate_limited:
            self.log_security_event(
                request, 'rate_limit_exceeded', 'medium',
                rate_message,
                blocked=True,
                action_taken="Request blocked due to rate limiting"
            )
            return HttpResponseForbidden("Rate limit exceeded")
        
        # Vérifier les en-têtes suspects
        suspicious_headers = self.check_suspicious_headers(request)
        if suspicious_headers:
            self.log_security_event(
                request, 'suspicious_activity', 'medium',
                f"Suspicious headers detected: {', '.join(suspicious_headers)}",
                blocked=False,
                action_taken="Request allowed but flagged for monitoring"
            )
        
        return None
    
    def process_response(self, request, response):
        """Traite la réponse sortante"""
        # Enregistrer les erreurs 4xx et 5xx comme des événements de sécurité potentiels
        if response.status_code >= 400:
            severity = 'high' if response.status_code >= 500 else 'medium'
            event_type = 'suspicious_activity'
            
            if response.status_code == 403:
                event_type = 'unauthorized_access'
            elif response.status_code == 404:
                event_type = 'suspicious_activity'
            elif response.status_code >= 500:
                event_type = 'system_error'
                severity = 'critical'
            
            self.log_security_event(
                request, event_type, severity,
                f"HTTP {response.status_code} response for {request.get_full_path()}",
                blocked=False,
                action_taken=f"HTTP {response.status_code} response"
            )
        
        return response


class FailedLoginMiddleware(MiddlewareMixin):
    """
    Middleware pour détecter les tentatives de connexion échouées
    """
    
    def process_request(self, request):
        """Traite la requête entrante"""
        if request.method == 'POST' and ('login' in request.path or 'auth' in request.path):
            # Cette logique sera complétée par les signaux d'authentification
            pass
        return None


class SessionSecurityMiddleware(MiddlewareMixin):
    """
    Middleware pour la sécurité des sessions
    """
    
    def process_request(self, request):
        """Traite la requête entrante"""
        if hasattr(request, 'user') and request.user.is_authenticated:
            # Vérifier la validité de la session
            session_key = request.session.session_key
            if session_key:
                # Vérifier si la session a été compromise
                # (Cette logique peut être étendue selon les besoins)
                pass
        return None
