import os
import re
import difflib
from functools import lru_cache
from typing import List, Tuple, Optional, Dict, Any
from core.platform_paths import resolve_font_path


SAFE_MARGIN_VISUAL_MAX_RATIO = 1.085
HARD_MAX_LINE_CHARS = 13
PAIR_ELASTIC_MAX_CHARS = 16
STRICT_ORPHAN_WORDS = {
    'el', 'la', 'lo', 'los', 'las', 'un', 'una', 'unos', 'unas',
    'de', 'del', 'al', 'a', 'en', 'con', 'por', 'para', 'sin', 'sobre', 'tras',
    'hacia', 'hasta', 'desde', 'contra', 'entre',
    'y', 'e', 'ni', 'o', 'u', 'que',
    'se', 'te', 'me', 'le', 'les', 'nos',
    'mi', 'tu', 'su', 'mis', 'tus', 'sus',
}
_NARROW_VISUAL_CHARS = set("iltfj.,:;!'|¡íìï")
_WIDE_VISUAL_CHARS = set("mwMWOGQAHNDBRSECKPUVXYZÁÉÍÓÚÑ")
_NOUN_BRIDGE_MID_WORDS = {'del', 'de', 'la', 'el', 'los', 'las', 'al'}
_HARD_SPLIT_DANGLING_WORDS = {
    'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas',
    'de', 'del', 'al', 'a', 'en', 'con', 'por', 'para', 'sin', 'sobre', 'tras',
    'mi', 'tu', 'su', 'mis', 'tus', 'sus',
    'me', 'te', 'se', 'le', 'les', 'lo', 'nos',
    'este', 'esta', 'estos', 'estas', 'ese', 'esa', 'esos', 'esas',
    'que', 'y', 'e', 'o', 'u',
    'ha', 'he', 'has', 'han', 'hemos',
}
_MID_SENTENCE_CAPITAL_STARTERS = {
    'esto', 'eso', 'ahora', 'entonces', 'pero', 'porque', 'cuando', 'aunque', 'mientras', 'además',
    'notas', 'tienes', 'puedes', 'debes', 'sabes', 'quieres', 'necesitas',
    'haz', 'entra', 'comenta', 'escríbeme', 'sígueme', 'imagina', 'descubre', 'recuerda',
}


@lru_cache(maxsize=64)
def _load_pil_font(font_path_or_name: str, size: int = 100):
    if not font_path_or_name:
        return None
    try:
        from PIL import ImageFont
        path = font_path_or_name if os.path.isfile(font_path_or_name) else resolve_font_path(font_path_or_name)
        if path and os.path.isfile(path):
            return ImageFont.truetype(path, size)
    except Exception:
        pass
    return None


def _measure_line_units(line: str, pil_font) -> float:
    if not line:
        return 0.0
    if pil_font is not None:
        try:
            return float(pil_font.getlength(line))
        except Exception:
            pass
    total = 0.0
    for ch in line:
        if ch in _NARROW_VISUAL_CHARS:
            total += 0.6
        elif ch in _WIDE_VISUAL_CHARS:
            total += 1.25
        else:
            total += 1.0
    return total


def measure_visual_width_ratio(
    text: str,
    font_path_or_name: str = "",
    max_chars: int = 18,
    is_uppercase: bool = False,
) -> float:
    """Measure widest line visually relative to average-character safe margin budget."""
    raw = str(text or '').strip()
    if not raw:
        return 0.0
    eff_max_chars = max(1, int(max_chars or 18))
    sample = raw.upper() if is_uppercase else raw
    ref = "DE LAS SEÑALES QUE NO" if is_uppercase else "de las señales que no"
    pil_font = _load_pil_font(str(font_path_or_name or ""), 100)
    ref_units = _measure_line_units(ref, pil_font)
    avg_ch = (ref_units / len(ref)) if ref_units > 0 else 1.0
    widest = max((_measure_line_units(ln.strip(), pil_font) for ln in sample.splitlines() if ln.strip()), default=0.0)
    return widest / (avg_ch * eff_max_chars)


def segment_exceeds_line_budget(
    toks_or_words: List[Any],
    max_chars: int = HARD_MAX_LINE_CHARS,
    max_words: int = 3,
    font_path: str = "",
    is_uppercase: bool = False,
    max_ratio: float = SAFE_MARGIN_VISUAL_MAX_RATIO,
) -> bool:
    """Return True when a multi-word line exceeds max_chars (default 13) or safe margins.
    Single-word lines are never split even if they exceed max_chars.
    """
    words: List[str] = []
    for t in toks_or_words:
        w = (t.get('word', '') if isinstance(t, dict) else str(t)).strip()
        if w:
            words.append(w)
    nw = len(words)
    if nw < 2:
        return False

    txt = " ".join(words)
    nc = len(txt)
    eff_mc = max(1, int(max_chars or HARD_MAX_LINE_CHARS))
    bares = [_strip_edge_punct(w).lower() for w in words]
    tiny_lone = (set(ORPHAN_SHORT_WORDS) | set(PROCLITIC_ORPHAN_WORDS) | {'hay'}) - {
        'esto', 'eso', 'hoy', 'aquí', 'aqui', 'ahí', 'ahi', 'allí', 'alli', 'sí', 'si'
    }
    if nw == 2 and (bares[0] in tiny_lone or bares[1] in tiny_lone):
        return False

    visual_cap = max(eff_mc, 18)
    ratio = measure_visual_width_ratio(txt, font_path_or_name=font_path, max_chars=visual_cap, is_uppercase=is_uppercase)
    if nw == 2:
        pair_cap = max(eff_mc, PAIR_ELASTIC_MAX_CHARS) if eff_mc <= PAIR_ELASTIC_MAX_CHARS else eff_mc
        return nc > pair_cap or ratio > max_ratio
    if nc > eff_mc:
        return True
    if ratio > max_ratio:
        return True

    eff_mw = max(1, int(max_words or 3))
    clens = [len(b) for b in bares]

    if nw >= eff_mw + 2:
        return True

    if nw > eff_mw:
        # With max_words==3, keep 4-word line only when it is a compact clitic phrase (e.g. 'Esto sí que es')
        is_compact_4 = (
            eff_mw == 3
            and nw == 4
            and nc <= min(15, eff_mc)
            and ratio <= 0.85
            and max(clens) <= 6
            and sum(1 for c in clens if c >= 5) <= 1
        )
        if not is_compact_4:
            return True

    if eff_mw <= 3 and nw == 3:
        mid = bares[1]
        if mid in _NOUN_BRIDGE_MID_WORDS and ratio <= max_ratio:
            return False
        if ratio > 0.98:
            return True
        if sum(1 for c in clens if c >= 5) >= 2 and nc >= 17:
            return True
        if nc >= 18:
            return True

    if eff_mw > 3 and nc > max(eff_mc + 4, 24):
        return True

    return False


def _split_tokens_for_safe_margins(
    template: Dict[str, Any],
    toks: List[Dict[str, Any]],
    max_chars: int,
    max_words: int,
    font_path: str,
    is_uppercase: bool,
    max_ratio: float,
    keep_punctuation: bool,
) -> List[Dict[str, Any]]:
    if len(toks) < 2:
        return [_build_item_from_tokens(template, toks, keep_punctuation=keep_punctuation)]

    if not segment_exceeds_line_budget(toks, max_chars=max_chars, max_words=max_words, font_path=font_path, is_uppercase=is_uppercase, max_ratio=max_ratio):
        return [_build_item_from_tokens(template, toks, keep_punctuation=keep_punctuation)]

    func_words = (set(ORPHAN_SHORT_WORDS) | set(PROCLITIC_ORPHAN_WORDS) | {'hay'}) - {
        'esto', 'eso', 'hoy', 'aquí', 'aqui', 'ahí', 'ahi', 'allí', 'alli', 'sí', 'si'
    }
    best_k = None
    best_score = float('inf')

    for k in range(1, len(toks)):
        left_toks = toks[:k]
        right_toks = toks[k:]
        left_txt = " ".join(t['word'] for t in left_toks)
        right_txt = " ".join(t['word'] for t in right_toks)

        r_left = measure_visual_width_ratio(left_txt, font_path, max(max_chars, 18), is_uppercase)
        r_right = measure_visual_width_ratio(right_txt, font_path, max(max_chars, 18), is_uppercase)

        score = (
            abs(r_left - r_right) * 18.0
            + abs(len(left_txt) - len(right_txt)) * 2.5
            + abs(len(left_toks) - len(right_toks)) * 4.0
        )
        if r_left > max_ratio:
            score += (r_left - max_ratio) * 200.0
        if r_right > max_ratio:
            score += (r_right - max_ratio) * 200.0

        if segment_exceeds_line_budget(left_toks, max_chars=max_chars, max_words=max_words, font_path=font_path, is_uppercase=is_uppercase, max_ratio=max_ratio):
            score += 120.0
        if segment_exceeds_line_budget(right_toks, max_chars=max_chars, max_words=max_words, font_path=font_path, is_uppercase=is_uppercase, max_ratio=max_ratio):
            score += 120.0

        last_left = _strip_edge_punct(left_toks[-1]['word']).lower()
        first_right = _strip_edge_punct(right_toks[0]['word']).lower()
        if (
            (len(left_toks) == 1 and last_left in func_words)
            or (len(right_toks) == 1 and first_right in func_words)
        ):
            score += 1000.0
        if not left_toks[-1]['word'].endswith((',', '.', '?', '!')):
            if last_left in _HARD_SPLIT_DANGLING_WORDS:
                score += 65.0
            elif last_left in PROCLITIC_ORPHAN_WORDS:
                score += 25.0

        if len(toks) == 4 and k == 2 and last_left not in _HARD_SPLIT_DANGLING_WORDS:
            score -= 12.0

        dur_left = left_toks[-1]['end_us'] - left_toks[0]['start_us']
        dur_right = right_toks[-1]['end_us'] - right_toks[0]['start_us']
        if dur_left < 280000:
            score += 30.0
        if dur_right < 280000:
            score += 30.0
        if left_toks[-1]['word'].endswith((',', '.', '?', '!')):
            score -= 20.0

        if score < best_score:
            best_score = score
            best_k = k

    if best_k is None or best_score >= 1000.0:
        return [_build_item_from_tokens(template, toks, keep_punctuation=keep_punctuation)]

    left_toks = toks[:best_k]
    right_toks = toks[best_k:]
    left_tpl = dict(template)
    right_tpl = dict(template)
    right_tpl['item'] = None

    left_parts = _split_tokens_for_safe_margins(left_tpl, left_toks, max_chars, max_words, font_path, is_uppercase, max_ratio, keep_punctuation)
    right_parts = _split_tokens_for_safe_margins(right_tpl, right_toks, max_chars, max_words, font_path, is_uppercase, max_ratio, keep_punctuation)
    return left_parts + right_parts


