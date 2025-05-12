import sys

input_file = 'datadump.json'
output_file = 'datadump_utf8.json'
# Prueba con estas codificaciones. 'latin-1' es una candidata común.
# Otras podrían ser 'windows-1252'.
original_encoding = 'latin-1' # O 'windows-1252'

try:
    with open(input_file, 'r', encoding=original_encoding, errors='surrogateescape') as f_in:
        content = f_in.read()

    with open(output_file, 'w', encoding='utf-8') as f_out:
        f_out.write(content)

    print(f"Archivo '{input_file}' convertido de '{original_encoding}' a UTF-8 y guardado como '{output_file}'")
    print("Intenta usar 'datadump_utf8.json' con el comando loaddata.")

except FileNotFoundError:
    print(f"Error: El archivo '{input_file}' no fue encontrado.")
except UnicodeDecodeError as e:
    print(f"Error de decodificación al leer con '{original_encoding}': {e}")
    print(f"Es posible que la codificación original ('{original_encoding}') no sea la correcta para tu archivo.")
    print("Podrías probar con otras como 'windows-1252' o revisar el contenido del archivo.")
except Exception as e:
    print(f"Ocurrió un error inesperado: {e}")