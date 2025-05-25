from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from catalogo.models import EnlaceCatalogoTemporal
from django.contrib.sites.models import Site # Para obtener el dominio

class Command(BaseCommand):
    help = 'Genera un nuevo enlace temporal para el catálogo.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias',
            type=int,
            default=7,
            help='Número de días que el enlace será válido.'
        )
        parser.add_argument(
            '--descripcion',
            type=str,
            default="Enlace autogenerado",
            help='Descripción para el enlace.'
        )

    def handle(self, *args, **options):
        dias_validez = options['dias']
        descripcion = options['descripcion']

        nuevo_enlace = EnlaceCatalogoTemporal.objects.create(
            descripcion=descripcion,
            expira_el=timezone.now() + timedelta(days=dias_validez)
        )

        # Para construir la URL completa sin un objeto 'request':
        try:
            current_site = Site.objects.get_current()
            domain = current_site.domain
            protocol = 'https' # Asume https, o configúralo según tu entorno
            url_path = nuevo_enlace.obtener_url_absoluta() # Esto da /catalogo/compartir/token/
            url_completa = f"{protocol}://{domain}{url_path}"
        except Site.DoesNotExist:
            url_completa = ("Por favor, configura el framework de 'Sites' en Django "
                          "o construye la URL base manualmente.")


        self.stdout.write(self.style.SUCCESS(f"Enlace creado: {nuevo_enlace}"))
        self.stdout.write(self.style.SUCCESS(f"URL para compartir: {url_completa}"))