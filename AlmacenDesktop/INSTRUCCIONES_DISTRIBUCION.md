# Distribución de AlmacenDesktop.exe

## Archivo Compilado

📦 **Ubicación**: `dist/AlmacenDesktop.exe`

📊 **Características**:
- **Tamaño**: 33 MB (archivo único, completamente empaquetado)
- **Tipo**: Executable Windows (.exe)
- **Requisitos**: Windows 7+ (64-bit)
- **Sin dependencias**: No necesita instalación, funciona directamente

---

## Pasos para Distribuir

### 1. Copiar el archivo

```bash
# Opción A: Directamente
copiar dist/AlmacenDesktop.exe → USB o servidor de distribución

# Opción B: Crear carpeta con documentación
mkdir AlmacenDesktop_v1.0
cp dist/AlmacenDesktop.exe AlmacenDesktop_v1.0/
cp README.md AlmacenDesktop_v1.0/
zip -r AlmacenDesktop_v1.0.zip AlmacenDesktop_v1.0/
```

### 2. Instalar en máquina del almacén

**Opción A: Ejecutable directo**
1. Copiar `AlmacenDesktop.exe` a: `C:\Program Files\AlmacenDesktop\` (crear carpeta)
2. Crear acceso directo en escritorio (click derecho → Enviar a → Escritorio)
3. Doble-click para ejecutar

**Opción B: Instalador (opcional)**
- El .exe puede ejecutarse desde cualquier ubicación
- Recomendación: Carpeta sin permisos de escritura por error del usuario

### 3. Configuración Inicial

Cuando se abre por primera vez:

1. **Configuración** → **Red y Sincronización**
2. **URL API**: Ingresa `https://tu-dominio.com/api`
3. Click **💾 Guardar**
4. Click **🧪 Probar Conexión** → Debe marcar verde ✓

### 4. Primer Uso

1. **Configuración** → **Red y Sincronización**
2. Click **🔄 Sincronizar ahora** → Descarga catálogo de productos
3. Espera a que termine (log mostrará ✓)
4. **← Menú** → **POS** → ¡Listo para vender!

---

## Verificación

```bash
# En Windows, verificar que el .exe es válido:
certutil -hashfile dist/AlmacenDesktop.exe SHA256

# Debería ejecutarse sin errores:
dist/AlmacenDesktop.exe
```

---

## Si algo falla

### Problema: No inicia el .exe

**Solución 1:**
```bash
# Instalar Visual C++ Redistributable
# Descargar de: https://support.microsoft.com/es-es/help/2977003
```

**Solución 2:**
- Copiar a una carpeta sin espacios ni caracteres especiales
- Ej: `C:\Almacen\` en lugar de `C:\Program Files\AlmacenDesktop\`

### Problema: Error "Windows protected your PC"

**Solución:**
- Click "More info"
- Click "Run anyway"
- (Es porque el .exe es nuevo y Windows es precavido)

### Problema: "Cannot connect to server"

**Solución:**
1. Verificar que la URL sea correcta en Configuración
2. Probar ping: `ping tu-dominio.com`
3. Revisar firewall/proxy del almacén

---

## Compilar Nuevamente

Si necesitas actualizar el .exe:

### Windows:
```bash
cd AlmacenDesktop
compilar.bat
```

### Linux/Mac:
```bash
cd AlmacenDesktop
python build_exe.py
```

---

## Control de Versiones

Mantener registro de versiones:

```
AlmacenDesktop_v1.0.0.exe  (Marzo 2026) - Primera versión
AlmacenDesktop_v1.1.0.exe  (Marzo 2026) - Conf editable
AlmacenDesktop_v2.0.0.exe  (Futuro) - Multi almacén
```

---

## Deployment Automático

Si tienes múltiples almacenes, puedes:

1. **Hosting en servidor**: `https://cdn.midominio.com/descargas/AlmacenDesktop.exe`
2. **Crear launcher** que automáticamente descarga versión nueva
3. **Notificar** a usuarios cuando hay update

---

## Archivos Generados

```
AlmacenDesktop/
├── dist/
│   └── AlmacenDesktop.exe  ← ESTE ES EL ARCHIVO A DISTRIBUIR
├── build/                  (temporal, puede eliminarse)
├── AlmacenDesktop.spec     (temporal, puede eliminarse)
├── README.md               (instrucciones de uso)
└── compilar.bat            (para recompilar)
```

---

## Checklist Pre-Distribución

- [ ] Compilar el .exe exitosamente
- [ ] Verificar que el archivo pesa ~33 MB
- [ ] Probar en máquina Windows limpia
- [ ] Verificar URL del servidor es correcta
- [ ] Probar sincronización de productos
- [ ] Probar una venta de prueba
- [ ] Verificar cierre de caja
- [ ] Documentar versión y fecha

---

**Última actualización**: Marzo 2026
**Versión actual**: 1.1.0
**Estado**: ✓ Listo para producción
