import re
import difflib
from typing import List, Tuple, Optional, Dict, Any


# Basic Spanish number maps
SPANISH_UNITS = {
    'cero': 0, 'uno': 1, 'dos': 2, 'tres': 3, 'cuatro': 4,
    'cinco': 5, 'seis': 6, 'siete': 7, 'ocho': 8, 'nueve': 9,
    'diez': 10, 'once': 11, 'doce': 12, 'trece': 13, 'catorce': 14,
    'quince': 15, 'dieciséis': 16, 'dieciseis': 16, 'diecisiete': 17,
    'dieciocho': 18, 'diecinueve': 19,
    'veinte': 20, 'veintiuno': 21, 'veintiún': 21, 'veintiun': 21,
    'veintiuna': 21, 'veintidós': 22, 'veintidos': 22,
    'veintitrés': 23, 'veintitres': 23, 'veinticuatro': 24,
    'veinticinco': 25, 'veintiséis': 26, 'veintiseis': 26,
    'veintisiete': 27, 'veintiocho': 28, 'veintinueve': 29
}

SPANISH_TENS = {
    'treinta': 30, 'cuarenta': 40, 'cincuenta': 50,
    'sesenta': 60, 'setenta': 70, 'ochenta': 80, 'noventa': 90
}

SPANISH_HUNDREDS = {
    'cien': 100, 'ciento': 100,
    'doscientos': 200, 'doscientas': 200,
    'trescientos': 300, 'trescientas': 300,
    'cuatrocientos': 400, 'cuatrocientas': 400,
    'quinientos': 500, 'quinientas': 500,
    'seiscientos': 600, 'seiscientas': 600,
    'setecientos': 700, 'setecientas': 700,
    'ochocientos': 800, 'ochocientas': 800,
    'novecientos': 900, 'novecientas': 900
}

SPANISH_UNIT_COMPOUNDS = {
    'un': 1, 'una': 1, 'uno': 1, 'dos': 2, 'tres': 3, 'cuatro': 4,
    'cinco': 5, 'seis': 6, 'siete': 7, 'ocho': 8, 'nueve': 9
}

def _parse_base_number(tokens: List[str], start_idx: int) -> Optional[Tuple[int, int]]:
    n = len(tokens)
    if start_idx >= n:
        return None
    t0 = tokens[start_idx].lower()

    # Standalone 'un' / 'una' are indefinite articles, NOT numbers,
    # unless followed by 'mil', 'millón', 'millon', 'millones'
    if t0 in ('un', 'una'):
        if start_idx + 1 < n and tokens[start_idx + 1].lower() in ('mil', 'millón', 'millon', 'millones'):
            return 1, 1
        return None

    if t0 in SPANISH_TENS:
        val = SPANISH_TENS[t0]
        consumed = 1
        if start_idx + 2 < n and tokens[start_idx + 1].lower() == 'y' and tokens[start_idx + 2].lower() in SPANISH_UNIT_COMPOUNDS:
            val += SPANISH_UNIT_COMPOUNDS[tokens[start_idx + 2].lower()]
            consumed = 3
        return val, consumed

    if t0 in SPANISH_HUNDREDS:
        val = SPANISH_HUNDREDS[t0]
        consumed = 1
        if start_idx + 1 < n:
            t1 = tokens[start_idx + 1].lower()
            if t1 in SPANISH_TENS:
                val += SPANISH_TENS[t1]
                consumed = 2
                if start_idx + 3 < n and tokens[start_idx + 2].lower() == 'y' and tokens[start_idx + 3].lower() in SPANISH_UNIT_COMPOUNDS:
                    val += SPANISH_UNIT_COMPOUNDS[tokens[start_idx + 3].lower()]
                    consumed = 4
            elif t1 in SPANISH_UNITS:
                val += SPANISH_UNITS[t1]
                consumed = 2
            elif t1 in ('un', 'una', 'uno'):
                val += 1
                consumed = 2
        return val, consumed

    if t0 in SPANISH_UNITS:
        return SPANISH_UNITS[t0], 1

    return None

def parse_spanish_number_tokens(tokens: List[str], start_idx: int) -> Optional[Tuple[int, int]]:
    """
    Parses a Spanish number sequence starting at tokens[start_idx].
    Returns (numeric_value, num_tokens_consumed) or None if no valid number.
    Does NOT match standalone 'un'/'una' as a number to preserve indefinite articles.
    """
    n = len(tokens)
    if start_idx >= n:
        return None
    t0 = tokens[start_idx].lower()

    if t0 == 'mil':
        val = 1000
        consumed = 1
        if start_idx + 1 < n:
            res2 = parse_spanish_number_tokens(tokens, start_idx + 1)
            if res2 and res2[0] < 1000:
                val += res2[0]
                consumed += res2[1]
        return val, consumed

    base = _parse_base_number(tokens, start_idx)
    if not base:
        return None
    val, consumed = base

    # Check millions (e.g. 'un millón', 'dos millones quinientos mil')
    if start_idx + consumed < n and tokens[start_idx + consumed].lower() in ('millón', 'millon', 'millones'):
        val *= 1000000
        consumed += 1
        if start_idx + consumed < n:
            res2 = parse_spanish_number_tokens(tokens, start_idx + consumed)
            if res2 and res2[0] < 1000000:
                val += res2[0]
                consumed += res2[1]
        return val, consumed

    # Check thousands (e.g. 'dos mil', 'veinte mil quinientos')
    if start_idx + consumed < n and tokens[start_idx + consumed].lower() == 'mil':
        val *= 1000
        consumed += 1
        if start_idx + consumed < n:
            res2 = parse_spanish_number_tokens(tokens, start_idx + consumed)
            if res2 and res2[0] < 1000:
                val += res2[0]
                consumed += res2[1]
        return val, consumed

    return val, consumed

