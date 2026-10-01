import os
import json
import shutil
import logging
from typing import Dict, List, Any, Optional

from core.platform_paths import get_default_draft_dir
from core.text_utils import clean_subtitle_text

logger = logging.getLogger('CCSubsPro.CapCutDraft')

DEFAULT_DRAFT_DIR = get_default_draft_dir()

class SubtitleItem:
    def __init__(self, track_index: int, segment: Dict[str, Any], text_material: Dict[str, Any]):
        self.track_index = track_index
        self.segment = segment
        self.text_material = text_material
        self.segment_id = segment.get('id', '')
        self.material_id = segment.get('material_id', '')
        self.target_timerange = segment.get('target_timerange', {})
        self.start_us = self.target_timerange.get('start', 0)
        self.duration_us = self.target_timerange.get('duration', 0)
        self.extra_material_refs = segment.setdefault('extra_material_refs', [])
        self.clip = segment.get('clip', {})
        
        self.raw_content = text_material.get('content', '')
        self.parsed_content: Dict[str, Any] = {}
        try:
            self.parsed_content = json.loads(self.raw_content)
        except Exception as e:
            logger.warning(f"Could not parse inner content JSON for material {self.material_id}: {e}")
            self.parsed_content = {'text': text_material.get('recognize_text', ''), 'styles': []}

    @property
    def text(self) -> str:
        return self.parsed_content.get('text', '')

    @text.setter
    def text(self, new_text: str):
        self.set_text(new_text)


    def sync_content_to_material(self):
        serialized = json.dumps(self.parsed_content, ensure_ascii=False, separators=(',', ':'))
        self.text_material['content'] = serialized
        if 'base_content' in self.text_material:
            self.text_material['base_content'] = serialized

    def set_text(self, new_text: str) -> str:
        """Sets new text for the subtitle item, ensuring clean punctuation and style range sync."""
        cleaned = clean_subtitle_text(new_text)
        self.parsed_content['text'] = cleaned
        styles = self.parsed_content.get('styles', [])
        if len(styles) == 1:
            styles[0]['range'] = [0, len(cleaned)]
        if 'words' in self.text_material and isinstance(self.text_material['words'], dict):
            self.text_material['words']['text'] = [cleaned]
        self.sync_content_to_material()
        return cleaned

    def clean_text(self) -> str:
        """Removes commas, periods, and colons from subtitle text and updates materials and style ranges."""
        return self.set_text(self.text)