def split_wide_segment_for_safe_margins(
    item: Dict[str, Any],
    max_chars: int = HARD_MAX_LINE_CHARS,
    max_words: int = 3,
    font_path: str = "",
    is_uppercase: bool = False,
    max_ratio: float = SAFE_MARGIN_VISUAL_MAX_RATIO,
    keep_punctuation: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """Split a wide or overly dense multi-word subtitle segment into word-timed pieces."""
    raw_text = str(item.get('text', '') or '').strip()
    if not raw_text or '\n' in raw_text:
        return [item]
    toks = _extract_word_tokens(item)
    if len(toks) < 2:
        return [item]
    if not segment_exceeds_line_budget(
        toks,
        max_chars=max_chars,
        max_words=max_words,
        font_path=font_path,
        is_uppercase=is_uppercase,
        max_ratio=max_ratio,
    ):
        return [item]
    kp = True if keep_punctuation is None else bool(keep_punctuation)
    return _split_tokens_for_safe_margins(item, toks, max_chars, max_words, font_path, is_uppercase, max_ratio, kp)


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

GALA_UNIQUE_SECOND_WORDS = {
    'unique', 'unik', 'unic', 'únic', 'unix', 'unick', 'unike',
    'uniq', 'uni', 'yunick', 'yunik', 'yunic', 'junik', 'junic'
}

_GALA_BRAND_FUSED_RE = re.compile(
    r'(?<!\w)gala(?:[yj]?un[iy](?:ck|ke|ch|c|k|x|q|g)?|unique)(?!\w)',
    re.IGNORECASE,
)
_GALA_BRAND_TWO_WORD_RE = re.compile(
    r'(?<!\w)gala\s+(?:unique|unick|unik|unic|únic|unix|unike|uniq|uni|yunick|yunik|yunic|junik|junic)(?!\w)',
    re.IGNORECASE,
)


def normalize_gala_brand_text(text: str, all_upper: bool = False) -> str:
    """Normalizes phonetic CapCut Whisper spellings of 'Gala Unique' into canonical casing."""
    if not text:
        return text
    target = "GALA UNIQUE" if all_upper else "Gala Unique"
    out = _GALA_BRAND_FUSED_RE.sub(lambda _m: target, text)
    out = _GALA_BRAND_TWO_WORD_RE.sub(lambda _m: target, out)
    return out


def clean_spanish_casing(text: str, is_sentence_start: bool = True) -> str:
    """
    Cleans Spanish casing in subtitle text:
    - Lowercases random ALL-CAPS words (e.g. 'DEBERÍAS' -> 'deberías' / 'Deberías', 'ESTÁN' -> 'están' / 'Están')
      while strictly preserving real Spanish acronyms (e.g. 'ADN', 'UCI', 'TDAH', 'TAC', 'OMS', 'VIH', 'COVID').
    - Fixes random title-casing of common words mid-sentence (e.g. 'y por qué Evita' -> 'y por qué evita',
      'para tu Pueblo' -> 'para tu pueblo').
    - Preserves proper sentence and question initial capitalization.
    - Strictly preserves intentional ALL-CAPS text (e.g. presets like Dr. Carrillo).
    """
    if not text:
        return ""
    # If text is already fully uppercase (or has no lowercase characters), do not downcase!
    # Intentional ALL-CAPS must be respected (e.g. presets like Dr. Carrillo).
    if not any(c.islower() for c in text):
        return text

    text = normalize_gala_brand_text(text, all_upper=False)

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

        # Capitalize recognized clinic/brand names ('Gala Unique', 'Clínica Gala', 'Clínica Dentok')
        prev_bare = re.sub(r'[¿¡?!,.;:\'"\(\)\[\]\{\}]', '', out[-1]).lower() if out else ''
        next_bare = re.sub(r'[¿¡?!,.;:\'"\(\)\[\]\{\}]', '', words[idx + 1]).lower() if idx + 1 < len(words) else ''
        if (
            (prev_bare in ('clínica', 'clinica') and core.lower() in ('gala', 'dentok'))
            or (core.lower() == 'gala' and next_bare in GALA_UNIQUE_SECOND_WORDS)
            or (prev_bare == 'gala' and core.lower() in GALA_UNIQUE_SECOND_WORDS)
        ):
            if prev_bare == 'gala' and core.lower() in GALA_UNIQUE_SECOND_WORDS:
                core = 'Unique'
            else:
                core = core[0].upper() + core[1:].lower()
            out.append(f"{lead}{core}{trail}")
            continue

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


def _normalize_spanish_punct_spacing(text: str) -> str:
    """Fix spaces and mid-word misplacements around ¿, ¡, ?, !."""
    if not text:
        return ""
    s = str(text)
    # Deduplicate repeated ¿, ?, ¡, !
    s = re.sub(r'¿+', '¿', s)
    s = re.sub(r'\?+', '?', s)
    s = re.sub(r'¡+', '¡', s)
    s = re.sub(r'!+', '!', s)

    # Fix mid-word ¿ or ¡ (e.g. t¿ienes -> ¿tienes) and mid-word ? or ! (e.g. problema?s -> problemas?)
    fixed_tokens = []
    for tok in s.split():
        if '¿' in tok and not tok.startswith('¿'):
            tok = '¿' + tok.replace('¿', '')
        if '¡' in tok and not tok.startswith('¡'):
            tok = '¡' + tok.replace('¡', '')
        if '?' in tok and not tok.endswith('?') and not re.fullmatch(r'[?!.,;:]+', tok):
            # Preserve any trailing punctuation after '?' when moving '?' to the end
            m_trail = re.match(r'^(.*?)([.,;:!]+)$', tok.replace('?', ''))
            if m_trail:
                tok = m_trail.group(1) + '?' + m_trail.group(2)
            else:
                tok = tok.replace('?', '') + '?'
        if '!' in tok and not tok.endswith('!') and not re.fullmatch(r'[?!.,;:]+', tok):
            tok = tok.replace('!', '') + '!'
        fixed_tokens.append(tok)
    s = " ".join(fixed_tokens)

    # Remove spaces after opening ¿/¡ and before closing ?/!/./,
    s = re.sub(r'([¿¡])\s+', r'\1', s)
    s = re.sub(r'\s+([?!])', r'\1', s)
    s = re.sub(r'\s+([.,])', r'\1', s)
    return s


def clean_subtitle_text(text: str, is_sentence_start: bool = True, preserve_case: bool = False, keep_punctuation: bool = False) -> str:
    """
    Cleans subtitle text by removing commas (,), periods (.), and colons (:),
    including ellipses (...), and normalizing whitespace.
    If keep_punctuation is True, preserves commas and periods as requested by specific presets (e.g. Abde).
    
    Also automatically corrects known CapCut speech-to-text uppercase glitches
    and erratic casing using clean_spanish_casing when text is not already all-caps.
    
    Preserves question marks (¿?), exclamation marks (¡!), hyphens, quotes,
    letters, accents, and numbers.
    """
    if not text:
        return ""

    normalized = _normalize_spanish_punct_spacing(str(text))

    # If preserve_case is requested or text is fully uppercase, do not apply clean_spanish_casing
    if preserve_case or not any(c.islower() for c in normalized):
        cleaned = normalized
    else:
        cleaned = clean_spanish_casing(normalized, is_sentence_start=is_sentence_start)
    
    # Remove commas, periods, colons unless keep_punctuation is True
    if not keep_punctuation:
        cleaned = re.sub(r'[,.:]+', '', cleaned)
    
    # Re-apply tight spacing around ¿?/¡! after punctuation removal
    cleaned = re.sub(r'([¿¡])\s+', r'\1', cleaned)
    cleaned = re.sub(r'\s+([?!])', r'\1', cleaned)
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
    'da', 'dan', 'dar', 'dando', 'doy', 'das',
    'creo', 'crees', 'cree', 'creen', 'creer', 'creyó', 'creyeron', 'creyendo', 'creía', 'creías',
    'pienso', 'piensas', 'piensa', 'piensan', 'pensar', 'parece', 'parecen', 'parecer', 'parecía',
    'opino', 'opinas', 'opina', 'opinar', 'supongo', 'supones', 'supone', 'suponer',
    'debo', 'debes', 'debemos', 'debería', 'deberías', 'debido', 'debía',
    'quiero', 'quieres', 'quiere', 'queremos', 'quieren', 'querer', 'quisiera',
    'puedo', 'puedes', 'podemos', 'pueda', 'puedas', 'podría', 'podrías',
    'doy', 'llevo', 'llevas', 'lleva', 'llevan', 'llevar',
    'estoy', 'estás', 'estamos', 'estuve', 'soy', 'eres', 'somos',
    'voy', 'vas', 'vaya', 'vayan', 'he', 'has', 'hemos',
    'vale', 'valen', 'bueno', 'así', 'eh', 'um',
    'caso', 'casos', 'cosa', 'cosas', 'forma', 'formas', 'manera', 'maneras',
    'modo', 'modos', 'tipo', 'tipos', 'parte', 'partes', 'vez', 'veces', 'poquito', 'poco',
    'mira', 'miras', 'miran', 'mirar', 'miró', 'miraron', 'mirando',
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
    'yo', 'tu', 'tú', 'él', 'ella', 'ello', 'nosotros', 'nosotras', 'vosotros', 'vosotras', 'ellos', 'ellas',
    'me', 'te', 'se', 'nos', 'os', 'le', 'les', 'lo', 'los', 'las',
    'mi', 'mis', 'tu', 'tus', 'su', 'sus', 'nuestro', 'nuestra', 'nuestros', 'nuestras',
    'este', 'esta', 'estos', 'estas', 'esto', 'ese', 'esa', 'esos', 'esas', 'eso',
    'aquel', 'aquella', 'aquellos', 'aquellas', 'aquello',
    'quien', 'quienes', 'cual', 'cuales', 'cuyo', 'cuya', 'cuyos', 'cuyas',
    # Auxiliary, Epistemic, Modal & Conversational Filler Verbs
    'es', 'son', 'fue', 'fueron', 'era', 'eran', 'ser', 'sido', 'siendo', 'sea', 'sean', 'soy', 'eres', 'somos',
    'está', 'están', 'estan', 'estar', 'estaba', 'estaban', 'estuvo', 'estuvieron', 'estando', 'esté', 'estén', 'estoy', 'estás', 'estamos', 'estuve',
    'ha', 'han', 'he', 'has', 'hemos', 'haber', 'había', 'habían', 'habido', 'habría', 'hay', 'hubo', 'habrá',
    'va', 'van', 'ir', 'iba', 'iban', 'vamos', 'yendo', 'voy', 'vas', 'vaya', 'vayan',
    'hace', 'hacen', 'hacer', 'hago', 'haces', 'hacemos', 'hizo', 'hicieron', 'hecho', 'haciendo', 'haga', 'hagas', 'hagan',
    'tener', 'tiene', 'tienen', 'tienes', 'tengo', 'tenemos', 'tenía', 'tenían', 'tuvo', 'tuve', 'tuviste', 'tuvieron',
    'decir', 'dice', 'dicen', 'digo', 'dices', 'digas', 'decimos', 'dijo', 'dijeron', 'diciendo',
    'puede', 'pueden', 'poder', 'pudo', 'pudieron', 'puedo', 'puedes', 'podemos', 'pueda', 'puedas', 'podría', 'podrías',
    'debe', 'deben', 'deber', 'debo', 'debes', 'debemos', 'debería', 'deberías', 'debido', 'debía',
    'creo', 'crees', 'cree', 'creen', 'creer', 'creía', 'creías', 'creí', 'creyó', 'creyendo',
    'pienso', 'piensas', 'piensa', 'piensan', 'pensar', 'pensaba',
    'parece', 'parecen', 'parecer', 'parecía', 'opino', 'opinas', 'opina', 'opinar',
    'supongo', 'supones', 'supone', 'suponer',
    'quiero', 'quieres', 'quiere', 'queremos', 'quieren', 'querer', 'quisiera',
    'siento', 'sientes', 'siente', 'sentimos', 'sienten',
    'sabe', 'saben', 'sabes', 'sé', 'sabemos', 'saber', 'sabía', 'supo',
    'veo', 'ves', 've', 'ven', 'vemos', 'ver', 'visto', 'viendo',
    'doy', 'das', 'da', 'dan', 'dar', 'dio', 'dieron', 'dado', 'dando',
    'vengo', 'vienes', 'viene', 'vienen', 'venir', 'vino', 'venga',
    'llevo', 'llevas', 'lleva', 'llevan', 'llevar',
    'pongo', 'pones', 'pone', 'ponen', 'poner', 'puso', 'puesto',
    'quedo', 'quedas', 'queda', 'quedan', 'quedar', 'quedó',
    'dejo', 'dejas', 'deja', 'dejan', 'dejar',
    'mira', 'miras', 'miran', 'mirar', 'fíjate', 'fijate',
    'suele', 'suelen', 'soler', 'tiende', 'tienden', 'trata', 'tratan', 'tratar',
    'acaba', 'acaban', 'acabar', 'empieza', 'empiezan', 'empezar', 'empezó', 'termina', 'terminan', 'terminar',
    'consigue', 'consiguen', 'conseguir', 'resulta', 'resultan',
    'ocurre', 'ocurren', 'ocurrir', 'pasa', 'pasan', 'pasar', 'sucede', 'suceden', 'existe', 'existen',
    'necesita', 'necesitan', 'necesitas', 'necesito',
    'usar', 'uso', 'usa', 'usas', 'usan', 'usando', 'usamos',
    'palabra', 'palabras',
    # Adverbs, Discourse Fillers & Vague Conversational Nouns
    'muy', 'tan', 'más', 'mas', 'menos', 'bueno', 'bien', 'mal', 'vale', 'claro', 'cierto',
    'aquí', 'aqui', 'allí', 'alli', 'acá', 'allá', 'ahí', 'ahi',
    'ahora', 'después', 'despues', 'antes', 'siempre', 'algo', 'alguien', 'casi', 'incluso', 'aún', 'aun', 'todavía', 'todavia', 'aparte', 'ojalá', 'ojala',
    'todo', 'toda', 'todos', 'todas', 'cada', 'otro', 'otra', 'otros', 'otras', 'mismo', 'misma', 'mismos', 'mismas',
    'algún', 'algun', 'alguna', 'alguno', 'algunos', 'algunas', 'ningun', 'cualquier', 'cualquiera', 'cuanto', 'cuanta', 'varios', 'varias',
    'diferente', 'diferentes', 'distinto', 'distinta', 'distintos', 'distintas',
    'mucho', 'mucha', 'muchos', 'muchas', 'poco', 'poca', 'pocos', 'pocas', 'poquito', 'poquita',
    'bastante', 'bastantes', 'demasiado', 'demasiada', 'demasiados', 'demasiadas',
    'montón', 'monton', 'montones',
    'intentar', 'intento', 'intentas', 'intenta', 'intentan', 'intentamos', 'intentando', 'intenté', 'intentó',
    'seguir', 'sigo', 'sigues', 'sigue', 'siguen', 'siguiendo',
    'francamente', 'realmente', 'básicamente', 'basicamente', 'simplemente', 'literalmente',
    'obviamente', 'claramente', 'prácticamente', 'practicamente', 'normalmente', 'generalmente', 'habitualmente',
    'totalmente', 'completamente', 'absolutamente', 'efectivamente', 'exactamente', 'precisamente',
    'seguramente', 'posiblemente', 'probablemente', 'lógicamente', 'logicamente', 'evidentemente',
    'sinceramente', 'honestamente', 'directamente', 'únicamente', 'unicamente', 'solamente',
    'eh', 'um', 'emm', 'hmm', 'mm', 'ah', 'oh', 'oye', 'oiga',
    'caso', 'casos', 'cosa', 'cosas', 'forma', 'formas', 'manera', 'maneras',
    'modo', 'modos', 'tipo', 'tipos', 'parte', 'partes', 'vez', 'veces',
    'ejemplo', 'supuesto', 'embargo', 'respecto', 'chica', 'chico'
}