def convert_spanish_numbers_to_digits(text: str) -> str:
    """
    Converts Spanish numbers written in words to digits within a text string.
    e.g. 'treinta y nueve' -> '39', 'ochenta' -> '80', 'ciento cincuenta' -> '150'.
    Preserves surrounding punctuation (such as ¿?, ¡!, quotes).
    Preserves standalone indefinite articles ('un paciente', 'una persona').
    """
    if not text:
        return ""
    words = text.split()
    out_words = []
    i = 0
    while i < len(words):
        w_raw = words[i]
        lead_m = re.match(r'^([¿¡"\'\(\[\{]*)(.*?)([?!\'"\)\]\}]*)$', w_raw)
        lead_punct, _, _ = lead_m.groups() if lead_m else ("", w_raw, "")

        # Prepare tokens for lookahead
        test_tokens = []
        for w in words[i:]:
            m = re.match(r'^[¿¡"\'\(\[\{]*(.*?)[?!\'"\)\]\}]*$', w)
            test_tokens.append(m.group(1) if m else w)

        parse_res = parse_spanish_number_tokens(test_tokens, 0)
        if parse_res:
            num_val, consumed = parse_res
            last_w = words[i + consumed - 1]
            last_m = re.match(r'^[¿¡"\'\(\[\{]*(.*?)([?!\'"\)\]\}]*)$', last_w)
            last_trail = last_m.group(2) if last_m else ""

            out_words.append(f"{lead_punct}{num_val}{last_trail}")
            i += consumed
        else:
            out_words.append(w_raw)
            i += 1

    res = " ".join(out_words)
    # Convert percentages: 'X por ciento', 'X por cien', 'X por 100', 'X porciento', 'X x 100', 'X x ciento' -> 'X%'
    pct_pattern = r'\b(\d+)\s*(?:por\s+ciento|por\s+cien|por\s+100|porciento|x\s+100|x\s+ciento)([?!\'\"\)\]\}]*)'
    res = re.sub(pct_pattern, r'\1%\2', res, flags=re.IGNORECASE)
    return res


SPANISH_ACRONYMS = {
    'ADN', 'ARN', 'UCI', 'TDAH', 'TAC', 'OMS', 'VIH', 'SIDA', 'COVID', 'CPR', 'RCP',
    'IA', 'AI', 'DGT', 'RNM', 'RMN', 'PET', 'ECG', 'EKG', 'EEG', 'IV', 'IM', 'ONU',
    'URL', 'PDF', 'VIP', 'LED', 'OK', 'TOC', 'TEA', 'IRPF', 'IVA', 'DNI', 'NIE',
    'BOE', 'BOP', 'BOM', 'RAE', 'EEUU', 'USA', 'UE', 'OTAN', 'FIFA', 'UEFA', 'ACB',
    'NBA', 'ATP', 'WTA', 'F1', 'TV', 'HD', '4K', 'GPS', 'SIM', 'SMS', 'APP', 'SEO',
    'SEM', 'CRM', 'B2B', 'B2C', 'CEO', 'CFO', 'CTO', 'CMO', 'RRHH', 'RSC', 'PYME',
    'PYMES', 'ONG', 'ONGD', 'ITV', 'MIR', 'EIR', 'PIR', 'FIR', 'BIR', 'QIR', 'RFIR'
}