class CapCutProject:
    def __init__(self, project_path: str):
        self.project_path = os.path.abspath(project_path)
        if os.path.isdir(self.project_path):
            self.content_file = os.path.join(self.project_path, 'draft_content.json')
        else:
            self.content_file = self.project_path
            self.project_path = os.path.dirname(self.content_file)

        if not os.path.isfile(self.content_file):
            raise FileNotFoundError(f"draft_content.json not found at {self.content_file}")

        self.data: Dict[str, Any] = {}
        self.subtitles: List[SubtitleItem] = []
        self.timeline_files: List[str] = []
        self._find_timeline_files()
        self._load()

    def _find_timeline_files(self):
        self.timeline_files.clear()
        timelines_dir = os.path.join(self.project_path, 'Timelines')
        if os.path.isdir(timelines_dir):
            proj_meta = os.path.join(timelines_dir, 'project.json')
            if os.path.isfile(proj_meta):
                try:
                    with open(proj_meta, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                    main_id = meta.get('main_timeline_id')
                    if main_id:
                        p = os.path.join(timelines_dir, main_id, 'draft_content.json')
                        if os.path.isfile(p):
                            self.timeline_files.append(p)
                except Exception as e:
                    logger.debug(f"Error reading project.json in Timelines: {e}")

            for item in os.listdir(timelines_dir):
                sub = os.path.join(timelines_dir, item)
                if os.path.isdir(sub):
                    for c_name in ['draft_content.json', 'template.json']:
                        candidate = os.path.join(sub, c_name)
                        if os.path.isfile(candidate) and candidate not in self.timeline_files:
                            self.timeline_files.append(candidate)

    def _load(self):
        with open(self.content_file, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

        if 'materials' not in self.data or 'tracks' not in self.data:
            raise ValueError(f"Invalid CapCut draft structure in {self.content_file}: missing materials or tracks.")

        self._parse_subtitles()

    def _parse_subtitles(self):
        self.subtitles.clear()
        materials = self.data.setdefault('materials', {})
        texts = materials.setdefault('texts', [])
        texts_by_id = {t.get('id'): t for t in texts if isinstance(t, dict) and 'id' in t}
        templates = materials.setdefault('text_templates', [])
        templates_by_id = {t.get('id'): t for t in templates if isinstance(t, dict) and 'id' in t}

        tracks = self.data.get('tracks', [])
        for trk_idx, trk in enumerate(tracks):
            if trk.get('type') == 'text':
                for seg in trk.get('segments', []):
                    mat_id = seg.get('material_id')
                    text_mat = None
                    if mat_id in texts_by_id:
                        text_mat = texts_by_id[mat_id]
                    elif mat_id in templates_by_id:
                        tmpl = templates_by_id[mat_id]
                        res_list = tmpl.get('text_info_resources', [])
                        if res_list:
                            t_mat_id = res_list[0].get('text_material_id')
                            if t_mat_id in texts_by_id:
                                text_mat = texts_by_id[t_mat_id]
                    if text_mat:
                        sub_item = SubtitleItem(trk_idx, seg, text_mat)
                        self.subtitles.append(sub_item)

        self.subtitles.sort(key=lambda s: (s.start_us, s.track_index))

    def clean_all_subtitles(self) -> int:
        """Cleans commas, periods, and colons from all subtitles in the project."""
        count = 0
        for sub in self.subtitles:
            sub.clean_text()
            count += 1
        return count

    def create_backup(self) -> str:
        backup_path = os.path.join(self.project_path, 'draft_content.backup.json')
        shutil.copy2(self.content_file, backup_path)

        root_t2 = os.path.join(self.project_path, 'template-2.tmp')
        if os.path.isfile(root_t2):
            try:
                shutil.copy2(root_t2, root_t2 + '.backup')
            except Exception:
                pass

        for tf in self.timeline_files:
            try:
                tf_backup = tf + '.backup'
                shutil.copy2(tf, tf_backup)
                tdir = os.path.dirname(tf)
                for tmp_name in ['template-2.tmp', 'template.tmp']:
                    tmp_p = os.path.join(tdir, tmp_name)
                    if os.path.isfile(tmp_p):
                        shutil.copy2(tmp_p, tmp_p + '.backup')
            except Exception:
                pass

        logger.info(f"Backup created at: {backup_path}")
        return backup_path

    def save(self, create_backup: bool = True) -> str:
        if create_backup:
            self.create_backup()

        for sub in self.subtitles:
            sub.sync_content_to_material()

        serialized = json.dumps(self.data, ensure_ascii=False, separators=(',', ':'))

        temp_file = self.content_file + '.tmp'
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(serialized)
        os.replace(temp_file, self.content_file)
        logger.info(f"Saved modified project to {self.content_file}")

        root_t2 = os.path.join(self.project_path, 'template-2.tmp')
        if os.path.isfile(root_t2):
            try:
                with open(root_t2, 'w', encoding='utf-8') as f:
                    f.write(serialized)
                logger.info(f"Synced to root template-2.tmp: {root_t2}")
            except Exception as e:
                logger.warning(f"Could not sync to root template-2.tmp: {e}")

        for tf in self.timeline_files:
            try:
                tf_temp = tf + '.tmp'
                with open(tf_temp, 'w', encoding='utf-8') as f:
                    f.write(serialized)
                os.replace(tf_temp, tf)
                logger.info(f"Synced to timeline file: {tf}")

                tdir = os.path.dirname(tf)
                for tmp_name in ['template-2.tmp', 'template.tmp']:
                    tmp_p = os.path.join(tdir, tmp_name)
                    if os.path.isfile(tmp_p):
                        with open(tmp_p, 'w', encoding='utf-8') as f:
                            f.write(serialized)
                        logger.info(f"Synced to timeline cache: {tmp_p}")
            except Exception as e:
                logger.warning(f"Could not sync to {tf}: {e}")

        return self.content_file


def list_available_projects(draft_dir: str = DEFAULT_DRAFT_DIR) -> List[Dict[str, Any]]:
    projects = []
    if not os.path.exists(draft_dir):
        return projects

    for name in os.listdir(draft_dir):
        proj_dir = os.path.join(draft_dir, name)
        content_path = os.path.join(proj_dir, 'draft_content.json')
        if os.path.isdir(proj_dir) and os.path.isfile(content_path):
            try:
                mtime = os.path.getmtime(content_path)
                with open(content_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                texts = data.get('materials', {}).get('texts', [])
                sub_count = sum(1 for t in texts if t.get('type') == 'subtitle' or t.get('recognize_task_id'))
                projects.append({
                    'name': name,
                    'path': proj_dir,
                    'mtime': mtime,
                    'total_texts': len(texts),
                    'subtitle_count': sub_count,
                    'duration_us': data.get('duration', 0)
                })
            except Exception as e:
                logger.debug(f"Skipping {name}: {e}")

    projects.sort(key=lambda x: x['mtime'], reverse=True)
    return projects
