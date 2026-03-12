# ✅ CHECKLIST PRE-DEPLOYMENT A HOSTINGER

**Fecha:** 2026-03-11
**Estado:** Listo para producción

---

## ✅ EN TU PC (Verificar antes de hacer deploy)

### 1. Django Check
```bash
python manage.py check
# Debe mostrar: System check identified no issues (0 silenced).
```
- [ ] Sin errores ✅

### 2. Git Status
```bash
git status
# NO debe mostrar:
# - .env
# - db.sqlite3
# - logs/
# - gestion_inventario/settings.py.backup.*
```
- [ ] .env no aparece ✅
- [ ] db.sqlite3 no aparece ✅
- [ ] logs/ no aparece ✅
- [ ] settings.py.backup.* no aparece ✅

### 3. Git Log
```bash
git log --oneline | head -3
```
Debe mostrar:
```
cb19f14 Actualiza .gitignore
e1486f2 Organiza settings.py
ba01537 Implementa correcciones Option B
```
- [ ] Últimos 3 commits correctos ✅

### 4. Settings.py Local
```bash
python manage.py shell
>>> from django.conf import settings
>>> settings.DEBUG
True
```
- [ ] DEBUG = True en desarrollo ✅

### 5. Acceso a http://127.0.0.1:8000
- [ ] Puedo acceder sin errores ✅
- [ ] Usuarios pueden loguearse ✅
- [ ] Base de datos funciona ✅

---

## 📤 PUSH A GITHUB

```bash
git push origin main
```

Verificar:
- [ ] Push completado sin errores
- [ ] GitHub muestra los últimos commits

---

## 🚀 EN HOSTINGER (Configurar después)

### 1. Variables de Entorno (.env en servidor)

En el panel de Hostinger, agregar:

```env
DEBUG=False
SECRET_KEY=tu-clave-secreta-aqui
DB_ENGINE=django.db.backends.postgresql
DB_NAME=pedidos_db
DB_USER=usuario_db
DB_PASSWORD=contraseña_segura_aqui
DB_HOST=localhost
DB_PORT=5432
R2_ACCESS_KEY_ID=tu-key-aqui
R2_SECRET_ACCESS_KEY=tu-secret-aqui
R2_BUCKET_NAME=pedidos-bucket
R2_ACCOUNT_ID=tu-account-id
```

- [ ] Variables agregadas en panel Hostinger ✅

### 2. Clonar desde GitHub

```bash
git clone https://github.com/gaelo80/pedidos.git
cd pedidos
cd sieslo
```

- [ ] Código descargado de GitHub ✅

### 3. Instalar Dependencias

```bash
pip install -r requirements.txt
```

- [ ] Dependencias instaladas ✅

### 4. Crear Carpeta logs

```bash
mkdir -p logs
chmod 755 logs
```

- [ ] Carpeta logs creada ✅

### 5. Migrations

```bash
python manage.py migrate
```

- [ ] Migraciones aplicadas ✅

### 6. Crear Dominio en Base de Datos

```bash
python manage.py shell
```

```python
from clientes.models import Dominio, Empresa

# Obtener la empresa (asume que existe)
empresa = Empresa.objects.first()

# Crear dominio para tu sitio
for dominio_nombre in ['pedidoslouisferry.online', 'www.pedidoslouisferry.online',
                        'pedidoswhite.online', 'www.pedidoswhite.online',
                        'pedidosharmony.online', 'www.pedidosharmony.online',
                        'pedidosamerican.online', 'www.pedidosamerican.online',
                        'pedidosexclusive.online', 'www.pedidosexclusive.online']:
    dominio, created = Dominio.objects.get_or_create(
        nombre_dominio=dominio_nombre,
        defaults={'empresa': empresa}
    )
    print(f"{'✅ Creado' if created else '✅ Existe'}: {dominio_nombre}")
```

- [ ] Dominios registrados en BD ✅

### 7. Verificar Settings en Producción

```bash
python manage.py check --deploy
# Debe mostrar: System check identified no issues (0 silenced).
```

- [ ] No hay errores de deploy ✅

### 8. Recolectar Static Files

```bash
python manage.py collectstatic --noinput
```

- [ ] Archivos estáticos recolectados ✅

### 9. Reiniciar Servidor

En el panel de Hostinger, reinicia la aplicación Django.

- [ ] Servidor reiniciado ✅

### 10. Probar en https://pedidoslouisferry.online

- [ ] Sitio carga correctamente ✅
- [ ] Puedo loguearme ✅
- [ ] HTTPS funciona (candado verde) ✅
- [ ] Sin errores 500 ✅

---

## ⚠️ PUNTOS CRÍTICOS

1. **DEBUG=False en Hostinger** (NO True)
   - Si dejas DEBUG=True, tu código fuente será visible

2. **SECRET_KEY único** en Hostinger
   - Usar uno diferente al local

3. **HTTPS obligatorio** en URLs
   - El settings fuerza HTTPS automáticamente

4. **Backup antes de deploy**
   ```bash
   # En tu PC
   tar -czf backup_antes_deploy.tar.gz .
   ```

5. **Database backup en Hostinger**
   - Hostinger probablemente lo hace automáticamente
   - Verifica en el panel

---

## 🔄 Si Algo Falla

### Error "DisallowedHost"
```bash
# Verificar que el dominio está en Dominio model
python manage.py shell
>>> from clientes.models import Dominio
>>> Dominio.objects.filter(nombre_dominio='pedidoslouisferry.online')
```

### Error CSRF 403
```bash
# Verificar que DEBUG=False en .env del servidor
# El settings debe aplicar CSRF_COOKIE_SECURE=True automáticamente
```

### Error "No module named 'almacen'"
```bash
# Verificar que almacen/signals.py existe
# Verificar que 'almacen.apps.AlmacenConfig' en INSTALLED_APPS
```

### Errores de Base de Datos
```bash
# Correr migraciones nuevamente
python manage.py migrate
```

---

## ✅ RESUMEN FINAL

| Paso | Hecho |
|------|-------|
| Settings inteligente (dev/prod) | ✅ |
| Signals de inventario | ✅ |
| .gitignore protegido | ✅ |
| Commit a GitHub | 📤 Listo |
| Variables en Hostinger | 📝 Por hacer |
| Dominios registrados | 📝 Por hacer |
| HTTPS verificado | 📝 Por hacer |

---

## 🙏 Última Nota

```
"A la mano de Dios"

Hemos hecho todo correctamente:
✅ Correcciones de inventario implementadas
✅ Settings organizados para dev/prod
✅ Código en GitHub protegido
✅ Documentación completa

El sistema está listo.
Conía en lo que hemos hecho.
```

---

**¡Mucho éxito con el deployment! 🚀**

---

**Versión:** 1.0
**Fecha:** 2026-03-11
**Status:** ✅ LISTO PARA PRODUCCIÓN
