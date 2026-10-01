# CC Subs Pro - Estilizador Nativo de Subtítulos para CapCut (Windows)

CC Subs Pro es una herramienta local de alta precisión que estiliza automáticamente los subtítulos generados por la función nativa de CapCut dentro de `draft_content.json`.

> **100% Nativo, Rápido y Editable**: No quema subtítulos, no renderiza video ni superpone imágenes. Modifica los materiales de texto y pistas de CapCut preservando la edición nativa por doble clic, textos, marcas acústicas, animaciones y audio.

---

## 🚀 Cómo Instalar en Otra PC con Windows (1 Clic)

1. **Copia o descomprime la carpeta `CC Subs Pro`** en cualquier ubicación de la nueva PC (por ejemplo, en Documentos o Escritorio).
2. **Haz doble clic en:**
   ```
   Instalar_CC_Subs_Pro.bat
   ```
   *El instalador automático:*
   - Verifica que Python esté disponible (si no lo está, te ayuda a descargarlo).
   - Instala y registra automáticamente en Windows **las 9 fuentes tipográficas** de todos los doctores sin pedir permisos de administrador.
   - Configura los efectos de animación y sonidos de click en la caché nativa de CapCut.
   - Crea un acceso directo llamado **CC Subs Pro** directamente en tu **Escritorio**.

3. **¡Listo!** Ya puedes abrir CC Subs Pro haciendo doble clic en el acceso directo de tu Escritorio o en `Iniciar_CC_Subs_Pro.bat`.

---

## 🩺 Presets de Doctores Integrados

| Doctor / Doctora | Pista Superior (Base) | Pista Inferior (Highlights) | Efectos y Sonido |
| :--- | :--- | :--- | :--- |
| **Dr. Gerardo** | `Aloevera Display Regular` (Blanco, Tam 10) | `Behind The Nineties` (Turquesa `#2F9FA3`, Tam 21) | Entrada deslizante izquierda + Click fx |
| **Dra. Gala** | `Helvetica Regular` (Blanco, Tam 8) | `Things` (Blanco grande, Tam 19.25) | Click fx sincronizado |
| **Dra. Laura Pediatra** | `Josefin Sans Regular` (Blanco, Tam 9) | `Josefin Sans SemiBold` (Celeste `#8ED1FC`, Tam 11, MAYÚSCULAS) | Click fx sincronizado |
| **Dra. Alharilla** | `Raleway Medium` (Blanco, Tam 10) | `Bebas Neue Regular` (Verde menta `#83C4BE`, Tam 19.32, MAYÚSCULAS) | Animación Proyección 2 + Click fx |
| **Dr. Jose Podólogo** | `Aglatia` (Blanco, Tam 10) | `Bluemun` (Oro `#D4AF37`, Tam 18) | Animación suave + Click fx |
| **🦶 Deditos Barefoot** | `Lilita One` (Blanco, Tam 9.5) | `Lilita One` (Naranja `#FF7A00`, Tam 11) | Mini zoom + Click fx |
| **🩺 Emilia** | `Neue Helvena Semibold` (Blanco, Tam 10) | `Karelle DEMO` (Amarillo `#FFDC6D`, Tam 12) | Mini zoom + Stickers CapCut sincronizados + Click fx |

---

## 📋 Flujo de Trabajo en 3 Pasos

1. **En CapCut**:
   - Abre tu proyecto de video y genera los subtítulos nativos:
     **Texto** $\rightarrow$ **Subtítulos automáticos** $\rightarrow$ **Crear**.
2. **En CC Subs Pro**:
   - Abre CC Subs Pro desde tu Escritorio.
   - Selecciona el proyecto en la lista desplegable (se detectan automáticamente).
   - Selecciona el Doctor/a deseado (**Dr. Gerardo**, **Dra. Gala**, **Dra. Laura Pediatra**, **Dra. Alharilla**).
   - Haz clic en **★ ESTILIZAR SUBTÍTULOS AHORA**.
3. **En CapCut**:
   - Vuelve a CapCut, sal a la pantalla principal de proyectos y vuelve a entrar en el proyecto para ver el timeline con doble capa, tipografías y clicks sincronizados.

---

## 🔒 Privacidad y Estándares de Calidad

- **100% Privado y Offline por defecto**: Utiliza un algoritmo de retención y bloqueo acústico local. No requiere ninguna clave de API ni conexión a internet para funcionar.
- **Regla Estricta de Cero Puntuación**: Elimina automáticamente todas las comas (`,`), puntos (`.`), dos puntos (`:`) y puntos suspensivos (`...`) de todos los textos.
- **Bloqueo Acústico 1 a 1**: Los subtítulos respetan estrictamente los timestamps fonéticos de CapCut; jamás se adelantan palabras ni se congelan frases pasadas.
- **Sincronización de Click**: Cada sonido de click coincide al microsegundo exacto con la entrada de la palabra clave.
- **Respaldo Automático**: Siempre genera una copia de seguridad `draft_content.backup.json` antes de realizar modificaciones.


---

### Opción B: Línea de Comandos (CLI)

```bash
# 1. Aplicar Doble Capa (Arriba/Abajo) en todo el video
python cc_subs_pro.py dual-style -p "letra gerardo"

# 2. Listar proyectos y subtítulos
python cc_subs_pro.py list -p "letra gerardo"

# 3. Inspeccionar un proyecto o subtítulo
python cc_subs_pro.py inspect -p "letra gerardo" -i 0

# 4. Probar en un solo subtítulo
python cc_subs_pro.py style-one -p "letra gerardo" -i 0

# 5. Aplicar estilo normal simple
python cc_subs_pro.py style-all -p "letra gerardo"

# 6. Highlights simples en línea única con IA o Heurístico
python cc_subs_pro.py highlight -p "letra gerardo" --provider heuristic
```

---

## Archivos de Configuración de Estilos
En la carpeta `styles/`:
- `styles/default.json`: Fuente `Aloevera Display Regular`, tamaño, color `#FFFFFF` y sombra.
- `styles/highlight.json`: Fuente `Behind The Nineties Medium Italic`, color `#2F9FA3`, tamaño, sombra y animación.

Puedes modificar estos JSON en cualquier momento para personalizar colores o fuentes.
