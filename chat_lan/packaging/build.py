"""Genera el cliente autónomo para el sistema donde se ejecuta este script."""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
extra = []
for library in (root / 'packaging/vendor/extracted/usr/lib').glob('*/libxcb-cursor.so.0'):
    extra.extend(['--add-binary', str(library) + ':.' ])
subprocess.run([
    sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
    '--onefile', '--windowed', '--name', 'ChatLAN',
    '--paths', str(root), '--distpath', str(root / 'dist'),
    '--workpath', str(root / 'build'), '--specpath', str(root / 'packaging'),
    *extra, str(root / 'packaging' / 'launcher.py'),
], check=True, cwd=root)
print('Ejecutable generado en', root / 'dist')
