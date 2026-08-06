# LEAN FX Live Simulator

Simulador en Python con Pygame.

## Requisitos

- Python 3.10 o superior

## Instalación

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Ejecución

```bash
python main.py
```

Deberías ver una ventana de **1080×1920** con fondo `#0D1117` y el título **LEAN FX LIVE**. Cierra la ventana para salir.

## Estructura del proyecto

```
LEAN_FX_GAME/
├── main.py              # Punto de entrada
├── requirements.txt
├── README.md
└── app/
    ├── engine/          # Motor: ventana, game loop, configuración
    ├── ui/              # Componentes de interfaz
    ├── scenarios/       # Escenarios y lógica de niveles
    └── assets/          # Imágenes, sonidos y recursos
```
