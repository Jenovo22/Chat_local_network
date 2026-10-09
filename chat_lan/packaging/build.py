"""Construye con PyInstaller el cliente autónomo para el sistema actual.

Este archivo es un script de empaquetado: ejecutarlo puede reemplazar el
contenido de ``build/`` y ``dist/``. No forma parte del cliente en ejecución.
"""
import subprocess
import sys
from pathlib import Path

# Se parte de la ubicación del script para que el comando no dependa del
# directorio desde el cual lo invoque la persona desarrolladora.
root = Path(__file__).resolve().parents[1]
extra = []
for library in (root / 'packaging/vendor/extracted/usr/lib').glob('*/libxcb-cursor.so.0'):
    # Algunas distribuciones necesitan incluir explícitamente esta biblioteca
    # de Qt. PyInstaller recibe --add-binary y un valor combinado ORIGEN:DESTINO.
    extra.extend(['--add-binary', str(library) + ':.' ])
# sys.executable conserva el mismo intérprete y entorno donde está instalado
# PyInstaller; check=True convierte un fallo del empaquetador en una excepción.
subprocess.run([
    sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
    '--onefile', '--windowed', '--name', 'ChatLAN',
    '--paths', str(root), '--distpath', str(root / 'dist'),
    '--workpath', str(root / 'build'), '--specpath', str(root / 'packaging'),
    # El desempaquetado de *extra inserta cero o más pares --add-binary.
    *extra, str(root / 'packaging' / 'launcher.py'),
], check=True, cwd=root)
print('Ejecutable generado en', root / 'dist')
