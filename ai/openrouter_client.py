"""
CC Subs Pro - OpenRouter AI Client
Integra modelos como google/gemini-2.0-flash-001 para:
1. Corrección inteligente de mayúsculas (eliminar artefactos de CapCut y colocar mayúsculas iniciales).
2. Detección e inserción de signos de interrogación completos (¿?).
3. Regla estricta de puntuación: 0 comas (,), 0 puntos (.), 0 dos puntos (:), 0 puntos suspensivos (...).
4. Selección curada de palabras destacadas de alto impacto cada ~3.5 a 4.5 segundos.
"""

import os
import json
import re
import urllib.request
import urllib.error
import logging
from typing import List, Dict, Any, Optional, Tuple

from core.text_utils import clean_subtitle_text, convert_spanish_numbers_to_digits, sanitize_highlight_phrase

logger = logging.getLogger('CCSubsPro.OpenRouter')

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "google/gemini-2.5-flash"
FALLBACK_MODELS = ["google/gemini-2.5-flash", "google/gemini-2.5-flash-lite"]

SYSTEM_PROMPT_SUBTITLES_BASE = """Eres un editor de video y lingüista profesional especializado en subtítulos virales de alta retención para redes sociales (Reels, TikTok, YouTube Shorts).

Tu tarea es recibir la lista cronológica de segmentos de subtítulos de un video (con sus IDs, marcas de tiempo y texto transcrito por CapCut) y realizar dos labores simultáneas:

1. CORRECCIÓN ORTOGRÁFICA Y DE ESTILO (texto general):
   a) CORREGIR MAYÚSCULAS ERRÓNEAS Y SOSTENIDAS (OBLIGATORIA): CapCut suele poner mayúsculas aleatorias o palabras completas en mayúsculas en medio de oraciones (por ejemplo: "que VA a ser", "para tu Pueblo", "LA gente", "ESTÁN", "MÁS", "que DEBERÍAS", "y por qué Evita"). NUNCA dejes palabras en MAYÚSCULAS sostenidas salvo acrónimos oficiales (ADN, UCI, TDAH, OMS). Todas las demás palabras en medio de oraciones DEBEN ir en minúscula natural.
   b) MAYÚSCULAS INICIALES: Coloca mayúscula inicial al comienzo de cada oración, locución o pregunta.
   c) SIGNOS DE INTERROGACIÓN: Detecta preguntas directas o retóricas del orador y añade los signos de interrogación completos de apertura (¿) y de cierre (?). El signo de apertura (¿) DEBE ir pegado a la primera palabra de la pregunta con mayúscula inicial (ejemplo: "¿Tienes este") y el signo de cierre (?) DEBE ir pegado a la última palabra de la pregunta (ejemplo: "problema?"). JAMÁS coloques un signo ¿ o ? solo en un segmento separado ni separado por espacios. Asegúrate de cerrar siempre cada pregunta con su signo de cierre (?).
   {punctuation_rule}
   e) REGLA CRÍTICA DE INTEGRIDAD Y LONGITUD DE SEGMENTO (ESTRICTA Y OBLIGATORIA):
      - CADA segmento individual de entrada representa un bloque de audio muy breve de CapCut (típicamente 1 a 3 palabras, máximo 18 caracteres).
      - NUNCA concatenes ni fusiones varios segmentos en oraciones largas.
      - Cada entrada en "corrected_subtitles" DEBE mantener exactamente las mismas palabras del segmento original correspondiente a su "index".
      - Por ejemplo, si el segmento 0 es "por", su corrección DEBE ser "Por" o "por". JAMÁS coloques una oración completa como "¿Por qué el alcohol puede provocarte" en el segmento 0. Si el segmento 1 es "qué el alcohol", su texto es "qué el alcohol" o "¿Qué el alcohol". NUNCA adelantes palabras de segmentos futuros.
      - Mantén siempre la longitud corta (1 a 3 palabras por segmento).
   f) CONVERSIÓN DE NÚMEROS A DÍGITOS Y PORCENTAJES (OBLIGATORIA):
      - Si el segmento contiene números hablados expresados en letras (por ejemplo: "treinta y nueve", "ochenta", "ciento cincuenta", "dos mil", "veinte"), conviértelos SIEMPRE a su representación numérica en dígitos (por ejemplo: "39", "80", "150", "2000", "20").
      - Si se menciona un porcentaje (por ejemplo "siete por ciento", "7 por ciento", "diez por ciento", "7 por 100", "por cien"), represéntalo SIEMPRE con el símbolo de porcentaje (por ejemplo: "7%", "10%", "100%"). JAMÁS escribas "7 por 100" ni "7 por ciento".
      - No conviertas artículos indefinidos comunes como "un paciente" o "una persona" a números con dígitos.

2. SELECCIÓN DE PALABRAS DESTACADAS (Highlights):
   a) Selecciona palabras o frases breves (de 1 a 2 palabras máximo, NUNCA más de 12 caracteres) de alto impacto visual o emocional.
   b) CADENCIA RÍTMICA Y FRECUENTE (MUY IMPORTANTE):
      - Debe aparecer una palabra o frase destacada CADA ~3 A 4 SEGUNDOS (aproximadamente cada 2 a 3 subtítulos).
      - En un video o reel de 60 segundos DEBEN HABER entre 15 a 18 palabras destacadas bien distribuidas a lo largo de todo el video. No dejes huecos largos sin palabras destacadas.
      - Resalta con dinamismo: conceptos clave, números importantes, términos anatómicos o médicos, verbos de impacto o palabras de advertencia/dolor.
   c) NO REPETIR EN EXCESO: Varía las palabras destacadas a lo largo del video. Busca conceptos variados, verbos de acción, números o ideas fuerza.
   d) CADA FRASE DESTACADA DEBE COINCIDIR EXACTAMENTE con palabras pronunciadas en ese segmento para poder sincronizarlas al microsegundo con la voz.
   e) CLASIFICACIÓN DE TONO (OBLIGATORIA): Si la palabra destaca un dolor, molestia, problema, enfermedad, falla o síntoma negativo (como "error", "dolor", "aprieta", "enrojecimiento"), clasifícala con "tone": "negative". En caso contrario, "tone": "normal".
   f) PALABRAS DESTACADAS SOLAS (OPCIONAL, 2 A 3 VECES MÁXIMO POR VIDEO): Si una palabra o frase breve es extremadamente contundente o una orden/llamado clave que funciona con fuerza por sí sola sin necesidad de texto acompañante (por ejemplo 'necesitas esto'), puedes marcarla con "is_solo": true. En cualquier otro caso, omite el campo o pon "is_solo": false.
   g) REGLA ESTRICTA DE UNIDAD SEMÁNTICA Y COHERENCIA GRAMATICAL (OBLIGATORIA):
      - NUNCA selecciones como frase destacada una combinación de palabras que pertenezcan a sintagmas u oraciones distintas.
      - NUNCA unas un sustantivo o adjetivo con el verbo que inicia la acción siguiente (por ejemplo: JAMÁS destaques "lingual forman", JAMÁS "bebé come", JAMÁS "paciente siente", JAMÁS "niño llora").
      - NUNCA unas una palabra destacada con conectores, preposiciones o conjunciones siguientes (por ejemplo: JAMÁS "dolor cuando", JAMÁS "ojos porque", JAMÁS "problema que", JAMÁS "pie para", JAMÁS "cirugía si").
      - Las frases destacadas de 2 palabras SÓLO se permiten si forman un concepto unitario inseparable de longitud corta (ejemplos válidos: "suelo pélvico", "alta demanda", "primeros meses").
      - Si la palabra clave va seguida de un verbo o conector, destaca ÚNICAMENTE la palabra clave aislada (ejemplo: destaca sólo "lingual", NO "lingual forman"; destaca sólo "dolor", NO "dolor cuando").
   h) PROHIBICIÓN ESTRICTA DE CONECTORES Y CONJUNCIONES:
      - JAMÁS destaques conectores ni conjunciones solas o al inicio de una frase (por ejemplo: JAMÁS destaques "porque", "pero", "cuando", "como", "que", "si", "donde", "mientras", "pues", "ya", "sino").
      - Una palabra como "porque" NUNCA debe ser una palabra destacada bajo ninguna circunstancia.
   i) PROHIBICIÓN TOTAL DE "NO", ARTÍCULOS O PALABRAS CORTAS VACÍAS:
      - JAMÁS destaques la palabra "no". La palabra "no" NUNCA es un highlight (aunque exprese negación o advertencia). Si una frase dice "no improvisas", destaca ÚNICAMENTE "improvisas", JAMÁS "no".
      - JAMÁS destaques palabras de 1 o 2 letras ("no", "el", "la", "o", "y", "un", "de", "en", "se", "al", "es", "ya", "ni", "si").
      - JAMÁS destaques palabras vacías como "así", "asi", "bien", "muy", "tan", "más", "cada".
      - Destaca ÚNICAMENTE palabras de verdadero peso semántico y valor informativo (conceptos clave, términos médicos, sustantivos o verbos de impacto).
   j) LONGITUD MÁXIMA Y MARGEN SEGURO (ESTRICTA Y OBLIGATORIA):
      - Cada palabra destacada DEBE ser concisa: 1 palabra (preferido) o máximo 2 palabras muy breves, y NUNCA superar los 12 caracteres en total (por ejemplo: "beneficio", "lactancia", "suelo pélvico").
      - NUNCA selecciones frases largas que rompan los márgenes laterales del video (por ejemplo: JAMÁS destaques "ningún beneficio", JAMÁS "diagnósticos prenatales", JAMÁS "no aportan ningún beneficio").
      - PROHIBICIÓN TOTAL DE CUANTIFICADORES Y DETERMINANTES: JAMÁS incluyas "ningún", "ninguna", "mucho", "poco", "tan", "más", "cada", "todo" en la palabra destacada. Si la frase dice "no aportan ningún beneficio", destaca ÚNICAMENTE "beneficio", JAMÁS "ningún beneficio" ni "no aportan".

DEBES RESPONDER EXCLUSIVAMENTE UN OBJETO JSON VÁLIDO CON LA SIGUIENTE ESTRUCTURA:
{{
  "corrected_subtitles": [
    {{
      "index": 0,
      "text": "{example_text}"
    }}
  ],
  "highlights": [
    {{
      "target_index": 1,
      "phrase": "palabra o frase destacada",
      "tone": "normal",
      "is_solo": false
    }}
  ]
}}
"""

