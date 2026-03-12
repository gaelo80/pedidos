# AlmacenDesktop - Aplicación de Punto de Venta

Sistema de gestión de ventas para almacén con sincronización automática con servidor Django.

## Características

- **POS Completo**: Registro de ventas, devoluciones, cambios
- **Inventario Local**: SQLite con sincronización
- **Modo Offline**: Funciona sin conexión, sincroniza cuando hay
- **Configuración desde UI**: Cambiar URL del servidor sin editar archivos
- **Informes**: Cierre de caja, historial de ventas
- **Seguro**: Validaciones de stock en tiempo real

---

## Instalación Rápida

### Opción 1: Ejecutable Standalone (Recomendado)

1. **Descargar**: Obtener `AlmacenDesktop.exe` compilado
2. **Ejecutar**: Doble-click en `AlmacenDesktop.exe`
3. **Configurar**:
   - Ir a "Configuración" → "Red y Sincronización"
   - Ingresar URL del servidor: `https://tu-dominio.com/api`
   - Click "Guardar"
   - Click "Probar Conexión"
4. **¡Listo!**

### Opción 2: Compilar desde Código

#### Requisitos
- Python 3.9 o superior
- pip (gestor de paquetes)

#### Pasos

1. **Clonar repositorio**
   ```bash
   cd C:\Pedidos\Pedidos-main\sieslo\AlmacenDesktop
   ```

2. **Instalar dependencias**
   ```bash
   pip install -r requirements.txt
   pip install pyinstaller
   ```

3. **Compilar**

   **Windows:**
   ```bash
   compilar.bat
   ```

   **Linux/Mac:**
   ```bash
   python build_exe.py
   ```

4. **Ejecutar**
   - Windows: `dist\AlmacenDesktop.exe`
   - Linux/Mac: `dist/AlmacenDesktop`

---

## Configuración del Servidor

### En el Almacén

Abre AlmacenDesktop → Configuración → Red y Sincronización

#### URLs por Entorno

- **Desarrollo Local**: `http://127.0.0.1:8000/api`
- **Hostinger**: `https://mi-negocio.com/api`
- **Servidor Propio**: `https://servidor.miempresa.com/api`

### Probar Conexión

1. Ingresa la URL
2. Click "Guardar"
3. Click "Probar Conexión"
4. Deberías ver "● Conectado (HTTP 200)" en verde

---

## Uso de la Aplicación

### Dashboard
- Vista general de ventas del día
- Acceso rápido a módulos

### Módulo POS (Ventas)
1. Busca productos por referencia
2. Agrega cantidades al carrito
3. Procesa pago
4. Se sincroniza automáticamente con servidor

### Devoluciones
- Registra devoluciones de clientes
- Actualiza inventario automáticamente

### Informes
- Cierre de caja diario
- Historial de transacciones
- Reportes de inventario

### Mantenimiento
- **Limpiar Historial**: Borra ventas locales
- **Vaciar Catálogo**: Fuerza nueva sincronización
- **Reset Total**: Limpia todo (irreversible)

---

## Sincronización

### Automática
Se ejecuta cada vez que:
- Inicia la aplicación
- Se cierra una venta
- Se completa una devolución

### Manual
En Configuración → Sincronización → Click "Sincronizar ahora"

### Base de Datos

Archivo: `almacen.db` (SQLite)

Tablas principales:
- `productos_local`: Catálogo cachée
- `ventas_pendientes_sincronizar`: Ventas sin enviar
- `devoluciones_pendientes`: Devoluciones sin enviar
- `configuracion`: Configuración guardada

---

## Solución de Problemas

### Error: "Sin conexión — servidor no alcanzable"

**Causas:**
- URL incorrecta
- Servidor offline
- Problema de red

**Solución:**
1. Verifica la URL en Configuración
2. Prueba ping al servidor
3. Revisa firewall/proxy

### Error: "Tiempo de espera agotado"

**Causa:** Red lenta

**Solución:**
1. Comprueba conexión a internet
2. Intenta en modo offline (funciona igual)
3. Sincroniza manualmente cuando haya mejor conexión

### No aparecen productos

**Causas:**
- Catálogo no sincronizado
- BD corrupta

**Solución:**
1. Ir a Mantenimiento → Vaciar Catálogo
2. Ir a Configuración → Sincronizar ahora
3. Reinicia la aplicación

---

## Requisitos del Sistema

### Mínimos
- **OS**: Windows 7+ / macOS 10.12+ / Linux
- **RAM**: 256 MB
- **Espacio**: 150 MB
- **Conexión**: 1 Mbps (para sincronización)

### Recomendados
- **OS**: Windows 10+
- **RAM**: 1 GB
- **Espacio**: 500 MB
- **Conexión**: 5+ Mbps

---

## API Esperada

El servidor Django debe tener estos endpoints:

- `GET /api/almacen/inventario/` - Descargar productos
- `POST /api/almacen/facturas/` - Enviar facturas
- `POST /api/almacen/devoluciones/` - Enviar devoluciones

---

## Contacto & Soporte

Para reportar errores o solicitar features:
1. Revisa la sección "Mantenimiento" en la aplicación
2. Consulta los logs en el archivo `almacen.db`
3. Contacta al equipo de desarrollo

---

## Versiones

- **v1.0.0**: Lanzamiento inicial con sincronización básica
- **v1.1.0**: Configuración editable desde UI + mejoras de sync
- **v2.0.0**: Próxima (con soporte para múltiples almacenes)

---

**Última actualización**: Marzo 2026
