import os
import sys
import argparse
import json
import logging
from typing import Optional, List

# Ensure safe UTF-8 output on Windows terminal
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from core.capcut_draft import CapCutProject, list_available_projects, DEFAULT_DRAFT_DIR
from core.styler import Styler
from ai.highlighter import AIHighlighter
from core.dual_styler import DualStyler
from core.text_utils import clean_subtitle_text
from core.preset_matcher import detect_preset_from_name


def resolve_preset(preset_name: str = "gerardo") -> dict:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    presets_file = os.path.join(script_dir, 'styles', 'presets.json')
    if os.path.isfile(presets_file):
        try:
            with open(presets_file, 'r', encoding='utf-8') as f:
                presets = json.load(f)
            norm = preset_name.lower().strip()
            if norm in presets:
                return presets[norm]
            key = norm.replace("letra ", "").replace("letra_", "").strip()
            if key in presets:
                return presets[key]
            key_no_de = key.replace("de ", "").replace("de_", "").strip()
            if key_no_de in presets:
                return presets[key_no_de]
        except Exception:
            pass
    gerardo_file = os.path.join(script_dir, 'styles', 'gerardo.json')
    if os.path.isfile(gerardo_file):
        try:
            with open(gerardo_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def setup_logging(debug: bool = False):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )

def resolve_project_path(project_arg: Optional[str]) -> str:
    if project_arg:
        if os.path.exists(project_arg):
            return project_arg
        candidate = os.path.join(DEFAULT_DRAFT_DIR, project_arg)
        if os.path.exists(candidate):
            return candidate
        raise FileNotFoundError(f"Proyecto '{project_arg}' no encontrado como ruta ni en {DEFAULT_DRAFT_DIR}")
    
    projects = list_available_projects()
    if not projects:
        raise FileNotFoundError(f"No se encontraron proyectos de CapCut en {DEFAULT_DRAFT_DIR}")
    print(f"[*] Ningun proyecto especificado. Seleccionado automaticamente el mas reciente: '{projects[0]['name']}'")
    return projects[0]['path']

def cmd_list(args):
    if args.project:
        proj_path = resolve_project_path(args.project)
        proj = CapCutProject(proj_path)
        print(f"\n=== Subtitulos en '{os.path.basename(proj.project_path)}' ({len(proj.subtitles)} encontrados) ===")
        for idx, sub in enumerate(proj.subtitles):
            tr = sub.target_timerange
            start_s = tr.get('start', 0) / 1000000.0
            dur_s = tr.get('duration', 0) / 1000000.0
            fonts = []
            for s in sub.parsed_content.get('styles', []):
                p = s.get('font', {}).get('path', 'default')
                fonts.append(os.path.basename(p) if p else 'default')
            font_str = ', '.join(fonts) if fonts else 'none'
            print(f"[{idx:>3}] [{start_s:6.2f}s - {start_s+dur_s:6.2f}s] ID={sub.segment_id[:8]}... MatID={sub.material_id[:8]}... Font=[{font_str}]")
            print(f"      Texto: \"{sub.text}\"")
    else:
        projects = list_available_projects()
        print(f"\n=== Proyectos de CapCut Disponibles ({len(projects)}) ===")
        for p in projects:
            print(f" - {p['name']:<30} | Subtitulos: {p['subtitle_count']:<3} | Total Textos: {p['total_texts']:<3}")

def cmd_inspect(args):
    proj_path = resolve_project_path(args.project)
    proj = CapCutProject(proj_path)
    print(f"\n=== DETALLES DEL PROYECTO: {os.path.basename(proj.project_path)} ===")
    print(f"Ruta: {proj.content_file}")
    print(f"Duracion: {proj.data.get('duration', 0) / 1000000.0:.2f}s")
    print(f"Total Subtitulos: {len(proj.subtitles)}")
    
    if args.index is not None:
        if 0 <= args.index < len(proj.subtitles):
            sub = proj.subtitles[args.index]
            print(f"\n--- SUBTITULO #{args.index} ---")
            print(f"Segment ID: {sub.segment_id}")
            print(f"Material ID: {sub.material_id}")
            print(f"Timerange: {sub.target_timerange}")
            print(f"Texto: {sub.text}")
            print(f"Styles:\n{json.dumps(sub.parsed_content.get('styles', []), indent=2, ensure_ascii=False)}")
            print(f"Extra Refs: {sub.extra_material_refs}")
        else:
            print(f"Indice fuera de rango (0 - {len(proj.subtitles)-1})")

