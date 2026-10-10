import os
import re
import json
import uuid
import copy
import logging
from typing import Dict, List, Any, Optional, Tuple
from core.capcut_draft import CapCutProject, SubtitleItem
from core.animator import Animator
from core.platform_paths import resolve_font_path, get_default_click_sound_path, resolve_effect_path, resolve_sticker_path
from core.text_utils import clean_subtitle_text, find_phrase_timing, convert_spanish_numbers_to_digits, sanitize_highlight_phrase, SPANISH_STOPWORDS, align_ai_corrections_to_raw_items
from ai.openrouter_client import OpenRouterClient, DEFAULT_MODEL


logger = logging.getLogger('CCSubsPro.DualStyler')

Y_TOP_DEFAULT = -0.11892300578826598
Y_BOTTOM_DEFAULT = -0.1988648662533823
SCALE_DEFAULT = {"x": 1.3550004042363974, "y": 1.3550004042363974}

NEGATIVE_KEYWORDS = {
    'error', 'errores', 'dolor', 'dolores', 'molestia', 'molestias', 'lesión', 'lesiones',
    'falla', 'fallan', 'daño', 'daños', 'inflamación', 'inflama',
    'fascitis', 'periostitis', 'tendinitis', 'espolón', 'artrosis',
    'fractura', 'deformidad', 'infección', 'infecciones', 'hongo',
    'hongos', 'problema', 'problemas', 'mal', 'malo', 'mala', 'peor',
    'peligro', 'peligroso', 'callo', 'callos', 'dureza', 'durezas',
    'ampolla', 'ampollas', 'herida', 'heridas', 'sobrecarga', 'tensión',
    'rigidez', 'desgaste', 'irritación', 'molesta', 'duele', 'doliendo',
    'roto', 'rotura', 'pronación', 'pronas', 'supinación'
}

def get_effective_font_size(style_cfg: Dict[str, Any], text_str: str) -> float:
    """
    Calcula el tamaño de fuente efectivo en CapCut:
    - Si el preset tiene dynamic_font_size o font_size_short/font_size_long,
      asigna tamaño grande (15-16) para palabras cortas (<=5 caracteres)
      y tamaño menor (al menos 13) para palabras largas.
    - De lo contrario, retorna el font_size estándar del preset.
    """
    if not style_cfg:
        return 10.0
    base_size = float(style_cfg.get('font_size', 10.0))
    clean_text = text_str.strip() if text_str else ""
    clean_len = len(clean_text)

    dyn_cfg = style_cfg.get('dynamic_font_size')
    if dyn_cfg and dyn_cfg.get('enabled', True):
        s_max = dyn_cfg.get('short_max_chars', 5)
        m_max = dyn_cfg.get('medium_max_chars', 8)
        if clean_len <= s_max:
            return float(dyn_cfg.get('short', 16.0))
        elif clean_len <= m_max:
            return float(dyn_cfg.get('medium', 14.5))
        else:
            return float(dyn_cfg.get('long', 13.0))

    if 'font_size_short' in style_cfg and 'font_size_long' in style_cfg:
        if clean_len <= 5:
            return float(style_cfg['font_size_short'])
        elif clean_len <= 8:
            med = style_cfg.get('font_size_medium')
            if med is not None:
                return float(med)
            return (float(style_cfg['font_size_short']) + float(style_cfg['font_size_long'])) / 2.0
        else:
            return float(style_cfg['font_size_long'])

    return base_size