COMMON_LOWERCASE_WORDS = {
    # Common verbs that CapCut or STT capitalizes erratically
    'evita', 'evitan', 'evitar', 'evitó', 'evitaron', 'evitando',
    'deberías', 'deberias', 'debes', 'debe', 'deben', 'deber', 'debemos', 'debió',
    'puedes', 'puede', 'pueden', 'podemos', 'poder', 'podría', 'podrías',
    'tienes', 'tiene', 'tienen', 'tenemos', 'tener', 'tenía', 'tuvo',
    'haces', 'hace', 'hacen', 'hacemos', 'hacer', 'hizo', 'hecho',
    'dices', 'dice', 'dicen', 'decimos', 'decir', 'dijo', 'dicho',
    'estás', 'estás', 'está', 'esta', 'están', 'estan', 'estamos', 'estar', 'estaba', 'estuvo',
    'eres', 'es', 'somos', 'son', 'ser', 'era', 'fue', 'sido', 'sea', 'sean',
    'vas', 'va', 'van', 'vamos', 'ir', 'iba', 'fue', 'vaya',
    'vienes', 'viene', 'vienen', 'venir', 'vino',
    'sabes', 'sabe', 'saben', 'saber', 'supo',
    'sigue', 'siguen', 'seguir', 'siguió',
    'mira', 'miras', 'mirar', 've', 'ves', 'ver', 'vemos',
    'ayuda', 'ayudan', 'ayudar', 'sirve', 'sirven', 'servir',
    'necesitas', 'necesita', 'necesitan', 'necesitar',
    'provoca', 'provocan', 'provocar', 'causa', 'causan', 'causar',
    'produce', 'producen', 'producir', 'genera', 'generan', 'generar',
    'ocurre', 'ocurren', 'ocurrir', 'pasa', 'pasan', 'pasar',
    'funciona', 'funcionan', 'funcionar', 'aporta', 'aportan', 'aportar',
    # Common nouns & adjectives that CapCut mistakenly capitalizes
    'pueblo', 'pueblos', 'gente', 'persona', 'personas', 'bebé', 'bebe', 'bebés', 'bebes',
    'niño', 'niña', 'niños', 'niñas', 'hijo', 'hija', 'hijos', 'hijas',
    'paciente', 'pacientes', 'mamá', 'mama', 'papá', 'papa', 'padres', 'madres',
    'problema', 'problemas', 'beneficio', 'beneficios', 'cuidado', 'cuidados',
    'salud', 'vida', 'cuerpo', 'cabeza', 'ojo', 'ojos', 'oído', 'oidos', 'boca', 'diente', 'dientes',
    'pie', 'pies', 'mano', 'manos', 'piel', 'sangre', 'pecho', 'espalda', 'cuello',
    'caso', 'casos', 'tiempo', 'forma', 'manera', 'momento', 'modo', 'tipo', 'tipos',
    'error', 'errores', 'dolor', 'dolores', 'molestia', 'molestias', 'síntoma', 'sintomas',
    'consejo', 'consejos', 'truco', 'trucos', 'paso', 'pasos', 'día', 'dias', 'mes', 'meses',
    'semana', 'semanas', 'año', 'años', 'vez', 'veces',
    'grande', 'grandes', 'pequeño', 'pequeña', 'pequeños', 'pequeñas',
    'nuevo', 'nueva', 'nuevos', 'nuevas', 'bueno', 'buena', 'buenos', 'buenas',
    'malo', 'mala', 'malos', 'malas', 'mejor', 'mejores', 'peor', 'peores',
    'importante', 'importantes', 'fundamental', 'fundamentales', 'clave',
    'normal', 'natural', 'común', 'comunes', 'frecuente', 'frecuentes',
    'seguro', 'segura', 'cierto', 'cierta', 'falso', 'falsa',
    # Grammatical particles & connectors
    'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas',
    'de', 'del', 'al', 'a', 'en', 'con', 'por', 'para', 'sin', 'sobre', 'tras',
    'hacia', 'hasta', 'desde', 'contra', 'entre',
    'y', 'e', 'ni', 'o', 'u', 'que', 'pero', 'aunque', 'porque', 'como', 'cuando', 'donde', 'si',
    'mi', 'tu', 'su', 'mis', 'tus', 'sus', 'nuestro', 'nuestra',
    'me', 'te', 'se', 'nos', 'le', 'les', 'lo',
    'muy', 'tan', 'más', 'mas', 'menos', 'ya', 'no', 'sí', 'si', 'tampoco', 'también', 'tambien',
    'este', 'esta', 'estos', 'estas', 'esto', 'ese', 'esa', 'esos', 'esas', 'eso'
}