def cmd_style_one(args):
    """Phase 3: Modify a single subtitle item safely."""
    proj_path = resolve_project_path(args.project)
    proj = CapCutProject(proj_path)
    
    if not proj.subtitles:
        print("No se encontraron subtitulos en el proyecto.")
        return

    idx = args.index if args.index is not None else 0
    if idx < 0 or idx >= len(proj.subtitles):
        print(f"Error: Indice {idx} fuera de rango. Total subtitulos: {len(proj.subtitles)}")
        return

    sub = proj.subtitles[idx]
    orig_text = sub.text
    orig_content = json.dumps(sub.parsed_content, ensure_ascii=False)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_style = args.style_default or os.path.join(script_dir, 'styles', 'default.json')
    highlight_style = args.style_highlight or os.path.join(script_dir, 'styles', 'highlight.json')
    styler = Styler(default_style, highlight_style)

    print(f"\n[*] Modificando subtitulo #{idx}: \"{orig_text}\"")
    if args.highlight:
        phrases = [clean_subtitle_text(p) for p in args.highlight.split(',') if clean_subtitle_text(p)]
        matches = styler.apply_highlight_to_item(sub, proj.data, phrases)
        print(f"    Highlights aplicados a: {phrases} (coincidencias: {matches})")
    else:
        styler.apply_default_style_to_item(sub, proj.data)
        print("    Estilo normal (Aloevera) aplicado.")

    if not args.no_backup:
        backup = proj.create_backup()
        print(f"    Backup creado: {backup}")

    proj.save(create_backup=False)
    print(f"[OK] Subtitulo #{idx} modificado con exito en {proj.content_file}.")
    if args.debug:
        print(f"\n--- DEBUG: Contenido Antes ---")
        print(orig_content)
        print(f"--- DEBUG: Contenido Despues ---")
        print(json.dumps(sub.parsed_content, indent=2, ensure_ascii=False))

def cmd_style_all(args):
    """Phase 4: Modify all subtitles applying normal style."""
    proj_path = resolve_project_path(args.project)
    proj = CapCutProject(proj_path)
    
    if not proj.subtitles:
        print("No se encontraron subtitulos en el proyecto.")
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_style = args.style_default or os.path.join(script_dir, 'styles', 'default.json')
    highlight_style = args.style_highlight or os.path.join(script_dir, 'styles', 'highlight.json')
    styler = Styler(default_style, highlight_style)

    print(f"\n[*] Aplicando estilo normal a {len(proj.subtitles)} subtitulos en '{os.path.basename(proj.project_path)}'...")
    
    if not args.no_backup:
        backup = proj.create_backup()
        print(f"[*] Backup creado: {backup}")

    modified_count = 0
    for sub in proj.subtitles:
        styler.apply_default_style_to_item(sub, proj.data)
        modified_count += 1

    proj.save(create_backup=False)
    print(f"[OK] Proceso completado exitosamente.")
    print(f"    Subtitulos encontrados: {len(proj.subtitles)}")
    print(f"    Subtitulos estilizados: {modified_count}")
    print(f"    Archivo guardado: {proj.content_file}")

