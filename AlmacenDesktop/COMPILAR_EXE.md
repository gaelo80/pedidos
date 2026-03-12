# 🔨 COMPILAR AlmacenDesktop.exe

## 📋 Requisitos

- **Python 3.10+** instalado en Windows
- **PyInstaller** (se instala automáticamente)
- **~500 MB** de espacio en disco

## 🚀 Proceso de Compilación (3 Pasos)

### Paso 1: Descargar Python (si no lo tienes)
1. Ve a: https://www.python.org/downloads/
2. Descarga **Python 3.12** (o la versión más reciente)
3. **IMPORTANTE**: Marca la opción **"Add Python to PATH"** durante la instalación
4. Verifica:
   ```cmd
   python --version
   ```

### Paso 2: Compilar el Ejecutable

#### Opción A: Automática (Recomendado)
```cmd
cd C:\Pedidos\Pedidos-main\sieslo\AlmacenDesktop
compilar_exe.bat
```

#### Opción B: Manual
```cmd
cd C:\Pedidos\Pedidos-main\sieslo\AlmacenDesktop

REM Instalar PyInstaller
python -m pip install pyinstaller --upgrade

REM Compilar
pyinstaller build_exe.spec
```

### Paso 3: Ubicar el Ejecutable
```
dist\AlmacenDesktop\AlmacenDesktop.exe
```

---

## 📦 Estructura después de Compilar

```
AlmacenDesktop/
├── dist/
│   └── AlmacenDesktop/
│       ├── AlmacenDesktop.exe  ← EJECUTABLE FINAL
│       ├── assets/
│       ├── _internal/
│       └── ...
├── build/          (Archivos temporales)
├── .env.example
└── ...
```

---

## ✅ Instalar en Otros PCs

### Opción 1: Carpeta Portátil
1. Copiar toda la carpeta `dist\AlmacenDesktop\` a una USB o carpeta compartida
2. En el otro PC, copiar a `C:\Program Files\AlmacenDesktop`
3. Crear acceso directo del .exe en Desktop
4. **Listo** - Ejecutar el .exe

### Opción 2: Instalador (Avanzado)
Si necesitas un instalador (.msi), usar:
```cmd
pip install pyinstaller-innosetup
```

---

## 🔧 Configuración Personalizada

### Cambiar Icono
1. Agregar archivo `almacen.ico` a la carpeta `assets/`
2. En `build_exe.spec`, cambiar:
   ```python
   icon='assets/almacen.ico'
   ```
3. Recompilar

### Agregar Consola de Debug
En `build_exe.spec`, cambiar:
```python
console=True,  # Mostrará ventana de consola para ver errores
```

### Cambiar Nombre
En `build_exe.spec`, cambiar:
```python
name='MiNombre',  # El .exe se llamará MiNombre.exe
```

---

## 🐛 Troubleshooting

### Error: "Python no está instalado"
```
❌ ERROR: Python no está instalado o no está en PATH
```
**Solución**:
- Reinstalar Python
- Marcar "Add Python to PATH"
- Reiniciar Windows

### Error: "PyInstaller no encontrado"
```
ModuleNotFoundError: No module named 'pyinstaller'
```
**Solución**:
```cmd
python -m pip install pyinstaller --upgrade
```

### El .exe no inicia
**Verificar**:
1. Windows Defender lo bloqueó → Agregar excepción
2. Falta archivo `.env` → Copiar `.env.example` a `.env`
3. Falta carpeta `assets/` → Verificar `dist\AlmacenDesktop\assets\`

### Error "conexión rechazada"
```
No se pudo conectar. Usando modo local.
```
**Verificar**:
- Django está corriendo: `python manage.py runserver`
- URL en `.env` es correcta
- Firewall permite conexión a puerto 8000

---

## 📊 Información Técnica

### Tamaño del Ejecutable
- **Sin optimización**: ~250 MB (carpeta completa)
- **Optimizado**: ~80 MB (removiendo imports innecesarios)

### Configuración Recomendada
```python
# En build_exe.spec para producción
console=False,           # Sin consola
strip=True,              # Remover símbolos debug
upx=True,                # Comprimir binarios
win_no_prefer_redirects=True,  # Mejor compatibilidad
```

---

## 🎯 Próximos Pasos

1. **Compilar**: `compilar_exe.bat`
2. **Probar**: `dist\AlmacenDesktop\AlmacenDesktop.exe`
3. **Distribuir**: Compartir carpeta `dist\AlmacenDesktop\`
4. **Automatizar**: Crear script de deployment automático

---

## 📞 Soporte

| Problema | Solución |
|----------|----------|
| ¿Cómo hago actualizaciones? | Recompilar y distribuir nueva versión |
| ¿Puedo usar en Mac? | Sí, pero compilar en Mac con `compilar_exe.sh` |
| ¿Puedo hacer instalador MSI? | Sí, usar InnoSetup + PyInstaller |

**Versión**: 1.0
**Fecha**: 2026-03-11
**Estado**: ✅ LISTO PARA COMPILAR
