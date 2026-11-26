"""
CC Subs Pro - Grammar & Orthography Checker (OpenRouter AI)
Verifies Spanish accents (tildes), diacritics, and spelling across CapCut subtitles
without modifying segment timings, animations, fonts, or styling tracks.
"""

import copy
import difflib
import json
import os
import re
from typing import Any, Callable, Dict, List, Optional

from core.capcut_draft import CapCutProject, SubtitleItem
from core.text_utils import COMMON_LOWERCASE_WORDS, _normalize_spanish_punct_spacing


def _resolve_keep_punctuation(preset_name: Optional[str]) -> bool:
    """Checks whether the active preset preserves periods and commas (e.g. Abde)."""
    if not preset_name:
        return False
    styles_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'styles')
    presets_file = os.path.join(styles_dir, 'presets.json')
    norm = preset_name.lower().strip()
    if os.path.isfile(presets_file):
        try:
            with open(presets_file, 'r', encoding='utf-8') as f:
                presets = json.load(f)
            for candidate in (
                norm,
                norm.replace('letra ', '').replace('letra_', '').strip(),
                norm.replace(' ', '_'),
            ):
                if candidate in presets:
                    return bool(presets[candidate].get('keep_punctuation', False))
        except Exception:
            pass
    return 'abde' in norm


def collect_grammar_segments(project: CapCutProject) -> List[Dict[str, Any]]:
    """
    Extracts non-empty subtitle items from all text tracks sorted chronologically.
    Deduplicates shared material IDs so each unique text material is checked once.
    """
    project._parse_subtitles()
    segments: List[Dict[str, Any]] = []
    seen_materials = set()

    for sub in sorted(project.subtitles, key=lambda s: (s.start_us, s.track_index)):
        txt = sub.text or ""
        if not txt.strip() or not re.search(r'[\wáéíóúÁÉÍÓÚñÑüÜ]', txt):
            continue
        mat_id = sub.material_id or sub.segment_id
        if mat_id in seen_materials:
            continue
        seen_materials.add(mat_id)
        segments.append({
            "index": len(segments),
            "track_index": sub.track_index,
            "segment_id": sub.segment_id,
            "material_id": sub.material_id,
            "start": sub.start_us,
            "end": sub.start_us + sub.duration_us,
            "duration": sub.duration_us,
            "text": txt,
            "sub_item": sub,
        })
    return segments


def _reinsert_line_break(orig_text: str, flat_corrected: str) -> str:
    """Preserves a 2-line '\\n' break from orig_text if AI flattened it onto one line."""
    if '\n' not in orig_text or '\n' in flat_corrected:
        return flat_corrected
    orig_lines = [ln.strip() for ln in orig_text.split('\n') if ln.strip()]
    words = flat_corrected.split()
    if len(orig_lines) != 2 or len(words) < 2:
        return flat_corrected
    target_w = len(orig_lines[0].split())
    split_at = max(1, min(len(words) - 1, target_w))
    return " ".join(words[:split_at]) + "\n" + " ".join(words[split_at:])


