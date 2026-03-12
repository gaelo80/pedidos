# BodegaDesktop - App de Despacho

Aplicación standalone para gestionar despachos de pedidos desde bodega, con soporte para escáner de código de barras (HID).

## Características

- ✅ **Login seguro**: Autenticación JWT contra servidor Django
- ✅ **Lista de pedidos**: Filtrable por cliente y estado
- ✅ **Escaneo de códigos**: Interfaz optimizada para escáner HID (teclado)
- ✅ **Despacho parcial**: Permite envíos incompletos
- ✅ **Comprobante PDF**: Abre automáticamente en navegador
- ✅ **Configuración editable**: URL del servidor sin reiniciar app
- ✅ **BD local**: SQLite para caché y configuración

## Instalación

### Windows

1. **Descargar ejecutable**
   ```
   dist/BodegaDesktop.exe
   ```

2. **Colocar en carpeta** (sin espacios):
   ```
   C:\Bodega\BodegaDesktop.exe
   ```

3. **Primera ejecución**
   - Click en "⚙️ Configurar Servidor"
   - Ingresa URL: `https://tu-dominio.com/api`
   - Click en "🧪 Probar Conexión" (debe mostrar verde ✅)
   - Ingresa usuario/contraseña Django
   - Click "INGRESAR"

4. **Listo**: Ya puedes usar la app

## Uso

### 1. Login
- **Usuario**: tu usuario Django
- **Contraseña**: tu contraseña Django
- Botón "Probar Conexión" para verificar URL del servidor

### 2. Listar Pedidos
- Muestra pedidos en estado `APROBADO_ADMIN`, `PROCESANDO`, `LISTO_BODEGA_DIRECTO`
- Filtra por cliente y estado
- Click "🚀 Despachar" para abrir panel de escaneo

### 3. Escanear Pedido
```
┌─────────────────────────────────────┐
│ Pedido #42 - Cliente X              │
├─────────────────────────────────────┤
│ 📦 ESCANEAR: [_________________]    │
│                                     │
│ Items:                Progreso:     │
│ REF-001 Azul          30/45 ▓▓▓▓░  │
│ T28: 2/3              Últimos       │
│ T30: 3/3              ✅ REF-001    │
│                                     │
│ [✅ Enviar] [⚠️ Incompleto] [❌Cancel] │
└─────────────────────────────────────┘
```

**Flujo:**
1. Coloca el escáner de códigos sobre el campo "ESCANEAR"
2. Escanea el código de barras (aparecerá feedback)
3. Repite hasta tener la cantidad requerida
4. Click "✅ Enviar Despacho" para confirmar

### 4. Comprobante
- Después de enviar, se abre automáticamente el PDF en navegador
- Puedes imprimir desde allí
- El comprobante queda guardado en el servidor

## Configuración

### Cambiar Servidor
1. Click "Configuración"
2. Tab "Red y Sincronización"
3. Modifica URL
4. Click "💾 Guardar"

### Probar Conexión
- Click "🧪 Probar Conexión"
- Debe mostrar ✅ verde

## Requisitos

- **Windows**: 7+ (64-bit)
- **Red**: Conexión a Internet / Intranet
- **Escáner**: Compatible con HID (emula teclado)
- **Servidor**: Django running + API de bodega configurada

## Troubleshooting

### "Sin conexión"
1. Verifica URL en "Configurar Servidor"
2. Prueba en navegador: `https://tu-dominio.com/api/token/`
3. Verifica firewall/proxy

### "Credenciales inválidas"
1. Verifica usuario y contraseña
2. Intenta login en web
3. Verifica permisos en Django

### "El escáner no funciona"
1. Verifica que sea escáner USB (HID/teclado)
2. Prueba en Bloc de Notas: escanea código (debe aparecer texto)
3. Coloca el escáner sobre el campo de entrada en la app

## Archivos

```
BodegaDesktop/
├── main.py                # Entry point
├── database.py            # SQLite local
├── requirements.txt       # Dependencias Python
├── build_exe.py          # Script PyInstaller
├── compilar.bat          # Batch para compilar
├── dist/
│   └── BodegaDesktop.exe # Ejecutable final (distribuir este)
├── modulos/
│   ├── pedidos.py        # Lista de pedidos
│   ├── despacho.py       # Interfaz de despacho
│   └── configuracion.py  # Configuración
└── assets/
    └── (íconos PNG)
```

## Compilar de Cero

```bash
cd BodegaDesktop
pip install -r requirements.txt
pip install pyinstaller
python build_exe.py
```

O en Windows:
```bash
compilar.bat
```

Resultado: `dist/BodegaDesktop.exe`

## Soporte

Contactar a administración IT para:
- Problemas de conexión
- Cambio de URL del servidor
- Actualizaciones de versión
- Reseteo de configuración

---

**Versión**: 0.1.0
**Última actualización**: Marzo 2026
**Estado**: ✅ En Producción