_DISCOURSE_MENTE_EXCEPTIONS = {'mentalmente'}


def is_weak_highlight_word(word: str) -> bool:
    """Return True if word is a conversational filler, stopword, hedge verb, or weak adverb."""
    bare = _strip_edge_punct(str(word or '')).lower()
    if not bare:
        return True
    if bare in SPANISH_STOPWORDS:
        return True
    if len(bare) <= 2 and not any(c.isdigit() for c in bare):
        return True
    if bare.endswith('mente') and len(bare) > 6 and bare not in _DISCOURSE_MENTE_EXCEPTIONS:
        return True
    return False

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
    'cualquier', 'cualquiera', 'varios', 'varias', 'algún', 'algun', 'alguna', 'alguno', 'algunos', 'algunas',
    'diferente', 'diferentes', 'distinto', 'distinta', 'distintos', 'distintas', 'montón', 'monton',
    # Non-essential verbs / auxiliaries at start
    'aportan', 'aporta', 'tienen', 'tiene', 'dan', 'da', 'hacen', 'hace', 'son', 'es', 'están', 'está', 'hay',
    'creo', 'cree', 'creen', 'pienso', 'parece', 'debo', 'debe', 'puedo', 'puede', 'bueno', 'entonces', 'francamente', 'realmente', 'vale'
}

