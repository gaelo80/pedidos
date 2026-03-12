# ⚠️ ACTUALIZACIONES REQUERIDAS PARA GITHUB

**Fecha:** 2026-03-11
**Prioridad:** ALTA

---

## 📋 CAMBIOS REALIZADOS EN SETTINGS.PY

### 1. ✅ Almacen App Config
**Cambio:**
```python
# ANTES
'almacen',

# AHORA
'almacen.apps.AlmacenConfig',  # ✅ Asegura que signals se carguen
```

**Razón:** AlmacenConfig tiene un método `ready()` que importa los signals automáticamente.

---

### 2. ✅ Configuración de Base de Datos
**Agregado:**
```python
'ATOMIC_REQUESTS': False,  # Usar transaction.atomic() explícitamente
```

**Razón:** Las correcciones de inventario dependen de transacciones explícitas con `transaction.atomic()`.

---

### 3. ✅ Mejora de Logging
**Agregado:**
- Formateo mejorado de logs
- Rotating file handler para logs de bodega y almacen
- Logs específicos para signals en `logs/django.log`

**Razón:** Ayuda a debuggear si hay problemas con signals o movimientos de inventario.

---

## 🚨 ARCHIVO .gitignore - VERIFICAR Y ACTUALIZAR

**NO SUBIR A GITHUB:**
```
# Secretos y credenciales
.env
.env.local
.env.*.local
.venv/
venv/

# Base de datos
db.sqlite3

# Media y Static
media/
staticfiles/

# Logs
logs/
*.log

# IDE
.vscode/
.idea/
*.pyc
__pycache__/
*.egg-info/

# AlmacenDesktop
AlmacenDesktop/dist/
AlmacenDesktop/build/
AlmacenDesktop/*.exe
AlmacenDesktop/*.msi
```

**Verificar que en .gitignore estén:**
```bash
git check-ignore .env
git check-ignore db.sqlite3
git check-ignore logs/
git check-ignore media/
```

---

## 🔐 VARIABLES DE ENTORNO (.env)

**Asegúrate que NUNCA estén commiteadas:**

```env
# Secretos Django
SECRET_KEY=tu-clave-secreta-aqui
DEBUG=True

# Base de Datos
DB_ENGINE=django.db.backends.postgresql
DB_NAME=pedidos_db
DB_USER=postgres
DB_PASSWORD=contraseña-segura
DB_HOST=localhost
DB_PORT=5432

# Cloudflare R2
R2_ACCESS_KEY_ID=tu-key
R2_SECRET_ACCESS_KEY=tu-secret
R2_BUCKET_NAME=pedidos-bucket
R2_ACCOUNT_ID=tu-account-id
```

**Cómo verificar que .env está ignorado:**
```bash
git log --all --oneline -- .env | wc -l
# Debe devolver 0 (nunca fue commiteado)
```

---

## 📝 ARCHIVOS A SUBIR A GITHUB

```
✅ bodega/models.py (modificado)
✅ bodega/admin.py (modificado)
✅ bodega/views.py (modificado)
✅ bodega/migrations/0005_*.py (nuevo)
✅ almacen/signals.py (nuevo)
✅ almacen/serializers.py (modificado)
✅ almacen/apps.py (modificado)
✅ gestion_inventario/settings.py (modificado - YA HECHO)
✅ IMPLEMENTACION_OPTION_B_COMPLETA.md (nuevo)
```

---

## ❌ ARCHIVOS QUE NO SUBIR

```
❌ .env (secretos)
❌ db.sqlite3 (base de datos local)
❌ media/ (archivos de usuarios)
❌ logs/ (logs locales)
❌ venv/ o .venv/ (entorno virtual)
❌ __pycache__/ (archivos compilados)
❌ AlmacenDesktop/dist/ (ejecutables)
❌ AlmacenDesktop/build/
```

---

## 🚀 PASOS PARA SUBIR A GITHUB

```bash
# 1. Verificar que no hay archivos sensibles
git status

# 2. Verificar específicamente
git check-ignore .env .env.local db.sqlite3

# 3. Si ya están commiteados, hacer:
git rm --cached .env db.sqlite3 logs/ media/
echo ".env" >> .gitignore
git add .gitignore
git commit -m "Remove sensitive files from git tracking"

# 4. Hacer push
git push origin main
```

---

## ✅ VERIFICACIÓN POST-PUSH

```bash
# Verificar que settings.py fue actualizado
git show origin/main:gestion_inventario/settings.py | grep "AlmacenConfig"
# Debe mostrar: 'almacen.apps.AlmacenConfig',

# Verificar que .env no está
git ls-remote origin --heads | grep .env
# No debe devolver nada
```

---

## 📞 CHECKLIST ANTES DE HACER PUSH

- [ ] `.env` no es tracked por git
- [ ] `db.sqlite3` no es tracked por git
- [ ] `media/` no es tracked por git
- [ ] `logs/` no es tracked por git
- [ ] `settings.py` tiene `AlmacenConfig`
- [ ] `settings.py` tiene `ATOMIC_REQUESTS: False`
- [ ] Todos los signals están en `ready()` de apps.py
- [ ] `bodega/migrations/0005_*.py` está en git
- [ ] `almacen/signals.py` está en git
- [ ] Commit message describe los cambios

---

## 🔧 COMANDOS ÚTILES

**Ver qué se va a hacer push:**
```bash
git log origin/main..main --oneline
```

**Ver archivos que se van a subir:**
```bash
git diff --name-only origin/main..main
```

**Hacer push de forma segura:**
```bash
git push --dry-run origin main  # Ver sin hacer cambios
git push origin main             # Hacer el push real
```

---

**Estado:** Listo para GitHub
**Última revisión:** 2026-03-11