def clean_spanish_casing(text: str, is_sentence_start: bool = True) -> str:
    """
    Cleans Spanish casing in subtitle text:
    - Lowercases random ALL-CAPS words (e.g. 'DEBERÍAS' -> 'deberías' / 'Deberías', 'ESTÁN' -> 'están' / 'Están')
      while strictly preserving real Spanish acronyms (e.g. 'ADN', 'UCI', 'TDAH', 'TAC', 'OMS', 'VIH', 'COVID').
    - Fixes random title-casing of common words mid-sentence (e.g. 'y por qué Evita' -> 'y por qué evita',
      'para tu Pueblo' -> 'para tu pueblo').
    - Preserves proper sentence and question initial capitalization.
    """
    if not text:
        return ""
    words = text.split()
    if not words:
        return ""

    out = []
    for idx, w in enumerate(words):
        m = re.match(r'^([¿¡"\'\(\[\{]*)(.*?)([?!,.;:\'"\)\]\}]*)$', w)
        if not m:
            out.append(w)
            continue
        lead, core, trail = m.groups()
        if not core:
            out.append(w)
            continue

        is_word_sent_start = False
        if idx == 0:
            is_word_sent_start = is_sentence_start
        elif out:
            prev_w = out[-1]
            if any(p in prev_w for p in ('?', '!', '.')):
                is_word_sent_start = True

        if lead and ('¿' in lead or '¡' in lead):
            is_word_sent_start = True

        # Check ALL CAPS (length >= 2)
        if core.isupper() and len(core) >= 2:
            if core in SPANISH_ACRONYMS:
                out.append(f"{lead}{core}{trail}")
            elif is_word_sent_start:
                out.append(f"{lead}{core.capitalize()}{trail}")
            else:
                out.append(f"{lead}{core.lower()}{trail}")
            continue

        # Check single letter uppercase ('Y', 'O', 'A', 'E', 'U') mid-sentence
        if core.isupper() and len(core) == 1:
            if is_word_sent_start:
                out.append(f"{lead}{core}{trail}")
            else:
                out.append(f"{lead}{core.lower()}{trail}")
            continue

        # Check Titlecase words mid-sentence
        if core[0].isupper() and not is_word_sent_start:
            if core.lower() in COMMON_LOWERCASE_WORDS:
                out.append(f"{lead}{core.lower()}{trail}")
            else:
                out.append(f"{lead}{core}{trail}")
            continue

        out.append(f"{lead}{core}{trail}")

    return " ".join(out)


def clean_subtitle_text(text: str, is_sentence_start: bool = True) -> str:
    """
    Cleans subtitle text by removing commas (,), periods (.), and colons (:),
    including ellipses (...), and normalizing whitespace.
    
    Also automatically corrects known CapCut speech-to-text uppercase glitches
    and erratic casing using clean_spanish_casing.
    
    Preserves question marks (¿?), exclamation marks (¡!), hyphens, quotes,
    letters, accents, and numbers.
    """
    if not text:
        return ""
    
    # Clean Spanish casing first (so periods/colons accurately signal sentence boundaries)
    cleaned = clean_spanish_casing(str(text), is_sentence_start=is_sentence_start)
    
    # Remove commas, periods, colons
    cleaned = re.sub(r'[,.:]+', '', cleaned)
    
    # Normalize multiple whitespace characters into a single space and strip
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned

def find_phrase_timing(
    segment_start_us: int,
    segment_duration_us: int,
    words_data: any,
    full_text: str,
    target_phrase: str
) -> tuple:
    """
    Returns (start_us, end_us) for target_phrase within a subtitle segment.
    Uses CapCut's acoustic words metadata down to the millisecond if available.
    Otherwise calculates proportional character timing within segment boundaries.
    """
    clean_full = clean_subtitle_text(full_text)
    clean_target = clean_subtitle_text(target_phrase)
    seg_end_us = segment_start_us + segment_duration_us

    if not clean_target or clean_target.lower() not in clean_full.lower():
        return segment_start_us, seg_end_us

    # 1. Match tokens using CapCut's acoustic words metadata
    if words_data and isinstance(words_data, dict):
        tokens = words_data.get('text', [])
        start_times = words_data.get('start_time', [])
        end_times = words_data.get('end_time', [])

        if tokens and start_times and end_times and len(tokens) == len(start_times) == len(end_times):
            non_empty = []
            for t, st, et in zip(tokens, start_times, end_times):
                c_tok = clean_subtitle_text(t)
                if c_tok:
                    non_empty.append((c_tok, st, et))

            target_words = clean_target.split()
            num_target = len(target_words)

            for i in range(len(non_empty) - num_target + 1):
                window = [non_empty[i + j][0].lower() for j in range(num_target)]
                if window == [w.lower() for w in target_words]:
                    match_start_ms = non_empty[i][1]
                    match_end_ms = non_empty[i + num_target - 1][2]

                    if match_end_ms > 10000 and match_end_ms <= segment_duration_us:
                        start_us = segment_start_us + int(match_start_ms)
                        end_us = segment_start_us + int(match_end_ms)
                    else:
                        start_us = segment_start_us + int(match_start_ms * 1000)
                        end_us = segment_start_us + int(match_end_ms * 1000)

                    # Clamp to segment bounds
                    start_us = max(segment_start_us, min(start_us, seg_end_us))
                    end_us = max(start_us + 100000, min(end_us, seg_end_us))
                    return start_us, end_us

    # 2. Fallback: Proportional character timing
    char_idx = clean_full.lower().find(clean_target.lower())
    total_len = max(len(clean_full), 1)

    start_ratio = char_idx / total_len
    end_ratio = (char_idx + len(clean_target)) / total_len

    start_us = segment_start_us + int(segment_duration_us * start_ratio)
    end_us = segment_start_us + int(segment_duration_us * end_ratio)
    end_us = max(start_us + 100000, min(end_us, seg_end_us))
    return start_us, end_us


