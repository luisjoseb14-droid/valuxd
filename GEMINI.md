# CC Subs Pro - Reglas del Proyecto y Guía para Antigravity / Asistentes

## REGLA ESTRICTA DE PUNTUACIÓN EN SUBTÍTULOS (OBLIGATORIA)
Al generar, curar, planificar, procesar o modificar subtítulos para CapCut en cualquier proyecto:
1. **NUNCA colocar comas (,), puntos (.) ni dos puntos (:)**.
2. **NUNCA colocar puntos suspensivos (...)**.
3. **Todo texto de subtítulo** (tanto en capas superiores como en capas inferiores destacadas) DEBE pasar siempre por la función de saneamiento `clean_subtitle_text()` de `core.text_utils`.
4. Si se elaboran planes curados manuales en formato JSON o scripts `build_*_plan.py`, asegurarse al 100% de que ningún string de texto contenga comas, puntos o dos puntos.
5. Los signos de interrogación (`¿?`) y exclamación (`¡!`) están permitidos si aportan expresión, pero comas, puntos y dos puntos quedan estrictamente prohibidos.

## REGLA ESTRICTA DE SINCRONIZACIÓN Y TIMESTAMPS
CapCut genera los subtítulos con marcas de tiempo acústicas alineadas a la voz humana mediante IA (forzado fonético).
1. **NUNCA ADELANTAR PALABRAS NO HABLADAS**: En segmentos regulares, no anticipar palabras de frases futuras.
2. **FORMATO CLÁSICO DOBLE CAPA (GENERAL ARRIBA Y DESTACADA ABAJO)**:
   - Al coincidir una palabra o frase destacada (highlight cada ~3 a 5 segundos), la **Capa Superior (General)** debe mantenerse visible / estirada durante todo el segmento del highlight (`curr_end`).
   - La **Capa Inferior (Destacada)** entra en el microsegundo exacto de la palabra clave (`hl_start`) y finaliza junto con la superior (`curr_end`).
   - Si el segmento destacado no tiene prefijo propio, el segmento anterior de la capa general se extiende/estira hasta `curr_end` para evitar cualquier hueco o línea vacía en la pista superior.
3. **EXTRACCIÓN ACÚSTICA DE HIGHLIGHTS**: Las palabras destacadas de la capa inferior deben iniciar en el microsegundo exacto en que se pronuncia la palabra clave, usando la función `find_phrase_timing()` de `core.text_utils` basada en la metadata `words` de CapCut.
4. **SINCRONIZACIÓN DE AUDIO CLICK**: Los efectos de sonido de click deben coincidir exactamente con el microsegundo de inicio del texto destacado (`start_us` del highlight).

## ARQUITECTURA DE SUBTÍTULOS
- **Formato Doble Capa (Presets: Gerardo, Gala)**:
  - Capa superior: texto base corto (1 a 3 palabras por línea, máximo 16 a 18 caracteres), manteniendo la continuidad visual sin huecos.
  - Capa inferior: palabras destacadas espaciadas cada ~3 a 5 segundos con su respectivo estilo, animación y efecto de sonido si el preset lo define.
- **Sincronización Atómica**:
  - Al guardar, sincronizar siempre el `draft_content.json` raíz y todos los sub-timelines en `Timelines/<UUID>/draft_content.json` vía `CapCutProject.save()`.
- **Integridad de Sombras CapCut**:
  - Mantener la estructura nativa CapCut (`fill.content.solid.color` y `shadows[].diffuse` normalizado) para evitar textos invisibles.