PUNCTUATION_RULE_NO = """d) REGLA ESTRICTA DE PUNTUACIÓN (OBLIGATORIA):
      - NUNCA coloques comas (,).
      - NUNCA coloques puntos (.).
      - NUNCA coloques dos puntos (:).
      - NUNCA coloques puntos suspensivos (...).
      - Las comas, puntos y dos puntos quedan estrictamente prohibidos en todos los subtítulos."""

PUNCTUATION_RULE_YES = """d) REGLA DE PUNTUACIÓN (PUNTOS Y COMAS ACTIVADOS):
      - Coloca puntos (.) y comas (,) con precisión según las reglas gramaticales estándar en español.
      - Coloca coma (,) para pausas naturales, vocativos, enumeraciones y cláusulas coordinadas/subordinadas.
      - Coloca punto (.) al finalizar oraciones completas y afirmaciones declarativas.
      - Las comas y puntos DEBEN ir adheridos al final de la palabra correspondiente (ejemplo: "desarrollo.", "crecer,").
      - NUNCA coloques dos puntos (:) ni puntos suspensivos (...)."""

def get_system_prompt_subtitles(keep_punctuation: bool = False) -> str:
    rule = PUNCTUATION_RULE_YES if keep_punctuation else PUNCTUATION_RULE_NO
    example = "Texto corregido con puntos y comas naturales, con mayúscula inicial" if keep_punctuation else "Texto corregido sin comas ni puntos con mayúscula inicial si inicia frase"
    return SYSTEM_PROMPT_SUBTITLES_BASE.format(punctuation_rule=rule, example_text=example)

