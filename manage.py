#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

def main():
    """Run administrative tasks."""
    # Asegúrate de que 'sieslo.settings' sea el nombre correcto de tu archivo de configuración.
    # Si tu proyecto se llama diferente o tu settings.py está en otro lugar, ajusta esta línea.
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_inventario.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()