import os

# Nombre del archivo final optimizado
ARCHIVO_SALIDA = "proyecto_completo.md"

# Carpetas pesadas o innecesarias que vamos a ignorar
CARPETAS_IGNORADAS = {'venv', '.git', '__pycache__', 'media', 'static', 'node_modules', 'migrations'}
# Archivos que sí nos interesan para entender tu aplicación
EXTENSIONES_PERMITIDAS = {'.py', '.html', '.css', '.js', '.json', '.md'}

print("Consolidando archivos... Por favor, espera.")

with open(ARCHIVO_SALIDA, 'w', encoding='utf-8') as f_out:
    for raiz, directorios, archivos in os.walk('.'):
        # Filtrar carpetas para no entrar en las ignoradas
        directorios[:] = [d for d in directorios if d not in CARPETAS_IGNORADAS]
        
        for archivo in archivos:
            _, ext = os.path.splitext(archivo)
            if ext in EXTENSIONES_PERMITIDAS:
                ruta_completa = os.path.join(raiz, archivo)
                ruta_relativa = os.path.relpath(ruta_completa, '.')
                
                # Evitar leer el propio script o el archivo de salida
                if ruta_relativa == ARCHIVO_SALIDA or archivo == 'consolidar.py':
                    continue
                    
                try:
                    # Leemos el código ignorando errores de caracteres extraños
                    with open(ruta_completa, 'r', encoding='utf-8', errors='ignore') as f_in:
                        contenido = f_in.read()
                    
                    # Detectar lenguaje para el bloque de código Markdown
                    lenguaje = ext.replace('.', '')
                    if lenguaje == 'py': lenguaje = 'python'
                    elif lenguaje == 'js': lenguaje = 'javascript'
                    
                    # Escribir la estructura en el Markdown unificado
                    f_out.write(f"# Archivo: {ruta_relativa}\n")
                    f_out.write(f"```{lenguaje}\n")
                    f_out.write(contenido)
                    f_out.write("\n```\n\n")
                except Exception as e:
                    pass

print(f"¡Listo! Se ha creado el archivo: {ARCHIVO_SALIDA}")