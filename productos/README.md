# Documentación de la Aplicación `productos`

## 📋 Propósito de la aplicación
La aplicación `productos` es el módulo central encargado de la gestión del catálogo de artículos en el sistema. Está diseñada para manejar productos con variaciones (tallas, colores), agrupaciones para la gestión de imágenes y soporte multi-inquilino (multi-tenant), garantizando que los usuarios solo vean e interactúen con los productos de su empresa (`Empresa`).

---

## 🏗️ Modelos y Arquitectura de Datos

La estructura de datos separa la variante específica (SKU vendible) de la agrupación visual (fotos por referencia y color).

1. **`Producto` (Variante / SKU)**
   - Representa un artículo específico que se puede vender, comprar y contar en el inventario.
   - Campos clave: `referencia`, `nombre`, `talla`, `color`, `genero`, `costo`, `precio_venta`, `codigo_barras`.
   - Propiedades: `stock_actual` (calculado a través de los movimientos de bodega).
   - Multi-tenant: Obligatoriamente vinculado a una `Empresa`.

2. **`ReferenciaColor` (Agrupador Visual)**
   - Agrupa los `Producto` que comparten la misma `referencia_base` y `color`.
   - Propósito: Evitar subir la misma foto repetidas veces para cada talla. Las fotos se asocian a este modelo y las variantes lo referencian (`articulo_color_fotos`).
   - Se crea y asigna automáticamente al guardar un `Producto`.

3. **`FotoProducto` (Galería de Imágenes)**
   - Representa un archivo de imagen específico (`ImageField`) asociado a un `ReferenciaColor`.
   - Permite organizar el `orden` de las fotos y añadir una `descripcion_foto`.

---

## 🖥️ Vistas Principales (Django Views)

La aplicación provee una robusta interfaz de usuario renderizada en el servidor, utilizando Class-Based Views (CBV) y Mixins de autenticación/multi-tenant.

- **Listado de Productos (`ProductoListView`)**: Muestra el catálogo paginado con buscador por referencia, nombre, talla, color y código de barras. Filtra automáticamente por la empresa del usuario.
- **Creación Simple (`ProductoCreateView`)**: Formulario para crear una única variante de producto.
- **Creación Multi-Talla (`crear_producto_multi_talla`)**: Vista altamente optimizada que permite crear múltiples variantes (diferentes tallas) bajo la misma referencia y color en una sola transacción atómica, previniendo errores de duplicidad.
- **Carga de Fotos Agrupadas (`subir_fotos_agrupadas_view`)**: Interfaz para cargar múltiples imágenes de una sola vez hacia una combinación de Referencia + Color.
- **Importación / Exportación (`producto_import_view`, `producto_export_view`)**: Permite la carga masiva mediante archivos Excel/CSV utilizando `django-import-export`, inyectando el tenant a los registros entrantes.

---

## 🔌 API REST (Endpoints)

Existen endpoints protegidos con JWT / Autenticación de sesión, utilizados principalmente para dinamismo en el frontend (ej. carga asíncrona de formularios de pedidos).

| Endpoint | Propósito |
|----------|-----------|
| `/api/buscar/` | Búsqueda global de productos (retorna `id`, `text` con formato Ref - Nombre - Talla). |
| `/api/buscar-referencias/` | Búsqueda de referencias únicas dentro del catálogo de la empresa. |
| `/api/referencia/<ref>/colores/` | Obtiene los colores disponibles para una referencia específica. |
| `/api/referencia/<ref>/color/<color>/tallas/` | Obtiene las variantes (tallas), IDs, stock y precio para una combinación exacta de referencia y color. |

---

## 🔑 Funcionalidades Clave y Seguridad

- **Arquitectura Multi-Tenant Segura**: Tanto en las consultas de BD (`get_queryset`) como en la persistencia (`save`), se inyecta o filtra explícitamente mediante `request.tenant` de forma silenciosa para el usuario final.
- **Transacciones Atómicas**: Operaciones como la creación multi-talla utilizan `@transaction.atomic` para asegurar consistencia en la base de datos (se insertan todas las tallas, o ninguna).
- **Gestión Avanzada de Archivos**: Los nombres de archivo de las imágenes son unificados, limpiados (`slugify`) y se organizan en carpetas dentro de `media/` segmentadas por el ID del tenant (`empresa_<id>/`).
- **Integración con Bodega**: El stock no se almacena como un valor estático en el modelo `Producto`; es una propiedad calculada sumando o restando entradas y salidas desde el módulo de inventario.
