# 📦 AlmacenDesktop - Guía de Distribución

## 🎯 ¿Qué es AlmacenDesktop?

Sistema de gestión de almacén en tiempo real con sincronización automática a Django:
- ✅ Punto de Venta local
- ✅ Control de inventario
- ✅ Gestión de devoluciones
- ✅ Sincronización automática cada 60 segundos
- ✅ Modo offline (continúa funcionando sin internet)

---

## 🚀 INICIO RÁPIDO

### Opción 1: Ejecutar desde Código Python (Desarrollo)
```bash
cd C:\Pedidos\Pedidos-main\sieslo\AlmacenDesktop
python main.py
```

### Opción 2: Descargar .exe Precompilado (Producción)
**[Próximamente disponible en la nube]**

### Opción 3: Compilar tu Propio .exe
```bash
# En Windows
compilar_exe.bat

# En Mac/Linux
./compilar_exe.sh
```

---

## 📥 INSTALACIÓN EN OTROS PCs

### Para PC con Python Instalado
```cmd
cd C:\ruta\a\AlmacenDesktop
python main.py
```

### Para PC SIN Python (Usar .exe)
1. Descargar `AlmacenDesktop.exe`
2. Copiar a `C:\Program Files\AlmacenDesktop\`
3. Crear acceso directo en Desktop
4. Ejecutar

---

## ⚙️ CONFIGURACIÓN

### Archivo: `.env`
```ini
# URL del servidor Django
ALMACEN_API_URL=http://127.0.0.1:8000/api

# Para producción:
# ALMACEN_API_URL=https://midominio.com/api
```

### Crear archivo .env
```bash
# Copiar plantilla
copy .env.example .env

# Editar con tu editor favorito
notepad .env
```

---

## 🔄 FLUJO DE SINCRONIZACIÓN

```
[Venta en AlmacenDesktop]
       ↓
[Guarda en SQLite Local]
       ↓
[Cada 60 segundos verifica]
       ↓
[Si hay conexión: envía a Django]
       ↓
[Marca como sincronizado]
       ↓
[Aparece en Django Admin]
```

---

## 🎯 OPCIONES DE DESCARGA

### Opción 1: GitHub Releases
```
https://github.com/tuusuario/Pedidos/releases/
```
- ✅ Descargar .exe empaquetado
- ✅ Actualizaciones automáticas
- ✅ Control de versiones

### Opción 2: Nube Compartida
```
https://drive.google.com/...
https://onedrive.com/...
```
- ✅ Acceso desde cualquier lugar
- ✅ Fácil actualización
- ✅ Sin necesidad de Git

### Opción 3: Servidor Interno
```
http://tu-servidor-interno/almacen/descargas/
```
- ✅ Control total
- ✅ Licencias
- ✅ Tracking de uso

---

## 📋 REQUISITOS MÍNIMOS

| Requisito | Especificación |
|-----------|----------------|
| **SO** | Windows 7+ / Mac OS 10.14+ / Linux (Ubuntu 18+) |
| **RAM** | 2 GB mínimo, 4 GB recomendado |
| **Almacenamiento** | 300 MB (con Python) o 100 MB (.exe) |
| **Conexión** | No requerida (funciona offline) |
| **Python** | 3.10+ (si ejecutas desde código) |

---

## 🔐 SEGURIDAD

### Credenciales
- Login con usuario/contraseña de Django
- Autenticación JWT (tokens seguros)
- Sin almacenamiento de contraseñas

### Base de Datos Local
- SQLite encriptado (recomendado en prod)
- Backup automático diario
- Sincronización bidireccional

### Firewall
- Puerto 8000 (Django) debe estar abierto
- HTTPS obligatorio en producción
- SSL/TLS para conexiones seguras

---

## 📊 ESTADÍSTICAS DE USO

### Tamaño
- **Código fuente**: 15 MB
- **Ejecutable compilado**: 250 MB (con Python embebido)
- **Base de datos local**: < 50 MB

### Rendimiento
- **Inicio**: 3-5 segundos
- **Sincronización**: Cada 60 segundos (configurable)
- **Historial**: Último año en caché local

---

## 🆘 SOPORTE Y ACTUALIZACIONES

### Reportar Bugs
```
Email: soporte@sieslo.com
Portal: https://issues.sieslo.com/
Teléfono: +57 (código)
```

### Descargar Actualizaciones
1. **Automáticas**: (en desarrollo)
2. **Manuales**:
   - Descargar nueva versión
   - Reemplazar .exe
   - Reiniciar aplicación

### Versiones Anteriores
```
dist/AlmacenDesktop_v1.0/
dist/AlmacenDesktop_v1.1/
dist/AlmacenDesktop_v1.2/  ← Latest
```

---

## 📝 NOTAS

- **Compatibilidad**: Trabaja con Django 5.0+
- **Multiidioma**: Actualmente español
- **Multitenant**: Un almacén por instalación
- **Escalabilidad**: Soporta ~100 productos

---

## 🎓 CAPACITACIÓN

### Manuales disponibles
- `PRODUCCION_CHECKLIST.md` - Deploy y configuración
- `COMPILAR_EXE.md` - Cómo compilar desde código
- `GUIA_USUARIO.md` - Cómo usar la app (próximamente)

### Videos tutoriales
- YouTube: [AlmacenDesktop Setup](https://youtube.com/...)
- Intranet: Grabaciones en vivo

---

**Versión**: 1.0
**Última actualización**: 2026-03-11
**Próxima versión**: v1.1 (Q2 2026)

---

¿Necesitas ayuda? Contacta al equipo técnico: `tech@sieslo.com`