# Trailing words that must NEVER end a multi-word highlight phrase (verbs, connectors, prepositions, conjunctions)
INVALID_TRAILING_HIGHLIGHT_WORDS = {
    # Common verbs in present, past, conditional, subjunctive, infinitive, gerund
    'forman', 'forma', 'formar', 'formó', 'formaron', 'formará', 'formarán', 'formando',
    'tiene', 'tienen', 'tener', 'tienes', 'tengo', 'tenemos', 'tenía', 'tenían', 'tuvo', 'tuvieron',
    'hace', 'hacen', 'hacer', 'hago', 'hacemos', 'hizo', 'hicieron', 'hecho', 'haciendo',
    'dice', 'dicen', 'decir', 'digo', 'decimos', 'dijo', 'dijeron', 'diciendo',
    'siente', 'sienten', 'sentir', 'siento', 'sentimos', 'sintió', 'sintieron', 'sintiendo',
    'pasa', 'pasan', 'pasar', 'pasó', 'pasaron', 'pasando',
    'queda', 'quedan', 'quedar', 'quedó', 'quedaron', 'quedando',
    've', 'ven', 'ver', 'vemos', 'vio', 'vieron', 'visto', 'viendo',
    'come', 'comen', 'comer', 'comió', 'comieron', 'comiendo',
    'duerme', 'duermen', 'dormir', 'durmió', 'durmieron', 'durmiendo',
    'llora', 'lloran', 'llorar', 'lloró', 'lloraron', 'llorando',
    'toma', 'toman', 'tomar', 'tomó', 'tomaron', 'tomando',
    'produce', 'producen', 'producir', 'produjo', 'produjeron', 'produciendo',
    'causa', 'causan', 'causar', 'causó', 'causaron', 'causando',
    'genera', 'generan', 'generar', 'generó', 'generaron', 'generando',
    'llega', 'llegan', 'llegar', 'llegó', 'llegaron', 'llegando',
    'empieza', 'empiezan', 'empezar', 'empezó', 'empezaron', 'empezando',
    'inicia', 'inician', 'iniciar', 'inició', 'iniciaron', 'iniciando',
    'termina', 'terminan', 'terminar', 'terminó', 'terminaron', 'terminando',
    'existe', 'existen', 'existir', 'existió', 'existieron', 'existiendo',
    'ocurre', 'ocurren', 'ocurrir', 'ocurrió', 'ocurrieron', 'ocurriendo',
    'debe', 'deben', 'deber', 'debió', 'debieron', 'debiendo',
    'puede', 'pueden', 'poder', 'pudo', 'pudieron', 'pudiendo',
    'sabe', 'saben', 'saber', 'supo', 'supieron', 'sabiendo',
    'sirve', 'sirven', 'servir', 'sirvió', 'sirvieron', 'sirviendo',
    'funciona', 'funcionan', 'funcionar', 'funcionó', 'funcionaron', 'funcionando',
    'permite', 'permiten', 'permitir', 'permitió', 'permitieron', 'permitiendo',
    'ayuda', 'ayudan', 'ayudar', 'ayudó', 'ayudaron', 'ayudando',
    'necesita', 'necesitan', 'necesitar', 'necesitó', 'necesitaron', 'necesitando',
    'es', 'son', 'fue', 'fueron', 'era', 'eran', 'ser', 'sido', 'siendo', 'sea', 'sean',
    'está', 'están', 'estar', 'estaba', 'estaban', 'estuvo', 'estuvieron', 'estando', 'esté', 'estén',
    'va', 'van', 'ir', 'iba', 'iban', 'vamos', 'yendo', 'vaya', 'vayan',
    'viene', 'vienen', 'venir', 'vino', 'vinieron', 'viniendo', 'venga', 'vengan',
    'sigue', 'siguen', 'seguir', 'siguió', 'siguieron', 'siguiendo',
    'pone', 'ponen', 'poner', 'puso', 'pusieron', 'poniendo',
    'sale', 'salen', 'salir', 'salió', 'salieron', 'saliendo',
    'da', 'dan', 'dar', 'dio', 'dieron', 'dando',
    'cree', 'creen', 'creer', 'creyó', 'creyeron', 'creyendo',
    'mira', 'miran', 'mirar', 'miró', 'miraron', 'mirando',
    'escucha', 'escuchan', 'escuchar', 'escuchó', 'escucharon', 'escuchando',
    'habla', 'hablan', 'hablar', 'habló', 'hablaron', 'hablando',
    'explica', 'explican', 'explicar', 'explicó', 'explicaron', 'explicando',
    'muestra', 'muestran', 'mostrar', 'mostró', 'mostraron', 'mostrando',
    'nota', 'notan', 'notar', 'notó', 'notaron', 'notando',
    'busca', 'buscan', 'buscar', 'buscó', 'buscaron', 'buscando',
    'encuentra', 'encuentran', 'encontrar', 'encontró', 'encontraron', 'encontrando',
    'evita', 'evitan', 'evitar', 'evitó', 'evitaron', 'evitando',
    'quita', 'quitan', 'quitar', 'quitó', 'quitaron', 'quitando',
    'cambia', 'cambian', 'cambiar', 'cambió', 'cambiaron', 'cambiando',
    'mejora', 'mejoran', 'mejorar', 'mejoró', 'mejoraron', 'mejorando',
    'afecta', 'afectan', 'afectar', 'afectó', 'afectaron', 'afectando',
    'provoca', 'provocan', 'provocar', 'provocó', 'provocaron', 'provocando',
    'aparece', 'aparecen', 'aparecer', 'apareció', 'aparecieron', 'apareciendo',
    'desaparece', 'desaparecen', 'desaparecer', 'desapareció', 'desaparecieron', 'desapareciendo',
    'hay', 'había', 'hubo', 'habrá',
    # Connectors, conjunctions, relatives, prepositions, particles
    'y', 'e', 'ni', 'o', 'u', 'pero', 'aunque', 'porque', 'pues', 'ya', 'si', 'sino',
    'que', 'quien', 'quienes', 'cual', 'cuales', 'cuyo', 'cuya', 'cuyos', 'cuyas',
    'como', 'cuando', 'donde', 'mientras', 'entonces', 'además', 'también', 'tampoco',
    'a', 'al', 'del', 'de', 'con', 'en', 'por', 'para', 'sin', 'sobre', 'tras',
    'hacia', 'hasta', 'desde', 'ante', 'bajo', 'contra', 'entre', 'mediante', 'según',
    'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas',
    'mi', 'tu', 'su', 'mis', 'tus', 'sus', 'nuestro', 'nuestra', 'nuestros', 'nuestras',
    'este', 'esta', 'estos', 'estas', 'ese', 'esa', 'esos', 'esas', 'aquel', 'aquella',
    'me', 'te', 'se', 'nos', 'os', 'le', 'les', 'lo'
}