def normalize_grammar_correction(
    orig_text: str,
    candidate_text: str,
    allow_commas_periods: bool = False,
    prev_text: str = ""
) -> str:
    """
    Sanitizes an AI grammar correction so it respects the original segment's
    casing (ALL CAPS vs mixed/lowercase), line breaks, and punctuation rules.
    """
    if not candidate_text:
        return orig_text

    cand = str(candidate_text).strip()
    cand = "\n".join(
        re.sub(r'\s+', ' ', _normalize_spanish_punct_spacing(ln)).strip()
        for ln in cand.splitlines()
        if ln.strip()
    )
    if not cand:
        return orig_text

    # Reinsert newline if orig had a 2-line split and AI flattened it
    cand = _reinsert_line_break(orig_text, cand)

    # Respect intentional ALL CAPS segments (keeping uppercase Spanish tildes ÁÉÍÓÚ)
    orig_has_alpha = any(c.isalpha() for c in orig_text)
    orig_is_upper = orig_has_alpha and not any(c.islower() for c in orig_text)
    if orig_is_upper:
        cand = cand.upper()
    else:
        # Avoid unprompted capitalization on the first common lowercase word of a mid-sentence segment
        first_orig = orig_text.split()[0] if orig_text.split() else ""
        first_cand = cand.split()[0] if cand.split() else ""
        prev_ended = prev_text.strip().endswith(('.', '?', '!')) if prev_text else False
        if (
            first_orig
            and first_cand
            and first_orig[0].islower()
            and first_cand[0].isupper()
            and not prev_ended
            and not first_cand.startswith(('¿', '¡'))
        ):
            bare_cand = re.sub(r'[^\wáéíóúÁÉÍÓÚñÑüÜ]', '', first_cand).lower()
            if bare_cand in COMMON_LOWERCASE_WORDS:
                cand = cand[0].lower() + cand[1:]

    # Strip unsolicited commas, periods, or colons unless preset keeps punctuation or orig already had them
    orig_has_punc = bool(re.search(r'[,.]', orig_text))
    if not allow_commas_periods and not orig_has_punc:
        cand = re.sub(r'[,.:]+', '', cand)
        cand = "\n".join(re.sub(r'\s+', ' ', ln).strip() for ln in cand.splitlines() if ln.strip())

    # Preserve spacing around ¿?/¡! after any punctuation cleanup
    cand = "\n".join(_normalize_spanish_punct_spacing(ln) for ln in cand.splitlines())
    return cand.strip()


