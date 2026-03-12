from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import InventarioAlmacen, FacturaAlmacen
from .serializers import InventarioAlmacenSerializer, FacturaAlmacenSerializer


class InventarioAlmacenViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Endpoint para que el .exe descargue el catálogo y stock actual.
    Requiere que el usuario del .exe inicie sesión (IsAuthenticated).
    """
    # select_related optimiza la base de datos cruzando la tabla InventarioAlmacen con Producto
    queryset = InventarioAlmacen.objects.select_related('producto').all()
    serializer_class = InventarioAlmacenSerializer
    permission_classes = [IsAuthenticated]


class FacturaAlmacenViewSet(viewsets.ModelViewSet):
    """
    Endpoint para que AlmacenDesktop envíe las facturas/ventas registradas.
    - GET: lista todas las facturas (opcional)
    - POST: crear nueva factura desde AlmacenDesktop
    Requiere autenticación JWT.
    """
    queryset = FacturaAlmacen.objects.prefetch_related('detalles').all()
    serializer_class = FacturaAlmacenSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        """Crear una factura con validación."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        return Response(
            {
                "id": serializer.data.get("id"),
                "consecutivo_local": serializer.data.get("consecutivo_local"),
                "mensaje": "Factura sincronizada exitosamente"
            },
            status=status.HTTP_201_CREATED
        )