# Complete Spanish Stopwords and Connectors (strictly prohibited as highlights)
SPANISH_STOPWORDS = {
    # Negations & Affirmations (Strictly prohibited as highlights)
    'no', 'non', 'sí', 'si', 'nunca', 'jamás', 'tampoco', 'nada', 'nadie', 'ningún', 'ninguno', 'ninguna',
    # Articles
    'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas',
    # Prepositions
    'a', 'al', 'del', 'de', 'con', 'en', 'por', 'para', 'sin', 'sobre', 'tras',
    'hacia', 'hasta', 'desde', 'ante', 'bajo', 'contra', 'entre', 'mediante', 'según', 'via', 'vía',
    # Conjunctions & Connectors (Strictly prohibited as highlights)
    'porque', 'pero', 'cuando', 'como', 'que', 'donde', 'mientras', 'pues', 'ya', 'sino',
    'entonces', 'además', 'también', 'aunque', 'y', 'e', 'ni', 'o', 'u',
    'así', 'asi', 'luego', 'asimismo', 'siquiera', 'acaso', 'quizá', 'quizás', 'tal',
    # Pronouns & Clitics
    'yo', 'tu', 'él', 'ella', 'ello', 'nosotros', 'nosotras', 'vosotros', 'vosotras', 'ellos', 'ellas',
    'me', 'te', 'se', 'nos', 'os', 'le', 'les', 'lo',
    'mi', 'mis', 'tu', 'tus', 'su', 'sus', 'nuestro', 'nuestra', 'nuestros', 'nuestras',
    'este', 'esta', 'estos', 'estas', 'esto', 'ese', 'esa', 'esos', 'esas', 'eso',
    'aquel', 'aquella', 'aquellos', 'aquellas', 'aquello',
    'quien', 'quienes', 'cual', 'cuales', 'cuyo', 'cuya', 'cuyos', 'cuyas',
    # Auxiliary & Common Verbs
    'es', 'son', 'fue', 'fueron', 'era', 'eran', 'ser', 'sido', 'siendo', 'sea', 'sean',
    'está', 'están', 'estar', 'estaba', 'estaban', 'estuvo', 'estuvieron', 'estando', 'esté', 'estén',
    'ha', 'han', 'haber', 'había', 'habían', 'hay', 'hubo', 'habrá',
    'va', 'van', 'ir', 'iba', 'iban', 'vamos', 'yendo',
    'hace', 'hacen', 'hacer', 'hago', 'hacemos', 'hizo', 'hicieron', 'hecho', 'haciendo',
    'tener', 'tiene', 'tienen', 'tienes', 'tengo', 'tenemos', 'tenía', 'tenían', 'tuvo', 'tuvieron',
    'decir', 'dice', 'dicen', 'digo', 'dijo', 'dijeron', 'diciendo',
    'puede', 'pueden', 'poder', 'pudo', 'pudieron',
    # Adverbs & Fillers
    'muy', 'tan', 'más', 'mas', 'menos', 'bueno', 'bien', 'mal', 'aquí', 'allí', 'acá', 'allá',
    'ahora', 'después', 'antes', 'siempre', 'algo', 'todo', 'todos', 'todas', 'cada'
}

