# -*- coding: utf-8 -*-
"""
CC Subs Pro - Detector y Reparador Acústico de Huecos de Voz en Subtítulos (Gap Healer)
Identifica silencios y huecos en las pistas de subtítulos de CapCut, verifica
acústicamente la presencia de voz mediante FFmpeg volumedetect, y permite
repararlos rellenando los textos ausentes respetando las reglas de GEMINI.md.
"""

import os
import re
import json
import uuid
import copy
import subprocess
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple

from core.capcut_draft import CapCutProject, SubtitleItem
from core.dual_styler import DualStyler
from core.platform_paths import resolve_font_path
from core.text_utils import clean_subtitle_text

logger = logging.getLogger('CCSubsPro.GapHealer')

DEFAULT_MIN_GAP_SEC = 0.4
DEFAULT_MAX_GAP_SEC = 6.0
DEFAULT_VOICE_THRESHOLD_DB = -42.0

@dataclass
class SubtitleGap:
    index: int
    start_us: int
    end_us: int
    duration_us: int
    prev_text: str = ""
    next_text: str = ""
    media_path: str = ""
    file_start_sec: float = 0.0
    duration_sec: float = 0.0
    has_voice: bool = False
    max_volume_db: float = -99.0
    mean_volume_db: float = -99.0
    suggested_text: str = ""
    prev_sub: Any = None
    next_sub: Any = None

    @property
    def start_time_str(self) -> str:
        s = self.start_us / 1_000_000.0
        m = int(s // 60)
        sec = s % 60
        return f"{m:02d}:{sec:05.2f}"

    @property
    def end_time_str(self) -> str:
        s = self.end_us / 1_000_000.0
        m = int(s // 60)
        sec = s % 60
        return f"{m:02d}:{sec:05.2f}"

    @property
    def duration_str(self) -> str:
        return f"{self.duration_sec:.2f}s"


def find_subtitle_gaps(
    project: CapCutProject,
    min_gap_sec: float = DEFAULT_MIN_GAP_SEC,
    max_gap_sec: float = DEFAULT_MAX_GAP_SEC
) -> List[SubtitleGap]:
    """
    Identifica todos los intervalos de tiempo en el proyecto donde no hay subtítulos
    activos durante una duración entre min_gap_sec y max_gap_sec.
    """
    min_gap_us = int(min_gap_sec * 1_000_000)
    max_gap_us = int(max_gap_sec * 1_000_000)

    # 1. Obtener todos los subtítulos ordenados por tiempo de inicio
    subs = sorted(project.subtitles, key=lambda s: s.start_us)
    if not subs:
        return []

    # Map materials videos & audios
    materials = project.data.get('materials', {})
    videos_by_id = {v.get('id'): v for v in materials.get('videos', []) if isinstance(v, dict)}
    audios_by_id = {a.get('id'): a for a in materials.get('audios', []) if isinstance(a, dict)}

    # Collect media segments from video and audio tracks
    media_segments: List[Dict[str, Any]] = []
    for trk in project.data.get('tracks', []):
        t_type = trk.get('type')
        if t_type in ('video', 'audio'):
            for seg in trk.get('segments', []):
                tr = seg.get('target_timerange')
                if tr and tr.get('duration', 0) > 0:
                    mid = seg.get('material_id')
                    mat = videos_by_id.get(mid) or audios_by_id.get(mid)
                    path = mat.get('path', '') if mat else ''
                    media_segments.append({
                        'segment': seg,
                        'track_type': t_type,
                        'start_us': tr.get('start', 0),
                        'end_us': tr.get('start', 0) + tr.get('duration', 0),
                        'source_start_us': seg.get('source_timerange', {}).get('start', 0) if seg.get('source_timerange') else 0,
                        'path': path
                    })

    gaps: List[SubtitleGap] = []
    gap_idx = 0

    for i in range(len(subs) - 1):
        curr_sub = subs[i]
        next_sub = subs[i + 1]

        curr_end_us = curr_sub.start_us + curr_sub.duration_us
        next_start_us = next_sub.start_us

        gap_duration_us = next_start_us - curr_end_us
        if min_gap_us <= gap_duration_us <= max_gap_us:
            # Buscar el clip de media correspondiente
            matched_media_path = ""
            matched_file_start_sec = 0.0

            # 1. Prefer video track media with valid path that covers the gap
            for m in [x for x in media_segments if x['track_type'] == 'video']:
                if m['path'] and os.path.exists(m['path']):
                    # Check overlap with gap
                    if m['start_us'] <= curr_end_us and m['end_us'] >= next_start_us:
                        matched_media_path = m['path']
                        offset_us = m['source_start_us'] + (curr_end_us - m['start_us'])
                        matched_file_start_sec = max(0.0, offset_us / 1_000_000.0)
                        break

            # 2. Prefer video track with partial overlap
            if not matched_media_path:
                for m in [x for x in media_segments if x['track_type'] == 'video']:
                    if m['path'] and os.path.exists(m['path']):
                        if m['start_us'] < next_start_us and m['end_us'] > curr_end_us:
                            matched_media_path = m['path']
                            offset_us = m['source_start_us'] + max(0, curr_end_us - m['start_us'])
                            matched_file_start_sec = max(0.0, offset_us / 1_000_000.0)
                            break

            # 3. Fallback to audio track if no video segment covered the gap
            if not matched_media_path:
                for m in [x for x in media_segments if x['track_type'] == 'audio']:
                    if m['path'] and os.path.exists(m['path']):
                        if m['start_us'] <= curr_end_us and m['end_us'] >= next_start_us:
                            matched_media_path = m['path']
                            offset_us = m['source_start_us'] + (curr_end_us - m['start_us'])
                            matched_file_start_sec = max(0.0, offset_us / 1_000_000.0)
                            break
                        elif m['start_us'] < next_start_us and m['end_us'] > curr_end_us:
                            matched_media_path = m['path']
                            offset_us = m['source_start_us'] + max(0, curr_end_us - m['start_us'])
                            matched_file_start_sec = max(0.0, offset_us / 1_000_000.0)
                            break

            gap_item = SubtitleGap(
                index=gap_idx,
                start_us=curr_end_us,
                end_us=next_start_us,
                duration_us=gap_duration_us,
                prev_text=curr_sub.text,
                next_text=next_sub.text,
                media_path=matched_media_path,
                file_start_sec=matched_file_start_sec,
                duration_sec=gap_duration_us / 1_000_000.0,
                prev_sub=curr_sub,
                next_sub=next_sub
            )
            gaps.append(gap_item)
            gap_idx += 1

    return gaps


def verify_gap_audio_energy(
    gap: SubtitleGap,
    threshold_db: float = DEFAULT_VOICE_THRESHOLD_DB
) -> Tuple[bool, float, float]:
    """
    Usa FFmpeg volumedetect en el fragmento de audio del hueco.
    Devuelve (has_voice, max_volume_db, mean_volume_db).
    """
    if not gap.media_path or not os.path.isfile(gap.media_path):
        return False, -99.0, -99.0

    cmd = [
        'ffmpeg', '-y',
        '-ss', f"{gap.file_start_sec:.3f}",
        '-t', f"{gap.duration_sec:.3f}",
        '-i', gap.media_path,
        '-af', 'volumedetect',
        '-f', 'null', '-'
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        stderr = proc.stderr or ""

        max_v = -99.0
        mean_v = -99.0

        m_max = re.search(r'max_volume:\s*([-\d.]+)\s*dB', stderr)
        if m_max:
            max_v = float(m_max.group(1))

        m_mean = re.search(r'mean_volume:\s*([-\d.]+)\s*dB', stderr)
        if m_mean:
            mean_v = float(m_mean.group(1))

        has_voice = (max_v >= threshold_db)
        gap.has_voice = has_voice
        gap.max_volume_db = max_v
        gap.mean_volume_db = mean_v

        return has_voice, max_v, mean_v
    except Exception as e:
        logger.warning(f"Error executing ffmpeg volumedetect for gap {gap.index}: {e}")
        return False, -99.0, -99.0


def extract_gap_audio_snippet(gap: SubtitleGap, output_file: str) -> bool:
    """
    Extrae un micro-archivo de audio WAV (16kHz mono) del intervalo exacto del hueco.
    """
    if not gap.media_path or not os.path.isfile(gap.media_path):
        return False

    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    cmd = [
        'ffmpeg', '-y',
        '-ss', f"{gap.file_start_sec:.3f}",
        '-t', f"{gap.duration_sec:.3f}",
        '-i', gap.media_path,
        '-vn',
        '-ar', '16000',
        '-ac', '1',
        output_file
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        return proc.returncode == 0 and os.path.isfile(output_file) and os.path.getsize(output_file) > 0
    except Exception as e:
        logger.warning(f"Error extracting audio snippet for gap {gap.index}: {e}")
        return False


def play_audio_snippet(audio_path: str):
    """
    Reproduce el fragmento de audio en un subproceso con ffplay.
    """
    if not os.path.isfile(audio_path):
        return

    cmd = [
        'ffplay', '-nodisp', '-autoexit', '-loglevel', 'quiet', audio_path
    ]
    try:
        subprocess.Popen(
            cmd,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
    except Exception as e:
        logger.warning(f"Error playing audio with ffplay: {e}")


def insert_healed_subtitles(
    project: CapCutProject,
    healed_items: List[Dict[str, Any]],
    styler: Optional[DualStyler] = None
) -> int:
    """
    Inserta subtítulos reparados en el proyecto CapCut respetando:
    1. Reglas de GEMINI.md: 0 comas, 0 puntos, 0 dos puntos, saneamiento con clean_subtitle_text().
    2. Parámetros de estilo del preset (fuente, escala, sombra diffuse: 0.025).
    3. Sincronización cronológica de la pista de texto.
    """
    if not healed_items:
        return 0

    materials = project.data.setdefault('materials', {})
    texts = materials.setdefault('texts', [])

    # Find text track
    tracks = project.data.setdefault('tracks', [])
    text_track = None
    for trk in tracks:
        if trk.get('type') == 'text':
            text_track = trk
            break

    if text_track is None:
        text_track = {
            "id": str(uuid.uuid4()).upper(),
            "type": "text",
            "segments": []
        }
        tracks.append(text_track)

    top_cfg = (styler.default_style if styler else {}) or {}

    shadow_cfg = copy.deepcopy(top_cfg.get('shadow', {
        "alpha": 0.4952380955219269,
        "angle": -45,
        "diffuse": 0.02500000037252903,
        "distance": 2.9999992847442627,
        "content": {"render_type": "solid", "solid": {"color": [0, 0, 0]}},
        "thickness_projection_angle": -45,
        "thickness_projection_distance": 0,
        "thickness_projection_enable": False
    }))
    # Ensure CapCut shadow diffuse integrity
    shadow_cfg['diffuse'] = 0.02500000037252903

    font_path_resolved = resolve_font_path(top_cfg.get('font_path', ''))
    font_name = top_cfg.get('font_name', '')
    font_title = top_cfg.get('font_title', 'none')
    font_size = float(top_cfg.get('font_size', 8.0))
    text_color = top_cfg.get('color', '#FFFFFF')
    rgb_color = top_cfg.get('rgb_color', [1.0, 1.0, 1.0])
    scale_dict = copy.deepcopy(top_cfg.get('scale', {"x": 1.3550004042363974, "y": 1.3550004042363974}))
    y_pos = float(top_cfg.get('y', 0.0))

    inserted_count = 0

    for item in healed_items:
        raw_text = item.get('text', '').strip()
        cleaned_text = clean_subtitle_text(raw_text)
        if not cleaned_text:
            continue

        start_us = int(item.get('start_us', 0))
        duration_us = int(item.get('duration_us', 0))
        if duration_us <= 0:
            continue

        mat_id = str(uuid.uuid4()).upper()

        text_content_dict = {
            "text": cleaned_text,
            "styles": [
                {
                    "fill": {
                        "content": {
                            "render_type": "solid",
                            "solid": {"color": rgb_color}
                        }
                    },
                    "font": {
                        "id": "",
                        "path": font_path_resolved
                    },
                    "range": [0, len(cleaned_text)],
                    "size": font_size,
                    "shadows": [shadow_cfg]
                }
            ]
        }

        serialized_content = json.dumps(text_content_dict, ensure_ascii=False, separators=(',', ':'))

        toks = [tok for tok in re.split(r'(\s+)', cleaned_text) if tok]
        non_space = [tok for tok in toks if not tok.isspace()]
        dur_ms = int(duration_us // 1000)
        n_words = len(non_space) or 1
        step_ms = dur_ms / n_words
        w_starts = []
        w_ends = []
        w_idx = 0
        for tok in toks:
            if not tok.isspace():
                w_starts.append(int(w_idx * step_ms))
                w_ends.append(int((w_idx + 1) * step_ms))
                w_idx += 1
            else:
                prev_e = w_ends[-1] if w_ends else 0
                w_starts.append(prev_e)
                w_ends.append(prev_e)

        text_material = {
            "id": mat_id,
            "name": "",
            "type": "subtitle",
            "content": serialized_content,
            "base_content": serialized_content,
            "font_path": font_path_resolved,
            "font_name": font_name,
            "font_title": font_title,
            "font_size": font_size,
            "text_color": text_color,
            "text_alpha": 1.0,
            "alignment": 1,
            "line_feed": 1,
            "words": {
                "start_time": w_starts,
                "end_time": w_ends,
                "text": toks
            }
        }
        texts.append(text_material)

        seg_id = str(uuid.uuid4()).upper()
        segment = {
            "id": seg_id,
            "material_id": mat_id,
            "target_timerange": {
                "start": start_us,
                "duration": duration_us
            },
            "source_timerange": None,
            "render_timerange": {"start": 0, "duration": 0},
            "speed": 1.0,
            "volume": 1.0,
            "clip": {
                "scale": scale_dict,
                "rotation": 0.0,
                "transform": {
                    "x": 0.0,
                    "y": y_pos
                },
                "flip": {"vertical": False, "horizontal": False},
                "alpha": 1.0
            },
            "uniform_scale": {"on": True, "value": 1.0},
            "extra_material_refs": [],
            "visible": True,
            "enable_color_curves": True,
            "enable_hsl_curves": True,
            "enable_color_wheels": True,
            "enable_video_mask": True
        }
        text_track['segments'].append(segment)
        inserted_count += 1

    # Re-sort segments in the text track by start_time
    text_track['segments'].sort(key=lambda s: s.get('target_timerange', {}).get('start', 0))

    # Re-parse project subtitles
    project._parse_subtitles()

    return inserted_count


def auto_heal_project_gaps(
    project: CapCutProject,
    styler: Optional[DualStyler] = None,
    transcriber: Optional[Any] = None,
    log_fn: Optional[Any] = None,
    min_gap_sec: float = DEFAULT_MIN_GAP_SEC,
    max_gap_sec: float = DEFAULT_MAX_GAP_SEC,
    threshold_db: float = DEFAULT_VOICE_THRESHOLD_DB
) -> Tuple[int, List[SubtitleGap]]:
    """
    Audita automáticamente los huecos de la línea de tiempo usando FFmpeg,
    intenta transcribir con IA aquellos con voz activa, e inserta
    los subtítulos recuperados directamente en el proyecto.
    
    Devuelve (count_healed, unhealed_voice_gaps).
    - count_healed: número de subtítulos recuperados e insertados automáticamente.
    - unhealed_voice_gaps: lista de huecos con voz activa que no pudieron ser
      auto-transcritos (por ejemplo si no hay API key o la IA no devolvió texto).
    """
    def _log(msg: str):
        if log_fn:
            log_fn(msg)
        else:
            logger.info(msg)

    gaps = find_subtitle_gaps(project, min_gap_sec=min_gap_sec, max_gap_sec=max_gap_sec)
    if not gaps:
        return 0, []

    _log(f"[*] Auditoría de continuidad: analizando {len(gaps)} espacios vacíos con FFmpeg...")

    import tempfile
    import shutil
    temp_dir = tempfile.mkdtemp(prefix="cc_subs_pro_auto_heal_")

    healed_items = []
    unhealed_voice_gaps = []

    try:
        for g in gaps:
            if not g.media_path or not os.path.isfile(g.media_path):
                continue

            has_voice, max_v, mean_v = verify_gap_audio_energy(g, threshold_db=threshold_db)
            if not has_voice:
                continue

            # Hay voz activa en el hueco
            snip_path = os.path.join(temp_dir, f"gap_{g.index}.wav")
            extract_gap_audio_snippet(g, snip_path)

            transcribed = ""
            if transcriber and getattr(transcriber, 'is_configured', lambda: False)():
                transcribed = transcriber.transcribe(snip_path)

            if transcribed:
                g.suggested_text = transcribed

                prev_text_clean = clean_subtitle_text(g.prev_text).lower()
                next_text_clean = clean_subtitle_text(g.next_text).lower()
                clean_t = clean_subtitle_text(transcribed).lower()
                words_t = clean_t.split()

                is_duplicate_tail = False
                if clean_t in prev_text_clean or clean_t in next_text_clean:
                    is_duplicate_tail = True
                elif len(words_t) == 1 and (words_t[0] in prev_text_clean or any(w.endswith(words_t[0]) for w in prev_text_clean.split())):
                    is_duplicate_tail = True
                elif words_t and all(w in prev_text_clean for w in words_t):
                    is_duplicate_tail = True

                if is_duplicate_tail:
                    _log(f"  [i] [Hueco en {g.start_time_str}] La voz ('{transcribed}') ya está incluida en el subtítulo adyacente. Sincronizando duración...")
                    if g.prev_sub and hasattr(g.prev_sub, 'segment'):
                        seg_tr = g.prev_sub.segment.get('target_timerange', {})
                        seg_start = seg_tr.get('start', 0)
                        gap_end = g.start_us + g.duration_us
                        new_dur = max(seg_tr.get('duration', 0), gap_end - seg_start)
                        seg_tr['duration'] = new_dur
                else:
                    healed_items.append({
                        'start_us': g.start_us,
                        'duration_us': g.duration_us,
                        'text': transcribed
                    })
                    _log(f"  [+] [Hueco Reparado en {g.start_time_str}] Voz activa ({max_v:.1f} dB): '{transcribed}'")
            else:
                unhealed_voice_gaps.append(g)
                _log(f"  [!] [Voz detectada sin texto en {g.start_time_str}] ({max_v:.1f} dB, {g.duration_str})")

        count_inserted = 0
        if healed_items:
            count_inserted = insert_healed_subtitles(project, healed_items, styler)
            _log(f"  [+] {count_inserted} subtítulo(s) recuperado(s) e insertado(s) automáticamente en CapCut.")

        return count_inserted, unhealed_voice_gaps

    finally:
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

