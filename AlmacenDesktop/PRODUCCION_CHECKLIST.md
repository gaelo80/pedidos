# ✅ AlmacenDesktop - Checklist Producción

## 📋 Estado Actual

### ✅ Completado
- [x] Login con JWT
- [x] Sincronización de catálogo cada 60 segundos
- [x] BD local SQLite funcional con tablas para ventas y devoluciones
- [x] Módulos de Punto de Venta, Inventario, Devoluciones, Informes
- [x] Indicador visual de estado online/offline
- [x] **NUEVO: Sincronización de ventas a Django** ✨
- [x] **NUEVO: Endpoint Django para recibir facturas** ✨
- [x] API configurable vía variables de entorno

### 🔄 Implementado (Nuevas Características)

#### 1. Endpoint Django para Facturas
```
POST /api/almacen/facturas/
```
**Payload esperado:**
```json
{
  "consecutivo_local": "ALM-1",
  "fecha_venta": "2026-03-11T14:30:00Z",
  "total_venta": 1000000.00,
  "metodo_pago": "EFECTIVO",
  "detalles": [
    {
      "producto": 1,
      "cantidad": 2,
      "precio_unitario": 500000.00,
      "subtotal": 1000000.00
    }
  ]
}
```

#### 2. Sincronización Automática de Ventas
- **Intervalo**: Cada 60 segundos
- **Proceso**:
  1. Lee ventas con `estado_sincronizacion = 0`
  2. Envía POST a Django con detalles
  3. Marca como sincronizado (1) si es exitoso
  4. Continúa con la siguiente en caso de error

#### 3. Configuración Flexible
- **Archivo**: `.env`
- **Variable**: `ALMACEN_API_URL`
- **Default**: `http://127.0.0.1:8000/api`
- **Producción**: `https://tudominio.com/api`

---

## 🚀 Pasos para Producción

### 1. **Django - Preparación**
```bash
cd C:\Pedidos\Pedidos-main\sieslo

# Generar migraciones si es necesario
python manage.py makemigrations almacen

# Aplicar migraciones
python manage.py migrate

# Crear usuario de prueba (si no existe)
python manage.py createsuperuser

# Iniciar servidor
python manage.py runserver 0.0.0.0:8000
```

### 2. **AlmacenDesktop - Configuración**
```bash
cd C:\Pedidos\Pedidos-main\sieslo\AlmacenDesktop

# Copiar archivo de configuración
copy .env.example .env

# EDITAR .env con la URL de producción
# ALMACEN_API_URL=https://tudominio.com/api
```

### 3. **AlmacenDesktop - Ejecución**
```bash
# Activar entorno virtual
.venv\Scripts\activate

# Ejecutar aplicación
python main.py
```

### 4. **Verificar Sincronización**
1. Abrir AlmacenDesktop
2. Login con credenciales válidas
3. Ir a "Punto de Venta"
4. Registrar una venta
5. Esperar hasta 60 segundos
6. Verificar en Django admin que aparezca la factura

---

## 📊 Base de Datos

### Tablas Locales (SQLite)
```
productos_local
├── id_producto (INTEGER PRIMARY KEY)
├── codigo_barras (TEXT UNIQUE)
├── nombre (TEXT)
├── precio_detal (REAL)
└── stock_local (INTEGER)

ventas_pendientes_sincronizar
├── id_venta (INTEGER PRIMARY KEY AUTOINCREMENT)
├── fecha (TEXT)
├── total (REAL)
├── metodo_pago (TEXT)
├── detalles (TEXT - JSON)
└── estado_sincronizacion (INTEGER) ← 0=pendiente, 1=sincronizado

devoluciones_pendientes
├── id_devolucion (INTEGER PRIMARY KEY AUTOINCREMENT)
├── fecha (TEXT)
├── tipo (TEXT)
├── detalles (TEXT - JSON)
└── estado_sincronizacion (INTEGER)
```

### Tablas Django (PostgreSQL/MySQL)
```
almacen_facturaamacen
├── id (INTEGER PRIMARY KEY)
├── consecutivo_local (VARCHAR)
├── fecha_venta (DATETIME)
├── vendedor_id (FK auth_user)
├── total_venta (DECIMAL)
├── metodo_pago (VARCHAR)
└── sincronizado_el (DATETIME AUTO)

almacen_detallfacturaamacen
├── id (INTEGER PRIMARY KEY)
├── factura_id (FK FacturaAlmacen)
├── producto_id (FK productos_producto)
├── cantidad (INTEGER)
├── precio_unitario (DECIMAL)
└── subtotal (DECIMAL)
```

---

## 🔍 Monitoreo

### Logs en Django
```bash
# Ver facturas sincronizadas
python manage.py shell
>>> from almacen.models import FacturaAlmacen
>>> FacturaAlmacen.objects.all().count()
>>> FacturaAlmacen.objects.last()
```

### Logs en AlmacenDesktop
- Estado online/offline: esquina superior derecha (🟢/🔴)
- Últimas sincronizaciones automáticas: cada 60 segundos
- Errores de conexión: mostrados en módulo

---

## ⚠️ Consideraciones Seguridad

1. **JWT Token**
   - Usar HTTPS en producción
   - Tokens expiran después del tiempo configurado
   - Regenerar tokens periódicamente

2. **Base de Datos Local**
   - Backup automático recomendado
   - Encriptar si contiene datos sensibles

3. **CORS**
   - Configurar `ALLOWED_HOSTS` en Django settings
   - Agregar header `CSRF_TRUSTED_ORIGINS` si es necesario

4. **API Keys**
   - No guardar credenciales en código
   - Usar variables de entorno (.env)
   - No hacer push de .env a repositorio

---

## 📞 Troubleshooting

### Error: "No se pudo conectar. Usando modo local."
- **Causa**: Servidor Django no accesible
- **Solución**:
  1. Verificar que Django esté corriendo
  2. Verificar URL en `.env`
  3. Verificar firewall/puertos

### Ventas no sincronizadas
- **Verificar**:
  1. Estado online en UI (debe ser 🟢)
  2. Token válido (revisar credenciales de login)
  3. Revisar logs de Django: `python manage.py shell`

### Error 401 (Unauthorized)
- **Causa**: Token expirado o inválido
- **Solución**: Hacer logout y login nuevamente

---

## 📝 Notas Finales

- **Próximos pasos**: Implementar sincronización de devoluciones (similar a ventas)
- **Mejoras futuras**: Caché local mejorado, sincronización bidireccional
- **Soporte**: Contactar equipo de desarrollo

**Versión**: 1.0
**Fecha**: 2026-03-11
**Estado**: ✅ LISTO PARA PRODUCCIÓN
