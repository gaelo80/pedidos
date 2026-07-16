# Sincronización de Catálogo para Etiquetas

Descarga automáticamente, desde el servidor, un Excel con `Referencia, Nombre,
Color, Talla, Codigo de Barras` de todos los productos activos, y lo guarda
siempre en la misma ruta local para que el programa de impresión de
etiquetas (Bartender, NiceLabel, etc.) lo use como fuente de datos.

## 1. Instalar dependencias

Necesitas Python instalado en el computador de oficina. Luego, en esta carpeta:

```
pip install -r requirements.txt
```

## 2. Configurar

Ejecuta el script una vez:

```
python sincronizar_catalogo.py
```

La primera vez no encontrará `config.json` y te va a crear uno de ejemplo
en esta misma carpeta. Ábrelo y completa:

```json
{
    "servidor_url": "https://pedidoslouisferry.online",
    "usuario": "tu_usuario_del_sistema",
    "password": "tu_contraseña",
    "carpeta_destino": "C:\\Users\\TU_USUARIO\\Documents\\CatalogoEtiquetas",
    "nombre_archivo": "catalogo_etiquetas.xlsx",
    "verificar_ssl": true
}
```

- `servidor_url`: el dominio real de la empresa cuyo catálogo quieres
  sincronizar (cada empresa tiene su propio dominio, así que este archivo
  solo sincroniza el catálogo de una empresa a la vez).
- `usuario` / `password`: cualquier usuario válido del sistema con permiso
  para ver productos.
- `carpeta_destino`: dónde se guarda el Excel. Puede ser una carpeta en
  Documentos, Escritorio, o cualquier ruta en C:\ — la que tu programa de
  etiquetas vaya a usar como fuente de datos.

La contraseña queda guardada en texto plano en este archivo. Asegúrate de
que solo el computador de oficina (de confianza) tenga acceso a esta carpeta.

## 3. Probar manualmente

```
python sincronizar_catalogo.py
```

Si todo sale bien verás `OK: catálogo actualizado en ...` y el archivo Excel
aparecerá en la carpeta configurada. Si algo falla, el detalle queda
registrado en `sincronizacion.log` (en esta misma carpeta).

## 4. Automatizar con el Programador de Tareas de Windows

Para que el archivo se actualice solo, sin que nadie tenga que acordarse:

1. Abre **Programador de tareas** (busca "Task Scheduler" en el menú de inicio).
2. Clic derecho sobre "Biblioteca del Programador de tareas" → **Crear tarea básica...**
3. Nombre: `Sincronizar Catálogo Etiquetas`.
4. Desencadenador: elige **Diariamente**, y en las opciones avanzadas marca
   "Repetir la tarea cada" → **5 minutos**, durante "1 día" (o el intervalo
   que prefieras).
5. Acción: **Iniciar un programa**.
   - Programa/script: la ruta completa a tu `python.exe` (o `pythonw.exe`
     para que no aparezca ninguna ventana), por ejemplo:
     `C:\Users\TU_USUARIO\AppData\Local\Programs\Python\Python312\pythonw.exe`
   - Agregar argumentos: la ruta completa a este script, entre comillas:
     `"C:\Proyectos\pedidos\pedidos\SincronizacionEtiquetas\sincronizar_catalogo.py"`
   - Iniciar en: la ruta de esta carpeta:
     `C:\Proyectos\pedidos\pedidos\SincronizacionEtiquetas`
6. Termina el asistente. Puedes hacer clic derecho sobre la tarea creada →
   **Ejecutar** para probarla de inmediato sin esperar los 5 minutos.

Desde ese momento el Excel se va a mantener actualizado solo, cada vez que
se creen productos nuevos en el sistema.
