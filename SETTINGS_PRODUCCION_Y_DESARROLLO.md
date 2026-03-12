# ✅ SETTINGS.PY ORGANIZADO PARA DESARROLLO Y PRODUCCIÓN

**Fecha:** 2026-03-11
**Estado:** ✅ IMPLEMENTADO Y VERIFICADO
**Commit:** e1486f2

---

## 📊 ¿Cómo Funciona?

El nuevo `settings.py` **detecta automáticamente** el modo y aplica la configuración correcta:

```
Variable de Entorno: DEBUG
         ↓
    ¿DEBUG=True?
    /          \
   SÍ           NO
  ↓             ↓
DESARROLLO    PRODUCCIÓN
(localhost)   (HTTPS online)
```

---

## 🔧 Configuración en DESARROLLO (DEBUG=True)

### ALLOWED_HOSTS
```python
ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
```
✅ Solo localhost, perfecto para desarrollo local.

### Seguridad (Desactivada para HTTP)
```python
CSRF_COOKIE_SECURE = False      # HTTP OK
SESSION_COOKIE_SECURE = False   # HTTP OK
SECURE_SSL_REDIRECT = False     # No fuerza HTTPS
SECURE_HSTS_SECONDS = 0         # Sin HSTS
```
✅ Funciona con HTTP local sin problemas.

### CSRF Trusted Origins
```python
CSRF_TRUSTED_ORIGINS = []
```
✅ Vacío en desarrollo local.

### Logging
```
Consola + Archivo (logs/django.log)
```
✅ Puedes debuggear fácilmente.

---

## 🔒 Configuración en PRODUCCIÓN (DEBUG=False)

### ALLOWED_HOSTS
```python
ALLOWED_HOSTS = [
    'pedidoslouisferry.online',
    'www.pedidoslouisferry.online',
    'pedidoswhite.online',
    'www.pedidoswhite.online',
    'pedidosharmony.online',
    'www.pedidosharmony.online',
    'pedidosamerican.online',
    'www.pedidosamerican.online',
    'pedidosexclusive.online',
    'www.pedidosexclusive.online',
]
```
✅ Solo tus dominios online.

### Seguridad (Activada para HTTPS)
```python
CSRF_COOKIE_SECURE = True       # Solo HTTPS
SESSION_COOKIE_SECURE = True    # Solo HTTPS
SECURE_SSL_REDIRECT = True      # Fuerza HTTPS
SECURE_HSTS_SECONDS = 31536000  # 1 año
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
```
✅ Máxima seguridad para producción.

### CSRF Trusted Origins
```python
CSRF_TRUSTED_ORIGINS = [
    'https://pedidoslouisferry.online',
    'https://www.pedidoslouisferry.online',
    # ... todos tus dominios HTTPS
]
```
✅ Solo tus dominios HTTPS.

---

## 📋 Nuevas Características Agregadas

### 1. Almacen App (Signals)
```python
INSTALLED_APPS = [
    # ...
    'almacen.apps.AlmacenConfig',  # ✅ Carga signals automáticamente
    # ...
]
```

### 2. Transacciones Explícitas
```python
DATABASES = {
    'default': {
        # ...
        'ATOMIC_REQUESTS': False,  # ✅ Transacciones explícitas en vistas
    }
}
```

### 3. Mejor Logging
```python
LOGGING = {
    # Archivo rotativo: logs/django.log (10 MB max, 5 backups)
    # Loggers específicos para bodega y almacen
    # Formato verbose: [LEVEL] TIMESTAMP NAME MESSAGE
}
```

---

## 🚀 Cómo Usar

### En DESARROLLO (Local)

**En tu `.env` o variable de entorno:**
```env
DEBUG=True
```

**Accede a:**
```
http://127.0.0.1:8000
http://localhost:8000
```

**Prueba con:**
```bash
python manage.py check        # ✅ Verifica que está correcto
python manage.py runserver    # ✅ Inicia servidor local
```

---

### En PRODUCCIÓN (Servidor)