SYSTEM_PROMPT_SUBTITLES = get_system_prompt_subtitles(keep_punctuation=False)

SYSTEM_PROMPT_GRAMMAR_CHECK = """Eres un corrector ortográfico y lingüista profesional de español (normativa RAE) especializado en subtítulos de video.

Los editores humanos a menudo editan manualmente los subtítulos pero olvidan colocar tildes o cometen errores tipográficos u ortográficos (por ejemplo: "clinica" en vez de "clínica", "mas" en vez de "más", "asi" o "haci" en vez de "así", "despues" en vez de "después", "a veses" o "habeses" en vez de "a veces", "esposicion" en vez de "exposición", "tambien", "rapido", "diagnostico", "nutricion", "llevo" vs "llevó", "esta" vs "está", "te" vs "té", "tu" vs "tú", "si" vs "sí", "que/como/cuando/donde/cual/por que" en preguntas directas o indirectas).

REGLAS ESTRICTAS:
1. Analiza la secuencia cronológica de segmentos teniendo en cuenta el CONTEXTO COMPLETO de la oración (incluso si la oración continúa entre segmentos consecutivos o pistas superpuestas) para determinar tildes diacríticas y tiempos verbales con precisión.
2. Corrige ÚNICAMENTE:
   - Tildes faltantes o sobrantes (agudas, graves, esdrújulas y tildes diacríticas: más/mas, tú/tu, él/el, sí/si, sé/se, té/te, mí/mi, aún/aun, está/esta, qué/que, cómo/como, cuándo/cuando, dónde/donde, cuál/cual, quién/quien, por qué/porque, verbos en pretérito/futuro/condicional).
   - Palabras mal escritas o con errores de ortografía / tipeo (b/v, c/s/z, g/j, ll/y, r/rr, h omitida o sobrante, letras cambiadas, omitidas o duplicadas, errores frecuentes de edición).
   - Signos de interrogación/exclamación claramente mal pegados o sin su apertura ¿ o cierre ? correspondiente.
3. PROHIBICIONES IMPORTANTES:
   - JAMÁS cambies palabras válidas por sinónimos ni reescribas o parafrasees el guion.
   - JAMÁS fusiones, dividas o elimines segmentos, ni cambies el orden de las palabras.
   - JAMÁS alteres, unas, separes ni reescribas anglicismos, marcas comerciales, nombres de clínicas o nombres propios válidos ya escritos por el editor (por ejemplo: "Gala Unique", "Clínica Gala", "barefoot", "Dentok", "Alharilla", "Abde", "Emilia", "Cuidus", "Visedo", "Enfocavisión", "botox", "lifting", "peeling", "spray", "clip", "reels", "tiktok"). Si una palabra o expresión parece un nombre propio o marca (como "Gala Unique"), respétala exactamente tal como aparece y NO la corrijas salvo una tilde inequívoca en español (ej. "Alvaro" -> "Álvaro").
   - RESPETA EL ESTILO DE MAYÚSCULAS DEL SEGMENTO: Si el segmento de entrada tiene "is_upper": true (TODO EN MAYÚSCULAS), devuelve "corrected_text" también TODO EN MAYÚSCULAS manteniendo las tildes (ejemplo: "ATENCION MEDICA" -> "ATENCIÓN MÉDICA"). Si el texto original está en minúsculas por continuación de frase, mantenlo en minúsculas salvo nombres propios o inicio tras punto/¿/¡.
   - RESPETA los saltos de línea ("\\n") si el texto original tiene dos líneas.
   - {punct_instruction}

FORMATO DE RESPUESTA:
Responde EXCLUSIVAMENTE un objeto JSON válido con las correcciones encontradas (incluye ÚNICAMENTE los índices que realmente necesitan corrección; si todo está bien, devuelve una lista vacía):
{{
  "corrections": [
    {{
      "index": 3,
      "corrected_text": "texto corregido exacto",
      "reason": "explicación breve (ej. 'Falta tilde en clínica')"
    }}
  ]
}}
"""