# Leading words that should not begin a highlight phrase if multi-word
INVALID_LEADING_HIGHLIGHT_WORDS = {
    'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas',
    'de', 'del', 'a', 'al', 'en', 'con', 'por', 'para', 'sin', 'sobre', 'tras',
    'hacia', 'hasta', 'desde', 'ante', 'bajo', 'contra', 'entre',
    'y', 'e', 'ni', 'o', 'u', 'que', 'pero', 'aunque', 'si', 'como', 'cuando', 'donde', 'porque', 'pues', 'ya', 'sino', 'mientras', 'entonces',
    'no', 'así', 'asi',
    'me', 'te', 'se', 'nos', 'os', 'le', 'les', 'lo',
    'mi', 'tu', 'su', 'mis', 'tus', 'sus',
    'este', 'esta', 'estos', 'estas', 'ese', 'esa', 'eso',
    'muy', 'tan', 'más', 'menos'
}

# Leading connectors, negations, and conjunctions that should not begin a highlight phrase
INVALID_LEADING_CONNECTORS = {
    'no', 'porque', 'pero', 'aunque', 'cuando', 'como', 'que', 'si', 'donde', 'mientras', 'pues', 'ya', 'sino',
    'entonces', 'además', 'también', 'tampoco', 'y', 'e', 'ni', 'o', 'u', 'así', 'asi',
    # Negative determiners / quantifiers (e.g. 'ningún beneficio' -> 'beneficio')
    'ningún', 'ningun', 'ninguna', 'ninguno', 'nada', 'nadie', 'nunca', 'jamás', 'jamas',
    # Indefinite & qualifying modifiers
    'mucho', 'mucha', 'muchos', 'muchas', 'poco', 'poca', 'pocos', 'pocas',
    'bastante', 'bastantes', 'demasiado', 'demasiada', 'demasiados', 'demasiadas',
    'tanto', 'tanta', 'tantos', 'tantas', 'tan', 'más', 'mas', 'menos',
    'cada', 'todo', 'toda', 'todos', 'todas', 'otro', 'otra', 'otros', 'otras',
    'cualquier', 'cualquiera',
    # Non-essential verbs / auxiliaries at start
    'aportan', 'aporta', 'tienen', 'tiene', 'dan', 'da', 'hacen', 'hace', 'son', 'es', 'están', 'está', 'hay'
}

def sanitize_highlight_phrase(phrase: str, max_chars: int = 18) -> str:
    """
    Sanitizes a highlight phrase to ensure strict semantic coherence and safe margins:
    1. Removes prohibited punctuation (commas, periods, colons) via clean_subtitle_text.
    2. Completely rejects phrases that consist only of stopwords/connectors (e.g. 'no', 'porque', 'pero', 'y').
    3. Rejects single words of 1 or 2 letters unless they contain digits (e.g. 'no', 'el', 'o', 'y', 'un').
    4. Strips invalid leading connectors, quantifiers, and negations (e.g. 'no', 'ningún', 'porque', 'mucho', 'tan').
    5. Preserves natural leading articles in short multi-word noun phrases (e.g. 'un congreso').
    6. Strips invalid trailing words (verbs, connectors, conjunctions) if multi-word,
       preventing grammatical spillover into subsequent sentences/clauses.
    7. Enforces max_chars constraint: if a multi-word phrase exceeds max_chars,
       extracts the core single keyword to prevent breaking safe screen margins.
    8. Re-checks the final result against stopwords and minimum meaningful length.
    """
    cleaned = clean_subtitle_text(phrase)
    if not cleaned:
        return ""
    words = cleaned.split()
    if not words:
        return ""

    # Reject single-word stopwords or short/empty words immediately
    if len(words) == 1:
        w_low = words[0].lower()
        if w_low in SPANISH_STOPWORDS:
            return ""
        if len(w_low) <= 2 and not any(c.isdigit() for c in w_low):
            return ""
        if w_low in {'asi', 'así', 'que', 'los', 'las', 'del', 'con', 'por', 'sin', 'mas', 'más', 'tan', 'muy', 'nos', 'les', 'sus', 'mis', 'tus', 'van', 'voy', 'dar', 'ver', 'fue', 'era', 'son', 'ese', 'esa', 'eso'}:
            return ""

    # Strip invalid leading connectors / negations / quantifiers (e.g. 'no', 'ningún', 'porque', 'mucho', 'tan')
    while len(words) > 1 and words[0].lower() in INVALID_LEADING_CONNECTORS:
        words.pop(0)

    # Strip invalid trailing words if multi-word
    while len(words) > 1 and words[-1].lower() in INVALID_TRAILING_HIGHLIGHT_WORDS:
        words.pop(-1)

    # If still multi-word and exceeds max_chars:
    # Extract the core single keyword (the most informative word that fits within max_chars)
    candidate = " ".join(words)
    if len(candidate) > max_chars and len(words) > 1:
        valid_words = [w for w in words if w.lower() not in SPANISH_STOPWORDS and len(w) <= max_chars and len(w) >= 3]
        if valid_words:
            candidate = max(valid_words, key=len)
        else:
            return ""

    # Check if final candidate is a stopword or too short
    cand_words = candidate.split()
    if len(cand_words) == 1:
        w_low = cand_words[0].lower()
        if w_low in SPANISH_STOPWORDS:
            return ""
        if len(w_low) <= 2 and not any(c.isdigit() for c in w_low):
            return ""
        if w_low in {'asi', 'así', 'que', 'los', 'las', 'del', 'con', 'por', 'sin', 'mas', 'más', 'tan', 'muy', 'nos', 'les', 'sus', 'mis', 'tus', 'van', 'voy', 'dar', 'ver', 'fue', 'era', 'son', 'ese', 'esa', 'eso'}:
            return ""

    return candidate