def sanitize_highlight_phrase(phrase: str, max_chars: int = 18) -> str:
    """
    Sanitizes a highlight phrase to ensure strict semantic coherence and safe margins:
    1. Removes prohibited punctuation (commas, periods, colons) via clean_subtitle_text.
    2. Completely rejects phrases that consist only of stopwords/connectors/fillers (e.g. 'no', 'creo', 'yo creo').
    3. Rejects single words of 1 or 2 letters unless they contain digits (e.g. 'no', 'el', 'o', 'y', 'un').
    4. Strips invalid leading connectors, quantifiers, and negations (e.g. 'no', 'ningún', 'porque', 'mucho', 'tan').
    5. Preserves natural leading articles in short multi-word noun phrases (e.g. 'un congreso').
    6. Strips invalid trailing words (verbs, connectors, conjunctions) if multi-word,
       preventing grammatical spillover into subsequent sentences/clauses.
    7. Enforces max_chars constraint: if a multi-word phrase exceeds max_chars,
       extracts the core single keyword to prevent breaking safe screen margins.
    8. Re-checks the final result against stopwords, weak fillers, and minimum meaningful length.
    """
    cleaned = clean_subtitle_text(phrase)
    if not cleaned:
        return ""
    words = cleaned.split()
    if not words:
        return ""

    # Reject single-word stopwords, filler words, or short/empty words immediately
    if len(words) == 1:
        if is_weak_highlight_word(words[0]):
            return ""
        w_low = _strip_edge_punct(words[0]).lower()
        if w_low in {'asi', 'así', 'que', 'los', 'las', 'del', 'con', 'por', 'sin', 'mas', 'más', 'tan', 'muy', 'nos', 'les', 'sus', 'mis', 'tus', 'van', 'voy', 'dar', 'ver', 'fue', 'era', 'son', 'ese', 'esa', 'eso'}:
            return ""

    # Reject multi-word phrases consisting purely of weak fillers/stopwords (e.g. 'yo creo', 'en este caso')
    if all(is_weak_highlight_word(w) for w in words):
        return ""

    # Strip invalid leading connectors / negations / quantifiers (e.g. 'no', 'ningún', 'porque', 'mucho', 'tan')
    while len(words) > 1 and _strip_edge_punct(words[0]).lower() in INVALID_LEADING_CONNECTORS:
        words.pop(0)

    # Strip invalid trailing words if multi-word
    while len(words) > 1 and _strip_edge_punct(words[-1]).lower() in INVALID_TRAILING_HIGHLIGHT_WORDS:
        words.pop(-1)

    # If still multi-word and exceeds max_chars:
    # Extract the core single keyword (the most informative word that fits within max_chars)
    candidate = " ".join(words)
    if len(candidate) > max_chars and len(words) > 1:
        valid_words = [w for w in words if not is_weak_highlight_word(w) and len(w) <= max_chars and len(w) >= 3]
        if valid_words:
            candidate = max(valid_words, key=len)
        else:
            return ""

    # Check if final candidate is a stopword, filler, or too short
    cand_words = candidate.split()
    if len(cand_words) == 1:
        if is_weak_highlight_word(cand_words[0]):
            return ""
        w_low = _strip_edge_punct(cand_words[0]).lower()
        if w_low in {'asi', 'así', 'que', 'los', 'las', 'del', 'con', 'por', 'sin', 'mas', 'más', 'tan', 'muy', 'nos', 'les', 'sus', 'mis', 'tus', 'van', 'voy', 'dar', 'ver', 'fue', 'era', 'son', 'ese', 'esa', 'eso'}:
            return ""
    elif not cand_words or all(is_weak_highlight_word(w) for w in cand_words):
        return ""

    return candidate


def normalize_word_for_alignment(w: str) -> str:
    """
    Normalizes a word for sequence alignment by removing punctuation,
    accents, and lowercasing.
    """
    w_clean = re.sub(r'^[¿¡\'"\(\[\{]+', '', w)
    w_clean = re.sub(r'[?!,.;:\'"\)\]\}]+$', '', w_clean)
    w_clean = w_clean.lower()
    accents = str.maketrans('áéíóúü', 'aeiouu')
    return w_clean.translate(accents)


def align_ai_corrections_to_raw_items(
    raw_items: List[Dict[str, Any]],
    corrected_subtitles: List[Dict[str, Any]],
    keep_punctuation: bool = False
) -> None:
    """
    Guarantees 100% microsecond acoustic synchronization by strictly binding
    AI corrections (casing, question marks, digits, and optional punctuation) to
    the original word slots of CapCut speech-to-text segments using sequence alignment.
    
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
        txt = clean_subtitle_text(c.get('text', ''), keep_punctuation=keep_punctuation)
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
                    it.set_text(rebuilt_text, keep_punctuation=keep_punctuation)
                elif hasattr(it, 'text'):
                    try:
                        it.text = rebuilt_text
                    except Exception:
                        pass


def heuristic_punctuation_fallback(raw_items: List[Dict[str, Any]]) -> None:
    """
    Heuristically adds periods (.) and commas (,) to unpunctuated segments
    based on acoustic pauses (gaps) and linguistic connectors.
    Used when keep_punctuation is True and input lacks punctuation.
    """
    if not raw_items:
        return
    
    # Check if text already has punctuation
    has_any_punc = any(re.search(r'[,.]', it.get('text', '')) for it in raw_items)
    if has_any_punc:
        return

    CONJUNCTIONS_COMMA = {'pero', 'aunque', 'sin embargo', 'ya que', 'porque', 'es decir', 'o sea', 'por lo tanto'}
    SENTENCE_STARTERS = {'cada', 'este', 'esta', 'estos', 'estas', 'esto', 'ademas', 'además', 'por eso', 'finalmente', 'primero', 'segundo'}

    n = len(raw_items)
    for i in range(n):
        curr = raw_items[i]
        curr_text = curr['text'].strip()
        if not curr_text:
            continue
        if curr_text[-1] in '.?!,;:':
            continue

        if i == n - 1:
            curr['text'] = curr_text + '.'
            it = curr.get('item')
            if it and hasattr(it, 'set_text'):
                it.set_text(curr['text'], keep_punctuation=True)
            continue

        nxt = raw_items[i + 1]
        gap_us = nxt.get('start', 0) - curr.get('end', 0)
        nxt_text = nxt.get('text', '').strip()
        first_nxt_word = nxt_text.split()[0].lower() if nxt_text.split() else ''

        if gap_us >= 320000:
            curr['text'] = curr_text + '.'
        elif first_nxt_word in SENTENCE_STARTERS and gap_us >= 180000:
            curr['text'] = curr_text + '.'
        elif first_nxt_word in CONJUNCTIONS_COMMA and gap_us >= 120000:
            curr['text'] = curr_text + ','
        elif gap_us >= 200000 and len(curr_text.split()) >= 3:
            curr['text'] = curr_text + ','

        it = curr.get('item')
        if it and hasattr(it, 'set_text'):
            it.set_text(curr['text'], keep_punctuation=True)


ORPHAN_SHORT_WORDS = {
    'el', 'la', 'lo', 'los', 'las', 'un', 'una', 'unos', 'unas',
    'de', 'del', 'al', 'a', 'en', 'con', 'por', 'para', 'sin', 'sobre', 'tras',
    'hacia', 'hasta', 'desde', 'contra', 'entre',
    'y', 'e', 'ni', 'o', 'u', 'que', 'pero', 'aunque', 'porque', 'como', 'cuando', 'donde', 'si', 'sí',
    'no', 'es', 'son', 'fue', 'era', 'se', 'te', 'me', 'nos', 'le', 'les',
    'mi', 'tu', 'su', 'mis', 'tus', 'sus',
    'ya', 'más', 'mas', 'muy', 'tan', 'así', 'asi', 'hoy', 'aquí', 'aqui', 'ahí', 'ahi', 'allí', 'alli',
    'este', 'esta', 'estos', 'estas', 'esto', 'ese', 'esa', 'esos', 'esas', 'eso'
}

PROCLITIC_ORPHAN_WORDS = {
    'el', 'la', 'lo', 'los', 'las', 'un', 'una', 'unos', 'unas',
    'de', 'del', 'al', 'a', 'en', 'con', 'por', 'para', 'sin', 'sobre', 'tras',
    'hacia', 'hasta', 'desde', 'contra', 'entre',
    'y', 'e', 'ni', 'o', 'u', 'que', 'pero', 'aunque', 'porque', 'como', 'cuando', 'donde', 'si',
    'no', 'es', 'son', 'fue', 'era', 'se', 'te', 'me', 'nos', 'le', 'les',
    'mi', 'tu', 'su', 'mis', 'tus', 'sus', 'muy', 'tan',
    'este', 'esta', 'estos', 'estas', 'ese', 'esa', 'esos', 'esas'
}


def _strip_edge_punct(word: str) -> str:
    return re.sub(r'^[¿¡"\'\(\[\{.,;:?!]+|[¿¡"\'\)\]\},.;:?!]+$', '', word or '')


def _extract_word_tokens(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Returns per-word token dicts [{'word': str, 'start_us': int, 'end_us': int}, ...]
    aligned with item['words'] metadata when available, or proportional character timing.
    """
    txt = (item.get('text') or '').strip()
    words = txt.split()
    seg_start = int(item.get('start', 0))
    seg_dur = int(item.get('duration', max(0, int(item.get('end', seg_start)) - seg_start)))
    seg_end = int(item.get('end', seg_start + seg_dur))
    if seg_end < seg_start:
        seg_end = seg_start + max(0, seg_dur)
    if not words:
        return []

    w_meta = item.get('words')
    meta_tokens = []
    if isinstance(w_meta, dict):
        m_texts = w_meta.get('text', [])
        m_starts = w_meta.get('start_time', [])
        m_ends = w_meta.get('end_time', [])
        for mt, ms, me in zip(m_texts, m_starts, m_ends):
            if str(mt).strip():
                abs_s = seg_start + int(ms) * 1000
                abs_e = seg_start + int(me) * 1000
                if abs_e <= abs_s:
                    abs_e = abs_s + 50000
                meta_tokens.append((abs_s, abs_e))

    if len(meta_tokens) == len(words):
        out = []
        for idx, w in enumerate(words):
            s_us, e_us = meta_tokens[idx]
            s_us = max(seg_start, min(s_us, seg_end))
            e_us = max(s_us, min(e_us, seg_end))
            out.append({'word': w, 'start_us': s_us, 'end_us': e_us})
        out[0]['start_us'] = seg_start
        out[-1]['end_us'] = seg_end
        return out

    # Proportional fallback weighted by visible characters (+2 overhead per word)
    weights = [max(1, len(_strip_edge_punct(w)) + 2) for w in words]
    total_w = float(sum(weights)) or 1.0
    total_dur = max(len(words) * 40000, seg_end - seg_start)
    cur_t = float(seg_start)
    out = []
    for idx, (w, wt) in enumerate(zip(words, weights)):
        slice_dur = total_dur * (wt / total_w)
        s_us = int(round(cur_t))
        e_us = int(round(cur_t + slice_dur)) if idx < len(words) - 1 else max(seg_end, seg_start + total_dur)
        if e_us <= s_us:
            e_us = s_us + 20000
        out.append({'word': w, 'start_us': s_us, 'end_us': e_us})
        cur_t += slice_dur
    return out