def get_system_prompt_grammar(keep_punctuation: bool = False) -> str:
    if keep_punctuation:
        punct_instr = "Mantén puntos (.) y comas (,) donde correspondan gramaticalmente, sin inventar dos puntos ni puntos suspensivos."
    else:
        punct_instr = "Mantén los puntos o comas solo si el segmento original ya los tenía; NO agregues comas ni puntos nuevos si el original no tenía."
    return SYSTEM_PROMPT_GRAMMAR_CHECK.format(punct_instruction=punct_instr)


class OpenRouterClient:
    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL):
        self.api_key = api_key or os.environ.get('OPENROUTER_API_KEY') or ""
        self.model = model

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def test_connection(self) -> Tuple[bool, str]:
        """Prueba la conexión con OpenRouter enviando un prompt mínimo."""
        if not self.is_configured():
            return False, "No se ha configurado ninguna API Key de OpenRouter."

        candidates = [self.model]
        for fb in FALLBACK_MODELS:
            if fb not in candidates:
                candidates.append(fb)

        last_error = ""
        for m in candidates:
            payload = {
                "model": m,
                "messages": [
                    {"role": "user", "content": "Responde solo 'OK'"}
                ],
                "max_tokens": 10
            }

            try:
                req = urllib.request.Request(
                    OPENROUTER_API_URL,
                    data=json.dumps(payload).encode('utf-8'),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key.strip()}",
                        "HTTP-Referer": "https://ccsubspro.local",
                        "X-Title": "CC Subs Pro"
                    },
                    method='POST'
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    if 'choices' in data and len(data['choices']) > 0:
                        self.model = m
                        return True, f"Conexión exitosa con OpenRouter ({m.split('/')[-1]})."
            except urllib.error.HTTPError as e:
                err_body = e.read().decode('utf-8', errors='replace')
                try:
                    err_json = json.loads(err_body)
                    msg = err_json.get('error', {}).get('message', str(e))
                except Exception:
                    msg = err_body[:200]
                last_error = f"Error HTTP {e.code}: {msg}"
            except Exception as e:
                last_error = f"Error de conexión: {str(e)}"

        return False, last_error

    def process_subtitles(self, segments: List[Dict[str, Any]], keep_punctuation: bool = False) -> Optional[Dict[str, Any]]:
        """
        Envía los segmentos originales transcritos a Gemini Flash en OpenRouter.
        Retorna un dict con:
          - 'corrected_subtitles': lista de dicts {index, text}
          - 'highlights': lista de dicts {target_index, phrase}
        """
        if not self.is_configured():
            logger.warning("OpenRouter API key not configured.")
            return None

        # Preparar datos resumidos para enviar al modelo
        items_payload = []
        for s in segments:
            idx = s.get('index', 0)
            st_s = s.get('start', 0) / 1e6
            et_s = s.get('end', 0) / 1e6
            txt = clean_subtitle_text(s.get('text', ''), keep_punctuation=keep_punctuation)
            items_payload.append({
                "index": idx,
                "start": f"{st_s:.2f}s",
                "end": f"{et_s:.2f}s",
                "text": txt
            })

        user_content = f"Procesa los siguientes {len(items_payload)} segmentos de subtítulos transcritos por CapCut:\n\n{json.dumps(items_payload, ensure_ascii=False, indent=2)}"

        candidates = [self.model]
        for fb in FALLBACK_MODELS:
            if fb not in candidates:
                candidates.append(fb)

        sys_prompt = get_system_prompt_subtitles(keep_punctuation=keep_punctuation)

        for m in candidates:
            payload = {
                "model": m,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_content}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.2
            }

            try:
                req = urllib.request.Request(
                    OPENROUTER_API_URL,
                    data=json.dumps(payload).encode('utf-8'),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key.strip()}",
                        "HTTP-Referer": "https://ccsubspro.local",
                        "X-Title": "CC Subs Pro"
                    },
                    method='POST'
                )
                with urllib.request.urlopen(req, timeout=45) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    raw_text = data['choices'][0]['message']['content'].strip()
                    if raw_text.startswith("```"):
                        import re
                        raw_text = re.sub(r'^```(?:json)?\s*', '', raw_text)
                        raw_text = re.sub(r'\s*```$', '', raw_text)
                    parsed = json.loads(raw_text)

                    # Sanitizar respuestas para garantizar puntuación según preset y números en dígitos
                    corrected = parsed.get('corrected_subtitles', [])
                    for item in corrected:
                        item['text'] = convert_spanish_numbers_to_digits(clean_subtitle_text(item.get('text', ''), keep_punctuation=keep_punctuation))

                    highlights = parsed.get('highlights', [])
                    for hl in highlights:
                        hl['phrase'] = convert_spanish_numbers_to_digits(sanitize_highlight_phrase(hl.get('phrase', '')))
                        hl['tone'] = 'negative' if hl.get('tone') == 'negative' else 'normal'
                        hl['is_solo'] = bool(hl.get('is_solo', False))

                    self.model = m
                    return {
                        "corrected_subtitles": corrected,
                        "highlights": highlights
                    }
            except Exception as e:
                logger.warning(f"Intento fallido con modelo {m}: {e}")

        logger.error("Todos los modelos candidatos de OpenRouter fallaron.")
        return None

    def check_grammar(
        self,
        segments: List[Dict[str, Any]],
        keep_punctuation: bool = False,
        batch_size: int = 75
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Envía los subtítulos a OpenRouter para revisar únicamente tildes,
        ortografía y palabras mal escritas manteniendo la estructura original.

        Retorna:
          - Lista de dicts {index, corrected_text, reason} con los cambios propuestos
            (vacía `[]` si no hay errores).
          - `None` si OpenRouter no está configurado o falló la conexión.
        """
        if not self.is_configured():
            logger.warning("OpenRouter API key not configured.")
            return None

        if not segments:
            return []

        sys_prompt = get_system_prompt_grammar(keep_punctuation=keep_punctuation)
        candidates = [self.model]
        for fb in FALLBACK_MODELS:
            if fb not in candidates:
                candidates.append(fb)

        all_corrections: List[Dict[str, Any]] = []
        n = len(segments)
        step = max(10, int(batch_size))

        for start_i in range(0, n, step):
            end_i = min(n, start_i + step)
            batch_segs = segments[start_i:end_i]
            ctx_before = [s.get('text', '') for s in segments[max(0, start_i - 4):start_i]]
            ctx_after = [s.get('text', '') for s in segments[end_i:min(n, end_i + 4)]]

            items_payload = []
            for s in batch_segs:
                txt = s.get('text', '')
                is_upper = bool(txt) and not any(c.islower() for c in txt) and any(c.isalpha() for c in txt)
                items_payload.append({
                    "index": s.get('index', 0),
                    "start": f"{s.get('start', 0) / 1e6:.2f}s",
                    "text": txt,
                    "is_upper": is_upper
                })

            user_payload = {
                "context_before": ctx_before,
                "segments_to_check": items_payload,
                "context_after": ctx_after
            }
            user_content = (
                "Revisa las tildes y ortografía de 'segments_to_check' usando 'context_before' "
                "y 'context_after' solo como referencia contextual. Devuelve en 'corrections' "
                "únicamente los elementos de 'segments_to_check' que requieran corrección:\n\n"
                + json.dumps(user_payload, ensure_ascii=False, indent=2)
            )

            batch_parsed = None
            for m in candidates:
                payload = {
                    "model": m,
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.1
                }
                try:
                    req = urllib.request.Request(
                        OPENROUTER_API_URL,
                        data=json.dumps(payload).encode('utf-8'),
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {self.api_key.strip()}",
                            "HTTP-Referer": "https://ccsubspro.local",
                            "X-Title": "CC Subs Pro"
                        },
                        method='POST'
                    )
                    with urllib.request.urlopen(req, timeout=45) as resp:
                        data = json.loads(resp.read().decode('utf-8'))
                        raw_text = data['choices'][0]['message']['content'].strip()
                        if raw_text.startswith("```"):
                            raw_text = re.sub(r'^```(?:json)?\s*', '', raw_text)
                            raw_text = re.sub(r'\s*```$', '', raw_text)
                        parsed = json.loads(raw_text)
                        self.model = m
                        batch_parsed = parsed.get('corrections', [])
                        if not isinstance(batch_parsed, list):
                            batch_parsed = []
                        break
                except Exception as e:
                    logger.warning(f"Intento fallido en check_grammar con modelo {m}: {e}")

            if batch_parsed is None:
                logger.error("Todos los modelos candidatos de OpenRouter fallaron en check_grammar.")
                return None

            valid_indices = {s.get('index') for s in batch_segs}
            for item in batch_parsed:
                if not isinstance(item, dict):
                    continue
                idx_val = item.get('index')
                if idx_val not in valid_indices:
                    continue
                corr_txt = str(item.get('corrected_text', '')).strip()
                reason = str(item.get('reason', '')).strip()
                if corr_txt:
                    all_corrections.append({
                        "index": idx_val,
                        "corrected_text": corr_txt,
                        "reason": reason or "Corrección ortográfica / tilde"
                    })

        return all_corrections