def cmd_highlight(args):
    """Phase 5 & 6: Highlight words/phrases (manual or AI)."""
    proj_path = resolve_project_path(args.project)
    proj = CapCutProject(proj_path)
    
    if not proj.subtitles:
        print("No se encontraron subtitulos en el proyecto.")
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_style = args.style_default or os.path.join(script_dir, 'styles', 'default.json')
    highlight_style = args.style_highlight or os.path.join(script_dir, 'styles', 'highlight.json')
    styler = Styler(default_style, highlight_style)

    highlights_map = {}
    
    if args.manual:
        if os.path.isfile(args.manual):
            with open(args.manual, 'r', encoding='utf-8') as f:
                manual_data = json.load(f)
        else:
            manual_data = json.loads(args.manual)

        if isinstance(manual_data, dict) and 'highlights' in manual_data:
            for item in manual_data['highlights']:
                highlights_map[item['subtitle_id']] = item.get('phrases', [])
        else:
            highlights_map = manual_data
            
    elif args.words:
        global_phrases = [clean_subtitle_text(w) for w in args.words.split(',') if clean_subtitle_text(w)]
        for sub in proj.subtitles:
            highlights_map[sub.segment_id] = global_phrases
            
    else:
        print("[*] Analizando subtitulos con IA para detectar palabras clave...")
        highlighter = AIHighlighter(api_key=args.api_key, provider=args.provider or 'auto')
        sub_payload = [{'subtitle_id': s.segment_id, 'text': s.text} for s in proj.subtitles]
        highlights_map = highlighter.get_highlights(sub_payload)

    if not args.no_backup:
        backup = proj.create_backup()
        print(f"[*] Backup creado: {backup}")

    total_highlights_count = 0
    modified_count = 0

    for idx, sub in enumerate(proj.subtitles):
        phrases = highlights_map.get(sub.segment_id, []) or highlights_map.get(str(idx), [])
        if phrases:
            matched = styler.apply_highlight_to_item(sub, proj.data, phrases)
            if matched > 0:
                total_highlights_count += matched
                if args.debug:
                    print(f"  [#{idx}] Destacadas {matched} en: \"{sub.text}\" -> {phrases}")
        else:
            styler.apply_default_style_to_item(sub, proj.data)
        modified_count += 1

    proj.save(create_backup=False)
    print(f"[OK] Proceso de estilizacion y highlights completado:")
    print(f"    Proyecto: {os.path.basename(proj.project_path)}")
    print(f"    Subtitulos encontrados: {len(proj.subtitles)}")
    print(f"    Subtitulos estilizados: {modified_count}")
    print(f"    Highlights aplicados: {total_highlights_count}")
    print(f"    Backup: {'Si' if not args.no_backup else 'No'}")


def cmd_dual_style(args):
    """Phase 7: Two-layer (arriba/abajo) subtitles with highlights every 3-5s."""
    proj_path = resolve_project_path(args.project)
    proj = CapCutProject(proj_path)

    preset_name = getattr(args, 'preset', None)
    if not preset_name or preset_name == 'auto':
        preset_name = detect_preset_from_name(proj_path) or 'gerardo'
    preset_dict = resolve_preset(preset_name)

    if preset_dict and not args.style_default and not args.style_highlight:
        print(f"[*] Aplicando preset: '{preset_dict.get('name', preset_name)}'")
        dual_styler = DualStyler.from_preset(preset_dict)
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        default_style = args.style_default or os.path.join(script_dir, 'styles', 'default.json')
        highlight_style = args.style_highlight or os.path.join(script_dir, 'styles', 'highlight.json')
        dual_styler = DualStyler(default_style, highlight_style)

    if not args.no_backup:
        backup = proj.create_backup()
        print(f"[*] Backup creado: {backup}")

    if args.plan and os.path.isfile(args.plan):
        with open(args.plan, 'r', encoding='utf-8') as f:
            plan = json.load(f)
        top_c, bot_c = dual_styler.apply_plan(proj, plan)
    else:
        highlighter = None
        openrouter_key = getattr(args, 'openrouter_key', None) or args.api_key
        if getattr(args, 'words', None):
            curated = [clean_subtitle_text(w) for w in args.words.split(',') if clean_subtitle_text(w)]
            class WordListHighlighter:
                def suggest_highlights(self, text, count=100):
                    return curated
            highlighter = WordListHighlighter()
        elif args.ai and not openrouter_key:
            highlighter = AIHighlighter(api_key=args.api_key, provider=args.provider or 'auto')
        top_c, bot_c = dual_styler.auto_dual_process(
            proj,
            highlighter=highlighter,
            openrouter_key=openrouter_key,
            min_pacing_sec=args.min_pacing,
            max_pacing_sec=args.max_pacing
        )

    # Strictly enforce 0 commas and 0 periods
    proj.clean_all_subtitles()
    proj.save(create_backup=False)
    print(f"[OK] Estilizacion en doble capa (Arriba / Abajo) completada:")
    print(f"    Proyecto: {os.path.basename(proj.project_path)}")
    print(f"    Subtitulos linea superior (blanco): {top_c}")
    print(f"    Subtitulos linea inferior (destacados): {bot_c}")
    print(f"    Archivo guardado: {proj.content_file}")