class DualStyler:
    """
    Engine for creating two-layer stacked subtitles (arriba / abajo):
    - Top Track (normal): Aloevera Display Regular, #FFFFFF, y=-0.1189, scale=1.355, no animation
    - Bottom Track (highlight): Behind The Nineties Medium Italic, #2F9FA3, y=-0.1989, scale=1.355,
      slide-in animation 7646371622298914068.
    """

    @staticmethod
    def _is_negative_term(text: str) -> bool:
        if not text:
            return False
        import re
        words = re.findall(r'\b\w+\b', text.lower())
        return any(w in NEGATIVE_KEYWORDS for w in words)

    def __init__(
        self,
        default_style_path: Optional[str] = None,
        highlight_style_path: Optional[str] = None,
        y_top: float = Y_TOP_DEFAULT,
        y_bottom: float = Y_BOTTOM_DEFAULT,
        scale: Optional[Dict[str, float]] = None,
        preset_data: Optional[Dict[str, Any]] = None
    ):
        if preset_data:
            self.preset_data = preset_data
            self.layout = preset_data.get('layout', 'dual')
            top_cfg = preset_data.get('top') or preset_data.get('general', {})
            bot_cfg = preset_data.get('bottom') or preset_data.get('escalera', {})
            self.default_style = top_cfg
            self.highlight_style = bot_cfg
            self.highlight_cfg = preset_data.get('highlight', bot_cfg)
            self.general_cfg = preset_data.get('general', top_cfg)
            self.escalera_cfg = preset_data.get('escalera', bot_cfg)
            self.y_top = top_cfg.get('y', y_top)
            self.y_bottom = bot_cfg.get('y', y_bottom)
            self.top_scale = top_cfg.get('scale', scale or SCALE_DEFAULT)
            self.bot_scale = bot_cfg.get('scale', self.top_scale)
            self.scale = self.top_scale
            self.sound_fx = preset_data.get('sound_fx', {'enabled': True, 'volume': 0.65})
            self.pacing = preset_data.get('pacing', {'min_seconds': 3.0, 'max_seconds': 4.5})
            self.margins = preset_data.get('margins', {'max_chars_per_line': 18, 'max_words_per_line': 3})
            self.preset_name = preset_data.get('name', 'Custom')
            self.stickers_cfg = preset_data.get('stickers', {})
        else:
            self.preset_data = None
            self.layout = 'dual'
            script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            def_path = default_style_path or os.path.join(script_dir, 'styles', 'default.json')
            hl_path = highlight_style_path or os.path.join(script_dir, 'styles', 'highlight.json')
            with open(def_path, 'r', encoding='utf-8') as f:
                self.default_style = json.load(f)
            with open(hl_path, 'r', encoding='utf-8') as f:
                self.highlight_style = json.load(f)
            self.highlight_cfg = self.highlight_style

            self.y_top = y_top
            self.y_bottom = y_bottom
            self.top_scale = scale or SCALE_DEFAULT
            self.bot_scale = scale or SCALE_DEFAULT
            self.scale = scale or SCALE_DEFAULT
            self.sound_fx = {'enabled': True, 'volume': 0.65, 'name': 'Click_Mouse_Click_02(864360)'}
            self.pacing = {'min_seconds': 3.0, 'max_seconds': 4.5}
            self.margins = {'max_chars_per_line': 18, 'max_words_per_line': 3}
            self.preset_name = 'Custom'
            self.stickers_cfg = {}

    @classmethod
    def from_preset(cls, preset_name_or_data: Any) -> 'DualStyler':
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        preset_dict = None
        if isinstance(preset_name_or_data, dict):
            preset_dict = preset_name_or_data
        elif isinstance(preset_name_or_data, str):
            norm = preset_name_or_data.lower().strip()
            p_name = (norm.replace("letra ", "").replace("letra_", "")
                          .replace("preset ", "").replace("preset_", "")
                          .replace("dr. ", "").replace("dr ", "")
                          .replace("dra. ", "").replace("dra ", "")
                          .replace("de ", "").replace("de_", "").strip())

            # 1. ALWAYS PRIORITIZE INDIVIDUAL FILE IN styles/
            candidates = [p_name, norm]
            if 'carrillo' in norm or 'carillo' in norm:
                candidates.insert(0, 'carrillo')
            if 'juan' in norm:
                candidates.insert(0, 'juan')
            if 'angel' in norm or 'ángel' in norm:
                candidates.insert(0, 'angel_cadenas')

            for cand in candidates:
                cand_clean = cand.replace(" ", "_").strip()
                cand_file = os.path.join(script_dir, 'styles', f'{cand_clean}.json')
                if os.path.isfile(cand_file):
                    try:
                        with open(cand_file, 'r', encoding='utf-8') as f:
                            preset_dict = json.load(f)
                            if preset_dict:
                                break
                    except Exception:
                        pass
                cand_file2 = os.path.join(script_dir, 'styles', f'{cand}.json')
                if not preset_dict and os.path.isfile(cand_file2):
                    try:
                        with open(cand_file2, 'r', encoding='utf-8') as f:
                            preset_dict = json.load(f)
                            if preset_dict:
                                break
                    except Exception:
                        pass

            # 2. Fall back to styles/presets.json
            if not preset_dict:
                presets_file = os.path.join(script_dir, 'styles', 'presets.json')
                if os.path.isfile(presets_file):
                    try:
                        with open(presets_file, 'r', encoding='utf-8') as f:
                            presets = json.load(f)
                        if norm in presets:
                            preset_dict = presets[norm]
                        elif p_name in presets:
                            preset_dict = presets[p_name]
                        else:
                            for k, v in presets.items():
                                if k == norm or k == p_name or norm in k:
                                    preset_dict = v
                                    break
                    except Exception:
                        pass

        if not preset_dict:
            gerardo_file = os.path.join(script_dir, 'styles', 'gerardo.json')
            if os.path.isfile(gerardo_file):
                with open(gerardo_file, 'r', encoding='utf-8') as f:
                    preset_dict = json.load(f)

        return cls(preset_data=preset_dict)

    def _create_text_material(self, draft_data: Dict[str, Any], text_str: str, style_cfg: Dict[str, Any], is_highlight: bool = False) -> str:
        text_str = clean_subtitle_text(text_str)
        if style_cfg.get('uppercase', False) or (self.preset_data and self.preset_data.get('uppercase', False)):
            text_str = text_str.upper()
        materials = draft_data.setdefault('materials', {})
        texts = materials.setdefault('texts', [])

        mat_id = str(uuid.uuid4()).upper()
        font_info = style_cfg.get('font', {})
        font_name = font_info.get('name') or style_cfg.get('font_name', 'none')
        font_path = resolve_font_path(font_info.get('path') or style_cfg.get('font_path', ''))
        font_size = get_effective_font_size(style_cfg, text_str)
        base_rgb = style_cfg.get('rgb_color', [1.0, 1.0, 1.0])
        shadow_cfg = style_cfg.get('shadow')

        styles = []
        is_rich = False

        # If Top General text: check if words should be colored in Red (pain/problem) or Yellow (key anatomy)
        if not is_highlight and (style_cfg.get('negative_color') or style_cfg.get('negative_rgb_color')):
            neg_rgb = style_cfg.get('negative_rgb_color', [0.92549, 0.11372, 0.11372])
            hl_rgb = style_cfg.get('highlight_rgb_color', [0.95686, 0.78039, 0.05882])

            import re
            lower_str = text_str.lower()
            matched_spans = []

            # 1. Negative keywords -> Red
            for neg_kw in NEGATIVE_KEYWORDS:
                for m in re.finditer(r'\b' + re.escape(neg_kw) + r'\b', lower_str):
                    matched_spans.append((m.start(), m.end(), neg_rgb))

            # 2. Key anatomical terms -> Yellow
            anatomy_keywords = {
                'tibial', 'fascia', 'gemelos', 'plantar', 'tobillo', 'pie', 'dedos',
                'talón', 'bíceps', 'músculo', 'músculos', 'tendón', 'aquiles', 'arco',
                'articulación', 'pisada', 'propiocepción', 'postura', 'isométrica'
            }
            for akw in anatomy_keywords:
                for m in re.finditer(r'\b' + re.escape(akw) + r'\b', lower_str):
                    if not any(s <= m.start() < e or s < m.end() <= e for s, e, _ in matched_spans):
                        matched_spans.append((m.start(), m.end(), hl_rgb))

            if matched_spans:
                is_rich = True
                matched_spans.sort(key=lambda x: x[0])
                curr_idx = 0
                for s_idx, e_idx, col in matched_spans:
                    if s_idx > curr_idx:
                        s_entry = {
                            "fill": {"content": {"render_type": "solid", "solid": {"color": base_rgb}}},
                            "font": {"path": font_path, "id": ""},
                            "size": font_size,
                            "range": [curr_idx, s_idx]
                        }
                        if shadow_cfg:
                            s_entry["shadows"] = [copy.deepcopy(shadow_cfg)]
                        styles.append(s_entry)

                    hl_entry = {
                        "fill": {"content": {"render_type": "solid", "solid": {"color": col}}},
                        "font": {"path": font_path, "id": ""},
                        "size": font_size,
                        "range": [s_idx, e_idx],
                        "useLetterColor": True
                    }
                    if shadow_cfg:
                        hl_entry["shadows"] = [copy.deepcopy(shadow_cfg)]
                    styles.append(hl_entry)
                    curr_idx = e_idx

                if curr_idx < len(text_str):
                    s_entry = {
                        "fill": {"content": {"render_type": "solid", "solid": {"color": base_rgb}}},
                        "font": {"path": font_path, "id": ""},
                        "size": font_size,
                        "range": [curr_idx, len(text_str)]
                    }
                    if shadow_cfg:
                        s_entry["shadows"] = [copy.deepcopy(shadow_cfg)]
                    styles.append(s_entry)

        if not styles:
            style_entry = {
                "fill": {
                    "content": {
                        "render_type": "solid",
                        "solid": {"color": base_rgb}
                    }
                },
                "font": {
                    "path": font_path,
                    "id": ""
                },
                "size": font_size,
                "range": [0, len(text_str)]
            }
            if is_highlight:
                style_entry["useLetterColor"] = True

            if shadow_cfg:
                style_entry["shadows"] = [copy.deepcopy(shadow_cfg)]
            styles = [style_entry]

        inner_content = {
            "text": text_str,
            "styles": styles
        }

        mat_obj = {
            "id": mat_id,
            "type": "subtitle",
            "recognize_task_id": "manual_styled",
            "recognize_text": text_str,
            "name": "",
            "content": json.dumps(inner_content, ensure_ascii=False, separators=(',', ':')),
            "base_content": json.dumps(inner_content, ensure_ascii=False, separators=(',', ':')),
            "font_path": font_path,
            "font_title": font_name,
            "font_id": "",
            "font_resource_id": "",
            "font_source_platform": 0,
            "fonts": [],
            "letter_spacing": style_cfg.get('letter_spacing', 0.0),
            "font_size": font_size,
            "text_color": style_cfg.get('color', '#FFFFFF'),
            "is_rich_text": is_rich,
            "has_shadow": bool(shadow_cfg),
            "words": {"start_time": [0], "end_time": [1000], "text": [text_str]}
        }
        if 'line_max_width' in style_cfg:
            mat_obj['line_max_width'] = float(style_cfg['line_max_width'])
        if shadow_cfg:
            mat_obj['shadow_color'] = shadow_cfg.get('color', '#000000')
            mat_obj['shadow_alpha'] = float(shadow_cfg.get('alpha', 0.5))
            mat_obj['shadow_distance'] = float(shadow_cfg.get('distance', 3.0))
            mat_obj['shadow_angle'] = float(shadow_cfg.get('angle', -45.0))
            mat_obj['shadow_smoothing'] = float(shadow_cfg.get('diffuse', 0.45))
        texts.append(mat_obj)
        return mat_id

    def _create_animation(self, draft_data: Dict[str, Any], duration_us: int = 500000) -> Optional[str]:
        anim_cfg = self.highlight_style.get('animation', {})
        if not anim_cfg.get('enabled', True):
            return None

        materials = draft_data.setdefault('materials', {})
        mat_anims = materials.setdefault('material_animations', [])

        anim_id = str(uuid.uuid4()).upper()
        res_id = str(anim_cfg.get('resource_id', '7646371622298914068'))
        anim_dur = min(duration_us, anim_cfg.get('duration', 500000))
        anim_path = anim_cfg.get('path', '')
        if not anim_path or not os.path.exists(anim_path):
            anim_path = resolve_effect_path(res_id, anim_path)
        anim_name = anim_cfg.get('name', 'Entrada deslizante desde la izquierda')
        cat_id = anim_cfg.get('category_id', 'ruchang')
        cat_name = anim_cfg.get('category_name', 'Entrada')
        anim_type = anim_cfg.get('type', 'in')

        new_anim = {
            "id": anim_id,
            "type": "sticker_animation",
            "animations": [{
                "id": res_id,
                "type": anim_type,
                "start": 0,
                "duration": anim_dur,
                "path": anim_path,
                "platform": "all",
                "resource_id": res_id,
                "third_resource_id": res_id,
                "source_platform": 1,
                "name": anim_name,
                "category_id": cat_id,
                "category_name": cat_name,
                "panel": "",
                "material_type": "sticker",
                "anim_adjust_params": None,
                "request_id": ""
            }],
            "multi_language_current": "none"
        }
        mat_anims.append(new_anim)
        return anim_id

    def _ensure_text_tracks(self, draft_data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        tracks = draft_data.setdefault('tracks', [])
        text_tracks = [t for t in tracks if t.get('type') == 'text']

        # Remove any excess text tracks beyond the 2 dual tracks
        if len(text_tracks) > 2:
            for extra in text_tracks[2:]:
                if extra in tracks:
                    tracks.remove(extra)
            text_tracks = text_tracks[:2]

        if not text_tracks:
            top_track = {
                "id": str(uuid.uuid4()).upper(),
                "type": "text",
                "flag": 1,
                "attribute": 0,
                "name": "",
                "segments": []
            }
            tracks.append(top_track)
            text_tracks.append(top_track)
        else:
            top_track = text_tracks[0]

        if len(text_tracks) < 2:
            bot_track = {
                "id": str(uuid.uuid4()).upper(),
                "type": "text",
                "flag": 1,
                "attribute": 0,
                "name": "",
                "segments": []
            }
            top_idx = tracks.index(top_track)
            tracks.insert(top_idx + 1, bot_track)
        else:
            bot_track = text_tracks[1]

        return top_track, bot_track

    def _ensure_sticker_track(self, draft_data: Dict[str, Any]) -> Dict[str, Any]:
        tracks = draft_data.setdefault('tracks', [])
        for t in tracks:
            if t.get('type') == 'sticker':
                return t
        stk_track = {
            "id": str(uuid.uuid4()).upper(),
            "type": "sticker",
            "flag": 0,
            "attribute": 0,
            "name": "",
            "segments": []
        }
        text_indices = [i for i, t in enumerate(tracks) if t.get('type') == 'text']
        if text_indices:
            insert_pos = max(text_indices) + 1
            tracks.insert(insert_pos, stk_track)
        else:
            tracks.append(stk_track)
        return stk_track

    def _create_sticker_material(self, draft_data: Dict[str, Any], stk_info: Dict[str, Any]) -> str:
        materials = draft_data.setdefault('materials', {})
        stickers = materials.setdefault('stickers', [])
        res_id = stk_info.get('resource_id')
        for s in stickers:
            if s.get('resource_id') == res_id:
                return s['id']
        mat_id = str(uuid.uuid4()).upper()
        stk_path = resolve_sticker_path(res_id, stk_info.get('path', ''))
        new_sticker = {
            "id": mat_id,
            "unique_id": "",
            "type": "sticker",
            "path": stk_path,
            "icon_url": stk_info.get('icon_url', ''),
            "preview_cover_url": stk_info.get('preview_cover_url', ''),
            "sticker_id": stk_info.get('sticker_id', res_id),
            "resource_id": res_id,
            "name": stk_info.get('name', 'Sticker'),
            "category_id": stk_info.get('category_id', '123456'),
            "category_name": stk_info.get('category_name', 'Stickers'),
            "platform": "all",
            "unicode": "",
            "source_platform": 1,
            "formula_id": "",
            "check_flag": 1,
            "team_id": "",
            "combo_info": {"text_templates": []},
            "sub_type": 0,
            "radius": {"top_left": 0.0, "top_right": 0.0, "bottom_left": 0.0, "bottom_right": 0.0},
            "global_alpha": 1.0,
            "background_color": "",
            "background_alpha": 1.0,
            "border_line_style": 0,
            "border_width": 0.0,
            "border_color": "",
            "has_shadow": False,
            "shadow_color": "",
            "shadow_alpha": 0.8,
            "shadow_smoothing": 0.0,
            "shadow_distance": 0.0,
            "shadow_point": {"x": 0.0, "y": 0.0},
            "shadow_angle": 0.0,
            "shape_param": {"shape_type": 0, "roundness": [], "custom_points": [], "shape_size": []},
            "original_size": [],
            "update_params": "",
            "aigc_type": "none",
            "sequence_type": False,
            "cycle_setting": True,
            "shape_fill_render_style": {
                "color": {
                    "solid": {"color": "#FFFFFF", "alpha": 1.0},
                    "gradient": {"color": [], "alpha": [], "percent": [], "angle": 90.0, "mode": "all", "style": "linear"},
                    "texture": {"path": "", "flip": [], "scale": 1.0, "alpha": 1.0, "angle": 90.0, "blend": "no", "range": 4, "fill": "tile", "resource_id": "", "effect_id": "", "play_speed": 1.0},
                    "render_type": "solid"
                },
                "alpha": 1.0
            },
            "shape_fill_use_flower_color": False,
            "multi_language_current": "none",
            "corner_pin": None
        }
        stickers.append(new_sticker)
        return mat_id

    def apply_plan(self, project: CapCutProject, layout_plan: List[Dict[str, Any]]) -> Tuple[int, int]:
        data = project.data
        top_track, bot_track = self._ensure_text_tracks(data)

        top_track['segments'] = []
        bot_track['segments'] = []
        data.setdefault('materials', {})['texts'] = []

        stk_track = None
        has_stickers = bool(getattr(self, 'stickers_cfg', {}).get('enabled', False) and getattr(self, 'stickers_cfg', {}).get('pool'))
        if has_stickers:
            stk_track = self._ensure_sticker_track(data)
            stk_track['segments'] = []

        total_top = 0
        total_bot = 0
        bot_starts = []

        for item in layout_plan:
            top_info = item.get('top')
            bot_info = item.get('bot')

            # Anti-Repetition Guard: If Top text is identical to or overlapping Bot text in the same segment
            if top_info and bot_info and top_info.get('text') and bot_info.get('text'):
                t_clean_lower = clean_subtitle_text(top_info['text']).lower().strip()
                b_clean_lower = clean_subtitle_text(bot_info['text']).lower().strip()
                if t_clean_lower == b_clean_lower or t_clean_lower in b_clean_lower or b_clean_lower in t_clean_lower:
                    # Duplicate detected! Do not create duplicate top segment.
                    top_info = None  # prevent adding duplicate top segment!

            if top_info and top_info.get('text'):
                top_text = clean_subtitle_text(top_info['text'])
                if self.default_style.get('uppercase', False) or (self.preset_data and self.preset_data.get('uppercase', False)):
                    top_text = top_text.upper()
                t_start = top_info.get('start', 0)
                t_end = top_info.get('end', 0)
                is_top_hl = top_info.get('is_highlight', False)
                if top_text and t_end > t_start:
                    dur = t_end - t_start
                    if is_top_hl:
                        style_to_use = copy.deepcopy(self.highlight_style)
                        neg_col = self.highlight_style.get('negative_color') or self.default_style.get('negative_color')
                        neg_rgb = self.highlight_style.get('negative_rgb_color') or self.default_style.get('negative_rgb_color')
                        if neg_col and neg_rgb:
                            is_neg = (top_info.get('tone') == 'negative') or self._is_negative_term(top_text)
                            if is_neg:
                                style_to_use['color'] = neg_col
                                style_to_use['rgb_color'] = neg_rgb

                        top_mat_id = self._create_text_material(data, top_text, style_to_use, is_highlight=True)
                        anim_ref = self._create_animation(data, dur)
                        extra_refs = [anim_ref] if anim_ref else []
                        bot_starts.append(t_start)
                    else:
                        top_mat_id = self._create_text_material(data, top_text, self.default_style, is_highlight=False)
                        extra_refs = []

                    top_scale = copy.deepcopy(self.top_scale)
                    if is_top_hl:
                        dyn_top_font = self.highlight_style.get('dynamic_font_size') or self.default_style.get('dynamic_font_size')
                        if not (dyn_top_font and dyn_top_font.get('enabled', True)):
                            char_count = len(top_text.strip())
                            if char_count > 11:
                                shrink_factor = max(0.75, 11.0 / char_count)
                                if isinstance(top_scale, dict) and 'x' in top_scale and 'y' in top_scale:
                                    top_scale['x'] = float(top_scale['x']) * shrink_factor
                                    top_scale['y'] = float(top_scale['y']) * shrink_factor

                    top_seg = {
                        "id": str(uuid.uuid4()).upper(),
                        "material_id": top_mat_id,
                        "target_timerange": {
                            "start": t_start,
                            "duration": dur
                        },
                        "source_timerange": None,
                        "render_timerange": {"start": 0, "duration": 0},
                        "clip": {
                            'scale': top_scale,
                            'transform': {'x': 0.0, 'y': self.y_top},
                            'rotation': 0.0,
                            'flip': {'vertical': False, 'horizontal': False},
                            'alpha': 1.0
                        },
                        "extra_material_refs": extra_refs,
                        "uniform_scale": {"on": True, "value": 1.0},
                        "state": 0,
                        "speed": 1.0,
                        "visible": True
                    }
                    top_track['segments'].append(top_seg)
                    total_top += 1

            bot_info = item.get('bot')
            if bot_info and bot_info.get('text'):
                bot_text = clean_subtitle_text(bot_info['text'])
                if self.highlight_style.get('uppercase', False) or (self.preset_data and self.preset_data.get('uppercase', False)):
                    bot_text = bot_text.upper()
                b_start = bot_info.get('start', 0)
                b_end = bot_info.get('end', 0)
                if top_info and top_info.get('end'):
                    b_end = min(b_end, top_info['end'])
                if bot_text and b_end > b_start:
                    dur = b_end - b_start
                    bot_starts.append(b_start)

                    style_to_use = copy.deepcopy(self.highlight_style)
                    neg_col = self.highlight_style.get('negative_color') or self.default_style.get('negative_color')
                    neg_rgb = self.highlight_style.get('negative_rgb_color') or self.default_style.get('negative_rgb_color')
                    if neg_col and neg_rgb:
                        is_neg = (bot_info.get('tone') == 'negative') or self._is_negative_term(bot_text)
                        if is_neg:
                            style_to_use['color'] = neg_col
                            style_to_use['rgb_color'] = neg_rgb

                    bot_mat_id = self._create_text_material(data, bot_text, style_to_use, is_highlight=True)
                    anim_ref = self._create_animation(data, dur)
                    extra_refs = [anim_ref] if anim_ref else []

                    # Safe margin safeguard: dynamically scale down highlight only when dynamic_font_size is NOT active
                    bot_scale = copy.deepcopy(self.bot_scale)
                    dyn_font = self.highlight_style.get('dynamic_font_size')
                    if not (dyn_font and dyn_font.get('enabled', True)):
                        char_count = len(bot_text.strip())
                        if char_count > 11:
                            shrink_factor = max(0.75, 11.0 / char_count)
                            if isinstance(bot_scale, dict) and 'x' in bot_scale and 'y' in bot_scale:
                                bot_scale['x'] = float(bot_scale['x']) * shrink_factor
                                bot_scale['y'] = float(bot_scale['y']) * shrink_factor

                    eff_bot_y = self.y_bottom
                    dyn_y_cfg = self.highlight_style.get('dynamic_y') or (self.preset_data.get('bottom', {}).get('dynamic_y') if self.preset_data else None)
                    if dyn_y_cfg and dyn_y_cfg.get('enabled', True):
                        top_text_str = top_info.get('text', '') if (top_info and isinstance(top_info, dict)) else ""
                        descenders = set('pqgyj')
                        has_top_descenders = any(c in descenders for c in top_text_str.lower())
                        has_tall_numbers = any(term.isdigit() and len(term) >= 4 for term in bot_text.split()) or len([c for c in bot_text if c.isdigit()]) >= 4
                        sz_used = get_effective_font_size(style_to_use, bot_text)

                        if not top_text_str:
                            eff_bot_y = float(dyn_y_cfg.get('solo_y', 0.0))
                        elif sz_used >= 21.0:
                            if has_top_descenders:
                                eff_bot_y = float(dyn_y_cfg.get('size22_descender_y', -0.1200))
                            else:
                                eff_bot_y = float(dyn_y_cfg.get('size22_y', -0.1138))
                        elif has_top_descenders:
                            eff_bot_y = float(dyn_y_cfg.get('descender_y', -0.1200))
                        elif has_tall_numbers:
                            eff_bot_y = float(dyn_y_cfg.get('tall_numbers_y', -0.1268))
                        elif bot_text.islower() and not any(c.isdigit() for c in bot_text) and len(bot_text) <= 14 and 'compact_y' in dyn_y_cfg:
                            eff_bot_y = float(dyn_y_cfg.get('compact_y', -0.0865))
                        else:
                            eff_bot_y = float(dyn_y_cfg.get('standard_y', -0.1081))

                    bot_seg = {
                        "id": str(uuid.uuid4()).upper(),
                        "material_id": bot_mat_id,
                        "target_timerange": {
                            "start": b_start,
                            "duration": dur
                        },
                        "source_timerange": None,
                        "render_timerange": {"start": 0, "duration": 0},
                        "clip": {
                            'scale': bot_scale,
                            'transform': {'x': 0.0, 'y': eff_bot_y},
                            'rotation': 0.0,
                            'flip': {'vertical': False, 'horizontal': False},
                            'alpha': 1.0
                        },
                        "extra_material_refs": extra_refs,
                        "uniform_scale": {"on": True, "value": 1.0},
                        "state": 0,
                        "speed": 1.0,
                        "visible": True
                    }
                    bot_track['segments'].append(bot_seg)
                    total_bot += 1

            # Sticker Accompaniment
            stk_info = item.get('sticker')
            if stk_track is not None and stk_info and stk_info.get('resource_id') and stk_info.get('duration', 0) > 0:
                stk_mat_id = self._create_sticker_material(data, stk_info)
                stk_seg = {
                    "id": str(uuid.uuid4()).upper(),
                    "material_id": stk_mat_id,
                    "target_timerange": {
                        "start": stk_info['start'],
                        "duration": stk_info['duration']
                    },
                    "source_timerange": None,
                    "render_timerange": {"start": 0, "duration": 0},
                    "clip": {
                        'scale': copy.deepcopy(stk_info.get('scale', {'x': 1.0, 'y': 1.0})),
                        'transform': copy.deepcopy(stk_info.get('transform', {'x': 0.0, 'y': 0.0})),
                        'rotation': float(stk_info.get('rotation', 0.0)),
                        'flip': {'vertical': False, 'horizontal': False},
                        'alpha': 1.0
                    },
                    "extra_material_refs": [],
                    "uniform_scale": {"on": True, "value": 1.0},
                    "state": 0,
                    "speed": 1.0,
                    "visible": True
                }
                stk_track['segments'].append(stk_seg)

        # Accompaniment Fail-Safe Guarantee: 100% of Bot segments must be accompanied by Top
        top_segs = top_track.get('segments', [])
        bot_segs = bot_track.get('segments', [])
        for b_seg in bot_segs:
            b_tr = b_seg.get('target_timerange', {})
            b_st = b_tr.get('start', 0)
            b_dur = b_tr.get('duration', 0)
            b_et = b_st + b_dur

            covering = [
                t for t in top_segs
                if t.get('target_timerange', {}).get('start', 0) <= b_st + 50000
                and (t.get('target_timerange', {}).get('start', 0) + t.get('target_timerange', {}).get('duration', 0)) >= b_et - 50000
            ]
            if not covering:
                preceding = [
                    t for t in top_segs
                    if t.get('target_timerange', {}).get('start', 0) <= b_st + 50000
                    and not t.get('extra_material_refs')
                ]
                if preceding:
                    closest = max(preceding, key=lambda t: t.get('target_timerange', {}).get('start', 0))
                    c_st = closest.get('target_timerange', {}).get('start', 0)
                    next_tops = [t for t in top_segs if t.get('target_timerange', {}).get('start', 0) > c_st]
                    max_allowed = min([t.get('target_timerange', {}).get('start', 0) for t in next_tops]) if next_tops else b_et
                    closest['target_timerange']['duration'] = max(closest['target_timerange']['duration'], min(b_et, max_allowed) - c_st)

        # STRICT ANTI-COLLISION CLAMP:
        # Absolutely guarantees that NO two segments on the same track ever overlap in time.
        # This prevents CapCut from ever creating a 3rd text track ("escalera de 3").
        tracks_to_clamp = [top_track, bot_track]
        if stk_track:
            tracks_to_clamp.append(stk_track)
        for trk in tracks_to_clamp:
            trk_segs = trk.get('segments', [])
            for i in range(len(trk_segs) - 1):
                cur_st = trk_segs[i]['target_timerange']['start']
                cur_dur = trk_segs[i]['target_timerange']['duration']
                next_st = trk_segs[i + 1]['target_timerange']['start']
                if cur_st + cur_dur > next_st:
                    trk_segs[i]['target_timerange']['duration'] = max(0, next_st - cur_st)

        if getattr(self, 'sound_fx', {}).get('enabled', True) and bot_starts:
            vol = float(self.sound_fx.get('volume', 0.65))
            snd_name = self.sound_fx.get('name', 'Click_Mouse_Click_02(864360)')
            snd_path = self.sound_fx.get('path')
            if not snd_path or not os.path.isfile(snd_path):
                snd_path = get_default_click_sound_path()
            self._add_click_sound_fx(data, bot_starts, volume=vol, sound_name=snd_name, sound_path=snd_path)

        is_upper_required = (
            (self.default_style.get('uppercase', False) and self.highlight_style.get('uppercase', False))
            or (self.preset_data and self.preset_data.get('uppercase', False))
            or self.default_style.get('uppercase', False)
        )
        if is_upper_required:
            for t_mat in data.get('materials', {}).get('texts', []):
                rec_txt = t_mat.get('recognize_text', '')
                if rec_txt:
                    t_mat['recognize_text'] = rec_txt.upper()
                c_raw = t_mat.get('content', '')
                if c_raw:
                    try:
                        c_obj = json.loads(c_raw)
                        c_obj['text'] = c_obj.get('text', '').upper()
                        if 'styles' in c_obj and len(c_obj['styles']) == 1:
                            c_obj['styles'][0]['range'] = [0, len(c_obj['text'])]
                        new_c = json.dumps(c_obj, ensure_ascii=False, separators=(',', ':'))
                        t_mat['content'] = new_c
                        t_mat['base_content'] = new_c
                    except Exception:
                        pass
                if 'words' in t_mat and isinstance(t_mat['words'], dict) and 'text' in t_mat['words']:
                    t_mat['words']['text'] = [w.upper() for w in t_mat['words']['text']]

        project._parse_subtitles()
        return total_top, total_bot

    def _consolidate_number_segments(
        self,
        raw_items: List[Dict[str, Any]],
        max_chars: int = 18,
        max_words: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Consolidates consecutive subtitle segments when a spoken number was split across them,
        converting the words to digits and merging the timeline segments into a single segment.
        """
        if not raw_items:
            return []

        import re
        result = []
        i = 0
        n = len(raw_items)

        number_continuators = {
            'y', 'diez', 'veinte', 'treinta', 'cuarenta', 'cincuenta',
            'sesenta', 'setenta', 'ochenta', 'noventa',
            'ciento', 'doscientos', 'doscientas', 'trescientos', 'trescientas',
            'cuatrocientos', 'cuatrocientas', 'quinientos', 'quinientas',
            'seiscientos', 'seiscientas', 'setecientos', 'setecientas',
            'ochocientos', 'ochocientas', 'novecientos', 'novecientas', 'mil'
        }

        def _check_split_percentage(text_a: str, text_b: str):
            # Case 1: text_a ends with '<num> por' or '<num> x', text_b starts with 'ciento / cien / 100'
            m1 = re.search(r'(.*?)\b(\d+)\s+(?:por|x)\s*([?!\'"\)\]\}]*)$', text_a, flags=re.IGNORECASE)
            if m1:
                prefix = m1.group(1)
                num = m1.group(2)
                punct = m1.group(3)
                m2 = re.match(r'^(?:ciento|cien|100)\b\s*(.*)$', text_b, flags=re.IGNORECASE)
                if m2:
                    rem_b = m2.group(1).strip()
                    new_a = f"{prefix}{num}%{punct}".strip()
                    return new_a, rem_b

            # Case 2: text_a ends with '<num>', text_b starts with 'por ciento / por cien / por 100 / porciento / x 100 / x ciento'
            m3 = re.search(r'(.*?)\b(\d+)\s*([?!\'"\)\]\}]*)$', text_a, flags=re.IGNORECASE)
            if m3:
                prefix = m3.group(1)
                num = m3.group(2)
                punct = m3.group(3)
                m4 = re.match(r'^(?:por\s+ciento|por\s+cien|por\s+100|porciento|x\s+100|x\s+ciento)\b\s*(.*)$', text_b, flags=re.IGNORECASE)
                if m4:
                    rem_b = m4.group(1).strip()
                    new_a = f"{prefix}{num}%{punct}".strip()
                    return new_a, rem_b

            return None

        while i < n:
            curr = raw_items[i]
            curr_text = curr['text']

            # Check for split percentage between curr and raw_items[i + 1]
            if i + 1 < n:
                next_item = raw_items[i + 1]
                cand_a = convert_spanish_numbers_to_digits(curr_text)
                cand_b = convert_spanish_numbers_to_digits(next_item['text'])
                pct_split = _check_split_percentage(cand_a, cand_b)
                if pct_split:
                    new_a, rem_b = pct_split
                    if not rem_b:
                        fused_item = {
                            'index': len(result),
                            'item': curr.get('item'),
                            'text': new_a,
                            'start': curr['start'],
                            'end': next_item['end'],
                            'duration': next_item['end'] - curr['start'],
                            'words': curr.get('words'),
                            'absorbed_indices': [next_item['index']]
                        }
                        result.append(fused_item)
                        i += 2
                        continue
                    else:
                        combined_test = f"{new_a} {rem_b}"
                        if len(combined_test) <= max_chars and len(combined_test.split()) <= max_words:
                            fused_item = {
                                'index': len(result),
                                'item': curr.get('item'),
                                'text': combined_test,
                                'start': curr['start'],
                                'end': next_item['end'],
                                'duration': next_item['end'] - curr['start'],
                                'words': curr.get('words'),
                                'absorbed_indices': [next_item['index']]
                            }
                            result.append(fused_item)
                            i += 2
                            continue
                        else:
                            curr_copy = dict(curr)
                            curr_copy['text'] = new_a
                            curr_copy['index'] = len(result)
                            result.append(curr_copy)

                            raw_items[i + 1]['text'] = rem_b
                            if raw_items[i + 1].get('item'):
                                raw_items[i + 1]['item'].text = rem_b
                            i += 1
                            continue

            merged_count = 0
            raw_candidate_text = curr_text
            candidate_end = curr['end']
            converted_candidate = convert_spanish_numbers_to_digits(curr_text)

            j = i + 1
            while j < n:
                next_item = raw_items[j]
                next_text = next_item['text']
                test_raw = f"{raw_candidate_text} {next_text}"

                converted_cand = convert_spanish_numbers_to_digits(raw_candidate_text)
                converted_next = convert_spanish_numbers_to_digits(next_text)
                converted_test = convert_spanish_numbers_to_digits(test_raw)

                digits_cand = re.findall(r'\b\d+\b', converted_cand)
                digits_next = re.findall(r'\b\d+\b', converted_next)
                digits_test = re.findall(r'\b\d+\b', converted_test)

                # Check if combining them resolves a split number
                has_split = False
                if digits_test and digits_test != (digits_cand + digits_next):
                    has_split = True
                elif raw_candidate_text.lower().split() and raw_candidate_text.lower().split()[-1] in number_continuators and digits_test:
                    has_split = True

                if has_split:
                    test_words = converted_test.split()
                    if len(converted_test) <= max_chars and len(test_words) <= max_words:
                        raw_candidate_text = test_raw
                        converted_candidate = converted_test
                        candidate_end = next_item['end']
                        merged_count += 1
                        j += 1
                        continue
                break

            if merged_count > 0:
                fused_item = {
                    'index': len(result),
                    'item': curr.get('item'),
                    'text': converted_candidate,
                    'start': curr['start'],
                    'end': candidate_end,
                    'duration': candidate_end - curr['start'],
                    'words': curr.get('words'),
                    'absorbed_indices': [raw_items[k]['index'] for k in range(i + 1, i + 1 + merged_count)]
                }
                result.append(fused_item)
                i += 1 + merged_count
            else:
                curr_copy = dict(curr)
                curr_copy['text'] = convert_spanish_numbers_to_digits(curr_text)
                curr_copy['index'] = len(result)
                result.append(curr_copy)
                i += 1

        return result

    def auto_dual_process(
        self,
        project: CapCutProject,
        highlighter=None,
        openrouter_key: Optional[str] = None,
        model: Optional[str] = None,
        min_pacing_sec: float = 3.0,
        max_pacing_sec: float = 5.0,
        max_chars_per_line: int = 18,
        max_words_per_line: int = 3,
        log_fn=None
    ) -> Tuple[int, int]:
        """
        Acoustically locked subtitle generator:
        - If layout == 'inline': executes single-track inline rich-text styling with descansos (e.g. Jose Podólogo).
        - If layout == 'dual': executes dual-track top/bottom styling.
        """
        if getattr(self, 'layout', 'dual') == 'inline':
            return self.auto_inline_process(
                project=project,
                highlighter=highlighter,
                openrouter_key=openrouter_key,
                model=model,
                min_pacing_sec=min_pacing_sec,
                max_pacing_sec=max_pacing_sec,
                max_chars_per_line=max_chars_per_line,
                max_words_per_line=max_words_per_line,
                log_fn=log_fn
            )
        elif getattr(self, 'layout', 'dual') == 'template':
            return self.auto_template_process(
                project=project,
                highlighter=highlighter,
                openrouter_key=openrouter_key,
                model=model,
                min_pacing_sec=min_pacing_sec,
                max_pacing_sec=max_pacing_sec,
                max_chars_per_line=max_chars_per_line,
                max_words_per_line=max_words_per_line,
                log_fn=log_fn
            )
        elif getattr(self, 'layout', 'dual') in ('dentok', 'escalera'):
            return self.auto_dentok_process(
                project=project,
                highlighter=highlighter,
                openrouter_key=openrouter_key,
                model=model,
                min_pacing_sec=min_pacing_sec,
                max_pacing_sec=max_pacing_sec,
                max_chars_per_line=max_chars_per_line,
                max_words_per_line=max_words_per_line,
                log_fn=log_fn
            )

        pacing_cfg = getattr(self, 'pacing', {})
        if (min_pacing_sec == 3.0 or min_pacing_sec is None) and 'min_seconds' in pacing_cfg:
            min_pacing_sec = float(pacing_cfg['min_seconds'])
        if (max_pacing_sec == 5.0 or max_pacing_sec is None) and 'max_seconds' in pacing_cfg:
            max_pacing_sec = float(pacing_cfg['max_seconds'])

        # Check if project text tracks are already styled into dual layers (Track 0 top, Track 1 bottom with temporal overlap)
        # or if they are separate sequential tracks generated in batches by the user.
        text_tracks = [t for t in project.data.get('tracks', []) if t.get('type') == 'text']
        is_already_dual = False
        if len(text_tracks) >= 2:
            t0_intervals = [(s['target_timerange']['start'], s['target_timerange']['start'] + s['target_timerange']['duration']) for s in text_tracks[0].get('segments', [])]
            t1_intervals = [(s['target_timerange']['start'], s['target_timerange']['start'] + s['target_timerange']['duration']) for s in text_tracks[1].get('segments', [])]
            for st1, et1 in t1_intervals:
                for st0, et0 in t0_intervals:
                    if max(st0, st1) < min(et0, et1):
                        is_already_dual = True
                        break
                if is_already_dual:
                    break

        if is_already_dual:
            first_text_idx = next(i for i, t in enumerate(project.data.get('tracks', [])) if t.get('type') == 'text')
            subs = [s for s in project.subtitles if s.track_index == first_text_idx]
        else:
            subs = project.subtitles

        subs = sorted(subs, key=lambda s: s.start_us)

        if not subs:
            logger.warning("No subtitles found to process.")
            return 0, 0

        UNFINISHED_ENDINGS = {
            'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas',
            'de', 'del', 'a', 'al', 'en', 'con', 'por', 'para', 'sin', 'sobre', 'tras',
            'hacia', 'hasta', 'desde', 'contra', 'entre',
            'y', 'e', 'ni', 'o', 'u', 'que', 'pero', 'aunque', 'porque', 'como', 'cuando', 'donde', 'si'
        }

        is_all_uppercase = (
            (self.default_style.get('uppercase', False) and self.highlight_style.get('uppercase', False))
            or (self.preset_data and self.preset_data.get('uppercase', False))
        )

        raw_items = []
        for idx, s in enumerate(subs):
            is_start = True
            if idx > 0 and raw_items:
                prev_txt = raw_items[-1]['text'].strip()
                prev_words = prev_txt.split()
                if prev_words and prev_words[-1].lower().rstrip('?!,.:;') in UNFINISHED_ENDINGS:
                    is_start = False
            txt = clean_subtitle_text(s.text, is_sentence_start=is_start)
            if is_all_uppercase:
                txt = txt.upper()
            w_data = s.text_material.get('words')
            if is_all_uppercase and w_data and isinstance(w_data, dict) and 'text' in w_data:
                w_data = copy.deepcopy(w_data)
                w_data['text'] = [w.upper() for w in w_data.get('text', [])]
            if txt and s.duration_us > 0:
                raw_items.append({
                    'index': idx,
                    'item': s,
                    'text': txt,
                    'orig_text': s.text,
                    'start': s.start_us,
                    'end': s.start_us + s.duration_us,
                    'duration': s.duration_us,
                    'words': w_data
                })

        if not raw_items:
            return 0, 0

        # Consolidate split numbers and convert words to digits
        eff_max_chars = self.margins.get('max_chars_per_line', max_chars_per_line)
        eff_max_words = self.margins.get('max_words_per_line', max_words_per_line)
        eff_max_hl_chars = int(self.margins.get('max_highlight_chars', self.margins.get('max_chars_per_line', 18)))
        raw_items = self._consolidate_number_segments(raw_items, max_chars=eff_max_chars, max_words=eff_max_words)

        # Check for OpenRouter AI Processing (Corrección de mayúsculas, ¿?, y selección de highlights)
        ai_phrases = []
        effective_key = openrouter_key or (getattr(highlighter, 'api_key', None) if getattr(highlighter, 'provider', None) == 'openrouter' else None) or os.environ.get('OPENROUTER_API_KEY')
        if effective_key:
            try:
                m = model or getattr(highlighter, 'model', None) or DEFAULT_MODEL
                if log_fn:
                    log_fn(f"[*] Conectando con OpenRouter ({m})...")
                client = OpenRouterClient(api_key=effective_key, model=m)
                ai_res = client.process_subtitles(raw_items)
                if ai_res:
                    # Align AI corrections strictly to original acoustic word slots via SequenceMatcher
                    # Prevents index-shifting and guarantees 100% voice synchronization
                    corrected_subs = ai_res.get('corrected_subtitles', [])
                    align_ai_corrections_to_raw_items(raw_items, corrected_subs)

                    # Extract highlight phrases from AI response
                    idx_to_text = {item['index']: item['text'] for item in raw_items}
                    for h in ai_res.get('highlights', []):
                        p = convert_spanish_numbers_to_digits(clean_subtitle_text(h.get('phrase', '')))
                        tone = h.get('tone', 'normal')
                        if not p:
                            t_idx = h.get('target_index')
                            if t_idx is not None:
                                p = convert_spanish_numbers_to_digits(clean_subtitle_text(idx_to_text.get(t_idx, '')))
                        if p:
                            ai_phrases.append({'phrase': p, 'tone': tone, 'is_solo': bool(h.get('is_solo', False))})
                    msg = f"[OK] OpenRouter procesó {len(raw_items)} subtítulos y curó {len(ai_phrases)} palabras destacadas."

                    logger.info(msg)
                    if log_fn:
                        log_fn(msg)
                else:
                    msg = "[!] OpenRouter no devolvió resultados válidos. Usando generador acústico offline de respaldo..."
                    logger.warning(msg)
                    if log_fn:
                        log_fn(msg)
            except Exception as e:
                msg = f"[!] Error en OpenRouter ({e}). Usando generador acústico offline de respaldo..."
                logger.warning(msg)
                if log_fn:
                    log_fn(msg)

        full_script = " ".join(item['text'] for item in raw_items)
        phrases_to_highlight = ai_phrases

        if not phrases_to_highlight and highlighter:
            try:
                suggested = highlighter.suggest_highlights(full_script, count=25)
                phrases_to_highlight = [clean_subtitle_text(p) for p in suggested if clean_subtitle_text(p)]
            except Exception as e:
                logger.warning(f"Highlighter error: {e}")

        if not phrases_to_highlight:
            from ai.highlighter import AIHighlighter
            hl = AIHighlighter(provider='heuristic')
            suggested = hl.suggest_highlights(full_script, count=25)
            phrases_to_highlight = [clean_subtitle_text(p) for p in suggested if clean_subtitle_text(p)]

        sanitized_phrases = []
        for entry in phrases_to_highlight:
            if isinstance(entry, dict):
                p_san = sanitize_highlight_phrase(entry.get('phrase', ''), max_chars=eff_max_hl_chars)
                if p_san:
                    entry_copy = dict(entry)
                    entry_copy['phrase'] = p_san
                    sanitized_phrases.append(entry_copy)
            else:
                p_san = sanitize_highlight_phrase(str(entry), max_chars=eff_max_hl_chars)
                if p_san:
                    sanitized_phrases.append(p_san)
        phrases_to_highlight = sanitized_phrases

        if is_all_uppercase:
            for item in raw_items:
                item['text'] = item['text'].upper()
                if item.get('item') and hasattr(item['item'], 'text'):
                    item['item'].text = item['item'].text.upper()
            for entry in phrases_to_highlight:
                if isinstance(entry, dict):
                    entry['phrase'] = entry['phrase'].upper()

        plan = []
        last_highlight_us = -int(min_pacing_sec * 1e6)
        solo_count = 0
        last_solo_us = -int(8.0 * 1e6)
        allow_solo = self.preset_data.get('allow_solo_highlights', True) if self.preset_data else True
        max_solo = self.preset_data.get('max_solo_highlights', 2) if self.preset_data else 2
        min_solo_interval_us = int(8.0 * 1e6)
        sticker_count = 0

        for curr_idx, curr in enumerate(raw_items):
            curr_text = curr['text']
            curr_start = curr['start']
            curr_end = curr['end']
            curr_dur = curr['duration']
            words_data = curr['words']
            prev_item = raw_items[curr_idx - 1] if curr_idx > 0 else None
            prev_text = prev_item['text'].strip() if prev_item else ""
            prev_end = prev_item['end'] if prev_item else 0

            matched_highlight = None
            matched_tone = 'normal'
            is_solo_entry = False
            time_since_last_sec = (curr_start - last_highlight_us) / 1e6

            if time_since_last_sec >= min_pacing_sec:
                for entry in phrases_to_highlight:
                    if isinstance(entry, dict):
                        p = entry.get('phrase', '')
                        tone = entry.get('tone', 'normal')
                        entry_solo = entry.get('is_solo', False)
                    else:
                        p = str(entry)
                        tone = 'normal'
                        entry_solo = False
                    p_clean = sanitize_highlight_phrase(p, max_chars=eff_max_hl_chars)
                    if not p_clean or p_clean.lower() in SPANISH_STOPWORDS:
                        continue
                    # 1. Exact or substring match: phrase is in curr_text
                    if p_clean.lower() in curr_text.lower() and len(p_clean) <= eff_max_hl_chars:
                        if p_clean.lower() not in SPANISH_STOPWORDS:
                            matched_highlight = p_clean
                            matched_tone = tone
                            is_solo_entry = entry_solo
                            break
                    # 2. Or curr_text is within p_clean (for multi-word AI suggestions spanning short segments)
                    elif curr_text.strip().lower() in p_clean.lower() and len(curr_text.strip()) >= 3 and len(curr_text.strip()) <= eff_max_hl_chars:
                        cand_text = sanitize_highlight_phrase(curr_text.strip(), max_chars=eff_max_hl_chars)
                        if cand_text and cand_text.lower() not in SPANISH_STOPWORDS:
                            matched_highlight = cand_text
                            matched_tone = tone
                            is_solo_entry = entry_solo
                            break

                # 3. Pacing fallback guarantee: if time exceeded max_pacing_sec, ensure constant visual rhythm
                if not matched_highlight and time_since_last_sec >= max_pacing_sec:
                    import re
                    cand_words = [
                        w for w in re.findall(r'\b[\wáéíóúÁÉÍÓÚñÑüÜ]+\b', curr_text)
                        if w.lower() not in SPANISH_STOPWORDS and len(w) <= eff_max_hl_chars and (len(w) >= 4 or w.lower() in {'pie', 'ojo', 'voz', 'tos'})
                    ]
                    if cand_words:
                        matched_highlight = max(cand_words, key=len)
                        matched_tone = 'normal'
                        is_solo_entry = False

            if matched_highlight:
                clean_hl_check = sanitize_highlight_phrase(matched_highlight, max_chars=eff_max_hl_chars)
                if not clean_hl_check or clean_hl_check.lower() in SPANISH_STOPWORDS or (len(clean_hl_check.strip()) <= 2 and not any(c.isdigit() for c in clean_hl_check)):
                    matched_highlight = None
                else:
                    matched_highlight = clean_hl_check

            if matched_highlight:
                hl_start, hl_end = find_phrase_timing(curr_start, curr_dur, words_data, curr_text, matched_highlight)
                clean_lower_curr = curr_text.lower()
                clean_lower_hl = matched_highlight.lower()
                hl_idx = clean_lower_curr.find(clean_lower_hl)

                prefix = clean_subtitle_text(curr_text[:hl_idx], preserve_case=is_all_uppercase) if hl_idx > 0 else ""
                suffix = clean_subtitle_text(curr_text[hl_idx + len(matched_highlight):], preserve_case=is_all_uppercase)
                if is_all_uppercase:
                    prefix = prefix.upper() if prefix else ""
                    suffix = suffix.upper() if suffix else ""

                # Build sticker entry if preset has stickers enabled
                stk_entry = None
                if getattr(self, 'stickers_cfg', {}).get('enabled', False) and getattr(self, 'stickers_cfg', {}).get('pool'):
                    stk_pool = self.stickers_cfg['pool']
                    stk_template = stk_pool[sticker_count % len(stk_pool)]
                    sticker_count += 1
                    stk_entry = {
                        'name': stk_template.get('name'),
                        'resource_id': stk_template.get('resource_id'),
                        'sticker_id': stk_template.get('sticker_id'),
                        'path': stk_template.get('path'),
                        'icon_url': stk_template.get('icon_url'),
                        'preview_cover_url': stk_template.get('preview_cover_url'),
                        'category_id': stk_template.get('category_id', '123456'),
                        'category_name': stk_template.get('category_name', 'Stickers'),
                        'start': hl_start,
                        'duration': curr_end - hl_start,
                        'transform': copy.deepcopy(stk_template.get('clip', {}).get('transform', {'x': 0.0, 'y': 0.0})),
                        'scale': copy.deepcopy(stk_template.get('clip', {}).get('scale', {'x': 1.0, 'y': 1.0})),
                        'rotation': float(stk_template.get('clip', {}).get('rotation', 0.0))
                    }

                bot_text = clean_subtitle_text(matched_highlight, preserve_case=is_all_uppercase)
                if is_all_uppercase:
                    bot_text = bot_text.upper()
                if suffix:
                    # Highlight finishes strictly when the keyword ends, so it doesn't linger while suffix is spoken
                    if (curr_end - hl_end) < 150000 and (curr_end - hl_start) >= 300000:
                        bot_end = max(hl_start + 150000, curr_end - 150000)
                    else:
                        bot_end = min(hl_end, curr_end)
                else:
                    bot_end = curr_end

                if stk_entry:
                    stk_entry['duration'] = bot_end - hl_start

                if prefix:
                    # Standard Dual-Layer: Top general text stays visible across prefix and highlight duration
                    top_entry = {
                        'text': clean_subtitle_text(prefix),
                        'start': curr_start,
                        'end': bot_end
                    }
                    bot_entry = {
                        'text': bot_text,
                        'start': hl_start,
                        'end': bot_end,
                        'tone': matched_tone
                    }
                    plan.append({'top': top_entry, 'bot': bot_entry, 'sticker': stk_entry})
                    if suffix:
                        plan.append({
                            'top': {
                                'text': clean_subtitle_text(suffix),
                                'start': bot_end,
                                'end': curr_end
                            },
                            'bot': None,
                            'sticker': None
                        })
                    last_highlight_us = hl_start
                else:
                    # Highlight is at the START of this segment (no prefix).
                    # Check whether this is the start of a sentence/clause or continuation of ongoing phrase.
                    SENTENCE_START_CONNECTORS = {
                        'porque', 'pero', 'cuando', 'como', 'si', 'donde', 'aunque', 'mientras', 'pues', 'ya', 'sino',
                        'entonces', 'además', 'así', 'luego'
                    }
                    UNFINISHED_ENDINGS = {
                        'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas',
                        'de', 'del', 'a', 'al', 'en', 'con', 'por', 'para', 'sin', 'sobre', 'tras',
                        'y', 'e', 'ni', 'o', 'u', 'que'
                    }

                    is_sentence_start = False
                    if not plan or curr_idx == 0:
                        is_sentence_start = True
                    else:
                        prev_words = prev_text.split()
                        last_prev_word = prev_words[-1].lower() if prev_words else ""
                        curr_words = curr_text.split()
                        first_curr_word = curr_words[0].lower() if curr_words else ""

                        time_gap = curr_start - prev_end
                        if time_gap >= 200000:
                            is_sentence_start = True
                        elif first_curr_word in SENTENCE_START_CONNECTORS:
                            is_sentence_start = True
                        elif last_prev_word in UNFINISHED_ENDINGS:
                            is_sentence_start = False
                        orig_curr = curr.get('orig_text', curr_text).strip()
                        if orig_curr and orig_curr[0].isupper() and last_prev_word not in UNFINISHED_ENDINGS:
                            is_sentence_start = True
                        else:
                            is_sentence_start = False

                    if is_sentence_start:
                        # User rule: Solo highlights higher up (TOP track), used sparingly.
                        time_since_last_solo = hl_start - last_solo_us
                        can_use_solo = (allow_solo and solo_count < max_solo and time_since_last_solo >= min_solo_interval_us)

                        if can_use_solo:
                            solo_count += 1
                            last_solo_us = hl_start
                            last_highlight_us = hl_start
                            plan.append({
                                'top': {
                                    'text': bot_text,
                                    'start': hl_start,
                                    'end': bot_end,
                                    'is_highlight': True,
                                    'tone': matched_tone
                                },
                                'bot': None,
                                'sticker': stk_entry
                            })
                            if suffix:
                                plan.append({
                                    'top': {
                                        'text': clean_subtitle_text(suffix),
                                        'start': bot_end,
                                        'end': curr_end
                                    },
                                    'bot': None,
                                    'sticker': None
                                })
                        elif suffix:
                            # Render dual layer: top general suffix + bottom highlight
                            bot_entry = {
                                'text': bot_text,
                                'start': hl_start,
                                'end': bot_end,
                                'tone': matched_tone
                            }
                            top_entry = {
                                'text': clean_subtitle_text(suffix),
                                'start': bot_end,
                                'end': curr_end
                            }
                            plan.append({'top': top_entry, 'bot': bot_entry, 'sticker': stk_entry})
                            last_highlight_us = hl_start
                        else:
                            # Full segment is the highlight: create top + bottom dual layer
                            bot_entry = {
                                'text': bot_text,
                                'start': hl_start,
                                'end': bot_end,
                                'tone': matched_tone
                            }
                            top_entry = {
                                'text': clean_subtitle_text(curr_text),
                                'start': curr_start,
                                'end': curr_end
                            }
                            plan.append({'top': top_entry, 'bot': bot_entry, 'sticker': stk_entry})
                            last_highlight_us = hl_start
                    else:
                        # Mid-sentence continuation from preceding segment (same grammatical phrase).
                        if plan and plan[-1].get('top') and plan[-1]['top'].get('text'):
                            prev_top = plan[-1]['top']
                            # Guard against excessive top extension: max 2.0s total duration and no audio gap > 150ms
                            if (bot_end - prev_top['start'] <= 2000000) and (curr_start - prev_top['end'] <= 150000):
                                prev_top['end'] = max(prev_top['end'], bot_end)


                        bot_entry = {
                            'text': bot_text,
                            'start': hl_start,
                            'end': bot_end,
                            'tone': matched_tone
                        }
                        plan.append({'top': None, 'bot': bot_entry, 'sticker': stk_entry})
                        if suffix:
                            plan.append({
                                'top': {
                                    'text': clean_subtitle_text(suffix),
                                    'start': bot_end,
                                    'end': curr_end
                                },
                                'bot': None,
                                'sticker': None
                            })
                        last_highlight_us = hl_start
            else:
                plan.append({
                    'top': {
                        'text': clean_subtitle_text(curr_text),
                        'start': curr_start,
                        'end': curr_end
                    },
                    'bot': None,
                    'sticker': None
                })



        return self.apply_plan(project, plan)


    def _add_click_sound_fx(
        self,
        draft_data: Dict[str, Any],
        start_times_us: List[int],
        volume: float = 0.65,
        sound_name: str = "Click_Mouse_Click_02(864360)",
        sound_path: str = ""
    ):
        """Injects Click_Mouse_Click_02 sound effect on an audio track for each highlight timestamp."""
        if not start_times_us:
            return

        if not sound_path or not os.path.isfile(sound_path):
            sound_path = get_default_click_sound_path()

        materials = draft_data.setdefault('materials', {})
        audios = materials.setdefault('audios', [])
        
        click_mat = None
        for a in audios:
            if 'Click_Mouse' in a.get('name', '') or a.get('path') == sound_path:
                click_mat = a
                break

        if not click_mat:
            click_id = str(uuid.uuid4()).upper()
            click_mat = {
                "id": click_id,
                "unique_id": "",
                "type": "sound",
                "name": sound_name,
                "duration": 866666,
                "path": sound_path,
                "category_name": "Favoritos",
                "wave_points": [],
                "music_id": "",
                "app_id": 1775,
                "text_id": "",
                "tone_type": "",
                "source_platform": 0,
                "video_id": "",
                "effect_id": "6873506883139799041",
                "resource_id": "",
                "third_resource_id": "",
                "category_id": "-100",
                "intensifies_path": "",
                "formula_id": "",
                "check_flag": 1,
                "team_id": "",
                "local_material_id": "",
                "is_text_edit_overdub": False,
                "is_ugc": False,
                "is_ai_clone_tone": False,
                "is_ai_clone_tone_post": False,
                "source_from": "",
                "copyright_limit_type": "none",
                "aigc_history_id": "",
                "aigc_item_id": "",
                "music_source": "",
                "pgc_id": "",
                "pgc_name": "",
                "similiar_music_info": {"original_song_id": "", "original_song_name": ""},
                "ai_music_type": 0,
                "ai_music_enter_from": "",
                "lyric_type": 0,
                "tts_task_id": "",
                "tts_generate_scene": "",
                "ai_music_generate_scene": 0,
                "tts_benefit_info": {"benefit_type": "none", "benefit_log_id": "", "benefit_log_extra": "", "benefit_amount": -1},
                "tts_language_info": None
            }
            audios.append(click_mat)
        else:
            click_id = click_mat['id']

        speeds = materials.setdefault('speeds', [])
        placeholder_infos = materials.setdefault('placeholder_infos', [])
        beats = materials.setdefault('beats', [])
        sound_channel_mappings = materials.setdefault('sound_channel_mappings', [])
        vocal_separations = materials.setdefault('vocal_separations', [])

        tracks = draft_data.setdefault('tracks', [])
        audio_tracks = [t for t in tracks if t.get('type') == 'audio']
        eff_track = None
        for at in audio_tracks:
            if at.get('name') == "Efectos de Sonido" or any(s.get('material_id') == click_id for s in at.get('segments', [])):
                eff_track = at
                break

        if not eff_track:
            eff_track = {
                "id": str(uuid.uuid4()).upper(),
                "type": "audio",
                "flag": 0,
                "attribute": 0,
                "name": "Efectos de Sonido",
                "is_default_name": True,
                "segments": []
            }
            tracks.append(eff_track)
        else:
            eff_track['segments'] = []

        CLICK_DUR = 866666
        for st in start_times_us:
            s_id = str(uuid.uuid4()).upper()
            p_id = str(uuid.uuid4()).upper()
            b_id = str(uuid.uuid4()).upper()
            scm_id = str(uuid.uuid4()).upper()
            vs_id = str(uuid.uuid4()).upper()

            speeds.append({"id": s_id, "type": "speed", "mode": 0, "speed": 1.0, "curve_speed": None})
            placeholder_infos.append({"id": p_id, "type": "placeholder_info", "meta_type": "none", "res_path": "", "res_text": "", "error_path": "", "error_text": ""})
            beats.append({
                "id": b_id,
                "type": "beats",
                "enable_ai_beats": False,
                "gear": 404,
                "gear_count": 0,
                "mode": 404,
                "user_beats": [],
                "user_delete_ai_beats": None,
                "ai_beats": {
                    "melody_url": "",
                    "melody_path": "",
                    "beats_url": "https://sf16-web-music.capcutstatic.com/obj/tos-alisg-v-2774/66c66029df634795bcf4057f0dfadcb9",
                    "beats_path": "",
                    "melody_percents": [0.0],
                    "beat_speed_infos": []
                }
            })
            sound_channel_mappings.append({"id": scm_id, "type": "none", "audio_channel_mapping": 0, "is_config_open": False})
            vocal_separations.append({"id": vs_id, "type": "vocal_separation", "choice": 0, "removed_sounds": [], "time_range": None, "production_path": "", "final_algorithm": "", "enter_from": ""})

            eff_track['segments'].append({
                "id": str(uuid.uuid4()).upper(),
                "source_timerange": {"start": 0, "duration": CLICK_DUR},
                "target_timerange": {"start": st, "duration": CLICK_DUR},
                "render_timerange": {"start": 0, "duration": 0},
                "desc": "",
                "state": 0,
                "speed": 1.0,
                "is_loop": False,
                "is_tone_modify": False,
                "reverse": False,
                "intensifies_audio": False,
                "cartoon": False,
                "volume": volume,
                "last_nonzero_volume": 1.0,
                "clip": None,
                "uniform_scale": None,
                "material_id": click_id,
                "extra_material_refs": [s_id, p_id, b_id, scm_id, vs_id],
                "render_index": 0,
                "keyframe_refs": [],
                "enable_lut": False,
                "enable_adjust": False,
                "enable_hsl": False,
                "visible": True,
                "group_id": "",
                "enable_color_curves": True,
                "enable_hsl_curves": True,
                "track_render_index": 0,
                "hdr_settings": None,
                "hdr_vivid_settings": None,
                "enable_color_wheels": True,
                "track_attribute": 0,
                "is_placeholder": False,
                "template_id": "",
                "enable_smart_color_adjust": False,
                "template_scene": "default",
                "common_keyframes": [],
                "caption_info": None,
                "responsive_layout": {"enable": False, "target_follow": "", "size_layout": 0, "horizontal_pos_layout": 0, "vertical_pos_layout": 0},
                "enable_color_match_adjust": False,
                "enable_color_correct_adjust": False,
                "enable_adjust_mask": False,
                "raw_segment_id": "",
                "lyric_keyframes": None,
                "enable_video_mask": True,
                "digital_human_template_group_id": "",
                "color_correct_alg_result": "",
                "source": "segmentsourcenormal",
                "enable_mask_stroke": False,
                "enable_mask_shadow": False,
                "enable_color_adjust_pro": False,
                "segment_color_tag": ""
            })

    def repair_project_subtitles(self, project: CapCutProject) -> Tuple[int, int]:
        """
        Repara la tipografía, tamaño, escala, posición y efectos de los subtítulos existentes
        sin modificar líneas de tiempo (target_timerange / source_timerange) ni editar textos:
        - Pista 0 (Top): Aplica fuente, tamaño, escala, posición Y y sombras de la capa superior.
        - Pista 1 (Bottom): Aplica fuente, tamaño, escala, posición Y, sombras y animación de la capa inferior.
        - Si solo hay 1 pista: Aplica los estilos de la capa superior.
        - Preserva intactos 100% de los timestamps y palabras.
        """
        data = project.data
        materials = data.setdefault('materials', {})
        texts = {t['id']: t for t in materials.setdefault('texts', [])}
        tracks = data.setdefault('tracks', [])
        text_tracks = [t for t in tracks if t.get('type') == 'text']

        if not text_tracks:
            logger.warning("No se encontraron pistas de texto para reparar.")
            return 0, 0

        # Parámetros Top
        top_font_info = self.default_style.get('font', {})
        top_font_name = top_font_info.get('name') or self.default_style.get('font_name', 'none')
        top_font_path = resolve_font_path(top_font_info.get('path') or self.default_style.get('font_path', ''))
        top_font_size = float(self.default_style.get('font_size', 10.0))
        top_rgb = self.default_style.get('rgb_color', [1.0, 1.0, 1.0])

        top_track = text_tracks[0]
        repaired_top = 0

        for seg in top_track.get('segments', []):
            mid = seg.get('material_id')
            tmat = texts.get(mid)
            if not tmat:
                continue

            raw_c = tmat.get('content', '')
            try:
                cj = json.loads(raw_c)
            except Exception:
                cj = {'text': raw_c}

            current_text = cj.get('text', '')
            seg_st = seg.get('target_timerange', {}).get('start', 0)
            seg_dur = seg.get('target_timerange', {}).get('duration', 0)
            seg_et = seg_st + seg_dur

            # Check if this segment in top track was a solo highlight
            is_solo_hl = False
            if (self.preset_data and self.preset_data.get('allow_solo_highlights')) or 'deditos' in self.preset_name.lower():
                has_bot = False
                if len(text_tracks) >= 2:
                    has_bot = any(
                        bs.get('target_timerange', {}).get('start', 0) < seg_et - 50000 and
                        (bs.get('target_timerange', {}).get('start', 0) + bs.get('target_timerange', {}).get('duration', 0)) > seg_st + 50000
                        for bs in text_tracks[1].get('segments', [])
                    )
                if not has_bot and (seg.get('extra_material_refs') or float(tmat.get('font_size', 0)) > (top_font_size + 3.0)):
                    is_solo_hl = True

            if is_solo_hl:
                bot_font_info = self.highlight_style.get('font', {})
                bot_font_name = bot_font_info.get('name') or self.highlight_style.get('font_name', 'none')
                bot_font_path = resolve_font_path(bot_font_info.get('path') or self.highlight_style.get('font_path', ''))
                bot_rgb = self.highlight_style.get('rgb_color', [0.9843137, 0.5568628, 0.282353])

                is_bot_upper = self.highlight_style.get('uppercase', False) or (self.preset_data and self.preset_data.get('uppercase', False))
                if is_bot_upper:
                    current_text = current_text.upper()
                    cj['text'] = current_text
                    if 'words' in tmat and isinstance(tmat['words'], dict):
                        tmat['words']['text'] = [w.upper() for w in tmat['words'].get('text', [])]

                bot_font_size = get_effective_font_size(self.highlight_style, current_text)

                seg['clip'] = {
                    'alpha': 1.0,
                    'flip': {'horizontal': False, 'vertical': False},
                    'rotation': 0.0,
                    'scale': copy.deepcopy(self.bot_scale),
                    'transform': {'x': 0.0, 'y': self.y_top}
                }
                seg['uniform_scale'] = {'on': True, 'value': 1.0}

                anim_ref = self._create_animation(data, seg_dur)
                seg['extra_material_refs'] = [anim_ref] if anim_ref else []

                style_entry = {
                    "fill": {"content": {"render_type": "solid", "solid": {"color": bot_rgb}}},
                    "font": {"path": bot_font_path, "id": ""},
                    "size": bot_font_size,
                    "range": [0, len(current_text)],
                    "useLetterColor": True
                }
                if 'shadow' in self.highlight_style and self.highlight_style['shadow']:
                    style_entry["shadows"] = [copy.deepcopy(self.highlight_style['shadow'])]
                cj['styles'] = [style_entry]
                tmat['content'] = json.dumps(cj, ensure_ascii=False, separators=(',', ':'))
                tmat['base_content'] = json.dumps(cj, ensure_ascii=False, separators=(',', ':'))
                tmat['font_path'] = bot_font_path
                tmat['font_title'] = bot_font_name
                tmat['font_size'] = bot_font_size
                tmat['text_color'] = self.highlight_style.get('color', '#FB8E48')
                repaired_top += 1
                continue

            seg['clip'] = {
                'alpha': 1.0,
                'flip': {'horizontal': False, 'vertical': False},
                'rotation': 0.0,
                'scale': copy.deepcopy(self.top_scale),
                'transform': {'x': 0.0, 'y': self.y_top}
            }
            seg['uniform_scale'] = {'on': True, 'value': 1.0}
            seg['extra_material_refs'] = []

            is_top_upper = self.default_style.get('uppercase', False) or (self.preset_data and self.preset_data.get('uppercase', False))
            if is_top_upper:
                current_text = current_text.upper()
                cj['text'] = current_text
                if 'words' in tmat and isinstance(tmat['words'], dict):
                    tmat['words']['text'] = [w.upper() for w in tmat['words'].get('text', [])]

            top_font_size = get_effective_font_size(self.default_style, current_text)

            style_entry = {
                "fill": {
                    "content": {
                        "render_type": "solid",
                        "solid": {"color": top_rgb}
                    }
                },
                "font": {
                    "path": top_font_path,
                    "id": ""
                },
                "size": top_font_size,
                "range": [0, len(current_text)]
            }
            if 'shadow' in self.default_style and self.default_style['shadow']:
                style_entry["shadows"] = [copy.deepcopy(self.default_style['shadow'])]

            cj['styles'] = [style_entry]
            tmat['content'] = json.dumps(cj, ensure_ascii=False, separators=(',', ':'))
            tmat['base_content'] = json.dumps(cj, ensure_ascii=False, separators=(',', ':'))
            tmat['font_path'] = top_font_path
            tmat['font_title'] = top_font_name
            tmat['font_size'] = top_font_size
            tmat['text_color'] = self.default_style.get('color', '#FFFFFF')
            tmat['has_shadow'] = False
            tmat['shadow'] = None
            repaired_top += 1

        repaired_bot = 0
        if len(text_tracks) >= 2:
            bot_font_info = self.highlight_style.get('font', {})
            bot_font_name = bot_font_info.get('name') or self.highlight_style.get('font_name', 'none')
            bot_font_path = resolve_font_path(bot_font_info.get('path') or self.highlight_style.get('font_path', ''))
            bot_rgb = self.highlight_style.get('rgb_color', [1.0, 1.0, 1.0])
            anim_cfg = self.highlight_style.get('animation', {})

            for bot_track in text_tracks[1:]:
                for seg in bot_track.get('segments', []):
                    seg['clip'] = {
                        'alpha': 1.0,
                        'flip': {'horizontal': False, 'vertical': False},
                        'rotation': 0.0,
                        'scale': copy.deepcopy(self.bot_scale),
                        'transform': {'x': 0.0, 'y': self.y_bottom}
                    }
                    seg['uniform_scale'] = {'on': True, 'value': 1.0}

                    # Animación si el preset lo define
                    if anim_cfg and anim_cfg.get('enabled', False):
                        dur_us = seg.get('target_timerange', {}).get('duration', 500000)
                        anim_ref = self._create_animation(data, dur_us)
                        seg['extra_material_refs'] = [anim_ref] if anim_ref else []
                    else:
                        seg['extra_material_refs'] = []

                    mid = seg.get('material_id')
                    tmat = texts.get(mid)
                    if not tmat:
                        continue

                    raw_c = tmat.get('content', '')
                    try:
                        cj = json.loads(raw_c)
                    except Exception:
                        cj = {'text': raw_c}

                    current_text = cj.get('text', '')
                    is_bot_upper = self.highlight_style.get('uppercase', False) or (self.preset_data and self.preset_data.get('uppercase', False))
                    if is_bot_upper:
                        current_text = current_text.upper()
                        cj['text'] = current_text
                        if 'words' in tmat and isinstance(tmat['words'], dict):
                            tmat['words']['text'] = [w.upper() for w in tmat['words'].get('text', [])]

                    bot_font_size = get_effective_font_size(self.highlight_style, current_text)

                    style_entry = {
                        "fill": {
                            "content": {
                                "render_type": "solid",
                                "solid": {"color": bot_rgb}
                            }
                        },
                        "font": {
                            "path": bot_font_path,
                            "id": ""
                        },
                        "size": bot_font_size,
                        "range": [0, len(current_text)],
                        "useLetterColor": True
                    }
                    if self.highlight_style.get('shadow'):
                        style_entry["shadows"] = [copy.deepcopy(self.highlight_style['shadow'])]

                    cj['styles'] = [style_entry]
                    tmat['content'] = json.dumps(cj, ensure_ascii=False, separators=(',', ':'))
                    tmat['base_content'] = json.dumps(cj, ensure_ascii=False, separators=(',', ':'))
                    tmat['font_path'] = bot_font_path
                    tmat['font_title'] = bot_font_name
                    tmat['font_size'] = bot_font_size
                    tmat['text_color'] = self.highlight_style.get('color', '#FFFFFF')
                    lmw = self.highlight_style.get('line_max_width')
                    if lmw:
                        tmat['line_max_width'] = float(lmw)
                    if self.highlight_style.get('shadow'):
                        tmat['has_shadow'] = True
                        sh = self.highlight_style['shadow']
                        tmat['shadow_color'] = sh.get('color', '#000000')
                        tmat['shadow_alpha'] = float(sh.get('alpha', 0.5))
                        tmat['shadow_distance'] = float(sh.get('distance', 3.0))
                        tmat['shadow_angle'] = float(sh.get('angle', -45.0))
                        tmat['shadow_smoothing'] = float(sh.get('diffuse', 0.45))
                    else:
                        tmat['has_shadow'] = False
                        tmat['shadow'] = None

                    eff_bot_y = self.y_bottom
                    dyn_y_cfg = self.highlight_style.get('dynamic_y') or (self.preset_data.get('bottom', {}).get('dynamic_y') if self.preset_data else None)
                    if dyn_y_cfg and dyn_y_cfg.get('enabled', True):
                        seg_st = seg.get('target_timerange', {}).get('start', 0)
                        seg_dur = seg.get('target_timerange', {}).get('duration', 0)
                        seg_et = seg_st + seg_dur

                        top_text_str = ""
                        for t_seg in text_tracks[0].get('segments', []):
                            t_st = t_seg.get('target_timerange', {}).get('start', 0)
                            t_et = t_st + t_seg.get('target_timerange', {}).get('duration', 0)
                            if max(seg_st, t_st) < min(seg_et, t_et):
                                t_mat = texts.get(t_seg.get('material_id'))
                                if t_mat:
                                    try:
                                        top_text_str = json.loads(t_mat.get('content', '{}')).get('text', '')
                                    except Exception:
                                        top_text_str = t_mat.get('content', '')
                                break

                        descenders = set('pqgyj')
                        has_top_descenders = any(c in descenders for c in top_text_str.lower())
                        has_tall_numbers = any(term.isdigit() and len(term) >= 4 for term in current_text.split()) or len([c for c in current_text if c.isdigit()]) >= 4
                        sz_used = bot_font_size

                        if not top_text_str:
                            eff_bot_y = float(dyn_y_cfg.get('solo_y', 0.0))
                        elif sz_used >= 21.0:
                            if has_top_descenders:
                                eff_bot_y = float(dyn_y_cfg.get('size22_descender_y', -0.1200))
                            else:
                                eff_bot_y = float(dyn_y_cfg.get('size22_y', -0.1138))
                        elif has_top_descenders:
                            eff_bot_y = float(dyn_y_cfg.get('descender_y', -0.1200))
                        elif has_tall_numbers:
                            eff_bot_y = float(dyn_y_cfg.get('tall_numbers_y', -0.1268))
                        elif current_text.islower() and not any(c.isdigit() for c in current_text) and len(current_text) <= 14 and 'compact_y' in dyn_y_cfg:
                            eff_bot_y = float(dyn_y_cfg.get('compact_y', -0.0865))
                        else:
                            eff_bot_y = float(dyn_y_cfg.get('standard_y', -0.1081))

                    seg['clip']['transform']['y'] = eff_bot_y
                    repaired_bot += 1

        is_upper_required = (
            (self.default_style.get('uppercase', False) and self.highlight_style.get('uppercase', False))
            or (self.preset_data and self.preset_data.get('uppercase', False))
            or self.default_style.get('uppercase', False)
        )
        if is_upper_required:
            for t_mat in texts.values():
                rec_txt = t_mat.get('recognize_text', '')
                if rec_txt:
                    t_mat['recognize_text'] = rec_txt.upper()
                c_raw = t_mat.get('content', '')
                if c_raw:
                    try:
                        c_obj = json.loads(c_raw)
                        c_obj['text'] = c_obj.get('text', '').upper()
                        if 'styles' in c_obj and len(c_obj['styles']) == 1:
                            c_obj['styles'][0]['range'] = [0, len(c_obj['text'])]
                        new_c = json.dumps(c_obj, ensure_ascii=False, separators=(',', ':'))
                        t_mat['content'] = new_c
                        t_mat['base_content'] = new_c
                    except Exception:
                        pass
                if 'words' in t_mat and isinstance(t_mat['words'], dict) and 'text' in t_mat['words']:
                    t_mat['words']['text'] = [w.upper() for w in t_mat['words']['text']]

        project._parse_subtitles()
        return repaired_top, repaired_bot


    def auto_inline_process(
        self,
        project: CapCutProject,
        highlighter=None,
        openrouter_key: Optional[str] = None,
        model: Optional[str] = None,
        min_pacing_sec: Optional[float] = None,
        max_pacing_sec: Optional[float] = None,
        max_chars_per_line: Optional[int] = None,
        max_words_per_line: Optional[int] = None,
        log_fn=None
    ) -> Tuple[int, int]:
        """
        Inline single-track rich-text subtitle styler (e.g. Jose Podólogo):
        - All subtitles remain on Track 0.
        - Highlights are spaced out with generous rests/descansos (min_pacing_sec >= 6.5s and min_neutral_segments >= 3).
        - Subtitles during descansos are 100% white Aglatia.
        - When a highlight occurs, the keyword is styled inline in Yellow (#F4C70F) or Red (#EC1D1D for negative terms)
          directly within the same text material via CapCut is_rich_text styles.
        - Synchronized audio clicks on each highlight onset.
        - 0 commas, 0 dots, 0 colons, 0 ellipses.
        """
        pacing_cfg = getattr(self, 'pacing', {})
        effective_min_pacing = min_pacing_sec if (min_pacing_sec is not None and min_pacing_sec != 3.0) else float(pacing_cfg.get('min_seconds', 6.5))
        min_neutral = int(pacing_cfg.get('min_neutral_segments', 3))

        margin_cfg = getattr(self, 'margins', {})
        effective_max_chars = max_chars_per_line if (max_chars_per_line is not None and max_chars_per_line != 18) else int(margin_cfg.get('max_chars_per_line', 20))

        # 1. Read Track 0 speech subtitles
        text_track_indices = [i for i, t in enumerate(project.data.get('tracks', [])) if t.get('type') == 'text']
        if text_track_indices:
            first_text_idx = text_track_indices[0]
            subs = [s for s in project.subtitles if s.track_index == first_text_idx]
        else:
            subs = project.subtitles

        if not subs:
            logger.warning("No subtitles found to process.")
            return 0, 0

        raw_items = []
        for idx, s in enumerate(subs):
            txt = clean_subtitle_text(s.text)
            if txt and s.duration_us > 0:
                raw_items.append({
                    'index': idx,
                    'item': s,
                    'text': txt,
                    'start': s.start_us,
                    'end': s.start_us + s.duration_us,
                    'duration': s.duration_us,
                    'words': s.text_material.get('words')
                })

        if not raw_items:
            return 0, 0

        eff_max_chars = effective_max_chars
        eff_max_words = int(margin_cfg.get('max_words_per_line', 3))
        raw_items = self._consolidate_number_segments(raw_items, max_chars=eff_max_chars, max_words=eff_max_words)

        # For inline styling: synchronize Track 0 segments if any were merged
        absorbed_seg_ids = set()
        for item in raw_items:
            if 'absorbed_indices' in item and item['absorbed_indices']:
                if item.get('item') and getattr(item['item'], 'segment', None):
                    item['item'].segment.setdefault('target_timerange', {})['duration'] = item['duration']
            for abs_idx in item.get('absorbed_indices', []):
                if abs_idx < len(subs):
                    abs_sub = subs[abs_idx]
                    if getattr(abs_sub, 'segment', None) and 'id' in abs_sub.segment:
                        absorbed_seg_ids.add(abs_sub.segment['id'])

        if absorbed_seg_ids and text_track_indices:
            trk = project.data['tracks'][first_text_idx]
            trk['segments'] = [seg for seg in trk.get('segments', []) if seg.get('id') not in absorbed_seg_ids]

        # 2. AI Processing with OpenRouter
        ai_phrases = []
        effective_key = openrouter_key or (getattr(highlighter, 'api_key', None) if getattr(highlighter, 'provider', None) == 'openrouter' else None) or os.environ.get('OPENROUTER_API_KEY')
        if effective_key:
            try:
                m = model or getattr(highlighter, 'model', None) or DEFAULT_MODEL
                if log_fn:
                    log_fn(f"[*] Conectando con OpenRouter ({m})...")
                client = OpenRouterClient(api_key=effective_key, model=m)
                ai_res = client.process_subtitles(raw_items)
                if ai_res:
                    # Align AI corrections strictly to original acoustic word slots via SequenceMatcher
                    # Prevents index-shifting and guarantees 100% voice synchronization
                    corrected_subs = ai_res.get('corrected_subtitles', [])
                    align_ai_corrections_to_raw_items(raw_items, corrected_subs)

                    idx_to_text = {item['index']: item['text'] for item in raw_items}
                    for h in ai_res.get('highlights', []):
                        p = convert_spanish_numbers_to_digits(clean_subtitle_text(h.get('phrase', '')))
                        tone = h.get('tone', 'normal')
                        if not p:
                            t_idx = h.get('target_index')
                            if t_idx is not None:
                                p = convert_spanish_numbers_to_digits(clean_subtitle_text(idx_to_text.get(t_idx, '')))
                        if p:
                            ai_phrases.append({'phrase': p, 'tone': tone})
                    msg = f"[OK] OpenRouter procesó {len(raw_items)} subtítulos y curó {len(ai_phrases)} palabras destacadas (con descansos)."

                    logger.info(msg)
                    if log_fn:
                        log_fn(msg)
                else:
                    msg = "[!] OpenRouter no devolvió resultados. Usando generador heurístico de respaldo..."
                    logger.warning(msg)
                    if log_fn:
                        log_fn(msg)
            except Exception as e:
                msg = f"[!] Error en OpenRouter ({e}). Usando generador heurístico de respaldo..."
                logger.warning(msg)
                if log_fn:
                    log_fn(msg)

        full_script = " ".join(item['text'] for item in raw_items)
        phrases_to_highlight = ai_phrases

        if not phrases_to_highlight and highlighter:
            try:
                suggested = highlighter.suggest_highlights(full_script, count=15)
                phrases_to_highlight = [clean_subtitle_text(p) for p in suggested if clean_subtitle_text(p)]
            except Exception as e:
                logger.warning(f"Highlighter error: {e}")

        if not phrases_to_highlight:
            from ai.highlighter import AIHighlighter
            hl = AIHighlighter(provider='heuristic')
            suggested = hl.suggest_highlights(full_script, count=15)
            phrases_to_highlight = [clean_subtitle_text(p) for p in suggested if clean_subtitle_text(p)]

        # 3. Setup styling configs
        top_style = self.default_style
        hl_style = getattr(self, 'highlight_cfg', self.highlight_style)
        
        font_path = resolve_font_path(top_style.get('font_path', 'Aglatia.ttf'))
        font_size = float(top_style.get('font_size', 9.0))
        letter_spacing = float(top_style.get('letter_spacing', -0.05))
        base_rgb = top_style.get('rgb_color', [1.0, 1.0, 1.0])
        
        hl_rgb = hl_style.get('rgb_color', [0.95686, 0.78039, 0.05882])
        neg_rgb = hl_style.get('negative_rgb_color', [0.92549, 0.11372, 0.11372])
        shadow_cfg = top_style.get('shadow', {
            "alpha": 0.4952380955219269,
            "angle": -45,
            "diffuse": 0.02500000037252903,
            "distance": 2.9999992847442627,
            "content": {"render_type": "solid", "solid": {"color": [0, 0, 0]}},
            "thickness_projection_angle": -45,
            "thickness_projection_distance": 0,
            "thickness_projection_enable": False
        })

        last_highlight_us = -int(effective_min_pacing * 1e6)
        neutral_segments = min_neutral
        highlight_count = 0
        click_starts = []

        # 4. Process each subtitle
        for curr in raw_items:
            curr_text = clean_subtitle_text(curr['text'])
            curr_start = curr['start']
            curr_end = curr['end']
            curr_dur = curr['duration']
            words_data = curr['words']
            item_obj = curr['item']

            time_since_last_sec = (curr_start - last_highlight_us) / 1e6
            can_highlight = (time_since_last_sec >= effective_min_pacing) and (neutral_segments >= min_neutral)

            matched_phrase = None
            matched_tone = 'normal'

            if can_highlight:
                lower_text = curr_text.lower()
                import re
                for neg_kw in NEGATIVE_KEYWORDS:
                    if re.search(r'\b' + re.escape(neg_kw) + r'\b', lower_text):
                        matched_phrase = neg_kw
                        matched_tone = 'negative'
                        break

                if not matched_phrase:
                    for entry in phrases_to_highlight:
                        if isinstance(entry, dict):
                            p = entry.get('phrase', '')
                            tone = entry.get('tone', 'normal')
                        else:
                            p = str(entry)
                            tone = 'normal'
                        p_clean = clean_subtitle_text(p)
                        if p_clean and len(p_clean) <= effective_max_chars:
                            if p_clean.lower() in lower_text:
                                matched_phrase = p_clean
                                matched_tone = tone
                                if self._is_negative_term(matched_phrase):
                                    matched_tone = 'negative'
                                break

            # Format subtitle
            if matched_phrase and matched_phrase.lower() in curr_text.lower():
                lower_curr = curr_text.lower()
                p_idx = lower_curr.find(matched_phrase.lower())
                p_end = p_idx + len(matched_phrase)
                if len(matched_phrase) >= 4:
                    while p_idx > 0 and not curr_text[p_idx - 1].isspace():
                        p_idx -= 1
                    while p_end < len(curr_text) and not curr_text[p_end].isspace():
                        p_end += 1
                    while p_end > p_idx and curr_text[p_end - 1] in '.,;:!?¿¡"\'':
                        p_end -= 1
                    while p_idx < p_end and curr_text[p_idx] in '.,;:!?¿¡"\'':
                        p_idx += 1
                actual_phrase = curr_text[p_idx:p_end]

                is_neg = (matched_tone == 'negative') or self._is_negative_term(actual_phrase)
                hl_color = neg_rgb if is_neg else hl_rgb

                hl_start, _ = find_phrase_timing(curr_start, curr_dur, words_data, curr_text, actual_phrase)
                click_starts.append(hl_start)

                styles = []
                if p_idx > 0:
                    styles.append({
                        "fill": {"content": {"render_type": "solid", "solid": {"color": base_rgb}}},
                        "font": {"path": font_path, "id": ""},
                        "size": font_size,
                        "shadows": [copy.deepcopy(shadow_cfg)],
                        "range": [0, p_idx]
                    })
                styles.append({
                    "fill": {"content": {"render_type": "solid", "solid": {"color": hl_color}}},
                    "font": {"path": font_path, "id": ""},
                    "size": font_size,
                    "shadows": [copy.deepcopy(shadow_cfg)],
                    "range": [p_idx, p_end],
                    "useLetterColor": True
                })
                if p_end < len(curr_text):
                    styles.append({
                        "fill": {"content": {"render_type": "solid", "solid": {"color": base_rgb}}},
                        "font": {"path": font_path, "id": ""},
                        "size": font_size,
                        "shadows": [copy.deepcopy(shadow_cfg)],
                        "range": [p_end, len(curr_text)]
                    })

                content_obj = {
                    "text": curr_text,
                    "styles": styles
                }
                hex_col = "#EC1D1D" if is_neg else "#F4C70F"
                is_rich = True
                last_highlight_us = hl_start
                neutral_segments = 0
                highlight_count += 1
            else:
                content_obj = {
                    "text": curr_text,
                    "styles": [{
                        "fill": {"content": {"render_type": "solid", "solid": {"color": base_rgb}}},
                        "font": {"path": font_path, "id": ""},
                        "size": font_size,
                        "shadows": [copy.deepcopy(shadow_cfg)],
                        "range": [0, len(curr_text)]
                    }]
                }
                hex_col = "#FFFFFF"
                is_rich = False
                neutral_segments += 1

            # Update material in project
            item_obj.parsed_content = content_obj
            item_obj.text_material['font_path'] = font_path
            item_obj.text_material['font_title'] = "Aglatia"
            item_obj.text_material['font_id'] = ""
            item_obj.text_material['font_resource_id'] = ""
            item_obj.text_material['font_source_platform'] = 0
            item_obj.text_material['fonts'] = []
            item_obj.text_material['letter_spacing'] = letter_spacing
            item_obj.text_material['font_size'] = font_size
            item_obj.text_material['text_color'] = hex_col
            item_obj.text_material['is_rich_text'] = is_rich
            item_obj.text_material['has_shadow'] = False
            item_obj.sync_content_to_material()

            # Align transform y and scale
            seg = item_obj.segment
            if seg:
                clip = seg.setdefault('clip', {})
                clip['scale'] = top_style.get('scale', {"x": 1.355, "y": 1.355})
                trans = clip.setdefault('transform', {})
                trans['y'] = top_style.get('y', -0.11634766240146056)

        # 5. Clean up any extra text tracks from old dual runs
        if len(text_track_indices) > 1:
            for extra_idx in text_track_indices[1:]:
                project.data['tracks'][extra_idx]['segments'] = []

        # 6. Add sound FX for each highlight onset
        if getattr(self, 'sound_fx', {}).get('enabled', True) and click_starts:
            vol = float(self.sound_fx.get('volume', 0.65))
            snd_name = self.sound_fx.get('name', 'Click_Mouse_Click_02(864360)')
            snd_path = self.sound_fx.get('path')
            if not snd_path or not os.path.isfile(snd_path):
                snd_path = get_default_click_sound_path()
            self._add_click_sound_fx(project.data, click_starts, volume=vol, sound_name=snd_name, sound_path=snd_path)

        project.clean_all_subtitles()
        project._parse_subtitles()
        return len(raw_items), highlight_count


    def auto_template_process(
        self,
        project: CapCutProject,
        highlighter=None,
        openrouter_key: Optional[str] = None,
        model: Optional[str] = None,
        min_pacing_sec: Optional[float] = None,
        max_pacing_sec: Optional[float] = None,
        max_chars_per_line: Optional[int] = None,
        max_words_per_line: Optional[int] = None,
        log_fn=None
    ) -> Tuple[int, int]:
        """
        Single-track CapCut native template subtitle styler (e.g. Ana Otorrino / 0922):
        - Subtitles are styled using CapCut's native text_template_subtitle with loop floating animation.
        - Base words: Liliana Bold, #FFFFFF, size 9.
        - Highlight words: Liliana Black, #FDE69A, size 11, useLetterColor: true within the same subtitle.
        - Fixed layer name 'D6B3869B-42B9-43ED-8435-C814651D7122' ensures exact CapCut template engine binding.
        - Generous pacing every ~3-5s.
        - 0 commas, 0 dots, 0 colons, 0 ellipses.
        """
        pacing_cfg = getattr(self, 'pacing', {})
        effective_min_pacing = min_pacing_sec if (min_pacing_sec is not None and min_pacing_sec != 3.0) else float(pacing_cfg.get('min_seconds', 3.0))
        min_neutral = int(pacing_cfg.get('min_neutral_segments', 1))

        margin_cfg = getattr(self, 'margins', {})
        eff_max_chars = max_chars_per_line if (max_chars_per_line is not None and max_chars_per_line != 18) else int(margin_cfg.get('max_chars_per_line', 21))

        # 1. Read Track 0 speech subtitles
        text_track_indices = [i for i, t in enumerate(project.data.get('tracks', [])) if t.get('type') == 'text']
        if not text_track_indices:
            logger.warning("No text track found in project.")
            return 0, 0
        first_text_idx = text_track_indices[0]
        text_track = project.data['tracks'][first_text_idx]
        segments = text_track.get('segments', [])
        if not segments:
            logger.warning("No segments in text track.")
            return 0, 0

        materials = project.data.setdefault('materials', {})
        texts_list = materials.setdefault('texts', [])
        texts_by_id = {t['id']: t for t in texts_list if isinstance(t, dict) and 'id' in t}
        templates_by_id = {t['id']: t for t in materials.setdefault('text_templates', []) if isinstance(t, dict) and 'id' in t}

        raw_items = []
        for idx, seg in enumerate(segments):
            mat_id = seg.get('material_id')
            t_mat = None
            if mat_id in texts_by_id:
                t_mat = texts_by_id[mat_id]
            elif mat_id in templates_by_id:
                res_list = templates_by_id[mat_id].get('text_info_resources', [])
                if res_list and res_list[0].get('text_material_id') in texts_by_id:
                    t_mat = texts_by_id[res_list[0]['text_material_id']]

            raw_text = ''
            if t_mat:
                c_str = t_mat.get('content', '')
                try:
                    c_obj = json.loads(c_str)
                    raw_text = c_obj.get('text', '')
                except Exception:
                    raw_text = t_mat.get('recognize_text', '')

            txt = clean_subtitle_text(raw_text)
            tr = seg.get('target_timerange', {})
            start_us = tr.get('start', 0)
            dur_us = tr.get('duration', 0)

            raw_items.append({
                'index': idx,
                'segment': seg,
                'text_material': t_mat,
                'text': txt,
                'start': start_us,
                'end': start_us + dur_us,
                'duration': dur_us,
                'words': t_mat.get('words') if t_mat else None
            })

        if not raw_items:
            return 0, 0

        # Helper: never allow isolated single words / connectors as independent segments
        ORPHAN_CONNECTORS = {
            'que', 'la', 'lo', 'el', 'de', 'y', 'en', 'un', 'una', 'a', 'por', 'con', 'o',
            'pero', 'si', 'es', 'se', 'te', 'me', 'su', 'al', 'del', 'los', 'las', 'unos', 'unas'
        }

        def merge_orphan_subtitles(items):
            merged = []
            i = 0
            while i < len(items):
                curr = items[i]
                words = curr['text'].split()
                is_orphan = (len(words) <= 1 and (not words or words[0].lower() in ORPHAN_CONNECTORS)) or (len(words) == 1 and curr['duration'] < 700000)
                if is_orphan:
                    if i + 1 < len(items):
                        nxt = items[i+1]
                        nxt['text'] = curr['text'] + ' ' + nxt['text']
                        c_w = curr.get('words') or {}
                        n_w = nxt.get('words') or {}
                        if c_w and n_w:
                            nxt_shift_ms = int((nxt['start'] - curr['start']) // 1000)
                            shifted_n_starts = [s + nxt_shift_ms for s in n_w.get('start_time', [])]
                            shifted_n_ends = [e + nxt_shift_ms for e in n_w.get('end_time', [])]
                            nxt['words'] = {
                                'text': c_w.get('text', []) + [' '] + n_w.get('text', []),
                                'start_time': c_w.get('start_time', []) + [0] + shifted_n_starts,
                                'end_time': c_w.get('end_time', []) + [0] + shifted_n_ends
                            }
                        nxt['duration'] = (nxt['start'] + nxt['duration']) - curr['start']
                        nxt['start'] = curr['start']
                    elif merged:
                        prev = merged[-1]
                        prev['text'] = prev['text'] + ' ' + curr['text']
                        prev['duration'] = (curr['start'] + curr['duration']) - prev['start']
                    i += 1
                    continue
                merged.append(curr)
                i += 1
            return merged

        def split_long_subtitles(items, max_chars=44, max_words=9):
            final_items = []

            def _split_item(item):
                txt = item['text']
                words_list = txt.split()
                if len(words_list) <= max_words and len(txt) <= max_chars:
                    return [item]

                w_dict = item.get('words') or {}
                tokens = w_dict.get('text', [])
                starts = w_dict.get('start_time', [])
                ends = w_dict.get('end_time', [])

                word_indices = [idx for idx, t in enumerate(tokens) if t.strip()]
                if len(word_indices) <= 3:
                    return [item]

                mid_idx = len(word_indices) // 2
                best_split_k = mid_idx
                best_penalty = float('inf')

                for k in range(max(2, mid_idx - 2), min(len(word_indices) - 1, mid_idx + 3)):
                    w_before = tokens[word_indices[k-1]].lower()
                    w_after = tokens[word_indices[k]].lower()
                    pen = abs(k - mid_idx) * 6
                    if w_before in {'un', 'una', 'el', 'la', 'los', 'las', 'de', 'del', 'al', 'su', 'mi', 'tu', 'y', 'o'}:
                        pen += 50
                    if w_after in {'y', 'pero', 'que', 'cuando', 'donde', 'porque', 'aunque', 'para', 'de', 'en'}:
                        pen -= 15
                    if pen < best_penalty:
                        best_penalty = pen
                        best_split_k = k

                split_tok_idx = word_indices[best_split_k]
                split_time_ms = ends[word_indices[best_split_k - 1]] if best_split_k - 1 < len(ends) else int((item['duration'] // 2000))
                split_time_us = int(split_time_ms * 1000)

                toks_a = tokens[:split_tok_idx]
                starts_a = starts[:split_tok_idx]
                ends_a = ends[:split_tok_idx]
                txt_a = "".join(toks_a).strip()
                dur_a_us = max(400000, min(item['duration'] - 400000, split_time_us))

                item_a = {
                    'text': txt_a,
                    'start': item['start'],
                    'duration': dur_a_us,
                    'words': {'text': toks_a, 'start_time': starts_a, 'end_time': ends_a}
                }

                toks_b = tokens[split_tok_idx:]
                shift_ms = int(dur_a_us // 1000)
                starts_b = [max(0, s - shift_ms) for s in starts[split_tok_idx:]]
                ends_b = [max(0, e - shift_ms) for e in ends[split_tok_idx:]]
                txt_b = "".join(toks_b).strip()
                start_b_us = item['start'] + dur_a_us
                dur_b_us = max(400000, item['duration'] - dur_a_us)

                item_b = {
                    'text': txt_b,
                    'start': start_b_us,
                    'duration': dur_b_us,
                    'words': {'text': toks_b, 'start_time': starts_b, 'end_time': ends_b}
                }

                out = []
                out.extend(_split_item(item_a))
                out.extend(_split_item(item_b))
                return out

            for it in items:
                final_items.extend(_split_item(it))
            return final_items

        def balance_line(text: str, max_len: int = eff_max_chars) -> str:
            words = text.split()
            if not words:
                return text
            if len(text) <= max_len or len(words) <= 2:
                return text

            best_split = len(words) // 2
            best_penalty = float('inf')

            for i in range(1, len(words)):
                l1 = ' '.join(words[:i])
                l2 = ' '.join(words[i:])

                p_len1 = max(0, len(l1) - max_len) * 25
                p_len2 = max(0, len(l2) - max_len) * 25
                p_diff = abs(len(l1) - len(l2)) * 1.5

                if len(words[:i]) == 1:
                    p_len1 += 120
                if len(words[i:]) == 1:
                    p_len2 += 120

                if words[i-1].lower() in {'de', 'que', 'en', 'a', 'la', 'el', 'un', 'una', 'y', 'al', 'del'}:
                    p_len1 += 35

                total_p = p_len1 + p_len2 + p_diff
                if total_p < best_penalty:
                    best_penalty = total_p
                    best_split = i

            line1 = ' '.join(words[:best_split])
            line2 = ' '.join(words[best_split:])
            return f'{line1}\n{line2}'

        # Preprocessing: merge orphan single words and split long overflowing cards
        raw_items = merge_orphan_subtitles(raw_items)
        raw_items = split_long_subtitles(raw_items, max_chars=44, max_words=9)
        for idx, it in enumerate(raw_items):
            it['index'] = idx

        # 2. AI Processing with OpenRouter or Heuristic Highlighter
        ai_phrases = []
        effective_key = openrouter_key or (getattr(highlighter, 'api_key', None) if getattr(highlighter, 'provider', None) == 'openrouter' else None) or os.environ.get('OPENROUTER_API_KEY')
        if not effective_key:
            cfg_p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.cc_subs_pro_config.json')
            if os.path.isfile(cfg_p):
                try:
                    with open(cfg_p, 'r', encoding='utf-8') as f:
                        cfg_d = json.load(f)
                        effective_key = cfg_d.get('openrouter_key') or cfg_d.get('api_key')
                except Exception:
                    pass
        if effective_key:
            try:
                m = model or getattr(highlighter, 'model', None) or DEFAULT_MODEL
                if log_fn:
                    log_fn(f"[*] Conectando con OpenRouter ({m})...")
                client = OpenRouterClient(api_key=effective_key, model=m)
                ai_res = client.process_subtitles(raw_items)
                if ai_res:
                    idx_to_text = {item['index']: item['text'] for item in raw_items}
                    for h in ai_res.get('highlights', []):
                        p = convert_spanish_numbers_to_digits(clean_subtitle_text(h.get('phrase', '')))
                        tone = h.get('tone', 'normal')
                        if not p:
                            t_idx = h.get('target_index')
                            if t_idx is not None:
                                p = convert_spanish_numbers_to_digits(clean_subtitle_text(idx_to_text.get(t_idx, '')))
                        if p:
                            ai_phrases.append({'phrase': p, 'tone': tone})
                    msg = f"[+] OpenRouter procesó subtítulos y curó {len(ai_phrases)} palabras destacadas para la plantilla."
                    logger.info(msg)
                    if log_fn:
                        log_fn(msg)
            except Exception as e:
                msg = f"[!] Error en OpenRouter ({e}). Usando generador heurístico de respaldo..."
                logger.warning(msg)
                if log_fn:
                    log_fn(msg)

        full_script = " ".join(item['text'] for item in raw_items)
        phrases_to_highlight = ai_phrases

        if not phrases_to_highlight and highlighter:
            try:
                suggested = highlighter.suggest_highlights(full_script, count=15)
                phrases_to_highlight = [{'phrase': clean_subtitle_text(p), 'tone': 'normal'} for p in suggested if clean_subtitle_text(p)]
            except Exception as e:
                logger.warning(f"Highlighter error: {e}")

        if not phrases_to_highlight:
            from ai.highlighter import AIHighlighter
            hl = AIHighlighter(provider='heuristic')
            suggested = hl.suggest_highlights(full_script, count=15)
            phrases_to_highlight = [{'phrase': clean_subtitle_text(p), 'tone': 'normal'} for p in suggested if clean_subtitle_text(p)]

        # 3. Setup styling configs
        top_style = self.default_style
        hl_style = getattr(self, 'highlight_cfg', self.highlight_style)
        tmpl_cfg = getattr(self, 'preset_data', {}).get('template', {})
        anim_cfg = getattr(self, 'preset_data', {}).get('animation', {})

        base_font = resolve_font_path(top_style.get('font_path', 'Liliana-Bold.otf'))
        hl_font = resolve_font_path(hl_style.get('font_path', 'Liliana-Black.otf'))
        base_size = float(top_style.get('font_size', 9.0))
        hl_size = float(hl_style.get('font_size', 11.0))
        base_color = top_style.get('rgb_color', [1, 1, 1])
        hl_color = hl_style.get('rgb_color', [0.99215686321258545, 0.901960790157318, 0.60392159223556519])
        y_pos = float(top_style.get('y', -0.049913544668588106))
        layer_name = tmpl_cfg.get('layer_name', 'D6B3869B-42B9-43ED-8435-C814651D7122')
        effect_id = tmpl_cfg.get('effect_id', '7331663549263023366')
        tmpl_name = tmpl_cfg.get('name', '基础上浮')
        tmpl_path = resolve_effect_path(effect_id, tmpl_cfg.get('path', ''))

        anim_res_id = anim_cfg.get('resource_id', '7258195155394499074')
        anim_path = resolve_effect_path('55651785', anim_cfg.get('path', ''))
        anim_duration = int(anim_cfg.get('duration', 500000))

        shadow_obj = top_style.get('shadow', {
            "thickness_projection_angle": -45,
            "thickness_projection_enable": False,
            "alpha": 0.9206600189208984,
            "distance": 4.902493000030518,
            "content": {"render_type": "solid", "solid": {"color": [0, 0, 0]}},
            "feather": 0.017568999901413918,
            "diffuse": 0.017568999901413918,
            "angle": -28.152999877929688,
            "thickness_projection_distance": 0
        })

        last_highlight_us = -int(effective_min_pacing * 1e6)
        neutral_segments = min_neutral
        highlight_count = 0
        click_starts = []

        new_texts = []
        new_tmpls = []
        new_anims = []
        new_segments = []

        # 4. Process each subtitle segment
        for item_idx, curr in enumerate(raw_items):
            clean_text = clean_subtitle_text(curr['text'])
            formatted_text = balance_line(clean_text)
            curr_start = curr['start']
            curr_dur = curr['duration']
            old_t_mat = curr.get('text_material')

            # Acoustic healing & lead-out duration calculation
            nxt_start = raw_items[item_idx + 1]['start'] if item_idx + 1 < len(raw_items) else curr_start + curr_dur + 5000000

            old_w = curr.get('words') or (old_t_mat.get('words', {}) if (old_t_mat and isinstance(old_t_mat.get('words'), dict)) else {})
            old_words_list = []
            for txt, ws, we in zip(old_w.get('text', []), old_w.get('start_time', []), old_w.get('end_time', [])):
                if txt.strip():
                    old_words_list.append((txt.strip(), ws, we))

            max_wend_us = (max(we for _, _, we in old_words_list) * 1000) if old_words_list else curr_dur
            eff_dur = max(curr_dur, max_wend_us)
            if curr_start + eff_dur > nxt_start - 50000 and item_idx + 1 < len(raw_items):
                eff_dur = max(curr_dur, nxt_start - curr_start - 50000)

            gap_after = nxt_start - (curr_start + eff_dur)
            padding_us = min(500000, gap_after - 80000) if gap_after > 150000 else 0
            final_dur_us = eff_dur + padding_us
            final_dur_ms = int(final_dur_us // 1000)

            # Tokenize preserving spaces and newlines so letter indexing never drifts
            tokens = [tok for tok in re.split(r'(\s+)', formatted_text) if tok]
            text_words = [tok for tok in tokens if not tok.isspace()]
            
            matched_timings = []
            if len(old_words_list) <= 1 and len(text_words) > 1:
                step_ms = final_dur_ms / len(text_words)
                for k, tw in enumerate(text_words):
                    ws = int(k * step_ms)
                    we = int((k + 1) * step_ms)
                    matched_timings.append((tw, ws, we))
            else:
                old_idx = 0
                for tw in text_words:
                    clean_tw = re.sub(r'[^\w]', '', tw.lower())
                    found = False
                    while old_idx < len(old_words_list):
                        ow, ow_s, ow_e = old_words_list[old_idx]
                        old_idx += 1
                        clean_ow = re.sub(r'[^\w]', '', ow.lower())
                        if clean_tw == clean_ow or clean_tw in clean_ow or clean_ow in clean_tw:
                            matched_timings.append((tw, ow_s, ow_e))
                            found = True
                            break
                    if not found:
                        prev_e = matched_timings[-1][2] if matched_timings else 0
                        matched_timings.append((tw, prev_e, min(prev_e + 250, final_dur_ms)))

            # Accelerate word entrance timings so final words appear earlier and have ample display time
            if matched_timings:
                last_idx = len(matched_timings) - 1
                last_w, last_s, last_e = matched_timings[last_idx]

                min_last_hold = max(550, int(final_dur_ms * 0.42))
                if final_dur_ms < 1100:
                    min_last_hold = max(420, int(final_dur_ms * 0.45))
                min_last_hold = min(min_last_hold, max(300, final_dur_ms - 200))

                target_last_start = max(0, final_dur_ms - min_last_hold)

                if last_s > target_last_start and last_s > 0:
                    alpha = target_last_start / float(last_s)
                    new_matched = []
                    for k_idx, (tw, s_val, e_val) in enumerate(matched_timings):
                        if k_idx == last_idx:
                            new_s = target_last_start
                            new_e = final_dur_ms
                        else:
                            new_s = int(s_val * alpha)
                            nxt_s_scaled = int(matched_timings[k_idx + 1][1] * alpha) if k_idx + 1 < last_idx else target_last_start
                            scaled_e = int(e_val * alpha)
                            new_e = max(new_s, min(scaled_e, nxt_s_scaled))
                        new_matched.append((tw, new_s, new_e))
                    matched_timings = new_matched
                else:
                    matched_timings[last_idx] = (last_w, min(last_s, target_last_start), final_dur_ms)

                if matched_timings[-1][2] > final_dur_ms:
                    max_t = matched_timings[-1][2]
                    matched_timings = [
                        (tw, int(s * final_dur_ms / max_t), int(e * final_dur_ms / max_t))
                        for (tw, s, e) in matched_timings
                    ]

            token_texts = []
            token_starts = []
            token_ends = []
            word_k = 0
            for tok in tokens:
                token_texts.append(tok)
                if not tok.isspace():
                    tw, ws, we = matched_timings[word_k]
                    ws_ms = int(ws)
                    we_ms = int(we)
                    if word_k == len(text_words) - 1:
                        we_ms = max(we_ms, final_dur_ms)
                    token_starts.append(ws_ms)
                    token_ends.append(we_ms)
                    word_k += 1
                else:
                    prev_e = token_ends[-1] if token_ends else 0
                    nxt_s = int(matched_timings[word_k][1]) if word_k < len(matched_timings) else prev_e
                    token_starts.append(prev_e)
                    token_ends.append(max(prev_e, nxt_s))

            time_since_last_sec = (curr_start - last_highlight_us) / 1e6
            can_highlight = (time_since_last_sec >= effective_min_pacing) and (neutral_segments >= min_neutral)

            matched_phrase = None
            hl_range = None

            if can_highlight:
                clean_lower = formatted_text.lower()
                for cand in phrases_to_highlight:
                    cand_str = cand.get('phrase', '') if isinstance(cand, dict) else str(cand)
                    cand_clean = clean_subtitle_text(cand_str)
                    if not cand_clean:
                        continue

                    cand_words = cand_clean.split()
                    if not cand_words:
                        continue

                    # 1. Whole-word regex match
                    pattern = r'\b' + r'\s+'.join(re.escape(w) for w in cand_words) + r'\b'
                    m = re.search(pattern, formatted_text, re.IGNORECASE)
                    if m:
                        matched_phrase = cand_clean
                        hl_range = (m.start(), m.end())
                        break

                    # 2. Substring match expanded to full word boundaries (e.g. "composición" -> "recomposición")
                    if len(cand_clean) >= 4:
                        idx_match = clean_lower.find(cand_clean.lower())
                        if idx_match != -1:
                            matched_phrase = cand_clean
                            raw_start = idx_match
                            raw_end = idx_match + len(cand_clean)
                            # Expand to full word boundaries so we never split prefixes/suffixes like "re-"
                            while raw_start > 0 and not formatted_text[raw_start - 1].isspace():
                                raw_start -= 1
                            while raw_end < len(formatted_text) and not formatted_text[raw_end].isspace():
                                raw_end += 1
                            while raw_end > raw_start and formatted_text[raw_end - 1] in '.,;:!?¿¡"\'':
                                raw_end -= 1
                            while raw_start < raw_end and formatted_text[raw_start] in '.,;:!?¿¡"\'':
                                raw_start += 1
                            hl_range = (raw_start, raw_end)
                            break

            # Build styles
            styles = []
            L = len(formatted_text)
            if hl_range:
                h_start, h_end = hl_range
                if h_start > 0:
                    styles.append({
                        "fill": {"content": {"render_type": "solid", "solid": {"color": base_color}}},
                        "font": {"path": base_font, "id": ""},
                        "range": [0, h_start],
                        "size": int(base_size),
                        "shadows": [copy.deepcopy(shadow_obj)]
                    })
                styles.append({
                    "fill": {"content": {"render_type": "solid", "solid": {"color": hl_color}}},
                    "font": {"path": hl_font, "id": ""},
                    "range": [h_start, h_end],
                    "size": int(hl_size),
                    "useLetterColor": True,
                    "shadows": [copy.deepcopy(shadow_obj)]
                })
                if h_end < L:
                    styles.append({
                        "fill": {"content": {"render_type": "solid", "solid": {"color": base_color}}},
                        "font": {"path": base_font, "id": ""},
                        "range": [h_end, L],
                        "size": int(base_size),
                        "shadows": [copy.deepcopy(shadow_obj)]
                    })
                last_highlight_us = curr_start
                neutral_segments = 0
                highlight_count += 1
                click_starts.append(curr_start)
            else:
                styles.append({
                    "fill": {"content": {"render_type": "solid", "solid": {"color": base_color}}},
                    "font": {"path": base_font, "id": ""},
                    "range": [0, L],
                    "size": int(base_size),
                    "shadows": [copy.deepcopy(shadow_obj)]
                })
                neutral_segments += 1

            new_text_id = str(uuid.uuid4()).upper()
            new_tmpl_id = str(uuid.uuid4()).upper()
            new_anim_id = str(uuid.uuid4()).upper()
            new_info_id = str(uuid.uuid4()).upper()

            # Text material
            text_mat = {
                "id": new_text_id,
                "name": layer_name,
                "recognize_text": clean_text,
                "recognize_task_id": old_t_mat.get('recognize_task_id', '') if old_t_mat else '',
                "content": json.dumps({"text": formatted_text, "styles": styles}, ensure_ascii=False, separators=(',', ':')),
                "base_content": "",
                "type": "text",
                "font_path": hl_font if hl_range else base_font,
                "font_size": hl_size if hl_range else base_size,
                "font_title": "none",
                "font_name": "",
                "fonts": [],
                "text_color": "#fde69a" if hl_range else "#ffffff",
                "text_alpha": 1.0,
                "alignment": 1,
                "line_feed": 1,
                "line_spacing": 0.05752961029877559,
                "is_rich_text": True,
                "has_shadow": False,
                "shadow_color": "#000000ea",
                "shadow_alpha": 0.9206600189208984,
                "shadow_distance": 4.902493000030518,
                "shadow_smoothing": 0.017568999901413918,
                "shadow_angle": -28.152999877929688,
                "shadow_point": {"x": 0.0, "y": 0.0},
                "shadow_thickness_projection_enable": False,
                "shadow_thickness_projection_angle": 0.0,
                "words": {"text": token_texts, "start_time": token_starts, "end_time": token_ends},
                "current_words": {"start_time": [], "end_time": [], "text": []},
                "global_alpha": 1.0,
                "combo_info": {"text_templates": []},
                "caption_template_info": {"category_id": "", "category_name": "", "effect_id": "", "is_new": False, "path": "", "request_id": "", "resource_id": "", "resource_name": "", "source_platform": 0, "third_resource_id": ""},
                "layer_weight": 1,
                "letter_spacing": 0.0,
                "text_curve": None,
                "text_loop_on_path": False,
                "offset_on_path": 0.0,
                "enable_path_typesetting": False,
                "text_exceeds_path_process_type": 0,
                "text_typesetting_paths": None,
                "text_typesetting_paths_file": "",
                "text_typesetting_path_index": 0,
                "border_alpha": 0.0,
                "border_color": "",
                "border_width": 0.0,
                "border_mode": 0,
                "style_name": "",
                "initial_scale": 1.0,
                "font_url": "",
                "typesetting": 0,
                "use_effect_default_color": False,
                "shape_clip_x": False,
                "shape_clip_y": False,
                "ktv_color": "",
                "text_to_audio_ids": [],
                "bold_width": 0.008,
                "italic_degree": 10,
                "underline": False,
                "underline_width": 0.05,
                "underline_offset": 0.22,
                "sub_type": 0,
                "check_flag": 47,
                "text_size": 30,
                "font_category_name": "",
                "font_source_platform": 0,
                "font_third_resource_id": "",
                "font_category_id": "",
                "add_type": 1,
                "operation_type": 0,
                "recognize_type": 0,
                "background_color": "",
                "background_alpha": 1.0,
                "background_style": 0,
                "background_round_radius": 0.0,
                "background_width": 0.14,
                "background_height": 0.14,
                "background_vertical_offset": 0.0,
                "background_horizontal_offset": 0.0,
                "background_fill": "",
                "single_char_bg_enable": False,
                "single_char_bg_color": "",
                "single_char_bg_alpha": 1.0,
                "single_char_bg_round_radius": 0.3,
                "single_char_bg_width": 0.0,
                "single_char_bg_height": 0.0,
                "single_char_bg_vertical_offset": 0.0,
                "single_char_bg_horizontal_offset": 0.0,
                "font_team_id": "",
                "tts_auto_update": False,
                "text_preset_resource_id": "",
                "group_id": f"Auto_{int(curr_start // 1000)}",
                "preset_id": "",
                "preset_name": "",
                "preset_category": "",
                "preset_category_id": "",
                "preset_index": 0,
                "preset_has_set_alignment": False,
                "force_apply_line_max_width": True,
                "language": "en-US",
                "relevance_segment": [],
                "original_size": [],
                "fixed_width": -1.0,
                "fixed_height": -1.0,
                "autoAdaptCanvasEnabled": False,
                "line_max_width": 0.82,
                "oneline_cutoff": False,
                "cutoff_postfix": "",
                "subtitle_template_original_fontsize": 0.0,
                "subtitle_keywords": None,
                "inner_padding": -1.0,
                "multi_language_current": "none",
                "source_from": "",
                "is_lyric_effect": False,
                "lyric_group_id": "",
                "lyrics_template": {"category_id": "", "category_name": "", "effect_id": "", "panel": "", "path": "", "request_id": "", "resource_id": "", "resource_name": ""},
                "is_batch_replace": False,
                "is_words_linear": False,
                "ssml_content": "",
                "subtitle_keywords_config": None,
                "sub_template_id": -1,
                "translate_original_text": ""
            }
            new_texts.append(text_mat)

            # Animation material
            anim_mat = {
                "id": new_anim_id,
                "type": "sticker_animation",
                "animations": [{
                    "id": "",
                    "type": "loop",
                    "start": 0,
                    "duration": anim_duration,
                    "path": anim_path,
                    "platform": "all",
                    "resource_id": anim_res_id,
                    "third_resource_id": "",
                    "source_platform": 0,
                    "name": "",
                    "category_id": "",
                    "category_name": "",
                    "panel": "",
                    "material_type": "sticker",
                    "anim_adjust_params": None,
                    "request_id": ""
                }],
                "multi_language_current": "none"
            }
            new_anims.append(anim_mat)

            # Template material
            max_line_len = max(len(l) for l in formatted_text.split('\n'))
            tmpl_mat = {
                "id": new_tmpl_id,
                "version": "1.0.0",
                "effect_id": effect_id,
                "resource_id": effect_id,
                "third_resource_id": tmpl_cfg.get('third_resource_id', '7262313922844168705'),
                "name": tmpl_name,
                "type": "text_template_subtitle",
                "path": tmpl_path,
                "category_id": "",
                "category_name": "",
                "platform": "all",
                "text_to_audio_ids": [],
                "source_platform": 1,
                "resources": [
                    {
                        "panel": "fonts",
                        "path": resolve_font_path("ProximaNova-Semibold.ttf"),
                        "resource_id": "7148719615961469441",
                        "source_platform": 0
                    },
                    {
                        "panel": "text",
                        "path": anim_path,
                        "resource_id": anim_res_id,
                        "source_platform": 0
                    }
                ],
                "formula_id": "",
                "text_info_resources": [{
                    "id": new_info_id,
                    "attach_info": {
                        "start_time": 0,
                        "duration": final_dur_us,
                        "original_size_width": float(max_line_len * 22.0),
                        "original_size_height": 105.0 if '\n' in formatted_text else 52.0,
                        "clip": {
                            "scale": {"x": 1.085138201713562, "y": 1.085138201713562},
                            "rotation": 0.0,
                            "transform": {"x": 0.0, "y": 0.0},
                            "flip": {"vertical": False, "horizontal": False},
                            "alpha": 1.0
                        }
                    },
                    "text_material_id": new_text_id,
                    "extra_material_refs": [new_anim_id],
                    "clip_type": "",
                    "lyric_keyframes": [],
                    "word_index": [],
                    "order_in_layer": 0,
                    "capital": ""
                }],
                "non_text_info_resources": [],
                "check_flag": 7,
                "text_template_preset_resource_id": "",
                "is_3d": False,
                "is_pre_rendered": False,
                "aigc_type": "none",
                "text_template_resource_type": "subtitle_template",
                "aigc_config": {
                    "prompt": "", "seed": 0, "model": "",
                    "font_item": {"category_id": "", "category_name": "", "effect_id": "", "file_uri": "", "id": str(uuid.uuid4()).upper(), "path": "", "request_id": "", "resource_id": "", "source_platform": 0, "team_id": "", "third_resource_id": "", "title": ""}
                },
                "request_id": "",
                "origin_word_info": {"end_time": 0, "keyword_ranges": [], "start_time": 0, "text": "", "words": []},
                "current_word_info": {"end_time": 0, "keyword_ranges": [], "start_time": 0, "text": "", "words": []},
                "is_dynamic_build": False,
                "is_ai_emoji": False,
                "is_lyric_effect": False,
                "lyric_group_id": "",
                "merge_content": "",
                "is_uneven_animation": False,
                "material_text_ranges": [],
                "ai_emoji_config": None,
                "preview_time": 0.1,
                "render_mode": 0
            }
            new_tmpls.append(tmpl_mat)

            # Build segment in track
            new_seg = {
                "id": str(uuid.uuid4()).upper(),
                "material_id": new_tmpl_id,
                "target_timerange": {
                    "start": curr_start,
                    "duration": final_dur_us
                },
                "source_timerange": None,
                "render_timerange": {"start": 0, "duration": 0},
                "speed": 1.0,
                "volume": 1.0,
                "extra_material_refs": [new_anim_id],
                "render_index": 14000,
                "track_render_index": first_text_idx,
                "clip": {
                    "scale": {"x": 1.0, "y": 1.0},
                    "transform": {"x": 0.0, "y": y_pos},
                    "rotation": 0.0,
                    "flip": {"vertical": False, "horizontal": False},
                    "alpha": 1.0
                },
                "uniform_scale": {"on": True, "value": 1.0},
                "visible": True,
                "enable_color_curves": True,
                "enable_hsl_curves": True,
                "enable_color_wheels": True,
                "enable_video_mask": True
            }
            new_segments.append(new_seg)

        # 5. Update track segments and materials in project
        text_track['segments'] = new_segments
        materials['texts'] = new_texts
        materials['text_templates'] = new_tmpls

        existing_non_sticker_anims = [a for a in materials.get('material_animations', []) if a.get('type') != 'sticker_animation']
        materials['material_animations'] = existing_non_sticker_anims + new_anims

        # 6. Clean up any extra text tracks from old dual runs
        if len(text_track_indices) > 1:
            for extra_idx in text_track_indices[1:]:
                project.data['tracks'][extra_idx]['segments'] = []

        # 7. Add sound FX if configured
        if getattr(self, 'sound_fx', {}).get('enabled', False) and click_starts:
            vol = float(self.sound_fx.get('volume', 0.65))
            snd_name = self.sound_fx.get('name', 'Click_Mouse_Click_02(864360)')
            snd_path = self.sound_fx.get('path')
            if not snd_path or not os.path.isfile(snd_path):
                snd_path = get_default_click_sound_path()
            self._add_click_sound_fx(project.data, click_starts, volume=vol, sound_name=snd_name, sound_path=snd_path)

        project._parse_subtitles()
        return len(raw_items), highlight_count

    @staticmethod
    def _chunk_dentok_escalera(text: str) -> List[str]:
        """
        Particiona una tarjeta de subtítulo (hook o punchline clave) en 2 a 4 peldaños
        en formato escalera para el estilo Dentok.
        Evita cortar en conectores/preposiciones finales y respeta la sintaxis natural española.
        """
        words = text.split()
        n = len(words)
        if n <= 1:
            return [text]
        if n == 2:
            return [words[0], words[1]]

        CONNECTING_END_WORDS = {
            'de', 'del', 'en', 'a', 'al', 'con', 'por', 'para', 'sin', 'sobre',
            'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas',
            'y', 'e', 'ni', 'o', 'u', 'que', 'su', 'sus', 'mi', 'mis', 'tu', 'tus',
            'te', 'me', 'se', 'nos', 'le', 'les', 'como', 'tan', 'más'
        }
        NATURAL_START_WORDS = {
            'un', 'una', 'el', 'la', 'los', 'las', 'de', 'del', 'en', 'para', 'por', 'con', 'sin', 'ni', 'y'
        }

        if n in (3, 4):
            target_k_options = [2, 3]
        elif n in (5, 6):
            target_k_options = [3, 4]
        else:
            target_k_options = [4, 3]

        best_chunks = None
        best_penalty = float('inf')

        for k in target_k_options:
            def get_partitions(remaining_words, parts_left):
                if parts_left == 1:
                    if 1 <= len(remaining_words) <= 4:
                        yield [remaining_words]
                    return
                for sz in range(1, min(4, len(remaining_words) - parts_left + 2)):
                    chunk = remaining_words[:sz]
                    rest = remaining_words[sz:]
                    for sub in get_partitions(rest, parts_left - 1):
                        yield [chunk] + sub

            for partition in get_partitions(words, k):
                pen = 0
                for idx_p, part in enumerate(partition[:-1]):
                    last_w = part[-1].lower().strip('.,!?')
                    next_first_w = partition[idx_p + 1][0].lower().strip('.,!?')
                    if last_w in CONNECTING_END_WORDS:
                        pen += 120
                    if next_first_w in NATURAL_START_WORDS:
                        pen -= 35
                    if len(part) > 3:
                        pen += 30
                    if len(part) == 1 and last_w in CONNECTING_END_WORDS:
                        pen += 80

                punch = partition[-1]
                last_w = punch[-1].lower().strip('.,!?')
                if last_w in CONNECTING_END_WORDS:
                    pen += 150
                if len(punch) > 3:
                    pen += 40

                sizes = [len(p) for p in partition]
                pen += (max(sizes) - min(sizes)) * 6
                if n >= 7 and k == 4:
                    pen -= 30

                if pen < best_penalty:
                    best_penalty = pen
                    best_chunks = partition

        if not best_chunks:
            step_sz = max(1, n // 3)
            best_chunks = [words[i:i + step_sz] for i in range(0, n, step_sz)]

        res = []
        for i, p in enumerate(best_chunks):
            s = ' '.join(p)
            if i == 0:
                s = s[0].upper() + s[1:] if len(s) > 1 else s.upper()
            res.append(s)
        return res

    def auto_dentok_process(
        self,
        project: Any,
        highlighter: Optional[Any] = None,
        openrouter_key: Optional[str] = None,
        model: Optional[str] = None,
        min_pacing_sec: float = 20.0,
        max_pacing_sec: float = 30.0,
        max_chars_per_line: int = 26,
        max_words_per_line: int = 6,
        log_fn: Optional[Callable[[str], None]] = None
    ) -> Tuple[int, int]:
        """
        Procesa subtítulos según las especificaciones del preset Dentok:
        - Hook (Segmento 0) SIEMPRE en formato escalera con Playfair Display Italic (#FFFFFF).
        - Momentos clave muy escasos (espaciados >= 20s, máx 2-3 en todo el video) en formato escalera.
        - Peldaños 0..(K-2) en tamaño 14.08, peldaño punchline en 18.08.
        - Tiempos de entrada progresivos por peldaño y salida simultánea al final de la tarjeta.
        - Subtítulos generales largos y elegantes sin animación en Helvetica Regular (#FFFFFF),
          tamaño 6.2, y=-0.167.
        - Pista 0 (flag=1) aloja subtítulos generales; Pistas 1..4 (flag=0) alojan los 4 peldaños de escalera.
        """
        # 1. Extraer subtítulos de todas las pistas de texto
        text_track_indices = [i for i, t in enumerate(project.data.get('tracks', [])) if t.get('type') == 'text']
        if not text_track_indices:
            logger.warning("No text track found in project.")
            return 0, 0

        materials = project.data.setdefault('materials', {})
        texts_list = materials.setdefault('texts', [])
        texts_by_id = {t['id']: t for t in texts_list if isinstance(t, dict) and 'id' in t}
        templates_by_id = {t['id']: t for t in materials.setdefault('text_templates', []) if isinstance(t, dict) and 'id' in t}

        all_segments = []
        for t_idx in text_track_indices:
            t = project.data['tracks'][t_idx]
            for seg in t.get('segments', []):
                all_segments.append(seg)

        all_segments.sort(key=lambda s: s.get('target_timerange', {}).get('start', 0))

        raw_items = []
        seen_starts = set()
        for seg in all_segments:
            st = seg.get('target_timerange', {}).get('start', 0)
            mat_id = seg.get('material_id')
            t_mat = None
            if mat_id in texts_by_id:
                t_mat = texts_by_id[mat_id]
            elif mat_id in templates_by_id:
                res_list = templates_by_id[mat_id].get('text_info_resources', [])
                if res_list and res_list[0].get('text_material_id') in texts_by_id:
                    t_mat = texts_by_id[res_list[0]['text_material_id']]

            raw_text = ''
            if t_mat:
                c_str = t_mat.get('content', '')
                try:
                    c_obj = json.loads(c_str)
                    raw_text = c_obj.get('text', '')
                except Exception:
                    raw_text = t_mat.get('recognize_text', '')

            txt = clean_subtitle_text(raw_text)
            if not txt:
                continue

            if st in seen_starts:
                continue
            seen_starts.add(st)

            tr = seg.get('target_timerange', {})
            start_us = tr.get('start', 0)
            dur_us = tr.get('duration', 0)

            raw_items.append({
                'index': len(raw_items),
                'segment': seg,
                'text_material': t_mat,
                'text': txt,
                'start': start_us,
                'end': start_us + dur_us,
                'duration': dur_us,
                'words': t_mat.get('words') if t_mat else None
            })

        if not raw_items:
            return 0, 0

        # Helper para evitar conectores o palabras sueltas aisladas
        ORPHAN_CONNECTORS = {
            'que', 'la', 'lo', 'el', 'de', 'y', 'en', 'un', 'una', 'a', 'por', 'con', 'o',
            'pero', 'si', 'es', 'se', 'te', 'me', 'su', 'al', 'del', 'los', 'las', 'unos', 'unas'
        }

        def merge_orphan_subtitles(items):
            merged = []
            i = 0
            while i < len(items):
                curr = items[i]
                words = curr['text'].split()
                is_orphan = (len(words) <= 1 and (not words or words[0].lower() in ORPHAN_CONNECTORS)) or (len(words) == 1 and curr['duration'] < 700000)
                if is_orphan:
                    if i + 1 < len(items):
                        nxt = items[i+1]
                        nxt['text'] = curr['text'] + ' ' + nxt['text']
                        c_w = curr.get('words') or {}
                        n_w = nxt.get('words') or {}
                        if c_w and n_w:
                            nxt_shift_ms = int((nxt['start'] - curr['start']) // 1000)
                            shifted_n_starts = [s + nxt_shift_ms for s in n_w.get('start_time', [])]
                            shifted_n_ends = [e + nxt_shift_ms for e in n_w.get('end_time', [])]
                            nxt['words'] = {
                                'text': c_w.get('text', []) + [' '] + n_w.get('text', []),
                                'start_time': c_w.get('start_time', []) + [0] + shifted_n_starts,
                                'end_time': c_w.get('end_time', []) + [0] + shifted_n_ends
                            }
                        nxt['duration'] = (nxt['start'] + nxt['duration']) - curr['start']
                        nxt['start'] = curr['start']
                    elif merged:
                        prev = merged[-1]
                        prev['text'] = prev['text'] + ' ' + curr['text']
                        prev['duration'] = (curr['start'] + curr['duration']) - prev['start']
                    i += 1
                    continue
                merged.append(curr)
                i += 1
            return merged

        raw_items = merge_orphan_subtitles(raw_items)

        # Helper para dividir tarjetas largas que desborden los márgenes seguros de pantalla (como en Ana Otorrino)
        CLAUSE_STARTERS = {'y', 'pero', 'que', 'cuando', 'donde', 'porque', 'aunque', 'para', 'de', 'en', 'por', 'con', 'sin', 'como', 'si'}
        CONNECTORS_BEFORE = {'un', 'una', 'el', 'la', 'los', 'las', 'de', 'del', 'al', 'su', 'mi', 'tu', 'y', 'o'}

        def split_long_subtitles(items, max_chars=42, max_words=8):
            final_items = []
            def _split_item(item):
                if item.get('index') == 0:
                    return [item]
                txt = item['text']
                words_list = txt.split()
                if len(words_list) <= max_words and len(txt) <= max_chars:
                    return [item]
                w_dict = item.get('words') or {}
                tokens = w_dict.get('text', [])
                starts = w_dict.get('start_time', [])
                ends = w_dict.get('end_time', [])
                word_indices = [idx for idx, t in enumerate(tokens) if t.strip()]
                if len(word_indices) <= 3:
                    word_indices = list(range(len(words_list)))
                    tokens = words_list
                    starts = [0] * len(words_list)
                    ends = [int(item['duration'] // 1000)] * len(words_list)

                mid_idx = len(word_indices) // 2
                best_split_k = mid_idx
                best_penalty = float('inf')
                for k in range(max(2, mid_idx - 2), min(len(word_indices) - 1, mid_idx + 3)):
                    w_before = tokens[word_indices[k-1]].lower()
                    w_after = tokens[word_indices[k]].lower()
                    pen = abs(k - mid_idx) * 6
                    if w_before in CONNECTORS_BEFORE:
                        pen += 50
                    if w_after in CLAUSE_STARTERS:
                        pen -= 25
                    if pen < best_penalty:
                        best_penalty = pen
                        best_split_k = k
                split_tok_idx = word_indices[best_split_k]
                split_time_ms = ends[word_indices[best_split_k - 1]] if best_split_k - 1 < len(ends) else int((item['duration'] // 2000))
                split_time_us = int(split_time_ms * 1000)
                toks_a = tokens[:split_tok_idx]
                txt_a = " ".join([t for t in toks_a if t.strip()]).strip()
                dur_a_us = max(400000, min(item['duration'] - 400000, split_time_us))
                item_a = {'index': item.get('index'), 'text': txt_a, 'start': item['start'], 'end': item['start'] + dur_a_us, 'duration': dur_a_us, 'words': {'text': toks_a, 'start_time': starts[:split_tok_idx], 'end_time': ends[:split_tok_idx]}}
                toks_b = tokens[split_tok_idx:]
                shift_ms = int(dur_a_us // 1000)
                starts_b = [max(0, s - shift_ms) for s in starts[split_tok_idx:]] if starts else []
                ends_b = [max(0, e - shift_ms) for e in ends[split_tok_idx:]] if ends else []
                txt_b = " ".join([t for t in toks_b if t.strip()]).strip()
                start_b_us = item['start'] + dur_a_us
                dur_b_us = max(400000, item['duration'] - dur_a_us)
                item_b = {'index': item.get('index'), 'text': txt_b, 'start': start_b_us, 'end': start_b_us + dur_b_us, 'duration': dur_b_us, 'words': {'text': toks_b, 'start_time': starts_b, 'end_time': ends_b}}
                out = []
                out.extend(_split_item(item_a))
                out.extend(_split_item(item_b))
                return out
            for it in items:
                final_items.extend(_split_item(it))
            return final_items

        margin_cfg = getattr(self, 'margins', {})
        max_tot = int(margin_cfg.get('max_chars_total', 42))
        max_wds = int(margin_cfg.get('max_words_per_line', 5)) * 2
        raw_items = split_long_subtitles(raw_items, max_chars=max_tot, max_words=max_wds)
        for idx, it in enumerate(raw_items):
            it['index'] = idx

        # Helper para equilibrar líneas de subtítulos generales dentro de la zona segura
        eff_max_chars = max_chars_per_line if (max_chars_per_line is not None and max_chars_per_line != 18) else int(margin_cfg.get('max_chars_per_line', 24))

        def balance_line(text: str, max_len: int = eff_max_chars) -> str:
            words = text.split()
            if not words:
                return text
            if len(text) <= max_len or len(words) <= 2:
                t = ' '.join(words)
                return t[0].upper() + t[1:] if len(t) > 1 else t.upper()

            best_split = len(words) // 2
            best_penalty = float('inf')

            for i in range(1, len(words)):
                l1 = ' '.join(words[:i])
                l2 = ' '.join(words[i:])

                p_len1 = max(0, len(l1) - max_len) * 45
                p_len2 = max(0, len(l2) - max_len) * 45
                p_diff = abs(len(l1) - len(l2)) * 1.5

                if len(words[:i]) == 1:
                    p_len1 += 120
                if len(words[i:]) == 1:
                    p_len2 += 120

                if words[i-1].lower() in CONNECTORS_BEFORE:
                    p_len1 += 35

                total_p = p_len1 + p_len2 + p_diff
                if total_p < best_penalty:
                    best_penalty = total_p
                    best_split = i

            line1 = ' '.join(words[:best_split])
            line2 = ' '.join(words[best_split:])
            line1 = line1[0].upper() + line1[1:] if len(line1) > 1 else line1.upper()
            return f'{line1}\n{line2}'

        # 2. Selección de tarjetas en Formato Escalera
        # Regla central: El Hook (índice 0) SIEMPRE es Escalera.
        # Momentos clave posteriores muy espaciados (>= 20s, máximo 2-3 en total).
        pacing_cfg = getattr(self, 'pacing', {})
        min_sec_between = float(pacing_cfg.get('min_seconds_between_highlights', min_pacing_sec or 20.0))
        max_hl = int(pacing_cfg.get('max_highlights_per_video', 3))

        escalera_indices = {0}
        last_hl_time_us = raw_items[0]['start']

        ai_phrases = []
        effective_key = openrouter_key or (getattr(highlighter, 'api_key', None) if getattr(highlighter, 'provider', None) == 'openrouter' else None) or os.environ.get('OPENROUTER_API_KEY')
        if not effective_key:
            cfg_p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.cc_subs_pro_config.json')
            if os.path.isfile(cfg_p):
                try:
                    with open(cfg_p, 'r', encoding='utf-8') as f:
                        cfg_d = json.load(f)
                        effective_key = cfg_d.get('openrouter_key') or cfg_d.get('api_key')
                except Exception:
                    pass

        if effective_key:
            try:
                m = model or getattr(highlighter, 'model', None) or DEFAULT_MODEL
                if log_fn:
                    log_fn(f"[*] Conectando con OpenRouter ({m}) para identificar momentos clave...")
                client = OpenRouterClient(api_key=effective_key, model=m)
                ai_res = client.process_subtitles(raw_items)
                if ai_res:
                    for h in ai_res.get('highlights', []):
                        p = clean_subtitle_text(h.get('phrase', ''))
                        if p:
                            ai_phrases.append(p.lower())
            except Exception as e:
                logger.warning(f"OpenRouter highlight check skipped: {e}")

        for it in raw_items[1:]:
            if len(escalera_indices) >= max_hl:
                break
            time_gap = (it['start'] - last_hl_time_us) / 1e6
            if time_gap < min_sec_between:
                continue

            it_lower = it['text'].lower()
            is_key_moment = False

            for p in ai_phrases:
                if p in it_lower or it_lower in p:
                    is_key_moment = True
                    break

            if not is_key_moment:
                if any(w in it_lower for w in ['somos dentok', 'dentok', 'ranking', 'importante', 'atención']):
                    is_key_moment = True

            if is_key_moment:
                escalera_indices.add(it['index'])
                last_hl_time_us = it['start']

        # 3. Configuraciones de estilo
        general_cfg = getattr(self, 'general_cfg', {}) or getattr(self, 'default_style', {})
        escalera_cfg = getattr(self, 'escalera_cfg', {}) or getattr(self, 'highlight_style', {})

        gen_font_path = resolve_font_path(general_cfg.get('font_path', 'Helvetica Regular.otf'))
        gen_font_title = general_cfg.get('font_title', 'Helvetica')
        gen_font_size = float(general_cfg.get('font_size', 6.2))
        gen_y = float(general_cfg.get('y', -0.167))
        gen_scale = general_cfg.get('scale', {"x": 1.316435, "y": 1.316435})
        gen_shadow = general_cfg.get('shadow', {
            "alpha": 0.5, "angle": -45.0, "diffuse": 0.025, "distance": 3.0,
            "content": {"render_type": "solid", "solid": {"color": [0, 0, 0]}},
            "thickness_projection_angle": -45.0, "thickness_projection_distance": 0.0,
            "thickness_projection_enable": False
        })

        esc_font_path = resolve_font_path(escalera_cfg.get('font_path', 'PlayfairDisplay-Italic.ttf'))
        esc_font_title = escalera_cfg.get('font_title', 'Playfair Display')
        esc_base_size = float(escalera_cfg.get('font_size', 14.08))
        esc_punch_size = float(escalera_cfg.get('font_size_punchline', 18.08))
        esc_scale = escalera_cfg.get('scale', {"x": 1.316435, "y": 1.316435})
        esc_shadow = escalera_cfg.get('shadow', {
            "alpha": 0.4963, "angle": -45.0, "diffuse": 0.025, "distance": 3.0,
            "content": {"render_type": "solid", "solid": {"color": [0, 0, 0]}},
            "thickness_projection_angle": -45.0, "thickness_projection_distance": 0.0,
            "thickness_projection_enable": False
        })

        staircase_cfg = escalera_cfg.get('staircase', {})
        start_x = float(staircase_cfg.get('start_x', -0.16))
        step_x = float(staircase_cfg.get('step_x', 0.12))
        start_y = float(staircase_cfg.get('start_y', -0.14))
        step_y = float(staircase_cfg.get('step_y', -0.095))

        new_texts = []
        general_segments = []
        escalera_segments_by_step: Dict[int, List[Dict[str, Any]]] = {0: [], 1: [], 2: [], 3: []}
        highlight_count = 0

        # 4. Generación de segmentos
        for it in raw_items:
            seg_start_us = it['start']
            seg_dur_us = it['duration']
            seg_end_us = it['end']

            if it['index'] in escalera_indices:
                highlight_count += 1
                chunks = self._chunk_dentok_escalera(it['text'])
                K = len(chunks)

                coords = []
                for k in range(K):
                    y_k = start_y + k * step_y
                    if K == 2:
                        x_k = -0.12 if k == 0 else 0.08
                    elif K == 3:
                        x_k = start_x if k == 0 else (-0.02 if k == 1 else 0.12)
                    else:
                        x_k = [-0.1636, -0.0273, -0.0795, -0.0526][min(k, 3)]
                    coords.append((x_k, y_k))

                w_info = it.get('words') or {}
                raw_toks = w_info.get('text', [])
                raw_starts = w_info.get('start_time', [])

                tok_words = []
                for idx_tok, tok in enumerate(raw_toks):
                    if tok.strip() and idx_tok < len(raw_starts):
                        tok_words.append((tok.strip().lower(), raw_starts[idx_tok]))

                for k, chunk_text in enumerate(chunks):
                    is_punchline = (k == K - 1)
                    f_size = esc_punch_size if is_punchline else esc_base_size
                    pos_x, pos_y = coords[k]

                    if k == 0:
                        step_st_us = seg_start_us
                    else:
                        first_chunk_w = chunk_text.split()[0].lower().strip('.,!?')
                        matched_ms = None
                        for tw, t_ms in tok_words:
                            if tw == first_chunk_w or first_chunk_w in tw:
                                matched_ms = t_ms
                                break
                        if matched_ms is not None and matched_ms > 0:
                            step_st_us = seg_start_us + int(matched_ms * 1000)
                        else:
                            step_st_us = seg_start_us + int((k / K) * seg_dur_us * 0.75)

                    step_st_us = max(seg_start_us, min(seg_end_us - 350000, step_st_us))
                    step_dur_us = seg_end_us - step_st_us

                    formatted_step_text = chunk_text + ' '
                    mat_id = str(uuid.uuid4()).upper()

                    content_obj = {
                        "text": formatted_step_text,
                        "styles": [{
                            "fill": {"content": {"render_type": "solid", "solid": {"color": [1.0, 1.0, 1.0]}}},
                            "font": {"path": esc_font_path, "id": ""},
                            "size": f_size,
                            "shadows": [copy.deepcopy(esc_shadow)],
                            "range": [0, len(formatted_step_text)]
                        }]
                    }
                    new_texts.append({
                        "id": mat_id,
                        "type": "subtitle",
                        "recognize_task_id": "manual_styled",
                        "recognize_text": formatted_step_text,
                        "name": "",
                        "content": json.dumps(content_obj, ensure_ascii=False, separators=(',', ':')),
                        "base_content": json.dumps(content_obj, ensure_ascii=False, separators=(',', ':')),
                        "font_path": esc_font_path,
                        "font_title": esc_font_title,
                        "font_id": "",
                        "font_resource_id": "",
                        "font_source_platform": 0,
                        "fonts": [],
                        "letter_spacing": 0.0,
                        "font_size": f_size,
                        "text_color": "#FFFFFF",
                        "is_rich_text": False,
                        "has_shadow": False,
                        "words": {"start_time": [0], "end_time": [int(step_dur_us // 1000)], "text": [formatted_step_text]}
                    })

                    step_seg = {
                        "id": str(uuid.uuid4()).upper(),
                        "material_id": mat_id,
                        "source_timerange": None,
                        "target_timerange": {
                            "start": step_st_us,
                            "duration": step_dur_us
                        },
                        "render_timerange": {"start": 0, "duration": 0},
                        "clip": {
                            "scale": copy.deepcopy(esc_scale),
                            "transform": {"x": pos_x, "y": pos_y},
                            "rotation": 0.0,
                            "flip": {"vertical": False, "horizontal": False},
                            "alpha": 1.0
                        },
                        "uniform_scale": {"on": True, "value": 1.0},
                        "visible": True,
                        "speed": 1.0,
                        "volume": 1.0,
                        "extra_material_refs": [],
                        "render_index": 14000,
                        "enable_color_curves": True,
                        "enable_hsl_curves": True,
                        "enable_color_wheels": True,
                        "enable_video_mask": True
                    }
                    escalera_step_idx = min(k, 3)
                    escalera_segments_by_step[escalera_step_idx].append(step_seg)
            else:
                gen_text = balance_line(it['text'], max_len=eff_max_chars)
                mat_id = str(uuid.uuid4()).upper()

                content_obj = {
                    "text": gen_text,
                    "styles": [{
                        "fill": {"content": {"render_type": "solid", "solid": {"color": [1.0, 1.0, 1.0]}}},
                        "font": {"path": gen_font_path, "id": ""},
                        "size": gen_font_size,
                        "shadows": [copy.deepcopy(gen_shadow)],
                        "range": [0, len(gen_text)]
                    }]
                }
                new_texts.append({
                    "id": mat_id,
                    "type": "subtitle",
                    "recognize_task_id": "manual_styled",
                    "recognize_text": gen_text,
                    "name": "",
                    "content": json.dumps(content_obj, ensure_ascii=False, separators=(',', ':')),
                    "base_content": json.dumps(content_obj, ensure_ascii=False, separators=(',', ':')),
                    "font_path": gen_font_path,
                    "font_title": gen_font_title,
                    "font_id": "",
                    "font_resource_id": "",
                    "font_source_platform": 0,
                    "fonts": [],
                    "letter_spacing": 0.0,
                    "font_size": gen_font_size,
                    "text_color": "#FFFFFF",
                    "is_rich_text": False,
                    "has_shadow": False,
                    "words": {"start_time": [0], "end_time": [int(seg_dur_us // 1000)], "text": [gen_text]}
                })

                gen_seg = {
                    "id": str(uuid.uuid4()).upper(),
                    "material_id": mat_id,
                    "source_timerange": None,
                    "target_timerange": {
                        "start": seg_start_us,
                        "duration": seg_dur_us
                    },
                    "render_timerange": {"start": 0, "duration": 0},
                    "clip": {
                        "scale": copy.deepcopy(gen_scale),
                        "transform": {"x": 0.0, "y": gen_y},
                        "rotation": 0.0,
                        "flip": {"vertical": False, "horizontal": False},
                        "alpha": 1.0
                    },
                    "uniform_scale": {"on": True, "value": 1.0},
                    "visible": True,
                    "speed": 1.0,
                    "volume": 1.0,
                    "extra_material_refs": [],
                    "render_index": 14000,
                    "enable_color_curves": True,
                    "enable_hsl_curves": True,
                    "enable_color_wheels": True,
                    "enable_video_mask": True
                }
                general_segments.append(gen_seg)

        # 5. Organización de Pistas en CapCut
        # Pista General (flag=1) y 4 Pistas de Escalera (flag=0)
        tracks = project.data.setdefault('tracks', [])
        existing_text_tracks = [t for t in tracks if t.get('type') == 'text']

        while len(existing_text_tracks) < 5:
            new_trk = {
                "id": str(uuid.uuid4()).upper(),
                "type": "text",
                "flag": 0,
                "attribute": 0,
                "name": f"Text_{len(existing_text_tracks)}",
                "is_default_name": True,
                "segments": []
            }
            tracks.append(new_trk)
            existing_text_tracks.append(new_trk)

        gen_track = existing_text_tracks[0]
        gen_track['flag'] = 1
        gen_track['name'] = "General"
        gen_track['segments'] = general_segments

        for step_idx in range(4):
            e_track = existing_text_tracks[1 + step_idx]
            e_track['flag'] = 0
            e_track['name'] = f"Escalera_{step_idx}"
            e_track['segments'] = escalera_segments_by_step[step_idx]

        for extra_trk in existing_text_tracks[5:]:
            extra_trk['segments'] = []

        materials['texts'] = new_texts
        materials['text_templates'] = []

        project._parse_subtitles()
        if log_fn:
            log_fn(f"[+] Preset Dentok aplicado: {len(general_segments)} subtítulos generales, {highlight_count} tarjeta(s) en escalera.")
        return len(raw_items), highlight_count