def _build_item_from_tokens(
    template: Dict[str, Any],
    tokens: List[Dict[str, Any]],
    keep_punctuation: bool = False
) -> Dict[str, Any]:
    """Builds a segment item dict from word tokens with synchronized word timings."""
    raw_text = " ".join(t['word'] for t in tokens).strip()
    is_all_caps = bool(raw_text) and not any(c.islower() for c in raw_text)
    cleaned = clean_subtitle_text(raw_text, preserve_case=is_all_caps, keep_punctuation=keep_punctuation)
    start_us = int(tokens[0]['start_us'])
    end_us = max(start_us + 50000, int(tokens[-1]['end_us']))
    dur_us = end_us - start_us

    rebuilt_words = cleaned.split() if cleaned else [t['word'] for t in tokens]
    # Preserve original sub-word acoustic timings when text boundaries and count are unchanged
    tpl_words = (template.get('text') or '').split()
    if (
        template.get('words')
        and rebuilt_words == tpl_words
        and start_us == int(template.get('start', start_us))
        and end_us == int(template.get('end', end_us))
    ):
        words_dict = template.get('words')
    # Otherwise rebuild per-word timing count matching rebuilt_words
    elif len(rebuilt_words) == len(tokens):
        w_texts = []
        w_starts = []
        w_ends = []
        for idx, (rw, tok) in enumerate(zip(rebuilt_words, tokens)):
            if idx > 0:
                w_texts.append(' ')
                prev_e = w_ends[-1]
                cur_s = max(0, int((tok['start_us'] - start_us) // 1000))
                w_starts.append(prev_e)
                w_ends.append(max(prev_e, cur_s))
            w_texts.append(rw)
            ws_ms = max(0, int((tok['start_us'] - start_us) // 1000))
            we_ms = max(ws_ms + 20, int((tok['end_us'] - start_us) // 1000))
            w_starts.append(ws_ms)
            w_ends.append(we_ms)
        words_dict = {'text': w_texts, 'start_time': w_starts, 'end_time': w_ends}
    else:
        words_dict = template.get('words')

    new_item = dict(template)
    new_item['text'] = cleaned
    new_item['orig_text'] = cleaned
    new_item['start'] = start_us
    new_item['end'] = end_us
    new_item['duration'] = dur_us
    new_item['words'] = words_dict

    it_obj = new_item.get('item')
    if it_obj:
        if hasattr(it_obj, 'set_text'):
            try:
                it_obj.set_text(cleaned, keep_punctuation=keep_punctuation)
            except Exception:
                pass
        elif hasattr(it_obj, 'text'):
            try:
                it_obj.text = cleaned
            except Exception:
                pass
    return new_item


def fix_question_marks_and_broken_tokens(
    raw_items: List[Dict[str, Any]],
    keep_punctuation: bool = False
) -> List[Dict[str, Any]]:
    """
    Repairs broken single-letter plural suffixes ('s'), standalone punctuation segments
    ('?', '¿', '!', '¡'), misplaced spacing around ¿?/¡!, and unclosed/unpaired
    Spanish question marks across segments.
    """
    if not raw_items:
        return []

    seg_list = []
    for it in raw_items:
        toks = _extract_word_tokens(it)
        if toks:
            seg_list.append({'template': dict(it), 'tokens': toks, 'absorbed': list(it.get('absorbed_indices', []))})

    if not seg_list:
        return []

    full_sample = " ".join(t['word'] for s in seg_list for t in s['tokens'])
    preserve_all_caps = bool(full_sample) and not any(c.islower() for c in full_sample)

    # Pass 1: Fuse standalone punctuation and stray plural 's' tokens with adjacent segments
    i = 0
    while i < len(seg_list):
        toks = seg_list[i]['tokens']
        if not toks:
            seg_list.pop(i)
            continue

        # 1a. Intra-segment cleanup: fuse standalone punct tokens inside a segment
        cleaned_toks = []
        for t in toks:
            w = t['word'].strip()
            if re.fullmatch(r'[?!.,;:]+', w):
                if cleaned_toks:
                    cleaned_toks[-1]['word'] = _normalize_spanish_punct_spacing(cleaned_toks[-1]['word'] + w)
                    cleaned_toks[-1]['end_us'] = max(cleaned_toks[-1]['end_us'], t['end_us'])
                else:
                    cleaned_toks.append(t)
            elif w in ('¿', '¡'):
                cleaned_toks.append(t)
            else:
                if cleaned_toks and cleaned_toks[-1]['word'] in ('¿', '¡'):
                    prefix_punc = cleaned_toks.pop()
                    t = dict(t)
                    t['word'] = prefix_punc['word'] + w
                    t['start_us'] = min(prefix_punc['start_us'], t['start_us'])
                cleaned_toks.append(t)
        toks = cleaned_toks
        seg_list[i]['tokens'] = toks

        first_w = toks[0]['word'].strip()
        last_w = toks[-1]['word'].strip()

        # 1b. Leading standalone closing punct ('?', '!', '.', ',') -> attach to previous segment
        if re.fullmatch(r'[?!.,;:]+', first_w) and i > 0:
            prev_last = seg_list[i - 1]['tokens'][-1]
            prev_last['word'] = _normalize_spanish_punct_spacing(prev_last['word'] + first_w)
            prev_last['end_us'] = max(prev_last['end_us'], toks[0]['end_us'])
            toks.pop(0)
            if not toks:
                seg_list[i - 1]['absorbed'].append(seg_list[i]['template'].get('index'))
                seg_list[i - 1]['absorbed'].extend(seg_list[i]['absorbed'])
                seg_list.pop(i)
                continue

        # 1c. Leading stray plural 's' (e.g. 'dermatiti' + 's', 'escape' + 's') -> fuse into previous word
        first_bare = _strip_edge_punct(toks[0]['word'])
        if first_bare.lower() == 's' and i > 0 and seg_list[i - 1]['tokens']:
            prev_last = seg_list[i - 1]['tokens'][-1]
            prev_bare = _strip_edge_punct(prev_last['word'])
            if len(prev_bare) >= 4 and not prev_last['word'].endswith(('s', 'S', '?', '!')):
                # Preserve any trailing punct from the 's' token (e.g. 's?')
                trail_m = re.search(r'([?!.,;:]+)$', toks[0]['word'])
                trail_punc = trail_m.group(1) if trail_m else ''
                prev_last['word'] = prev_last['word'] + toks[0]['word'][0] + trail_punc
                prev_last['end_us'] = max(prev_last['end_us'], toks[0]['end_us'])
                toks.pop(0)
                if not toks:
                    seg_list[i - 1]['absorbed'].append(seg_list[i]['template'].get('index'))
                    seg_list[i - 1]['absorbed'].extend(seg_list[i]['absorbed'])
                    seg_list.pop(i)
                    continue

        # 1d. Trailing standalone opening punct ('¿', '¡') -> prepend to next segment
        if seg_list[i]['tokens'] and seg_list[i]['tokens'][-1]['word'].strip() in ('¿', '¡') and i + 1 < len(seg_list):
            p_tok = seg_list[i]['tokens'].pop()
            nxt_first = seg_list[i + 1]['tokens'][0]
            nxt_first['word'] = p_tok['word'].strip() + nxt_first['word']
            nxt_first['start_us'] = min(p_tok['start_us'], nxt_first['start_us'])
            if not seg_list[i]['tokens']:
                seg_list[i + 1]['absorbed'].append(seg_list[i]['template'].get('index'))
                seg_list[i + 1]['absorbed'].extend(seg_list[i]['absorbed'])
                seg_list.pop(i)
                continue

        i += 1

    # Pass 2: Normalize punct spacing & balance ¿ / ? across nearby segments
    for seg in seg_list:
        for t in seg['tokens']:
            t['word'] = _normalize_spanish_punct_spacing(t['word'])

    n = len(seg_list)
    # Close unclosed ¿ or open missing ¿ for trailing ?
    open_q_seg = None
    for idx in range(n):
        toks = seg_list[idx]['tokens']
        seg_text = " ".join(t['word'] for t in toks)
        has_open = '¿' in seg_text
        has_close = '?' in seg_text

        if has_open and not has_close:
            open_q_seg = idx
        elif has_close and not has_open:
            if open_q_seg is not None and (idx - open_q_seg) <= 3:
                open_q_seg = None
            else:
                # Attach ¿ at the start of the question clause (walk back at most 1 continuous segment)
                start_idx = idx
                if idx > 0:
                    prev_toks = seg_list[idx - 1]['tokens']
                    prev_text = " ".join(t['word'] for t in prev_toks)
                    gap_us = toks[0]['start_us'] - prev_toks[-1]['end_us']
                    if gap_us <= 300000 and not any(p in prev_text for p in ('.', '?', '!', '¿')) and len(prev_toks) <= 3 and len(toks) <= 2:
                        start_idx = idx - 1
                first_tok = seg_list[start_idx]['tokens'][0]
                if not first_tok['word'].startswith('¿'):
                    first_tok['word'] = '¿' + first_tok['word']
                open_q_seg = None
        elif has_open and has_close:
            # Verify '?' isn't before '¿' in the same segment
            if seg_text.find('?') < seg_text.find('¿'):
                open_q_seg = idx
            else:
                open_q_seg = None
        elif open_q_seg is not None:
            # We have an earlier unclosed ¿
            gap_to_curr = toks[0]['start_us'] - seg_list[idx - 1]['tokens'][-1]['end_us']
            first_bare = _strip_edge_punct(toks[0]['word']).lower()
            ANSWER_STARTERS = {'sí', 'si', 'no', 'pero', 'porque', 'en', 'pues', 'bueno', 'mira'}
            if gap_to_curr >= 350000 or first_bare in ANSWER_STARTERS or (idx - open_q_seg) >= 3:
                prev_last = seg_list[idx - 1]['tokens'][-1]
                if not prev_last['word'].endswith(('?', '!', '.')):
                    prev_last['word'] = prev_last['word'] + '?'
                open_q_seg = None

    if open_q_seg is not None and seg_list:
        last_tok = seg_list[-1]['tokens'][-1]
        if not last_tok['word'].endswith(('?', '!', '.')):
            last_tok['word'] = last_tok['word'] + '?'

    # Capitalize the word immediately following ¿ or ¡ (unless entire script is ALL-CAPS)
    if not preserve_all_caps:
        for seg in seg_list:
            for t in seg['tokens']:
                w = t['word']
                if w.startswith(('¿', '¡')) and len(w) > 1 and w[1].islower():
                    t['word'] = w[0] + w[1].upper() + w[2:]

    result = []
    for idx, seg in enumerate(seg_list):
        if not seg['tokens']:
            continue
        item_out = _build_item_from_tokens(seg['template'], seg['tokens'], keep_punctuation=keep_punctuation)
        item_out['index'] = idx
        if seg['absorbed']:
            item_out['absorbed_indices'] = [x for x in seg['absorbed'] if x is not None]
        result.append(item_out)
    return result


def rebalance_subtitle_segments(
    raw_items: List[Dict[str, Any]],
    max_chars: int = HARD_MAX_LINE_CHARS,
    max_words: int = 3,
    keep_punctuation: bool = False
) -> List[Dict[str, Any]]:
    """
    Re-chunks CapCut subtitle segments along Spanish syntactic, phrase, and acoustic
    boundaries so that:
    1. Broken words ('s') and standalone question marks ('¿', '?') are repaired.
    2. Sentences keep grammatical continuity across lines (predicates stay completed,
       'clínica Gala' stays together, 'sígueme para más' stays unified as a CTA).
    3. Ultra-short 1-word functional lines ('que', 'la', 'el', 'es', 'con', 'para', etc.)
       are merged with the adjacent line they grammatically belong to.
    """
    if not raw_items:
        return []

    fixed_items = fix_question_marks_and_broken_tokens(raw_items, keep_punctuation=keep_punctuation)
    if not fixed_items:
        return []

    full_sample = " ".join(it.get('text', '') for it in fixed_items)
    preserve_all_caps = bool(full_sample) and not any(c.islower() for c in full_sample)

    segs = []
    for it in fixed_items:
        toks = _extract_word_tokens(it)
        if toks:
            segs.append({
                'template': dict(it),
                'tokens': toks,
                'absorbed': list(it.get('absorbed_indices', []))
            })

    if not segs:
        return []

    INTENSIFIERS_AND_COPULAS = {
        'es', 'son', 'está', 'esta', 'están', 'estan', 'fue', 'era', 'fueron', 'será', 'sera',
        'completamente', 'totalmente', 'absolutamente', 'muy', 'tan', 'más', 'mas', 'menos',
        'super', 'súper', 'bastante', 'demasiado', 'realmente', 'total'
    }
    CLAUSE_OR_PREP_STARTERS = {
        'en', 'para', 'por', 'con', 'sin', 'sobre', 'hacia', 'hasta', 'desde', 'entre',
        'donde', 'cuando', 'como', 'porque', 'aunque', 'pero', 'sino', 'si', 'que', 'y', 'o',
        'sígueme', 'sigueme', 'síguenos', 'siguenos', 'escríbeme', 'escribeme', 'comenta',
        'comparte', 'guarda', 'agenda', 'visítanos', 'visitanos'
    }
    PROPER_HEAD_NOUNS = {'clínica', 'clinica', 'doctor', 'doctora', 'dr', 'dra', 'hospital', 'centro', 'instituto', 'san', 'santa'}
    PROPER_KNOWN_NAMES = {'gala', 'unique', 'dentok'}
    CTA_STARTERS = {'sígueme', 'sigueme', 'síguenos', 'siguenos', 'escríbeme', 'escribeme', 'comenta', 'comparte', 'guarda', 'agenda', 'visítanos', 'visitanos', 'haz', 'dale'}
    CTA_CONTINUATIONS = {'para', 'en', 'el', 'la', 'los', 'las', 'este', 'esta', 'más', 'mas', 'clic', 'click', 'tu', 'un', 'una', 'si', 'y'}
    DANGLING_END_WORDS = {
        'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas',
        'de', 'del', 'al', 'a', 'en', 'con', 'por', 'para', 'sin', 'sobre', 'tras',
        'que', 'y', 'e', 'o', 'u', 'pero', 'aunque', 'porque', 'como', 'cuando', 'donde', 'si',
        'no', 'se', 'me', 'te', 'le', 'les', 'nos', 'lo', 'mi', 'tu', 'su', 'mis', 'tus', 'sus',
        'este', 'esta', 'estos', 'estas', 'ese', 'esa', 'esos', 'esas'
    }
    _REL_OPENER_PREPS = {'por', 'en', 'de', 'con', 'para', 'sin', 'sobre', 'a'}
    _REL_OPENER_ARTS = {'el', 'la', 'lo', 'los', 'las'}
    _PERIPHRASIS_AUX_WORDS = {
        'tiene', 'tienen', 'tengo', 'tienes', 'tenemos', 'tenía', 'tenían',
        'voy', 'vas', 'va', 'van', 'vamos', 'iba', 'iban',
        'vuelve', 'vuelven', 'empieza', 'empiezan',
    }
    SOFT_MAX_WORDS = max(1, int(max_words or 3))
    HARD_MAX_CHARS = max(1, int(max_chars or HARD_MAX_LINE_CHARS))
    SOFT_MAX_CHARS = max(HARD_MAX_CHARS + 2, 20) if HARD_MAX_CHARS > HARD_MAX_LINE_CHARS else HARD_MAX_CHARS
    ORPHAN_MERGE_MAX_CHARS = max(HARD_MAX_CHARS, 16) if HARD_MAX_CHARS > HARD_MAX_LINE_CHARS else HARD_MAX_CHARS
    MAX_FLOW_GAP_US = 600000

    def _seg_text(s_entry: Dict[str, Any]) -> str:
        return " ".join(t['word'] for t in s_entry['tokens'])

    def _ends_sentence(s_entry: Dict[str, Any]) -> bool:
        w = s_entry['tokens'][-1]['word'] if s_entry['tokens'] else ''
        return w.endswith(('?', '!', '.'))

    # Pass 1: Split overcrowded multi-clause segments before rebalancing
    def _split_multi_clause_entry(s_entry: Dict[str, Any]) -> List[Dict[str, Any]]:
        toks = s_entry['tokens']
        if len(toks) < 2:
            return [s_entry]
        raw_src = str(s_entry['template'].get('raw_asr_text') or s_entry['template'].get('orig_text') or '')
        raw_words = raw_src.split()
        has_aligned_raw = len(raw_words) == len(toks)
        cap_source = raw_words if has_aligned_raw else [t['word'] for t in toks]
        all_cap_tokens = not preserve_all_caps and all(
            (not any(c.islower() for c in w)) for w in cap_source if any(c.isalpha() for c in w)
        )
        split_idx = None
        split_at_cap_starter = False
        for k in range(1, len(toks)):
            bare_k = _strip_edge_punct(toks[k]['word']).lower()
            prev_bare = _strip_edge_punct(toks[k - 1]['word']).lower()
            if len(toks) >= 4 and bare_k in CTA_STARTERS and k + 1 < len(toks):
                nxt_bare = _strip_edge_punct(toks[k + 1]['word']).lower()
                if nxt_bare in CTA_CONTINUATIONS:
                    split_idx = k
                    break
            if len(toks) >= 4 and bare_k == 'en' and k + 1 < len(toks):
                nxt_bare = _strip_edge_punct(toks[k + 1]['word']).lower()
                if nxt_bare in PROPER_HEAD_NOUNS:
                    split_idx = k
                    break
            if k >= 2 and toks[k - 1]['word'].endswith(('?', '!', '.')):
                split_idx = k
                break
            src_w = cap_source[k]
            prev_src_w = cap_source[k - 1]
            if (
                not preserve_all_caps
                and not all_cap_tokens
                and bare_k in _MID_SENTENCE_CAPITAL_STARTERS
                and any(c.isupper() for c in src_w[:2])
                and any(c.islower() for c in prev_src_w)
                and prev_bare not in {'que', 'y', 'o', 'e', 'u', 'pero', 'como', 'si', 'cuando', 'porque', 'aunque', 'de', 'del', 'a', 'al', 'en', 'con', 'por', 'para', 'sin', 'sobre', 'lo'}
            ):
                split_idx = k
                split_at_cap_starter = True
                break
        if not split_idx:
            return [s_entry]
        t_a = toks[:split_idx]
        t_b = toks[split_idx:]
        if split_at_cap_starter and t_b:
            m_cap = re.search(r'[A-Za-zÁÉÍÓÚÑÜáéíóúñü]', t_b[0]['word'])
            if m_cap:
                w0 = t_b[0]['word']
                t_b[0]['word'] = w0[:m_cap.start()] + w0[m_cap.start()].upper() + w0[m_cap.start() + 1:]
        tpl_a = dict(s_entry['template'])
        tpl_b = dict(s_entry['template'])
        tpl_b['item'] = None
        if has_aligned_raw:
            tpl_a['raw_asr_text'] = " ".join(raw_words[:split_idx])
            tpl_b['raw_asr_text'] = " ".join(raw_words[split_idx:])
        left = {'template': tpl_a, 'tokens': t_a, 'absorbed': list(s_entry['absorbed'])}
        right = {'template': tpl_b, 'tokens': t_b, 'absorbed': []}
        return _split_multi_clause_entry(left) + _split_multi_clause_entry(right)

    split_segs = []
    for s_entry in segs:
        split_segs.extend(_split_multi_clause_entry(s_entry))
    segs = split_segs

    # Pass 2: Iterative syntactic boundary rebalancing across adjacent segments
    for _pass in range(4):
        changed = False
        i = 0
        while i < len(segs) - 1:
            curr = segs[i]
            nxt = segs[i + 1]
            c_toks = curr['tokens']
            n_toks = nxt['tokens']
            if not c_toks or not n_toks:
                i += 1
                continue

            gap_us = n_toks[0]['start_us'] - c_toks[-1]['end_us']
            if gap_us > MAX_FLOW_GAP_US or _ends_sentence(curr):
                i += 1
                continue

            last_c = _strip_edge_punct(c_toks[-1]['word']).lower()
            first_n = _strip_edge_punct(n_toks[0]['word']).lower()
            second_n = _strip_edge_punct(n_toks[1]['word']).lower() if len(n_toks) >= 2 else ''

            moved = False

            # 2a. Pull proper compound tail backward (e.g. "en clinica" + "gala..." -> "en clínica Gala", or "Gala" + "Unique...")
            if (
                (
                    last_c in PROPER_HEAD_NOUNS
                    and first_n not in CLAUSE_OR_PREP_STARTERS
                    and not (first_n == 'gala' and second_n in GALA_UNIQUE_SECOND_WORDS)
                )
                or (last_c == 'gala' and first_n in GALA_UNIQUE_SECOND_WORDS)
            ) and len(n_toks) >= 2:
                cand_len = len(_seg_text(curr)) + 1 + len(n_toks[0]['word'])
                if len(c_toks) + 1 <= SOFT_MAX_WORDS and cand_len <= SOFT_MAX_CHARS:
                    moved_tok = n_toks.pop(0)
                    c_toks.append(moved_tok)
                    moved = True

            # 2b. Pull predicate/adjective completion backward (e.g. "es completamente" + "curable en clinica" -> "es completamente curable" + "en clinica")
            elif (
                last_c in INTENSIFIERS_AND_COPULAS
                and len(n_toks) >= 2
                and first_n not in CLAUSE_OR_PREP_STARTERS
                and (second_n in CLAUSE_OR_PREP_STARTERS or len(n_toks) >= 3)
            ):
                cand_len = len(_seg_text(curr)) + 1 + len(n_toks[0]['word'])
                if len(c_toks) + 1 <= SOFT_MAX_WORDS and cand_len <= SOFT_MAX_CHARS:
                    moved_tok = n_toks.pop(0)
                    c_toks.append(moved_tok)
                    moved = True

            # 2b-bis. Keep compound relative openers ('por las que', 'en el que', 'de la que') together
            elif (
                len(c_toks) >= 3
                and _strip_edge_punct(c_toks[-2]['word']).lower() in _REL_OPENER_PREPS
                and last_c in _REL_OPENER_ARTS
                and first_n == 'que'
                and not c_toks[-2]['word'].endswith(('?', '!', '.', ','))
                and not c_toks[-1]['word'].endswith(('?', '!', '.', ','))
                and not (len(c_toks) == 3 and _strip_edge_punct(c_toks[0]['word']).lower() in STRICT_ORPHAN_WORDS)
            ):
                bridge_len = len(c_toks[-2]['word']) + 1 + len(c_toks[-1]['word']) + 1 + len(n_toks[0]['word'])
                if bridge_len <= max(SOFT_MAX_CHARS, 14):
                    rem_n_orphan = (
                        len(n_toks) == 2
                        and _strip_edge_punct(n_toks[1]['word']).lower() in STRICT_ORPHAN_WORDS
                        and i + 2 >= len(segs)
                    )
                    if len(n_toks) == 1 and bridge_len <= max(SOFT_MAX_CHARS, 14):
                        t2 = c_toks.pop()
                        t1 = c_toks.pop()
                        n_toks.insert(0, t2)
                        n_toks.insert(0, t1)
                        moved = True
                    elif len(n_toks) >= 2 and not rem_n_orphan:
                        t2 = c_toks.pop()
                        t1 = c_toks.pop()
                        q_tok = n_toks.pop(0)
                        mid_tpl = dict(curr['template'])
                        mid_tpl['item'] = None
                        segs.insert(i + 1, {'template': mid_tpl, 'tokens': [t1, t2, q_tok], 'absorbed': []})
                        moved = True

            # 2c. Push CTA starter forward (e.g. "la curamos sigueme" + "para mas" -> "la curamos" + "sigueme para mas")
            elif len(c_toks) >= 2 and last_c in CTA_STARTERS and first_n in CTA_CONTINUATIONS:
                cand_len = len(c_toks[-1]['word']) + 1 + len(_seg_text(nxt))
                if len(n_toks) + 1 <= SOFT_MAX_WORDS and cand_len <= SOFT_MAX_CHARS:
                    moved_tok = c_toks.pop()
                    n_toks.insert(0, moved_tok)
                    moved = True

            # 2c-bis. Keep verbal periphrases ('tienen que', 'va a', 'empiezan a') together across segments
            elif (
                len(c_toks) >= 3
                and last_c in _PERIPHRASIS_AUX_WORDS
                and first_n in {'que', 'a'}
                and not c_toks[-1]['word'].endswith(('?', '!', '.', ','))
            ):
                rem_n_orphan = (
                    len(n_toks) == 2
                    and _strip_edge_punct(n_toks[1]['word']).lower() in STRICT_ORPHAN_WORDS
                    and i + 2 >= len(segs)
                )
                if len(n_toks) + 1 <= SOFT_MAX_WORDS and (len(c_toks[-1]['word']) + 1 + len(_seg_text(nxt))) <= SOFT_MAX_CHARS:
                    n_toks.insert(0, c_toks.pop())
                    moved = True
                elif len(n_toks) >= 2 and (len(c_toks[-1]['word']) + 1 + len(n_toks[0]['word'])) <= max(HARD_MAX_CHARS, 13) and not rem_n_orphan:
                    aux_tok = c_toks.pop()
                    rel_tok = n_toks.pop(0)
                    mid_tpl = dict(curr['template'])
                    mid_tpl['item'] = None
                    segs.insert(i + 1, {'template': mid_tpl, 'tokens': [aux_tok, rel_tok], 'absorbed': []})
                    moved = True

            # 2d. Move dangling article/preposition/conjunction forward so segment never ends dangling on 'la', 'en', 'de', 'que', 'para'
            elif (
                len(c_toks) >= 2
                and last_c in DANGLING_END_WORDS
                and not c_toks[-1]['word'].endswith(('?', '!', '.', ','))
                and first_n not in CTA_STARTERS
            ):
                is_intact_rel_opener = (
                    len(c_toks) == 3
                    and _strip_edge_punct(c_toks[0]['word']).lower() in _REL_OPENER_PREPS
                    and _strip_edge_punct(c_toks[1]['word']).lower() in _REL_OPENER_ARTS
                    and last_c == 'que'
                )
                is_intact_periphrasis = (
                    last_c in {'que', 'a'}
                    and _strip_edge_punct(c_toks[-2]['word']).lower() in _PERIPHRASIS_AUX_WORDS
                )
                if len(n_toks) == 1 and len(c_toks) + 1 <= SOFT_MAX_WORDS and (len(_seg_text(curr)) + 1 + len(n_toks[0]['word'])) <= SOFT_MAX_CHARS:
                    moved_tok = n_toks.pop(0)
                    c_toks.append(moved_tok)
                    moved = True
                elif (
                    not is_intact_rel_opener
                    and not is_intact_periphrasis
                    and len(n_toks) + 1 <= SOFT_MAX_WORDS
                    and (len(c_toks[-1]['word']) + 1 + len(_seg_text(nxt))) <= SOFT_MAX_CHARS
                    and not (len(c_toks) == 2 and _strip_edge_punct(c_toks[0]['word']).lower() in (ORPHAN_SHORT_WORDS | {'hay'}))
                ):
                    moved_tok = c_toks.pop()
                    n_toks.insert(0, moved_tok)
                    moved = True

            if moved:
                changed = True
                if not n_toks:
                    curr['absorbed'].append(nxt['template'].get('index'))
                    curr['absorbed'].extend(nxt['absorbed'])
                    segs.pop(i + 1)
                    continue
                if not c_toks:
                    nxt['absorbed'].append(curr['template'].get('index'))
                    nxt['absorbed'].extend(curr['absorbed'])
                    segs.pop(i)
                    continue

            i += 1
        if not changed:
            break

    # Pass 3: Unify tiny / 1-word orphan segments ('que', 'la', 'el', 'es', 'para', 'con', 'pero', etc.)
    changed = True
    while changed and len(segs) > 1:
        changed = False
        i = 0
        while i < len(segs):
            curr = segs[i]
            toks = curr['tokens']
            if len(toks) == 1:
                w = toks[0]['word']
                w_bare = _strip_edge_punct(w).lower()
                is_tiny = (not w_bare.isdigit()) and ((w_bare in ORPHAN_SHORT_WORDS) or (len(w_bare) <= 1))

                if is_tiny and len(segs) > 1:
                    is_cap_sentence_starter = (
                        not preserve_all_caps
                        and bool(w[:1].isupper())
                        and w_bare in _MID_SENTENCE_CAPITAL_STARTERS
                    )
                    prefer_forward = (
                        (w_bare in PROCLITIC_ORPHAN_WORDS or w.startswith(('¿', '¡')) or is_cap_sentence_starter)
                        and not w.endswith(('?', '!', '.'))
                    )
                    if i == len(segs) - 1:
                        prefer_forward = False
                    elif i == 0:
                        prefer_forward = True

                    merged_ok = False
                    directions = ('fwd', 'bwd') if prefer_forward else ('bwd', 'fwd')
                    for direction in directions:
                        if direction == 'fwd' and i + 1 < len(segs):
                            nxt = segs[i + 1]
                            gap_us = nxt['tokens'][0]['start_us'] - toks[-1]['end_us']
                            comb_words = len(nxt['tokens']) + 1
                            comb_chars = len(w) + 1 + len(_seg_text(nxt))
                            within_budget = (
                                (comb_words <= SOFT_MAX_WORDS and comb_chars <= ORPHAN_MERGE_MAX_CHARS)
                                or (SOFT_MAX_WORDS == 3 and comb_words == 4 and comb_chars <= min(14, HARD_MAX_CHARS))
                            )
                            if not w.endswith(('?', '!', '.')) and gap_us <= 650000 and within_budget:
                                nxt['tokens'].insert(0, toks[0])
                                nxt['absorbed'].append(curr['template'].get('index'))
                                nxt['absorbed'].extend(curr['absorbed'])
                                segs.pop(i)
                                merged_ok = True
                                changed = True
                                break
                        elif direction == 'bwd' and i > 0:
                            prev = segs[i - 1]
                            gap_us = toks[0]['start_us'] - prev['tokens'][-1]['end_us']
                            comb_words = len(prev['tokens']) + 1
                            comb_chars = len(_seg_text(prev)) + 1 + len(w)
                            within_budget = (
                                (comb_words <= SOFT_MAX_WORDS and comb_chars <= ORPHAN_MERGE_MAX_CHARS)
                                or (SOFT_MAX_WORDS == 3 and comb_words == 4 and comb_chars <= min(14, HARD_MAX_CHARS))
                            )
                            if not w.startswith(('¿', '¡')) and not is_cap_sentence_starter and not _ends_sentence(prev) and gap_us <= 650000 and within_budget:
                                prev['tokens'].append(toks[0])
                                prev['absorbed'].append(curr['template'].get('index'))
                                prev['absorbed'].extend(curr['absorbed'])
                                segs.pop(i)
                                merged_ok = True
                                changed = True
                                break
                    if merged_ok:
                        continue

                    # 3b. Rescue strict functional orphans ('para', 'de', 'con', 'por', 'y', 'el', etc.) blocked by tight max_chars:
                    # First try rebalancing by stealing the leading word from the next segment ('para' + 'que puedas' -> 'para que' + 'puedas')
                    # Then try merging up to 16 chars if it avoids stranding a lone strict orphan on screen.
                    if w_bare in STRICT_ORPHAN_WORDS:
                        stole_token = False
                        if prefer_forward and i + 1 < len(segs) and not w.endswith(('?', '!', '.')):
                            nxt = segs[i + 1]
                            gap_us = nxt['tokens'][0]['start_us'] - toks[-1]['end_us']
                            if gap_us <= 850000 and len(nxt['tokens']) >= 2:
                                stolen = nxt['tokens'][0]
                                cand_chars = len(w) + 1 + len(stolen['word'])
                                nxt_rem_bare = _strip_edge_punct(nxt['tokens'][1]['word']).lower() if len(nxt['tokens']) == 2 else ''
                                rem_lone_orphan = (len(nxt['tokens']) == 2 and nxt_rem_bare in STRICT_ORPHAN_WORDS)
                                if cand_chars <= max(HARD_MAX_CHARS, 15) and not rem_lone_orphan:
                                    curr['tokens'].append(nxt['tokens'].pop(0))
                                    stole_token = True
                                    changed = True
                                    # If stealing left a 1-word nxt, coalesce it forward when it fits cleanly (e.g. 'puedas' + 'elegir' -> 'puedas elegir')
                                    if len(nxt['tokens']) == 1 and i + 2 < len(segs):
                                        n2 = segs[i + 2]
                                        nt0 = nxt['tokens'][0]
                                        gap2_us = n2['tokens'][0]['start_us'] - nt0['end_us']
                                        comb2_words = 1 + len(n2['tokens'])
                                        comb2_chars = len(nt0['word']) + 1 + len(_seg_text(n2))
                                        if (
                                            not nt0['word'].endswith(('?', '!', '.'))
                                            and gap2_us <= 500000
                                            and comb2_words <= SOFT_MAX_WORDS
                                            and comb2_chars <= max(HARD_MAX_CHARS, 13)
                                        ):
                                            n2['tokens'].insert(0, nt0)
                                            n2['absorbed'].append(nxt['template'].get('index'))
                                            n2['absorbed'].extend(nxt['absorbed'])
                                            segs.pop(i + 1)

                        if not stole_token:
                            elastic_cap = max(HARD_MAX_CHARS + 3, PAIR_ELASTIC_MAX_CHARS)
                            for direction in directions:
                                if direction == 'fwd' and i + 1 < len(segs):
                                    nxt = segs[i + 1]
                                    gap_us = nxt['tokens'][0]['start_us'] - toks[-1]['end_us']
                                    comb_words = len(nxt['tokens']) + 1
                                    comb_chars = len(w) + 1 + len(_seg_text(nxt))
                                    if (
                                        not w.endswith(('?', '!', '.'))
                                        and gap_us <= 850000
                                        and comb_words <= SOFT_MAX_WORDS
                                        and (comb_chars <= elastic_cap or len(nxt['tokens']) == 1)
                                    ):
                                        nxt['tokens'].insert(0, toks[0])
                                        nxt['absorbed'].append(curr['template'].get('index'))
                                        nxt['absorbed'].extend(curr['absorbed'])
                                        segs.pop(i)
                                        merged_ok = True
                                        changed = True
                                        break
                                elif direction == 'bwd' and i > 0:
                                    prev = segs[i - 1]
                                    gap_us = toks[0]['start_us'] - prev['tokens'][-1]['end_us']
                                    comb_words = len(prev['tokens']) + 1
                                    comb_chars = len(_seg_text(prev)) + 1 + len(w)
                                    if (
                                        not w.startswith(('¿', '¡'))
                                        and not is_cap_sentence_starter
                                        and not _ends_sentence(prev)
                                        and gap_us <= 850000
                                        and comb_words <= SOFT_MAX_WORDS
                                        and comb_chars <= elastic_cap
                                    ):
                                        prev['tokens'].append(toks[0])
                                        prev['absorbed'].append(curr['template'].get('index'))
                                        prev['absorbed'].extend(curr['absorbed'])
                                        segs.pop(i)
                                        merged_ok = True
                                        changed = True
                                        break
                            if merged_ok:
                                continue
            i += 1

    # Pass 4: Spanish orthography polish on rebalanced tokens (clinica->clínica, Gala, Sígueme para más, sentence start capitalization)
    if not preserve_all_caps:
        for seg_idx, s_entry in enumerate(segs):
            toks = s_entry['tokens']
            for k, t in enumerate(toks):
                w = t['word']
                m = re.match(r'^([¿¡"\'\(\[\{]*)(.*?)([?!,.;:\'"\)\]\}]*)$', w)
                if not m:
                    continue
                lead, core, trail = m.groups()
                if not core:
                    continue
                c_low = core.lower()
                prev_c_low = _strip_edge_punct(toks[k - 1]['word']).lower() if k > 0 else ''
                nxt_c_low = _strip_edge_punct(toks[k + 1]['word']).lower() if k + 1 < len(toks) else ''

                if c_low == 'clinica':
                    core = 'Clínica' if core[0].isupper() else 'clínica'
                elif c_low == 'sigueme':
                    core = 'Sígueme' if core[0].isupper() else 'sígueme'
                elif c_low == 'mas' and prev_c_low in ('para', 'mucho', 'nada', 'algo', 'cada', 'aún', 'todavía'):
                    core = 'más'
                elif c_low in PROPER_KNOWN_NAMES:
                    core = core[0].upper() + core[1:].lower()
                t['word'] = f"{lead}{core}{trail}"

            # Capitalize first word of video, after sentence-ending punctuation, after ¿/¡, or CTA opener
            if toks:
                w0 = toks[0]['word']
                m0 = re.match(r'^([¿¡"\'\(\[\{]*)(.*?)([?!,.;:\'"\)\]\}]*)$', w0)
                if m0:
                    lead0, core0, trail0 = m0.groups()
                    prev_ended = (seg_idx > 0 and _ends_sentence(segs[seg_idx - 1]))
                    is_cta_start = _strip_edge_punct(w0).lower() in CTA_STARTERS and len(toks) >= 2 and _strip_edge_punct(toks[1]['word']).lower() in CTA_CONTINUATIONS
                    is_q_start = ('¿' in lead0 or '¡' in lead0)
                    if core0 and core0[0].islower() and (prev_ended or is_cta_start or is_q_start):
                        toks[0]['word'] = f"{lead0}{core0[0].upper()}{core0[1:]}{trail0}"

    out_items = []
    for idx, s_entry in enumerate(segs):
        if not s_entry['tokens']:
            continue
        it_out = _build_item_from_tokens(s_entry['template'], s_entry['tokens'], keep_punctuation=keep_punctuation)
        it_out['index'] = idx
        if s_entry['absorbed']:
            it_out['absorbed_indices'] = [x for x in s_entry['absorbed'] if x is not None]
        out_items.append(it_out)

    return fix_question_marks_and_broken_tokens(out_items, keep_punctuation=keep_punctuation)