**En tu `.env` del servidor:**
```env
DEBUG=False
SECRET_KEY=tu-clave-secreta
DB_ENGINE=django.db.backends.postgresql
DB_NAME=pedidos_db
DB_USER=postgres
DB_PASSWORD=contraseña
DB_HOST=localhost
DB_PORT=5432
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=...
R2_ACCOUNT_ID=...
```

**Accede a:**
```
https://pedidoslouisferry.online
https://www.pedidoslouisferry.online
(etc - con HTTPS obligatorio)
```

**Verifica:**
```bash
python manage.py check --deploy
```

---

## ⚠️ Importante: Variable DEBUG

**El settings AUTOMÁTICAMENTE detecta DEBUG:**

```python
DEBUG = os.getenv('DEBUG', 'True') == 'True'
```

- Si `DEBUG=True` (o no existe): Modo desarrollo
- Si `DEBUG=False`: Modo producción

**NO necesitas tocar el código**, solo la variable de entorno.

---

## 🔄 Flujo de Desarrollo

```
1. Desarrollo Local
   └─ DEBUG=True en .env
   └─ ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
   └─ CSRF_COOKIE_SECURE = False
   └─ Funciona en HTTP ✅

2. Testear en Producción (Local)
   └─ DEBUG=False en .env
   └─ Simula seguridad HTTPS
   └─ Verifica que ALLOWED_HOSTS esté correcto

3. Producción (Servidor)
   └─ DEBUG=False en .env del servidor
   └─ HTTPS forzado automáticamente
   └─ Máxima seguridad ✅
```

---

## ✅ Verificación Post-Implementación

```bash
# 1. Verificar que Django está OK
python manage.py check
# System check identified no issues (0 silenced). ✅

# 2. Verificar que tu usuario local funciona
# Accede a http://127.0.0.1:8000 con tu usuario

# 3. Verificar que los signals cargan
python manage.py shell
>>> from almacen import signals
# Sin error = OK ✅

# 4. Verificar que el logging funciona
# Debe haber archivo logs/django.log
ls -la logs/django.log
```

---

## 📊 Comparativa: Antes vs Después

| Aspecto | Antes | Después |
|--------|-------|---------|
| **Desarrollo** | ❌ Error CSRF en localhost | ✅ Funciona perfecto |
| **Producción** | ✅ Seguro | ✅ Más seguro aún |
| **Signals** | ❌ No cargaban | ✅ Se cargan automáticamente |
| **Transacciones** | ⚠️ Parcial | ✅ Completas |
| **Logging** | ⚠️ Consola solo | ✅ Archivo rotativo |
| **Mantenimiento** | Complejo | ✅ Simple (solo .env) |

---

## 🎯 Próximos Pasos (Opcionales)

- [ ] Crear `.env.example` para documentar variables
- [ ] Agregar whitenoise para archivos estáticos en prod
- [ ] Configurar sentry para monitoreo de errores
- [ ] Backup automático de base de datos

---

## 📞 Si Algo Falla

### Error "DisallowedHost" en 127.0.0.1
**Causa:** ALLOWED_HOSTS no tiene 127.0.0.1
**Solución:** DEBUG debe ser True en .env

### Error CSRF 403
**Causa:** DEBUG=False pero usando HTTP
**Solución:** O poner DEBUG=True, o usar HTTPS

### Error "No tenant found"
**Causa:** Dominio no registrado en base de datos
**Solución:** Agregar Dominio para 127.0.0.1 (ya lo hiciste ✅)

---

## 🎓 Resumen

✅ Settings inteligente y automático
✅ Funciona en desarrollo sin problemas
✅ Funciona en producción con máxima seguridad
✅ No requiere cambios de código, solo .env
✅ Signals, transacciones y logging completos

**¡El sistema está listo para desarrollo y producción!**

---

**Versión:** 1.0
**Estado:** ✅ LISTO PARA USAR
**Última actualización:** 2026-03-11
**Commit:** e1486f2
