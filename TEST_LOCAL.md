# Testing Local de BodegaDesktop

## ✅ Setup Completado

### 1. Django Running
```
http://127.0.0.1:8000
```
Django está corriendo en background.

### 2. Usuario de Test Creado
```
Username: test_bodega
Password: test123456
```

### 3. Dominio Configurado
```
127.0.0.1 → Empresa Test
localhost → Empresa Test
```

### 4. API Endpoints Funcionan
```
✅ POST http://127.0.0.1:8000/api/token/
   → Retorna JWT token

✅ GET http://127.0.0.1:8000/api/bodega/pedidos/
   → Retorna lista de pedidos (vacía por ahora)
```

---

## 🧪 Testing de BodegaDesktop.exe

### Opción 1: Ejecutar desde Python (desarrollo)
```bash
cd C:\Pedidos\Pedidos-main\sieslo\BodegaDesktop
python main.py
```

### Opción 2: Ejecutar el .exe compilado
```bash
C:\Pedidos\Pedidos-main\sieslo\BodegaDesktop\dist\BodegaDesktop.exe
```

---

## 📝 Pasos de Testing

### 1. Abrir BodegaDesktop
```
Click en BodegaDesktop.exe
```

### 2. Configurar Servidor
```
Click "⚙️ Configurar Servidor"
URL: http://127.0.0.1:8000/api
Click "Guardar"
```

### 3. Probar Conexión
```
Click "🧪 Probar Conexión"
Debe mostrar: ✅ Servidor respondiendo correctamente
```

### 4. Login
```
Usuario: test_bodega
Contraseña: test123456
Click "INGRESAR"
```

### 5. Ver Pedidos
```
Si hay pedidos, aparecerán en la lista
Si no hay, la lista está vacía pero el API funciona ✅
```

---

## 🔍 Verificar Endpoints con curl

### Token
```bash
curl -X POST http://127.0.0.1:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"test_bodega","password":"test123456"}' | python -m json.tool
```

### Pedidos (sin token)
```bash
curl http://127.0.0.1:8000/api/bodega/pedidos/
# Debe retornar: []  (vacío)
```

### Pedidos (con token)
```bash
TOKEN="<access_token_aqui>"

curl -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8000/api/bodega/pedidos/
# Debe retornar: [] (funciona)
```

---

## ✅ Que está funcionando:

- ✅ API REST endpoint `/api/bodega/pedidos/`
- ✅ JWT authentication
- ✅ TenantMiddleware con 127.0.0.1
- ✅ Usuario test_bodega creado
- ✅ BodegaDesktop.exe compilado
- ✅ URL normalization en BodegaDesktop (auto-arregla URLs)
- ✅ Manejo de focus/dialogs sin errors

---

## 🚀 Próximos Pasos (Testing Real):

1. Crear pedidos de test para la Empresa Test
2. Testear escaneo en BodegaDesktop
3. Testear despacho completo
4. Hacer push a Hostinger y cambiar URL

---

**Estado**: ✅ API REST funcionando en localhost
**Credenciales test**: test_bodega / test123456
**URL local**: http://127.0.0.1:8000/api
