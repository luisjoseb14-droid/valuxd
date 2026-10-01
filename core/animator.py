import uuid
from typing import Dict, Any, Optional

class Animator:
    @staticmethod
    def apply_animation_to_segment(
        draft_data: Dict[str, Any],
        segment: Dict[str, Any],
        animation_config: Dict[str, Any]
    ) -> str:
        '''
        Ensures the animation from animation_config is in materials.material_animations
        and referenced in segment['extra_material_refs'].
        Returns the material_animation id.
        '''
        if not animation_config or not animation_config.get('enabled', True):
            return ""

        materials = draft_data.setdefault('materials', {})
        mat_animations = materials.setdefault('material_animations', [])
        
        resource_id = str(animation_config.get('resource_id', '7646371622298914068'))
        anim_path = animation_config.get('path', '')
        anim_name = animation_config.get('name', 'Entrada deslizante desde la izquierda')
        anim_type = animation_config.get('type', 'in')
        duration_us = int(animation_config.get('duration', 500000))
        
        # Clamp animation duration to segment duration if segment is shorter
        seg_dur = segment.get('target_timerange', {}).get('duration', duration_us)
        effective_duration = min(duration_us, seg_dur)

        extra_refs = segment.setdefault('extra_material_refs', [])
        
        # Check if an existing sticker_animation ref exists on this segment
        existing_mat_anim = None
        for ref_id in extra_refs:
            for ma in mat_animations:
                if ma.get('id') == ref_id and ma.get('type') == 'sticker_animation':
                    existing_mat_anim = ma
                    break
            if existing_mat_anim:
                break

        if existing_mat_anim is not None:
            # Update animations list in the existing material_animation
            existing_mat_anim['animations'] = [{
                "id": resource_id,
                "type": anim_type,
                "start": 0,
                "duration": effective_duration,
                "path": anim_path,
                "platform": "all",
                "resource_id": resource_id,
                "third_resource_id": "0",
                "source_platform": 1,
                "name": anim_name,
                "category_id": "ruchang_fav",
                "category_name": "Favoritos",
                "panel": "",
                "material_type": "sticker",
                "anim_adjust_params": None,
                "request_id": ""
            }]
            return existing_mat_anim['id']
        else:
            # Create a new material_animation
            new_id = str(uuid.uuid4()).upper()
            new_mat_anim = {
                "id": new_id,
                "type": "sticker_animation",
                "animations": [{
                    "id": resource_id,
                    "type": anim_type,
                    "start": 0,
                    "duration": effective_duration,
                    "path": anim_path,
                    "platform": "all",
                    "resource_id": resource_id,
                    "third_resource_id": "0",
                    "source_platform": 1,
                    "name": anim_name,
                    "category_id": "ruchang_fav",
                    "category_name": "Favoritos",
                    "panel": "",
                    "material_type": "sticker",
                    "anim_adjust_params": None,
                    "request_id": ""
                }],
                "multi_language_current": "none"
            }
            mat_animations.append(new_mat_anim)
            extra_refs.append(new_id)
            return new_id
