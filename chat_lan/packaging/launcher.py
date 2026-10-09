"""Punto de entrada mínimo del ejecutable generado por PyInstaller.

La lógica permanece en ``client.main`` para que el cliente empaquetado y el
ejecutado con Python compartan exactamente el mismo flujo de inicio.
"""
from client.main import main

if __name__ == '__main__':
    # La guarda evita iniciar la aplicación si una herramienta importa el módulo.
    main()