def normalize_word_for_alignment(w: str) -> str:
    """
    Normalizes a word for sequence alignment by removing punctuation
    and lowercasing.
    """
    w_clean = re.sub(r'^[¿¡\'"\(\[\{]+', '', w)
    w_clean = re.sub(r'[?!,.;:\'"\)\]\}]+$', '', w_clean)
    return w_clean.lower()


def align_ai_corrections_to_raw_items(
    raw_items: List[Dict[str, Any]],
    corrected_subtitles: List[Dict[str, Any]]
) -> None:
    """
    Guarantees 100% microsecond acoustic synchronization by strictly binding
    AI corrections (casing, question marks, digits) to the original word slots
    of CapCut speech-to-text segments using sequence alignment.
    
    Prevents AI models (such as Gemini Flash) from shifting words between segments,
    ensuring subtitles never drift or desynchronize from the speaker's voice.
    """
    if not raw_items or not corrected_subtitles:
        return

    # 1. Flatten original segment words and track their item index
    orig_words = []
    word_to_item = []
    for item_idx, item in enumerate(raw_items):
        ws = item['text'].split()
        for w in ws:
            orig_words.append(w)
            word_to_item.append(item_idx)

    if not orig_words:
        return

    # 2. Flatten AI corrected words
    ai_words = []
    for c in corrected_subtitles:
        txt = clean_subtitle_text(c.get('text', ''))
        txt = convert_spanish_numbers_to_digits(txt)
        for w in txt.split():
            ai_words.append(w)

    if not ai_words:
        return

    # 3. Balance / close unclosed question marks in AI words before alignment
    in_q = False
    q_start_idx = -1
    for idx, w in enumerate(ai_words):
        if '¿' in w:
            in_q = True
            q_start_idx = idx
        if '?' in w:
            in_q = False
        elif in_q and idx > q_start_idx:
            # If next word starts with uppercase or sentence starter, close previous word
            w_bare = re.sub(r'^[¿¡\'"\(\[\{]+', '', w)
            if w_bare and (w_bare[0].isupper() or w_bare.lower() in {'sí', 'si', 'no'}) and w_bare.lower() in {'sí', 'si', 'no', 'pero', 'se', 'es', 'consiste', 'por', 'en', 'hay'}:
                ai_words[idx - 1] = ai_words[idx - 1] + '?'
                if w_bare.lower() in {'sí', 'si', 'no'}:
                    ai_words[idx] = ai_words[idx].capitalize()
                in_q = False

    # 4. Sequence alignment
    norm_orig = [normalize_word_for_alignment(w) for w in orig_words]
    norm_ai = [normalize_word_for_alignment(w) for w in ai_words]

    matcher = difflib.SequenceMatcher(None, norm_orig, norm_ai)
    aligned_words = list(orig_words)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            for k in range(i2 - i1):
                aligned_words[i1 + k] = ai_words[j1 + k]
        elif tag == 'replace':
            if (i2 - i1) == (j2 - j1):
                for k in range(i2 - i1):
                    w_o = norm_orig[i1 + k]
                    w_a = norm_ai[j1 + k]
                    # Accept replacement if words match normalized or number-equivalent
                    if w_o == w_a or convert_spanish_numbers_to_digits(w_o) == convert_spanish_numbers_to_digits(w_a):
                        aligned_words[i1 + k] = ai_words[j1 + k]

    # 5. Reconstruct segment texts strictly within original word counts
    item_word_chunks = [[] for _ in raw_items]
    for w_idx, item_idx in enumerate(word_to_item):
        item_word_chunks[item_idx].append(aligned_words[w_idx])

    for item_idx, chunk in enumerate(item_word_chunks):
        if chunk:
            rebuilt_text = " ".join(chunk)
            raw_items[item_idx]['text'] = rebuilt_text
            it = raw_items[item_idx].get('item')
            if it:
                if hasattr(it, 'set_text'):
                    it.set_text(rebuilt_text)
                elif hasattr(it, 'text'):
                    try:
                        it.text = rebuilt_text
                    except Exception:
                        pass