def remap_rich_styles(
    orig_text: str,
    new_text: str,
    styles: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Remaps CapCut rich-text style character ranges [start, end] from orig_text
    to new_text using SequenceMatcher so highlight color/font spans remain aligned
    with their exact words even when characters are added or removed.
    """
    if not styles:
        return []
    new_styles = copy.deepcopy(styles)
    L_new = len(new_text)
    L_orig = len(orig_text)

    if len(new_styles) == 1:
        new_styles[0]['range'] = [0, L_new]
        return new_styles

    if orig_text == new_text or L_orig == 0:
        for st in new_styles:
            r = st.get('range', [0, L_new])
            st['range'] = [max(0, min(int(r[0]), L_new)), max(0, min(int(r[1]), L_new))]
        return new_styles

    # Build monotonic index mapping orig_idx (0..L_orig) -> new_idx (0..L_new)
    orig_to_new = [0] * (L_orig + 1)
    matcher = difflib.SequenceMatcher(None, orig_text, new_text, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            for k in range(i2 - i1 + 1):
                orig_to_new[i1 + k] = j1 + k
        else:
            span_old = i2 - i1
            span_new = j2 - j1
            if span_old == 0:
                orig_to_new[i1] = max(orig_to_new[i1], j2)
            else:
                orig_to_new[i1] = max(orig_to_new[i1], j1)
                for k in range(1, span_old + 1):
                    mapped = j1 + int(round(span_new * (k / float(span_old))))
                    orig_to_new[i1 + k] = max(orig_to_new[i1 + k - 1], min(L_new, mapped))
    for k in range(1, L_orig + 1):
        if orig_to_new[k] < orig_to_new[k - 1]:
            orig_to_new[k] = orig_to_new[k - 1]
    orig_to_new[L_orig] = L_new

    prev_end = 0
    for idx, st in enumerate(new_styles):
        r = st.get('range', [0, L_orig])
        old_s = max(0, min(L_orig, int(r[0])))
        old_e = max(old_s, min(L_orig, int(r[1])))
        new_s = orig_to_new[old_s]
        new_e = orig_to_new[old_e]
        if new_s < prev_end and old_s >= (new_styles[idx - 1].get('range', [0, 0])[1] if idx > 0 else 0):
            new_s = prev_end
        if new_e < new_s:
            new_e = new_s
        if idx == len(new_styles) - 1 and old_e == L_orig:
            new_e = L_new
        st['range'] = [new_s, new_e]
        prev_end = new_e

    return new_styles


def _sync_words_metadata(
    w_dict: Dict[str, Any],
    new_text: str,
    total_dur_ms: int
) -> None:
    """
    Synchronizes text_material['words'] when subtitle spelling changes.
    Preserves acoustic word start_time / end_time if word count is unchanged.
    """
    if not isinstance(w_dict, dict) or 'text' not in w_dict:
        return

    w_texts = w_dict.get('text', [])
    w_starts = w_dict.get('start_time', [])
    w_ends = w_dict.get('end_time', [])

    new_tokens = [t for t in re.split(r'(\s+)', new_text) if t]
    if len(new_tokens) == len(w_texts):
        w_dict['text'] = new_tokens
        return

    new_words = new_text.split()
    old_word_indices = [i for i, wt in enumerate(w_texts) if str(wt).strip()]

    if len(new_words) == len(old_word_indices) and len(w_starts) == len(w_texts) and len(w_ends) == len(w_texts):
        # Word count identical; whitespace formatting changed (e.g. \n) -> update word entries and rebuild spacing
        rebuilt_t = []
        rebuilt_s = []
        rebuilt_e = []
        for k, (nw, old_i) in enumerate(zip(new_words, old_word_indices)):
            if k > 0:
                prev_e = rebuilt_e[-1]
                cur_s = int(w_starts[old_i])
                rebuilt_t.append(" ")
                rebuilt_s.append(prev_e)
                rebuilt_e.append(max(prev_e, cur_s))
            rebuilt_t.append(nw)
            rebuilt_s.append(int(w_starts[old_i]))
            rebuilt_e.append(int(w_ends[old_i]))
        w_dict['text'] = rebuilt_t
        w_dict['start_time'] = rebuilt_s
        w_dict['end_time'] = rebuilt_e
        return

    # Fallback when word count itself changed (e.g. "habeses" -> "a veces" or "por que" -> "porque")
    if len(w_texts) <= 1:
        w_dict['text'] = [new_text]
        return

    if new_words:
        dur_ms = max(100, int(total_dur_ms or 500))
        weights = [max(1, len(w)) for w in new_words]
        total_w = float(sum(weights))
        cur = 0.0
        rebuilt_t, rebuilt_s, rebuilt_e = [], [], []
        for k, (nw, wt) in enumerate(zip(new_words, weights)):
            if k > 0:
                prev_e = rebuilt_e[-1]
                rebuilt_t.append(" ")
                rebuilt_s.append(prev_e)
                rebuilt_e.append(prev_e)
            slice_ms = dur_ms * (wt / total_w)
            s_ms = int(round(cur))
            e_ms = int(round(cur + slice_ms)) if k < len(new_words) - 1 else dur_ms
            rebuilt_t.append(nw)
            rebuilt_s.append(s_ms)
            rebuilt_e.append(max(s_ms + 20, e_ms))
            cur += slice_ms
        w_dict['text'] = rebuilt_t
        w_dict['start_time'] = rebuilt_s
        w_dict['end_time'] = rebuilt_e


def check_project_grammar(
    project: CapCutProject,
    client: Any,
    preset_name: Optional[str] = None,
    keep_punctuation: Optional[bool] = None,
    log_fn: Optional[Callable[[str], None]] = None
) -> Optional[List[Dict[str, Any]]]:
    """
    Runs OpenRouter grammar, accent (tilde), and spelling verification on all
    text segments in a CapCut project.

    Returns:
      - List of proposed fix dicts if API call succeeded (empty `[]` if zero errors).
      - `None` if OpenRouter call failed / API key invalid.
    """
    segments = collect_grammar_segments(project)
    if not segments:
        return []

    eff_keep_punc = _resolve_keep_punctuation(preset_name) if keep_punctuation is None else bool(keep_punctuation)
    if not eff_keep_punc:
        # Also auto-detect if project subtitles already use commas/periods consistently
        punc_hits = sum(1 for s in segments if re.search(r'[,.]', s['text']))
        if punc_hits >= max(2, len(segments) // 3):
            eff_keep_punc = True

    if log_fn:
        log_fn(f"[*] Analizando {len(segments)} subtítulo(s) con OpenRouter ({getattr(client, 'model', 'gemini')})...")

    if not hasattr(client, "check_grammar"):
        if log_fn:
            log_fn("[*] Detectado módulo ai/openrouter_client.py desactualizado; sincronizando módulos de IA desde GitHub...")
        try:
            from core.updater import ensure_ai_modules_up_to_date
            _, updated_files = ensure_ai_modules_up_to_date(force=True)
            if updated_files and log_fn:
                log_fn(f"[OK] Módulos de IA sincronizados: {', '.join(updated_files)}")
        except Exception as sync_err:
            if log_fn:
                log_fn(f"[!] Aviso al sincronizar módulos de IA: {sync_err}")

        import ai.openrouter_client as orc_mod
        refreshed_cls = getattr(orc_mod, "OpenRouterClient", None)
        if refreshed_cls is not None and hasattr(refreshed_cls, "check_grammar"):
            client = refreshed_cls(
                api_key=getattr(client, "api_key", ""),
                model=getattr(client, "model", None) or getattr(orc_mod, "DEFAULT_MODEL", "google/gemini-2.5-flash"),
            )
        else:
            raise RuntimeError(
                "El módulo 'ai/openrouter_client.py' de esta instalación está desactualizado "
                "(no contiene 'check_grammar') y no pudo descargarse automáticamente desde GitHub.\n\n"
                "Verifica tu conexión a internet o haz clic en 'Actualizar' arriba para sincronizar la carpeta 'ai/'."
            )

    payload_segs = [
        {"index": s["index"], "start": s["start"], "end": s["end"], "text": s["text"]}
        for s in segments
    ]
    raw_corrections = client.check_grammar(payload_segs, keep_punctuation=eff_keep_punc)
    if raw_corrections is None:
        return None

    seg_by_idx = {s["index"]: s for s in segments}
    fixes: List[Dict[str, Any]] = []
    seen_indices = set()

    for corr in raw_corrections:
        idx = corr.get("index")
        if idx not in seg_by_idx or idx in seen_indices:
            continue
        seg = seg_by_idx[idx]
        orig_text = seg["text"]
        prev_text = seg_by_idx[idx - 1]["text"] if (idx - 1) in seg_by_idx else ""
        cleaned_cand = normalize_grammar_correction(
            orig_text=orig_text,
            candidate_text=corr.get("corrected_text", ""),
            allow_commas_periods=eff_keep_punc,
            prev_text=prev_text,
        )
        if not cleaned_cand or cleaned_cand == orig_text.strip():
            continue

        seen_indices.add(idx)
        fixes.append({
            "index": idx,
            "track_index": seg["track_index"],
            "segment_id": seg["segment_id"],
            "material_id": seg["material_id"],
            "start_us": seg["start"],
            "end_us": seg["end"],
            "duration_us": seg["duration"],
            "time_str": f"{seg['start'] / 1e6:05.2f}s",
            "original_text": orig_text,
            "corrected_text": cleaned_cand,
            "reason": corr.get("reason", "Corrección ortográfica / tilde"),
            "sub_item": seg["sub_item"],
        })

    fixes.sort(key=lambda f: (f["start_us"], f["track_index"]))
    return fixes


def apply_grammar_fixes(
    project: CapCutProject,
    fixes: List[Dict[str, Any]]
) -> int:
    """
    Applies confirmed grammar/spelling corrections to project SubtitleItems while
    preserving timestamps, animations, fonts, and multi-span rich text styles.
    """
    applied = 0
    for fix in fixes:
        sub: Optional[SubtitleItem] = fix.get("sub_item")
        new_text = (fix.get("corrected_text") or "").strip()
        if not sub or not new_text:
            continue

        orig_text = sub.text or fix.get("original_text", "")
        if new_text == orig_text:
            continue

        sub.parsed_content["text"] = new_text
        styles = sub.parsed_content.get("styles", [])
        if isinstance(styles, list) and styles:
            sub.parsed_content["styles"] = remap_rich_styles(orig_text, new_text, styles)

        if "words" in sub.text_material and isinstance(sub.text_material["words"], dict):
            _sync_words_metadata(
                sub.text_material["words"],
                new_text=new_text,
                total_dur_ms=int(sub.duration_us // 1000),
            )
        if "recognize_text" in sub.text_material:
            sub.text_material["recognize_text"] = new_text

        sub.sync_content_to_material()
        applied += 1

    return applied
