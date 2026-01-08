# config/theme.py
# Configuration visuelle du portail captif
# Modifier ces valeurs pour personnaliser l'apparence

from pydantic_settings import BaseSettings
from typing import Optional


class ThemeSettings(BaseSettings):
    """Configuration du thème du portail."""
    
    # Identité
    company_name: str = "Université du Bénin"
    portal_title: str = "Portail WiFi"
    portal_subtitle: str = "Authentification réseau"
    
    # Logo (chemin relatif depuis /static ou URL)
    logo_url: Optional[str] = "/static/logo.png"
    logo_width: str = "120px"
    logo_height: str = "auto"
    
    # Favicon
    favicon_url: str = "/static/favicon.ico"
    
    # Couleurs principales
    primary_color: str = "#1a365d"        # Bleu foncé - boutons, liens
    primary_hover: str = "#2d5a87"        # Hover boutons
    secondary_color: str = "#4a5568"      # Gris - texte secondaire
    accent_color: str = "#48bb78"         # Vert - succès
    error_color: str = "#e53e3e"          # Rouge - erreurs
    
    # Fond
    background_gradient_start: str = "#1a365d"
    background_gradient_end: str = "#2d5a87"
    background_type: str = "gradient"     # "gradient", "solid", "image"
    background_image_url: Optional[str] = None
    
    # Carte centrale
    card_background: str = "#ffffff"
    card_border_radius: str = "12px"
    card_shadow: str = "0 20px 60px rgba(0,0,0,0.3)"
    
    # Texte
    text_primary: str = "#2d3748"
    text_secondary: str = "#4a5568"
    text_muted: str = "#718096"
    
    # Boutons
    button_radius: str = "8px"
    button_padding: str = "16px"
    
    # Polices
    font_family: str = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    font_size_base: str = "16px"
    font_size_small: str = "13px"
    font_size_large: str = "24px"
    
    # Textes personnalisables
    login_button_text: str = "Se connecter avec mon compte universitaire"
    success_message: str = "Tu es maintenant connecté au réseau WiFi."
    footer_text: str = "En te connectant, tu acceptes les conditions d'utilisation du réseau."
    
    # Liens
    terms_url: Optional[str] = None       # URL conditions d'utilisation
    help_url: Optional[str] = None        # URL aide/support
    
    # Langue
    lang: str = "fr"
    
    class Config:
        env_prefix = "THEME_"
        env_file = ".env"


theme = ThemeSettings()


def get_css_variables() -> str:
    """Génère les variables CSS depuis la config."""
    return f"""
    :root {{
        --primary-color: {theme.primary_color};
        --primary-hover: {theme.primary_hover};
        --secondary-color: {theme.secondary_color};
        --accent-color: {theme.accent_color};
        --error-color: {theme.error_color};
        
        --bg-gradient-start: {theme.background_gradient_start};
        --bg-gradient-end: {theme.background_gradient_end};
        
        --card-bg: {theme.card_background};
        --card-radius: {theme.card_border_radius};
        --card-shadow: {theme.card_shadow};
        
        --text-primary: {theme.text_primary};
        --text-secondary: {theme.text_secondary};
        --text-muted: {theme.text_muted};
        
        --btn-radius: {theme.button_radius};
        --btn-padding: {theme.button_padding};
        
        --font-family: {theme.font_family};
        --font-size-base: {theme.font_size_base};
        --font-size-small: {theme.font_size_small};
        --font-size-large: {theme.font_size_large};
    }}
    """
