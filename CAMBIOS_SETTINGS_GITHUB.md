# 🚀 CAMBIOS PARA ACTUALIZAR settings.py EN GITHUB

**3 cambios mínimos y críticos para que funcionen las correcciones de inventario**

---

## 📍 CAMBIO #1: AGREGAR 'almacen.apps.AlmacenConfig' (LÍNEA DESPUÉS DE 'pedidos_online')

### Antes:
```python
INSTALLED_APPS = [
        'django.contrib.admin',
        # ... otras apps ...
        'notificaciones',
        'pedidos_online',


        # APLICACIONES DE TERCERO
```

### Después:
```python
INSTALLED_APPS = [
        'django.contrib.admin',
        # ... otras apps ...
        'notificaciones',
        'pedidos_online',
        'almacen.apps.AlmacenConfig',  # ✅ CRÍTICO: Carga signals automáticamente


        # APLICACIONES DE TERCERO
```

**¿Por qué?** Sin esto, los signals de sincronización automática de inventarios NO funcionarán.

---

## 📍 CAMBIO #2: AGREGAR 'ATOMIC_REQUESTS' EN DATABASES (DENTRO DEL 'default')

### Antes:
```python
DATABASES = {
    'default': {
        'ENGINE': config('DB_ENGINE', default='django.db.backends.sqlite3'),
        'NAME': config('DB_NAME', default=BASE_DIR / 'db.sqlite3'),
        'USER': config('DB_USER', default=''),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default=''),
        'PORT': config('DB_PORT', default=''),
    }
}
```

### Después:
```python
DATABASES = {
    'default': {
        'ENGINE': config('DB_ENGINE', default='django.db.backends.sqlite3'),
        'NAME': config('DB_NAME', default=BASE_DIR / 'db.sqlite3'),
        'USER': config('DB_USER', default=''),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default=''),
        'PORT': config('DB_PORT', default=''),
        'ATOMIC_REQUESTS': False,  # ✅ Necesario para transaction.atomic() explícito en vistas
    }
}
```

**¿Por qué?** Las correcciones usan `transaction.atomic()` en las vistas de cambios, devoluciones y conteos.

---

## 📍 CAMBIO #3: REEMPLAZAR TODO EL LOGGING (OPCIONAL PERO RECOMENDADO)

### Antes:
```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'ERROR',
        },
        '': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

### Después:
```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {name} {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'simple': {
            'format': '[{levelname}] {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'bodega.models': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'almacen.signals': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

**¿Por qué?** Para poder debuggear si hay problemas con signals o movimientos de inventario. Los logs se guardarán en `logs/django.log`.

---

## ✅ VERIFICACIÓN FINAL

Después de hacer los cambios:

```bash
# 1. Crear directorio logs si no existe
mkdir -p logs

# 2. Verificar que settings está correcto
python manage.py check
# Debe mostrar: System check identified no issues (0 silenced).

# 3. Hacer git add y commit
git add gestion_inventario/settings.py
git commit -m "Actualiza settings para soporte de signals de inventario"
git push origin main
```

---

## 🔒 LO QUE NO CAMBIES

✅ Mantener igual:
- ✅ CONTRASEÑA_PARA_VERIFICAR_PEDIDO = "Admin1234"
- ✅ ALLOWED_HOSTS (todos los dominios)
- ✅ CSRF_TRUSTED_ORIGINS (todos los HTTPS)
- ✅ AWS_S3_CUSTOM_DOMAIN = 'pub-3189840290c243e499cc02ac48d3a787.r2.dev'
- ✅ AUTH_USER_MODEL = 'core.User'
- ✅ DATA_UPLOAD_MAX_NUMBER_FIELDS = 12000
- ✅ REST_FRAMEWORK (autenticación)
- ✅ Todas las demás configuraciones

---

## 📋 RESUMEN

| Cambio | Archivo | Línea | Crítico |
|--------|---------|-------|---------|
| Agregar almacen.apps.AlmacenConfig | INSTALLED_APPS | ~ 150 | ⚠️ SÍ |
| Agregar ATOMIC_REQUESTS | DATABASES | ~ 210 | ⚠️ SÍ |
| Mejorar LOGGING | LOGGING | ~ 280 | ℹ️ Opcional |

**Sin los cambios #1 y #2, los inventarios volverán a descuadrarse.**

---

**Versión:** 1.0
**Estado:** Listo para GitHub
**Fecha:** 2026-03-11
