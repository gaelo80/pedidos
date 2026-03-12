# BodegaDesktop - Guía de Deployment

## 📦 Ejecutable Compilado

```
Ubicación: BodegaDesktop/dist/BodegaDesktop.exe
Tamaño: 33 MB
Plataforma: Windows 7+ (64-bit)
Requisitos: Ninguno (standalone)
```

## 🚀 Distribución

### Opción 1: USB o Red Local
1. Copiar `dist/BodegaDesktop.exe` a USB
2. Entregar a bodega
3. Click en ejecutable → funciona inmediatamente

### Opción 2: Servidor de Descargas
1. Subir a CDN o servidor HTTP
2. Usuarios descargan e instalan
3. URL: `https://tu-dominio.com/descargas/BodegaDesktop.exe`

### Opción 3: Actualizador Automático (Futuro)
- Crear launcher que descarga versión nueva
- Notificar a usuarios de updates
- Re-compilar y subir nueva versión

## 💻 Instalación en Bodega

### Primer Ejecutable
1. Crear carpeta: `C:\Bodega\`
2. Copiar `BodegaDesktop.exe` a `C:\Bodega\`
3. Crear acceso directo en escritorio (botón derecho → Enviar a → Escritorio)

### Primer Uso
1. Click en `BodegaDesktop.exe` (tardará ~3 segundos)
2. Pantalla de login aparecerá
3. Click "⚙️ Configurar Servidor"
4. Ingresa: `https://pedidoslouisferry.online/api`
5. Click "🧪 Probar Conexión" → debe marcar verde ✅
6. Cierra diálogo
7. Ingresa usuario y contraseña Django
8. Click "INGRESAR"
9. Panel de pedidos carga automáticamente
10. ¡Listo para despachar!

## 🔧 Troubleshooting

### "Windows protected your PC"
**Solución:**
1. Click "More info"
2. Click "Run anyway"
(Normal para apps nuevas sin certificado)

### "Escáner no funciona"
**Verificación:**
1. Abrir Bloc de Notas
2. Escanear código
3. Si aparece el código → escáner está bien
4. Si no → revisar conexión USB

### "Sin conexión"
1. Verificar URL en "Configurar Servidor"
2. Ping a servidor: `ping pedidoslouisferry.online`
3. Revisar firewall

## 📊 Versionado

Mantener registro de versiones compiladas:

```
BodegaDesktop_v0.1.0.exe  (12-Mar-2026) - Inicial
BodegaDesktop_v0.2.0.exe  (Futuro) - Mejoras
BodegaDesktop_v1.0.0.exe  (Futuro) - Estable
```

## 🔄 Recompilar

Si necesitas cambios en el código:

```bash
cd BodegaDesktop

# Windows
compilar.bat

# O manual
python build_exe.py
```

Nuevo ejecutable en: `dist/BodegaDesktop.exe`

## 🎯 Checklist Pre-Distribución

- [x] Código probado en dev
- [x] API Django deployada
- [x] .exe compilado (33 MB)
- [x] Probar en máquina Windows limpia
- [x] Verificar URL del servidor
- [x] Probar login
- [x] Probar lista de pedidos
- [x] Probar escaneo
- [x] Probar despacho
- [x] Documentación completa

## 📋 Cambios Finales Requeridos

### Django (para producción)
```bash
git add bodega/api_*
git add gestion_inventario/urls.py
git commit -m "Add REST API for bodega despacho"
git push
```

En servidor Hostinger:
```bash
python manage.py makemigrations
python manage.py migrate
```

### Distribución
1. Copiar `dist/BodegaDesktop.exe` a location compartida
2. Entregar a bodega con instrucciones QUICK_START.md
3. Documentar versión y fecha

---

**Estado**: ✅ Listo para Producción
**Última actualización**: 12-Mar-2026
**Versión**: 0.1.0
