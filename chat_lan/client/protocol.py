"""Compatibilidad para código que importa el protocolo desde ``client.protocol``."""

# Se reexporta la implementación común para mantener la ruta histórica de importación
# sin duplicar las reglas de encuadre ni la validación compartida con el servidor.
from common.protocol import *  # noqa: F401,F403
