import json
import re
import copy
from typing import Dict, List, Any, Tuple, Optional
from core.capcut_draft import SubtitleItem
from core.animator import Animator
from core.text_utils import clean_subtitle_text

def hex_to_rgb_norm(hex_color: str) -> List[float]:
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return [r, g, b]
    return [1.0, 1.0, 1.0]

class Styler:
    def __init__(self, default_style_path: str, highlight_style_path: str):
        with open(default_style_path, 'r', encoding='utf-8') as f:
            self.default_style = json.load(f)
        with open(highlight_style_path, 'r', encoding='utf-8') as f:
            self.highlight_style = json.load(f)

    def _build_style_entry(self, style_dict: Dict[str, Any], range_span: Tuple[int, int]) -> Dict[str, Any]:
        rgb = style_dict.get('rgb_color')
        if not rgb:
            rgb = hex_to_rgb_norm(style_dict.get('color', '#FFFFFF'))

        font_info = style_dict.get('font', {})
        font_path = font_info.get('path', '')
        font_id = font_info.get('id', '')

        entry: Dict[str, Any] = {
            "fill": {
                "content": {
                    "render_type": "solid",
                    "solid": {
                        "color": rgb
                    }
                }
            },
            "font": {
                "path": font_path,
                "id": font_id
            },
            "size": float(style_dict.get('font_size', 10.0)),
            "range": [range_span[0], range_span[1]]
        }

        if style_dict.get('useLetterColor'):
            entry["useLetterColor"] = True

        if 'shadow' in style_dict:
            entry["shadows"] = [copy.deepcopy(style_dict['shadow'])]

        return entry

    def apply_default_style_to_item(self, item: SubtitleItem, draft_data: Dict[str, Any]):
        '''Applies 100% default style to entire subtitle text and its segment animation.'''
        text = clean_subtitle_text(item.text)
        item.parsed_content['text'] = text
        if not text:
            return

        # 1. Update inner parsed content styles
        style_entry = self._build_style_entry(self.default_style, (0, len(text)))
        item.parsed_content['styles'] = [style_entry]

        # 2. Update top-level text material properties for local font
        font_info = self.default_style.get('font', {})
        item.text_material['font_path'] = font_info.get('path', '')
        item.text_material['font_title'] = font_info.get('name', 'none')
        item.text_material['font_id'] = ''
        item.text_material['font_name'] = ''
        item.text_material['font_resource_id'] = ''
        item.text_material['font_source_platform'] = 0
        item.text_material['fonts'] = []
        item.text_material['letter_spacing'] = 0.0
        item.text_material['font_size'] = float(self.default_style.get('font_size', 10.0))
        item.text_material['text_color'] = self.default_style.get('color', '#FFFFFF')
        item.sync_content_to_material()

        # 3. Apply animation to segment if configured
        anim_cfg = self.default_style.get('animation')
        if anim_cfg and anim_cfg.get('enabled'):
            Animator.apply_animation_to_segment(draft_data, item.segment, anim_cfg)

    def apply_highlight_to_item(
        self,
        item: SubtitleItem,
        draft_data: Dict[str, Any],
        phrases_to_highlight: List[str]
    ) -> int:
        '''
        Applies highlight style to specific phrases and default style to the rest of the text.
        Returns the number of highlighted phrases matched.
        '''
        text = clean_subtitle_text(item.text)
        item.parsed_content['text'] = text
        if not text:
            return 0

        # Find character ranges for all phrases
        highlight_intervals: List[Tuple[int, int]] = []
        matches_count = 0

        for phrase in phrases_to_highlight:
            phrase_str = clean_subtitle_text(phrase)
            if not phrase_str:
                continue
            
            # Case-insensitive search using regex escape
            pattern = re.escape(phrase_str)
            for m in re.finditer(pattern, text, re.IGNORECASE):
                highlight_intervals.append((m.start(), m.end()))
                matches_count += 1

        if not highlight_intervals:
            # No highlights matched, apply normal default style
            self.apply_default_style_to_item(item, draft_data)
            return 0

        # Merge overlapping intervals
        highlight_intervals.sort(key=lambda x: x[0])
        merged_highlights: List[Tuple[int, int]] = []
        for start, end in highlight_intervals:
            if not merged_highlights:
                merged_highlights.append((start, end))
            else:
                prev_s, prev_e = merged_highlights[-1]
                if start <= prev_e:
                    merged_highlights[-1] = (prev_s, max(prev_e, end))
                else:
                    merged_highlights.append((start, end))

        # Build contiguous partition of [0, len(text)]
        styles_list: List[Dict[str, Any]] = []
        curr_idx = 0

        for h_start, h_end in merged_highlights:
            if curr_idx < h_start:
                # Default style segment
                styles_list.append(self._build_style_entry(self.default_style, (curr_idx, h_start)))
            # Highlight style segment
            styles_list.append(self._build_style_entry(self.highlight_style, (h_start, h_end)))
            curr_idx = h_end

        if curr_idx < len(text):
            styles_list.append(self._build_style_entry(self.default_style, (curr_idx, len(text))))

        item.parsed_content['styles'] = styles_list

        # Top-level font setup (default style)
        font_info = self.default_style.get('font', {})
        item.text_material['font_path'] = font_info.get('path', '')
        item.text_material['font_title'] = font_info.get('name', 'none')
        item.text_material['font_id'] = ''
        item.text_material['font_name'] = ''
        item.text_material['font_resource_id'] = ''
        item.text_material['font_source_platform'] = 0
        item.text_material['fonts'] = []
        item.text_material['letter_spacing'] = 0.0
        item.sync_content_to_material()

        # Animation to segment
        anim_cfg = self.default_style.get('animation')
        if anim_cfg and anim_cfg.get('enabled'):
            Animator.apply_animation_to_segment(draft_data, item.segment, anim_cfg)

        return matches_count
