# Quick Start - BodegaDesktop

## 🚀 Empezar Rápido

### Opción 1: Usar Ejecutable Compilado (Recomendado)
```
dist/BodegaDesktop.exe
```
- Copiar a `C:\Bodega\BodegaDesktop.exe`
- Click en el ejecutable
- Configurar servidor URL
- ¡Listo!

### Opción 2: Ejecutar desde Python
```bash
cd BodegaDesktop
pip install -r requirements.txt
python main.py
```

### Opción 3: Compilar Nuevo Ejecutable
```bash
cd BodegaDesktop
compilar.bat              # En Windows
# o
python build_exe.py
```

## ⚙️ Configuración Inicial

1. **Login Screen**
   - Click "⚙️ Configurar Servidor"
   - Ingresa: `https://pedidoslouisferry.online/api`
   - Click "🧪 Probar Conexión" → debe salir verde ✅

2. **Autenticación**
   - Usuario: (tu usuario Django)
   - Contraseña: (tu contraseña Django)
   - Click "INGRESAR"

3. **Ya está**
   - Panel de pedidos carga automáticamente
   - Presiona "🚀 Despachar" en un pedido

## 📦 Escanear Pedido

1. En el panel de despacho, coloca el escáner sobre el campo "ESCANEAR"
2. Escanea cada código de barras
3. Verás feedback visual por cada scan
4. Cuando termines, click "✅ Enviar Despacho"
5. Se abre el PDF del comprobante en Chrome automáticamente

## 📋 Workflow Completo

```
Login → Lista Pedidos → Seleccionar Pedido
  ↓
Panel Despacho (escanear items)
  ↓
Botón "Enviar Despacho"
  ↓
PDF se abre en navegador → Imprimir
  ↓
Volver a lista de pedidos
```

## 🐛 Problemas Comunes

| Problema | Solución |
|----------|----------|
| "Sin conexión" | Verifica URL en Configurar Servidor |
| "Credenciales inválidas" | Intenta login en web primero |
| "Escáner no funciona" | Coloca el escáner sobre el campo de entrada |
| App muy lenta | Cierra otros programas, verifica red |

## 📞 Soporte

- **Bug reports**: Contactar IT
- **Cambio de servidor**: Usar "⚙️ Configurar Servidor"
- **Feedback**: Enviar a administración

---

**Made with ❤️ for Bodega**
