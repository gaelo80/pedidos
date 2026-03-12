# 🔧 SOLUCIÓN: Error 403 CSRF (Prohibido - Verificación CSRF fallida)

**Fecha:** 2026-03-11
**Problema:** `Prohibido (403) - La verificación CSRF ha fallado. Solicitud abortada.`

---

## 🎯 Causa Raíz

Tu settings.py en GitHub tiene estas líneas **SIEMPRE ACTIVAS**:

```python
CSRF_COOKIE_SECURE = True          # Solo funciona en HTTPS
SESSION_COOKIE_SECURE = True       # Solo funciona en HTTPS
SECURE_SSL_REDIRECT = True         # Fuerza HTTPS
SECURE_HSTS_SECONDS = 31536000    # HSTS por 1 año
```

Pero probablemente **estés en desarrollo local (HTTP) o el servidor no está en HTTPS**.

---

## ✅ SOLUCIÓN: Settings.py Inteligente

He creado un settings.py que **auto-detecta DEBUG** y aplica seguridad solo en PRODUCCIÓN:

**Archivo:** `gestion_inventario/settings_github_correcto.py`

### Lo que hace:

**Si DEBUG = True (Desarrollo):**
```python
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
```

**Si DEBUG = False (Producción - HTTPS):**
```python
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
ALLOWED_HOSTS = [todas tus URLs https]
CSRF_TRUSTED_ORIGINS = [tus dominios HTTPS]
```

---

## 📋 PASOS PARA APLICAR LA SOLUCIÓN

### Paso 1: Copiar el nuevo settings.py

```bash
# En tu proyecto
cp gestion_inventario/settings_github_correcto.py gestion_inventario/settings.py
```

O manualmente:
1. Abre `gestion_inventario/settings_github_correcto.py`
2. Copia TODO el contenido
3. Pégalo en `gestion_inventario/settings.py`
4. Guarda

### Paso 2: Verificar que funciona localmente

```bash
# Debe ser DEBUG=True localmente
python manage.py check
# System check identified no issues (0 silenced).
```

### Paso 3: Crear carpeta logs si no existe

```bash
mkdir -p logs
```

### Paso 4: Hacer git add y push

```bash
git add gestion_inventario/settings.py
git commit -m "Corrige error 403 CSRF: Settings inteligente según DEBUG

- Seguridad condicional (HTTPS solo en producción)
- ALLOWED_HOSTS automático según DEBUG
- Agrega almacen.apps.AlmacenConfig para signals
- Agrega ATOMIC_REQUESTS para transacciones
- Mejora LOGGING con rotación de archivos"

git push origin main
```

---

## 🔍 QUÉ CAMBIÓ (Resumen)

| Aspecto | Desarrollo (DEBUG=True) | Producción (DEBUG=False) |
|--------|------------------------|-------------------------|
| **CSRF_COOKIE_SECURE** | False (HTTP OK) | True (HTTPS requerido) |
| **SESSION_COOKIE_SECURE** | False | True |
| **SECURE_SSL_REDIRECT** | False (HTTP OK) | True (Fuerza HTTPS) |
| **ALLOWED_HOSTS** | localhost, 127.0.0.1 | tus dominios |
| **CSRF_TRUSTED_ORIGINS** | [] (vacío) | [tus dominios] |

**IMPORTANTE:** Es el `DEBUG` en el `.env` o variable de entorno quien controla esto.

---

## 🌍 VARIABLE DE ENTORNO PARA PRODUCCIÓN

En tu servidor de producción, asegúrate que `.env` tenga:

```env
DEBUG=False
```

Así Django usa la configuración HTTPS/seguridad.

En desarrollo local, asegúrate:

```env
DEBUG=True
```

O déjalo vacío (por defecto es `True`):

```python
DEBUG = os.getenv('DEBUG', 'True') == 'True'  # Por defecto True si no existe
```

---

## ✅ VERIFICACIÓN

Después de actualizar, verifica:

```bash
# En desarrollo (DEBUG=True)
python manage.py shell
>>> from django.conf import settings
>>> settings.DEBUG
True
>>> settings.CSRF_COOKIE_SECURE
False
>>> settings.SECURE_SSL_REDIRECT
False
```

Si ves `False` en CSRF_COOKIE_SECURE y SECURE_SSL_REDIRECT, **está bien en desarrollo**.

---

## 🚨 SI SIGUE FALLANDO

Si aún ves error 403 CSRF después de esto:

1. **Borrar cache del navegador:**
   - Ctrl+Shift+Supr (Chrome/Firefox)
   - Seleccionar "Todos los tiempos"
   - Borrar cookies

2. **Reiniciar servidor Django:**
   ```bash
   python manage.py runserver
   ```

3. **Verificar que DEBUG=True localmente:**
   ```bash
   # En .env o variable de entorno
   DEBUG=True
   ```

4. **Verificar ALLOWED_HOSTS incluye tu host:**
   ```python
   # Si accedes desde 192.168.1.100, asegúrate que esté en ALLOWED_HOSTS
   # En desarrollo, ['127.0.0.1', 'localhost'] es suficiente para localhost
   ```

---

## 📊 CAMBIOS COMPLETOS EN ESTE settings.py

✅ Seguridad condicional según DEBUG
✅ Agrega `'almacen.apps.AlmacenConfig'` (signals)
✅ Agrega `'ATOMIC_REQUESTS': False` (transacciones)
✅ Mejora LOGGING con archivo rotativo
✅ Mantiene dominio R2 correcto
✅ Mantiene CONTRASEÑA_PARA_VERIFICAR_PEDIDO
✅ Mantiene DATA_UPLOAD_MAX_NUMBER_FIELDS = 12000

---

**Estado:** ✅ Listo para GitHub
**Versión:** 1.0
**Última actualización:** 2026-03-11