def cmd_clean_text(args):
    """Clean all commas, periods, and colons from subtitles in the project."""
    proj_path = resolve_project_path(args.project)
    proj = CapCutProject(proj_path)
    if not proj.subtitles:
        print("No se encontraron subtitulos en el proyecto.")
        return

    if not args.no_backup:
        backup = proj.create_backup()
        print(f"[*] Backup creado: {backup}")

    count = proj.clean_all_subtitles()
    proj.save(create_backup=False)
    print(f"[OK] Puntuación eliminada (, . :) en {count} subtitulos de '{os.path.basename(proj.project_path)}'.")
    print(f"    Archivo guardado: {proj.content_file}")

def cmd_repair_subs(args):
    """Repair fonts and effects on existing subtitles without moving timelines or changing text."""
    proj_path = resolve_project_path(args.project)
    proj = CapCutProject(proj_path)
    if not proj.subtitles:
        print(f"No se encontraron subtítulos en '{os.path.basename(proj.project_path)}'.")
        return

    preset_name = getattr(args, 'preset', 'gerardo') or 'gerardo'
    styler = DualStyler.from_preset(preset_name)

    if not args.no_backup:
        backup = proj.create_backup()
        print(f"[*] Backup creado: {backup}")

    top_c, bot_c = styler.repair_project_subtitles(proj)
    proj.save(create_backup=False)

    print(f"[OK] Reparación de subtítulos completada:")
    print(f"    Proyecto: {os.path.basename(proj.project_path)}")
    print(f"    Preset: {styler.preset_name}")
    print(f"    Subtítulos superiores reparados: {top_c}")
    print(f"    Subtítulos destacados reparados: {bot_c}")
    print("    Líneas de tiempo: 100% INTACTAS")
    print("    Palabras y texto: 100% INTACTAS")
    print(f"    Archivo guardado: {proj.content_file}")

