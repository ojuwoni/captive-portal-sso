# Fichiers statiques

Placer ici les assets de ta société :

## Fichiers attendus

| Fichier | Dimensions | Format | Description |
|---------|------------|--------|-------------|
| `logo.png` | 120x120px (ou ratio similaire) | PNG/SVG | Logo principal |
| `favicon.ico` | 32x32px | ICO/PNG | Icône navigateur |
| `background.jpg` | 1920x1080px | JPG/PNG | Image de fond (optionnel) |

## Personnalisation

### Via variables d'environnement

```bash
# .env
THEME_COMPANY_NAME="IDADU TECH"
THEME_PRIMARY_COLOR="#00A651"
THEME_LOGO_URL="/static/logo.png"
```

### Via config/theme.py

Modifier directement les valeurs par défaut dans `config/theme.py`.

## Exemples de thèmes

### Thème IDADU TECH (vert)
```python
primary_color = "#00A651"
primary_hover = "#008C44"
background_gradient_start = "#004D25"
background_gradient_end = "#00A651"
```

### Thème Université (bleu)
```python
primary_color = "#1a365d"
primary_hover = "#2d5a87"
background_gradient_start = "#1a365d"
background_gradient_end = "#2d5a87"
```

### Thème Orange/EdTech
```python
primary_color = "#F97316"
primary_hover = "#EA580C"
background_gradient_start = "#7C2D12"
background_gradient_end = "#F97316"
```
