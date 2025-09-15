# Configuration Email pour Gmail (Optionnel)
# Décommentez ces lignes dans settings.py si vous voulez utiliser Gmail

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'votre_email@gmail.com'
EMAIL_HOST_PASSWORD = 'votre_mot_de_passe_application'  # Mot de passe d'application Gmail

# Pour utiliser Gmail, vous devez :
# 1. Activer l'authentification à 2 facteurs sur votre compte Gmail
# 2. Générer un "mot de passe d'application" dans les paramètres de sécurité
# 3. Utiliser ce mot de passe d'application au lieu de votre mot de passe normal