def main():
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument('--debug', action='store_true', help="Habilitar modo debug detallado")

    parser = argparse.ArgumentParser(description="CC Subs Pro: Estilizador nativo de subtitulos para CapCut Windows", parents=[common_parser])
    subparsers = parser.add_subparsers(dest="command", required=True)

    # repair-subs
    p_repair = subparsers.add_parser("repair-subs", aliases=["repair"], help="Reparar fuentes y efectos de subtitulos existentes sin tocar tiempos ni texto", parents=[common_parser])
    p_repair.add_argument("--project", "-p", help="Nombre o ruta del proyecto")
    p_repair.add_argument("--preset", default="gerardo", help="Preset de estilo (gerardo, gala, laura, alharilla, default: gerardo)")
    p_repair.add_argument("--no-backup", action='store_true', help="Omitir creacion de backup")

    # list
    p_list = subparsers.add_parser("list", help="Listar proyectos o subtitulos de un proyecto", parents=[common_parser])
    p_list.add_argument("--project", "-p", help="Nombre o ruta del proyecto")

    # inspect
    p_inspect = subparsers.add_parser("inspect", help="Inspeccion detallada de un proyecto o subtitulo", parents=[common_parser])
    p_inspect.add_argument("--project", "-p", help="Nombre o ruta del proyecto")
    p_inspect.add_argument("--index", "-i", type=int, help="Indice del subtitulo a inspeccionar")

    # style-one (Phase 3)
    p_one = subparsers.add_parser("style-one", help="Modificar UN SOLO subtitulo de prueba", parents=[common_parser])
    p_one.add_argument("--project", "-p", help="Nombre o ruta del proyecto")
    p_one.add_argument("--index", "-i", type=int, default=0, help="Indice del subtitulo a modificar (default 0)")
    p_one.add_argument("--highlight", help="Frase o palabras para destacar (separadas por coma)")
    p_one.add_argument("--style-default", help="Ruta a default.json")
    p_one.add_argument("--style-highlight", help="Ruta a highlight.json")
    p_one.add_argument("--no-backup", action='store_true', help="Omitir creacion de backup")

    # style-all (Phase 4)
    p_all = subparsers.add_parser("style-all", help="Aplicar estilo normal a todos los subtitulos", parents=[common_parser])
    p_all.add_argument("--project", "-p", help="Nombre o ruta del proyecto")
    p_all.add_argument("--style-default", help="Ruta a default.json")
    p_all.add_argument("--style-highlight", help="Ruta a highlight.json")
    p_all.add_argument("--no-backup", action='store_true', help="Omitir creacion de backup")

    # highlight (Phase 5 & 6)
    p_hl = subparsers.add_parser("highlight", help="Aplicar estilo normal + highlights a subtitulos", parents=[common_parser])
    p_hl.add_argument("--project", "-p", help="Nombre o ruta del proyecto")
    p_hl.add_argument("--manual", help="Ruta a archivo JSON con highlights o string JSON")
    p_hl.add_argument("--words", help="Lista global de palabras a destacar separadas por coma")
    p_hl.add_argument("--provider", choices=['auto', 'gemini', 'openai', 'heuristic'], default='auto')
    p_hl.add_argument("--api-key", help="API key para modelo de IA")
    p_hl.add_argument("--style-default", help="Ruta a default.json")
    p_hl.add_argument("--style-highlight", help="Ruta a highlight.json")
    p_hl.add_argument("--no-backup", action='store_true', help="Omitir creacion de backup")


    # dual-style
    p_dual = subparsers.add_parser("dual-style", help="Aplicar subtitulos en doble capa (arriba blanco / abajo destacado)", parents=[common_parser])
    p_dual.add_argument("--project", "-p", help="Nombre o ruta del proyecto")
    p_dual.add_argument("--preset", default="auto", help="Preset de estilo ('cuidus', 'gerardo', 'laura burgos', etc.). Default: 'auto' (detecta automaticamente por el nombre del proyecto)")
    p_dual.add_argument("--plan", help="Ruta a archivo JSON con plan de layout predefinido")
    p_dual.add_argument("--words", help="Lista de palabras o frases clave a destacar separadas por coma")
    p_dual.add_argument("--ai", action='store_true', help="Usar IA para seleccionar palabras destacadas")
    p_dual.add_argument("--min-pacing", type=float, default=3.0, help="Segundos minimos entre highlights (default 3.0)")
    p_dual.add_argument("--max-pacing", type=float, default=5.0, help="Segundos maximos entre highlights (default 5.0)")
    p_dual.add_argument("--provider", choices=['auto', 'gemini', 'openai', 'heuristic'], default='auto')
    p_dual.add_argument("--api-key", help="API key para modelo de IA")
    p_dual.add_argument("--openrouter-key", help="API key de OpenRouter (Gemini Flash)")
    p_dual.add_argument("--style-default", help="Ruta a default.json")
    p_dual.add_argument("--style-highlight", help="Ruta a highlight.json")
    p_dual.add_argument("--no-backup", action='store_true', help="Omitir creacion de backup")

    # clean-text
    p_clean = subparsers.add_parser("clean-text", help="Eliminar comas, puntos y dos puntos (, . :) de todos los subtitulos", parents=[common_parser])
    p_clean.add_argument("--project", "-p", help="Nombre o ruta del proyecto")
    p_clean.add_argument("--no-backup", action='store_true', help="Omitir creacion de backup")

    # gui
    subparsers.add_parser("gui", help="Abrir la interfaz grafica interactiva", parents=[common_parser])

    args = parser.parse_args()
    setup_logging(args.debug)

    if args.command == "gui":
        import gui
        app = gui.CCSubsProGUI()
        app.mainloop()
    elif args.command == "clean-text":
        cmd_clean_text(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "inspect":
        cmd_inspect(args)
    elif args.command == "style-one":
        cmd_style_one(args)
    elif args.command == "style-all":
        cmd_style_all(args)
    elif args.command == "highlight":
        cmd_highlight(args)
    elif args.command == "dual-style":
        cmd_dual_style(args)
    elif args.command in ["repair-subs", "repair"]:
        cmd_repair_subs(args)


if __name__ == '__main__':
    main()
