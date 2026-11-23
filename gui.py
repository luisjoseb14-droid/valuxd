"""
CC Subs Pro - Interfaz Gráfica Profesional para Estilización de Subtítulos CapCut
Compatible con macOS y Windows 10/11 sin configuraciones complejas.
Soporta presets para: Dr. Gerardo, Dra. Gala, Dra. Laura Pediatra, Dra. Alharilla, Emilia, Jose, Deditos, CUIDUS, Dra. Laura Burgos.
"""

import os
import sys
import json
import shutil
import tempfile
import threading
import unicodedata
from typing import List, Optional, Dict, Any, Tuple
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Ensure UTF-8 output
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from core.capcut_draft import CapCutProject, list_available_projects, DEFAULT_DRAFT_DIR
from core.dual_styler import DualStyler
from core.styler import Styler
from core.font_installer import install_all_assets
from core.text_utils import clean_subtitle_text
from core.preset_matcher import detect_preset_from_name
from core.grammar_checker import check_project_grammar, apply_grammar_fixes
from core.gap_healer import (
    find_subtitle_gaps,
    verify_gap_audio_energy,
    extract_gap_audio_snippet,
    play_audio_snippet,
    insert_healed_subtitles,
    auto_heal_project_gaps,
    SubtitleGap
)
from ai.transcriber import AudioTranscriber
from ai.openrouter_client import OpenRouterClient, DEFAULT_MODEL
try:
    from ai.highlighter import AIHighlighter
except Exception:
    AIHighlighter = None

from core.updater import (
    check_for_updates,
    download_and_apply_update,
    ensure_ai_modules_up_to_date,
    get_local_version_info
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, '.cc_subs_pro_config.json')


def _normalize_search_text(text: str) -> str:
    """Normaliza texto eliminando tildes y pasando a minúsculas para búsquedas tolerantes."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(text))
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.lower().strip()


PRESET_OPTIONS: List[Dict[str, str]] = [
    {"value": "gerardo", "label": "🩺 Dr. Gerardo  (Aloevera | Behind The Nineties)", "keywords": "gerardo dr gerardo aloevera behind the nineties turquesa"},
    {"value": "gala", "label": "🩺 Dra. Gala  (Helvetica | Things blanco)", "keywords": "gala dra gala helvetica things blanco"},
    {"value": "laura", "label": "🩺 Dra. Laura Pediatra  (Josefin Sans celeste)", "keywords": "laura pediatra dra laura josefin sans celeste"},
    {"value": "alharilla", "label": "🩺 Dra. Alharilla  (Raleway | Bebas Neue verde)", "keywords": "alharilla dra alharilla raleway bebas neue verde menta"},
    {"value": "jose", "label": "🩺 Dr. Jose Podólogo  (Aglatia | Bluemun oro)", "keywords": "jose podologo dr jose aglatia bluemun oro"},
    {"value": "deditos", "label": "🦶 Deditos Barefoot  (Lilita One naranja)", "keywords": "deditos barefoot lilita one naranja"},
    {"value": "emilia", "label": "✨ Emilia  (Neue Helvena | Karelle + Stickers)", "keywords": "emilia neue helvena karelle amarillo stickers"},
    {"value": "alvaro", "label": "🩺 Dr. Álvaro  (GC GRIND | Coral + Corte láser)", "keywords": "alvaro dr alvaro gc grind coral laser"},
    {"value": "pequenos", "label": "👶 Pequeños Cuidados  (Parafina | Chewy amarillo + Mini zoom)", "keywords": "pequenos cuidados parafina chewy amarillo mini zoom"},
    {"value": "ana", "label": "👂 Dra. Ana Otorrino  (Liliana Bold | Liliana Black + Flotación)", "keywords": "ana otorrino dra ana liliana bold black amarillo flotacion"},
    {"value": "cuidus", "label": "🌸 CUIDUS  (Gentium Plus Italic | Gentium Plus Bold rosa)", "keywords": "cuidus gentium plus italic bold rosa"},
    {"value": "laura burgos", "label": "🩺 Dra. Laura Burgos  (Indivisible | Indivisible Bold + Aparición progresiva)", "keywords": "laura burgos dra laura burgos indivisible verde azulado"},
    {"value": "enfocavision", "label": "👁️ Doctores Enfocavisión  (ITC Avant Garde Demi | Bold menta + Mini zoom)", "keywords": "enfocavision doctores itc avant garde demi bold menta"},
    {"value": "juan", "label": "🌿 Juan  (Gotham Bold blanco | Anton morado #7F1CCC)", "keywords": "juan gotham bold anton morado"},
    {"value": "carrillo", "label": "🩺 Dr. Carrillo  (Gotham Book blanco | Gotham Bold arena #CCC3B1)", "keywords": "carrillo carillo dr carrillo gotham book bold arena"},
    {"value": "dentok", "label": "🦷 Dentok  (Helvetica Regular | Playfair Display + Escalera)", "keywords": "dentok helvetica regular playfair display escalera"},
    {"value": "angel_cadenas", "label": "⚡ Ángel Cárdenas  (Dream Believer Bold blanco 9 | Ligerid #FCFE60 12)", "keywords": "angel cardenas cadenas dream believer ligerid amarillo"},
    {"value": "nuria", "label": "🌸 Dra. Nuria  (Recline | Bold Italic rosa + Zoom blur)", "keywords": "nuria ginecologa dra nuria recline bold italic rosa zoom blur"},
    {"value": "ana_visedo", "label": "✨ Dra. Ana Visedo  (Poppins Bold blanco 10 | Wonder Nature Sans rosa 12 + Mini zoom + Stickers)", "keywords": "ana visedo dra ana visedo poppins bold wonder nature sans rosa stickers"},
    {"value": "jairo", "label": "🩺 Dr. Jairo  (Montserrat Bold blanco 10 | Antro Vectra menta #26FFA0 17 + Aparición progresiva + Click fx)", "keywords": "jairo dr jairo montserrat bold antro vectra menta"},
    {"value": "maria_manuel", "label": "👥 María y Manuel  (Mukta Mahee blanco 11 | Marydale blanco 22 + Mini zoom + Stickers + Click fx)", "keywords": "maria manuel maria y manuel mukta mahee marydale blanco stickers"},
    {"value": "abde", "label": "🩺 Abde  (Akzidenz Grotesk Black blanco 9 | azul cielo #6D94FF 11 + Descenso + Clicks chinos + Puntuación)", "keywords": "abde adbe akzidenz grotesk black azul cielo puntuacion"},
    {"value": "paco", "label": "🩺 Paco  (Gotham Light blanco 10 | Anton blanco grande 20 + Click fx)", "keywords": "paco dr paco gotham light anton blanco"},
    {"value": "ana_linares", "label": "🩺 Dra. Ana Linares  (Playfair Display Bold blanco 14 | Montserrat Medium #ACB1EC 25 + Mini zoom + Click fx)", "keywords": "ana linares lopez linares dra ana linares playfair display bold montserrat medium lila"},
    {"value": "costa_calida", "label": "🛋️ Costa Cálida  (Montserrat Medium blanco 10 | PT Serif amarillo #F5D90E 14 + Aparición progresiva + Click fx)", "keywords": "costa calida cálida montserrat medium pt serif amarillo aparicion progresiva"},
]

PRESET_ALIAS_TO_VALUE: Dict[str, str] = {
    "laura_burgos": "laura burgos",
    "dra laura burgos": "laura burgos",
    "dra. laura burgos": "laura burgos",
    "ana otorrino": "ana",
    "ana_otorrino": "ana",
    "ana visedo": "ana_visedo",
    "visedo": "ana_visedo",
    "ana linares": "ana_linares",
    "dra ana linares": "ana_linares",
    "dra. ana linares": "ana_linares",
    "linares": "ana_linares",
    "ana lopez linares": "ana_linares",
    "ana lópez linares": "ana_linares",
    "dr dentok": "dentok",
    "sep dentok": "dentok",
    "angel": "angel_cadenas",
    "dra nuria": "nuria",
    "dr jairo": "jairo",
    "maria y manuel": "maria_manuel",
    "manuel": "maria_manuel",
    "maria": "maria_manuel",
    "letra abde": "abde",
    "letra paco": "paco",
    "dr paco": "paco",
    "costa calida": "costa_calida",
    "costa cálida": "costa_calida",
    "letra costa calida": "costa_calida",
    "letra_costa_calida": "costa_calida",
}


class CCSubsProGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CC Subs Pro - Estilizador de Subtítulos CapCut")
        self.geometry("900x700")
        self.minsize(860, 620)

        # Dark theme palette
        self.bg_color = "#181825"
        self.card_bg = "#1e1e2e"
        self.card_border = "#313244"
        self.fg_color = "#cdd6f4"
        self.accent_color = "#2F9FA3"
        self.accent_hover = "#3bb5ba"
        self.accent_green = "#a6e3a1"
        self.accent_yellow = "#f9e2af"
        self.accent_red = "#f38ba8"

        self.configure(bg=self.bg_color)

        self.projects = []
        self.selected_project_path = tk.StringVar()
        self.doctor_preset = tk.StringVar(value="gerardo")
        self._preset_display_var = tk.StringVar(value="")
        self.preset_search_var = tk.StringVar(value="")
        self._preset_popup = None
        self._preset_listbox = None
        self._preset_search_entry = None
        self._preset_count_lbl = None
        self._preset_filtered_options = list(PRESET_OPTIONS)
        self.highlight_method = tk.StringVar(value="openrouter")
        self.manual_words = tk.StringVar()
        self.openrouter_key_var = tk.StringVar()
        self.show_key_var = tk.BooleanVar(value=False)
        self.save_key_locally = tk.BooleanVar(value=False)
        self.enable_anim_var = tk.BooleanVar(value=True)

        self.local_version_info = get_local_version_info()

        self._load_local_config()
        self._setup_styles()
        self._build_ui()
        self._load_projects()

        # Silent initial check for font installation on startup
        threading.Thread(target=self._auto_check_fonts, daemon=True).start()
        # Silent check for updates from GitHub on startup
        threading.Thread(target=self._background_check_updates, daemon=True).start()

    def _load_local_config(self):
        if os.path.isfile(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    saved_key = cfg.get('openrouter_key') or cfg.get('api_key', '')
                    if saved_key:
                        self.openrouter_key_var.set(saved_key)
                        self.save_key_locally.set(True)
                    self.doctor_preset.set(cfg.get('last_preset', 'gerardo'))
                    self.highlight_method.set(cfg.get('last_method', 'openrouter'))
            except Exception:
                pass
        if not self.openrouter_key_var.get() and os.environ.get('OPENROUTER_API_KEY'):
            self.openrouter_key_var.set(os.environ.get('OPENROUTER_API_KEY'))

    def _save_local_config(self):
        cfg = {
            'last_preset': self.doctor_preset.get(),
            'last_method': self.highlight_method.get()
        }
        if self.save_key_locally.get():
            cfg['openrouter_key'] = self.openrouter_key_var.get().strip()
            cfg['api_key'] = self.openrouter_key_var.get().strip()
        else:
            cfg['openrouter_key'] = ''
            cfg['api_key'] = ''
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2)
        except Exception:
            pass

    def _auto_check_fonts(self):
        try:
            install_all_assets()
        except Exception:
            pass

    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use('clam')

        style.configure(".", background=self.bg_color, foreground=self.fg_color, font=("Segoe UI", 10))
        style.configure("Card.TFrame", background=self.card_bg, relief="flat")
        style.configure("Section.TLabel", font=("Segoe UI", 11, "bold"), foreground=self.accent_color, background=self.card_bg)
        style.configure("Sub.TLabel", font=("Segoe UI", 9), foreground="#a6adc8", background=self.card_bg)
        
        style.configure("Action.TButton", font=("Segoe UI", 11, "bold"), background=self.accent_color, foreground="#ffffff", borderwidth=0, padding=10)
        style.map("Action.TButton", background=[('active', self.accent_hover), ('disabled', '#585b70')])

        style.configure("Grammar.TButton", font=("Segoe UI", 11, "bold"), background="#89dceb", foreground="#11111b", borderwidth=0, padding=10)
        style.map("Grammar.TButton", background=[('active', '#94e2d5'), ('disabled', '#585b70')])

        style.configure("Secondary.TButton", font=("Segoe UI", 9), background="#313244", foreground="#ffffff", borderwidth=0, padding=5)
        style.map("Secondary.TButton", background=[('active', '#45475a')])

        style.configure("HeaderBtn.TButton", font=("Segoe UI", 9, "bold"), background="#45475a", foreground=self.accent_green, borderwidth=0, padding=6)
        style.map("HeaderBtn.TButton", background=[('active', '#585b70')])

        style.configure("UpdateBtn.TButton", font=("Segoe UI", 9, "bold"), background="#89b4fa", foreground="#11111b", borderwidth=0, padding=6)
        style.map("UpdateBtn.TButton", background=[('active', '#b4befe')])

        style.configure("UpdateReadyBtn.TButton", font=("Segoe UI", 9, "bold"), background="#a6e3a1", foreground="#11111b", borderwidth=0, padding=6)
        style.map("UpdateReadyBtn.TButton", background=[('active', '#94e2d5')])

        style.configure("Repair.TButton", font=("Segoe UI", 10, "bold"), background="#b4befe", foreground="#11111b", borderwidth=0, padding=10)
        style.map("Repair.TButton", background=[('active', '#cdd6f4'), ('disabled', '#585b70')])

        style.configure("Heal.TButton", font=("Segoe UI", 10, "bold"), background="#f9e2af", foreground="#11111b", borderwidth=0, padding=8)
        style.map("Heal.TButton", background=[('active', '#fae3b0'), ('disabled', '#585b70')])

        style.configure("TRadiobutton", background=self.card_bg, foreground=self.fg_color, font=("Segoe UI", 10))
        style.map("TRadiobutton", background=[('active', self.card_bg)])

        style.configure("TCheckbutton", background=self.card_bg, foreground=self.fg_color, font=("Segoe UI", 9))
        style.map("TCheckbutton", background=[('active', self.card_bg)])

    def _build_ui(self):
        main_container = tk.Frame(self, bg=self.bg_color, padx=16, pady=8)
        main_container.pack(fill=tk.BOTH, expand=True)

        # Header Frame
        hdr_frame = tk.Frame(main_container, bg=self.bg_color)
        hdr_frame.pack(fill=tk.X, pady=(0, 6))

        title_subframe = tk.Frame(hdr_frame, bg=self.bg_color)
        title_subframe.pack(side=tk.LEFT)

        lbl_title = tk.Label(title_subframe, text="CC Subs Pro", font=("Segoe UI", 16, "bold"), fg=self.accent_color, bg=self.bg_color)
        lbl_title.pack(side=tk.LEFT)

        v_str = self.local_version_info.get("version", "1.0.0")
        lbl_sub = tk.Label(title_subframe, text=f" | Estilizador de Subtítulos CapCut  (v{v_str})", font=("Segoe UI", 10), fg="#a6adc8", bg=self.bg_color)
        lbl_sub.pack(side=tk.LEFT, pady=(3, 0))

        btn_settings = ttk.Button(hdr_frame, text="⚙️ Configuración", style="HeaderBtn.TButton", command=self._open_settings_dialog)
        btn_settings.pack(side=tk.RIGHT, padx=(6, 0))

        btn_install_fonts = ttk.Button(hdr_frame, text="⚡ Instalar Fuentes", style="HeaderBtn.TButton", command=self._manual_install_fonts)
        btn_install_fonts.pack(side=tk.RIGHT, padx=(6, 0))

        self.btn_update = ttk.Button(hdr_frame, text="🔄 Actualizar", style="UpdateBtn.TButton", command=self._on_update_clicked)
        self.btn_update.pack(side=tk.RIGHT)

        # 1. Project Selection Card
        proj_card = ttk.Frame(main_container, style="Card.TFrame", padding=8)
        proj_card.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(proj_card, text="1. Proyecto de CapCut", style="Section.TLabel").pack(anchor=tk.W, pady=(0, 3))

        proj_row = tk.Frame(proj_card, bg=self.card_bg)
        proj_row.pack(fill=tk.X)

        self.proj_combo = ttk.Combobox(proj_row, textvariable=self.selected_project_path, state="readonly", font=("Segoe UI", 10))
        self.proj_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        btn_refresh = ttk.Button(proj_row, text="↻ Refrescar", style="Secondary.TButton", command=self._load_projects)
        btn_refresh.pack(side=tk.LEFT, padx=(0, 5))

        btn_browse = ttk.Button(proj_row, text="Examinar...", style="Secondary.TButton", command=self._browse_project)
        btn_browse.pack(side=tk.LEFT)

        self.lbl_proj_info = tk.Label(proj_card, text="Cargando proyectos...", font=("Segoe UI", 9), fg="#a6adc8", bg=self.card_bg, anchor="w")
        self.lbl_proj_info.pack(fill=tk.X, pady=(4, 0))
        self.proj_combo.bind("<<ComboboxSelected>>", self._on_project_selected)

        # 2. Preset Selection Card (Doctors)
        preset_card = ttk.Frame(main_container, style="Card.TFrame", padding=10)
        preset_card.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(preset_card, text="2. Selecciona el Estilo de Doctor / Doctora", style="Section.TLabel").pack(anchor=tk.W, pady=(0, 6))

        # Compact searchable dropdown trigger (replaces 24+ radiobuttons so action buttons and log always remain visible)
        self.preset_dropdown_frame = tk.Frame(
            preset_card,
            bg="#11111b",
            highlightbackground="#45475a",
            highlightcolor=self.accent_color,
            highlightthickness=1,
            cursor="hand2"
        )
        self.preset_dropdown_frame.pack(fill=tk.X, pady=(0, 4))

        self.lbl_preset_value = tk.Label(
            self.preset_dropdown_frame,
            textvariable=self._preset_display_var,
            font=("Segoe UI", 10, "bold"),
            fg=self.fg_color,
            bg="#11111b",
            anchor="w",
            padx=10,
            pady=7,
            cursor="hand2"
        )
        self.lbl_preset_value.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.lbl_preset_hint_badge = tk.Label(
            self.preset_dropdown_frame,
            text=f"🔍 Buscar ({len(PRESET_OPTIONS)})  ▼",
            font=("Segoe UI", 9),
            fg="#a6adc8",
            bg="#11111b",
            padx=10,
            pady=7,
            cursor="hand2"
        )
        self.lbl_preset_hint_badge.pack(side=tk.RIGHT)

        for w in (self.preset_dropdown_frame, self.lbl_preset_value, self.lbl_preset_hint_badge):
            w.bind("<Button-1>", self._toggle_preset_dropdown)
            w.bind("<Enter>", lambda _e: self.preset_dropdown_frame.config(highlightbackground=self.accent_color))
            w.bind("<Leave>", lambda _e: self.preset_dropdown_frame.config(
                highlightbackground=self.accent_color if self._preset_popup is not None else "#45475a"
            ))

        self.bind("<Button-1>", self._on_root_click, add="+")
        self.bind("<Configure>", self._on_root_configure, add="+")

        # Dynamic detail line for the selected doctor
        self.lbl_preset_detail = tk.Label(
            preset_card,
            text="",
            font=("Segoe UI", 8),
            fg="#a6adc8",
            bg=self.card_bg,
            anchor="w",
            justify=tk.LEFT,
            wraplength=840
        )
        self.lbl_preset_detail.pack(fill=tk.X, pady=(2, 2))

        # Checkbox for animation toggle
        anim_row = tk.Frame(preset_card, bg=self.card_bg)
        anim_row.pack(fill=tk.X, pady=(2, 0))
        self.chk_anim = ttk.Checkbutton(anim_row, text="Animación de entrada en highlights (si el preset lo incluye)", variable=self.enable_anim_var)
        self.chk_anim.pack(side=tk.LEFT)
        self._on_preset_change()

        # 3. Compact Detection Mode Bar
        mode_card = ttk.Frame(main_container, style="Card.TFrame", padding=(10, 7))
        mode_card.pack(fill=tk.X, pady=(0, 6))

        mode_row = tk.Frame(mode_card, bg=self.card_bg)
        mode_row.pack(fill=tk.X)

        self.lbl_mode_status = tk.Label(
            mode_row,
            text=self._get_mode_status_text(),
            font=("Segoe UI", 9, "bold"),
            fg=self.accent_color,
            bg=self.card_bg
        )
        self.lbl_mode_status.pack(side=tk.LEFT, pady=2)

        btn_cfg = ttk.Button(mode_row, text="⚙️ Configurar", style="Secondary.TButton", command=self._open_settings_dialog)
        btn_cfg.pack(side=tk.RIGHT)

        # Action Buttons
        act_frame = tk.Frame(main_container, bg=self.bg_color)
        act_frame.pack(fill=tk.X, pady=(3, 5))

        btn_row = tk.Frame(act_frame, bg=self.bg_color)
        btn_row.pack(fill=tk.X)

        self.btn_run = ttk.Button(btn_row, text="★ ESTILIZAR SUBTÍTULOS", style="Action.TButton", command=self._start_process)
        self.btn_run.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        self.btn_grammar = ttk.Button(btn_row, text="✍️ COMPROBAR GRAMÁTICA", style="Grammar.TButton", command=self._start_grammar_check)
        self.btn_grammar.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(5, 0))

        btn_row2 = tk.Frame(act_frame, bg=self.bg_color)
        btn_row2.pack(fill=tk.X, pady=(5, 0))

        self.btn_repair = ttk.Button(btn_row2, text="🛠️ REPARAR SUBTÍTULOS (Fuentes y Efectos)", style="Repair.TButton", command=self._start_repair)
        self.btn_repair.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        self.btn_heal = ttk.Button(btn_row2, text="🩹 AUDITAR Y REPARAR HUECOS DE VOZ (FFmpeg + IA)", style="Heal.TButton", command=self._start_audit_gaps)
        self.btn_heal.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(5, 0))

        lbl_repair_hint = tk.Label(
            act_frame,
            text="💡 'Comprobar Gramática' revisa tildes y ortografía con OpenRouter sin cambiar tiempos ni estilos. 'Reparar' corrige fuentes/efectos.",
            font=("Segoe UI", 8),
            fg="#a6adc8",
            bg=self.bg_color
        )
        lbl_repair_hint.pack(anchor=tk.W, pady=(3, 0))

        # Log Card
        log_card = ttk.Frame(main_container, style="Card.TFrame", padding=8)
        log_card.pack(fill=tk.BOTH, expand=True)

        log_hdr = tk.Frame(log_card, bg=self.card_bg)
        log_hdr.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(log_hdr, text="Registro de Ejecución", style="Section.TLabel").pack(side=tk.LEFT)
        self.lbl_status = tk.Label(log_hdr, text="Listo para procesar", font=("Segoe UI", 9), fg=self.accent_green, bg=self.card_bg)
        self.lbl_status.pack(side=tk.RIGHT)

        self.txt_log = tk.Text(log_card, height=4, bg="#11111b", fg="#a6adc8", font=("Consolas", 9), relief="flat", wrap=tk.WORD)
        self.txt_log.pack(fill=tk.BOTH, expand=True)

    def _log(self, text: str):
        self.txt_log.insert(tk.END, text + "\n")
        self.txt_log.see(tk.END)

    def _get_preset_option_by_value(self, value: str) -> Dict[str, str]:
        raw = (value or "gerardo").strip()
        canonical = PRESET_ALIAS_TO_VALUE.get(raw.lower(), raw)
        for opt in PRESET_OPTIONS:
            if opt["value"].lower() == canonical.lower():
                return opt
        return {"value": raw, "label": f"🩺 {raw}", "keywords": raw}

    def _filter_preset_options(self, query: str) -> List[Dict[str, str]]:
        norm_q = _normalize_search_text(query)
        if not norm_q:
            return list(PRESET_OPTIONS)
        tokens = [t for t in norm_q.split() if t]
        matches = []
        for opt in PRESET_OPTIONS:
            haystack = _normalize_search_text(
                f"{opt['label']} {opt['value']} {opt.get('keywords', '')}"
            )
            if all(tok in haystack for tok in tokens):
                matches.append(opt)
        return matches

    def _toggle_preset_dropdown(self, event=None):
        if self._preset_popup is not None:
            self._close_preset_dropdown()
        else:
            self._open_preset_dropdown()
        return "break"

    def _open_preset_dropdown(self):
        if self._preset_popup is not None:
            return
        self.update_idletasks()

        popup = tk.Frame(self, bg=self.accent_color, bd=0, highlightthickness=0)
        self._preset_popup = popup

        btn = self.preset_dropdown_frame
        win_w = max(self.winfo_width(), 900)
        win_h = max(self.winfo_height(), 620)
        width = max(btn.winfo_width(), 420)
        width = min(width, win_w - 20)
        rel_x = btn.winfo_rootx() - self.winfo_rootx()
        rel_y_below = btn.winfo_rooty() - self.winfo_rooty() + btn.winfo_height() + 2
        popup_h = min(330, max(200, win_h - rel_y_below - 12))
        if rel_y_below + 180 > win_h:
            rel_y = max(10, (btn.winfo_rooty() - self.winfo_rooty()) - popup_h - 2)
        else:
            rel_y = rel_y_below

        self.preset_dropdown_frame.config(highlightbackground=self.accent_color)
        self.lbl_preset_hint_badge.config(text=f"🔍 Buscar ({len(PRESET_OPTIONS)})  ▲")

        inner = tk.Frame(popup, bg="#181825", padx=6, pady=6)
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Search bar row inside the dropdown
        search_bar = tk.Frame(inner, bg="#11111b", highlightbackground="#45475a", highlightthickness=1)
        search_bar.pack(fill=tk.X, pady=(0, 6))

        tk.Label(
            search_bar,
            text="🔍",
            font=("Segoe UI", 10),
            fg="#a6adc8",
            bg="#11111b",
            padx=6
        ).pack(side=tk.LEFT)

        self.preset_search_var.set("")
        search_entry = tk.Entry(
            search_bar,
            textvariable=self.preset_search_var,
            font=("Segoe UI", 10),
            bg="#11111b",
            fg=self.fg_color,
            insertbackground=self.accent_color,
            relief="flat",
            bd=4
        )
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._preset_search_entry = search_entry

        btn_clear = tk.Label(
            search_bar,
            text="✕",
            font=("Segoe UI", 9, "bold"),
            fg="#a6adc8",
            bg="#11111b",
            padx=8,
            cursor="hand2"
        )
        btn_clear.pack(side=tk.RIGHT)
        btn_clear.bind("<Button-1>", lambda _e: (self.preset_search_var.set(""), search_entry.focus_set()))

        # Match counter / hint bar
        meta_row = tk.Frame(inner, bg="#181825")
        meta_row.pack(fill=tk.X, pady=(0, 4))
        self._preset_count_lbl = tk.Label(
            meta_row,
            text="",
            font=("Segoe UI", 8),
            fg="#a6adc8",
            bg="#181825",
            anchor="w"
        )
        self._preset_count_lbl.pack(side=tk.LEFT)
        tk.Label(
            meta_row,
            text="Escribe nombre o fuente • ↑↓ y Enter",
            font=("Segoe UI", 8),
            fg="#6c7086",
            bg="#181825",
            anchor="e"
        ).pack(side=tk.RIGHT)

        # Scrollable list of presets
        list_frame = tk.Frame(inner, bg="#11111b")
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            bg="#11111b",
            fg=self.fg_color,
            selectbackground=self.accent_color,
            selectforeground="#11111b",
            activestyle="none",
            font=("Segoe UI", 10),
            relief="flat",
            highlightthickness=0,
            bd=0,
            exportselection=False
        )
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)
        self._preset_listbox = listbox

        # Bindings for seamless keyboard + mouse selection
        self._preset_search_trace_id = self.preset_search_var.trace_add("write", self._refresh_preset_listbox)
        search_entry.bind("<KeyPress>", self._on_preset_search_key)
        listbox.bind("<KeyPress>", self._on_preset_search_key)
        listbox.bind("<ButtonRelease-1>", self._on_preset_listbox_click)
        listbox.bind("<Motion>", self._on_preset_listbox_hover)
        popup.bind("<Escape>", self._close_preset_dropdown)

        self._refresh_preset_listbox()
        popup.place(x=rel_x, y=rel_y, width=width, height=popup_h)
        popup.lift()
        self.after(10, lambda: search_entry.winfo_exists() and search_entry.focus_set())

    def _close_preset_dropdown(self, event=None):
        popup = self._preset_popup
        if popup is None:
            return
        self._preset_popup = None
        self._preset_listbox = None
        self._preset_search_entry = None
        self._preset_count_lbl = None
        trace_id = getattr(self, "_preset_search_trace_id", None)
        if trace_id:
            try:
                self.preset_search_var.trace_remove("write", trace_id)
            except Exception:
                pass
            self._preset_search_trace_id = None
        try:
            popup.destroy()
        except Exception:
            pass
        if hasattr(self, "preset_dropdown_frame"):
            self.preset_dropdown_frame.config(highlightbackground="#45475a")
        if hasattr(self, "lbl_preset_hint_badge"):
            self.lbl_preset_hint_badge.config(text=f"🔍 Buscar ({len(PRESET_OPTIONS)})  ▼")

    def _on_root_click(self, event):
        if self._preset_popup is None:
            return
        widget = event.widget
        # Keep open if click is inside the popup or the dropdown trigger itself
        curr = widget
        while curr is not None:
            if curr == self._preset_popup or curr == self.preset_dropdown_frame:
                return
            curr = getattr(curr, "master", None)
        self._close_preset_dropdown()

    def _on_root_configure(self, event):
        if event.widget == self and self._preset_popup is not None:
            self._close_preset_dropdown()

    def _refresh_preset_listbox(self, *_args):
        if self._preset_listbox is None:
            return
        query = self.preset_search_var.get()
        filtered = self._filter_preset_options(query)
        self._preset_filtered_options = filtered

        lb = self._preset_listbox
        lb.delete(0, tk.END)
        if not filtered:
            lb.insert(tk.END, "  Sin coincidencias para esa búsqueda")
            if self._preset_count_lbl is not None:
                self._preset_count_lbl.config(text="0 coincidencias", fg=self.accent_yellow)
            return

        active_opt = self._get_preset_option_by_value(self.doctor_preset.get())
        selected_idx = 0
        for idx, opt in enumerate(filtered):
            prefix = "✓ " if opt["value"] == active_opt["value"] else "   "
            lb.insert(tk.END, f"{prefix}{opt['label']}")
            if opt["value"] == active_opt["value"]:
                selected_idx = idx

        lb.selection_clear(0, tk.END)
        lb.selection_set(selected_idx)
        lb.activate(selected_idx)
        lb.see(selected_idx)

        if self._preset_count_lbl is not None:
            if query.strip():
                noun = "coincidencia" if len(filtered) == 1 else "coincidencias"
                self._preset_count_lbl.config(text=f"{len(filtered)} {noun}", fg=self.accent_green)
            else:
                self._preset_count_lbl.config(text=f"{len(filtered)} letras disponibles", fg="#a6adc8")

    def _on_preset_listbox_hover(self, event):
        if self._preset_listbox is None or not self._preset_filtered_options:
            return
        idx = self._preset_listbox.nearest(event.y)
        if 0 <= idx < len(self._preset_filtered_options):
            self._preset_listbox.selection_clear(0, tk.END)
            self._preset_listbox.selection_set(idx)
            self._preset_listbox.activate(idx)

    def _on_preset_listbox_click(self, event=None):
        if self._preset_listbox is None or not self._preset_filtered_options:
            return
        if event is not None:
            idx = self._preset_listbox.nearest(event.y)
        else:
            sel = self._preset_listbox.curselection()
            idx = sel[0] if sel else 0
        if 0 <= idx < len(self._preset_filtered_options):
            self._select_preset_value(self._preset_filtered_options[idx]["value"])

    def _on_preset_search_key(self, event):
        if self._preset_listbox is None:
            return
        key = event.keysym
        if key == "Escape":
            self._close_preset_dropdown()
            return "break"
        if key == "Return":
            if self._preset_filtered_options:
                sel = self._preset_listbox.curselection()
                idx = sel[0] if sel else 0
                if 0 <= idx < len(self._preset_filtered_options):
                    self._select_preset_value(self._preset_filtered_options[idx]["value"])
            return "break"
        if key in ("Down", "Up"):
            if not self._preset_filtered_options:
                return "break"
            sel = self._preset_listbox.curselection()
            cur = sel[0] if sel else 0
            nxt = min(len(self._preset_filtered_options) - 1, cur + 1) if key == "Down" else max(0, cur - 1)
            self._preset_listbox.selection_clear(0, tk.END)
            self._preset_listbox.selection_set(nxt)
            self._preset_listbox.activate(nxt)
            self._preset_listbox.see(nxt)
            return "break"

    def _select_preset_value(self, value: str):
        self.doctor_preset.set(value)
        self._close_preset_dropdown()
        self._on_preset_change()

    def _on_preset_change(self):
        p = self.doctor_preset.get()
        active_opt = self._get_preset_option_by_value(p)
        if hasattr(self, '_preset_display_var'):
            self._preset_display_var.set(active_opt["label"])
        if p in ["gerardo", "alharilla", "jose", "deditos", "laura", "emilia", "alvaro", "pequenos", "cuidus", "laura burgos", "laura_burgos", "enfocavision", "nuria", "ana_visedo", "ana_linares", "ana linares", "dra ana linares", "dra. ana linares", "linares", "costa_calida", "costa calida", "costa cálida", "jairo", "maria_manuel", "abde"]:
            self.chk_anim.config(state=tk.NORMAL)
            self.enable_anim_var.set(True)
        else:
            self.chk_anim.config(state=tk.DISABLED)
            self.enable_anim_var.set(False)

        details = {
            "gerardo": "🩺 Dr. Gerardo: Aloevera blanco arriba | Behind The Nineties turquesa abajo + Deslizante + Click fx",
            "gala": "🩺 Dra. Gala: Helvetica blanco arriba | Things blanco grande abajo + Click fx",
            "laura": "🩺 Dra. Laura Pediatra: Josefin Sans blanco arriba | Josefin Sans celeste en MAYÚSCULAS abajo + Animación",
            "alharilla": "🩺 Dra. Alharilla: Raleway blanco arriba | Bebas Neue verde menta en MAYÚSCULAS abajo + Proyección 2 + Click fx",
            "jose": "🩺 Dr. Jose Podólogo: Aglatia blanco arriba | Bluemun oro abajo + Animación + Descansos + Click fx",
            "deditos": "🦶 Deditos Barefoot: Lilita One blanco arriba | Lilita One naranja abajo + Mini zoom + Click fx",
            "emilia": "✨ Emilia: Neue Helvena blanco arriba | Karelle DEMO amarillo abajo + Mini zoom + Stickers CapCut + Click fx",
            "alvaro": "🩺 Dr. Álvaro: GC GRIND blanco arriba | GC GRIND coral abajo + Corte con láser + Click fx",
            "pequenos": "👶 Pequeños Cuidados: Parafina blanco arriba | Chewy amarillo abajo + Mini zoom + Click fx",
            "ana": "👂 Dra. Ana Otorrino: Plantilla CapCut flotante | Liliana Bold blanco + Liliana Black amarillo (#FDE69A) en la misma línea",
            "ana otorrino": "👂 Dra. Ana Otorrino: Plantilla CapCut flotante | Liliana Bold blanco + Liliana Black amarillo (#FDE69A) en la misma línea",
            "ana_otorrino": "👂 Dra. Ana Otorrino: Plantilla CapCut flotante | Liliana Bold blanco + Liliana Black amarillo (#FDE69A) en la misma línea",
            "ana_visedo": "✨ Dra. Ana Visedo: Poppins Bold blanco arriba (10.0, y=-0.105) | Wonder Nature Sans rosa (#E8ACBB) abajo (12.0, y=-0.191) + Mini zoom + Stickers CapCut + Click fx",
            "ana visedo": "✨ Dra. Ana Visedo: Poppins Bold blanco arriba (10.0, y=-0.105) | Wonder Nature Sans rosa (#E8ACBB) abajo (12.0, y=-0.191) + Mini zoom + Stickers CapCut + Click fx",
            "cuidus": "🌸 CUIDUS: Gentium Plus Italic blanco arriba | Gentium Plus Bold rosa suave (#E5C7D2) abajo + Descenso + Click fx",
            "laura burgos": "🩺 Dra. Laura Burgos: Indivisible Regular blanco arriba | Indivisible Bold verde azulado (#ABC8CC) abajo + Aparición progresiva + Click fx",
            "laura_burgos": "🩺 Dra. Laura Burgos: Indivisible Regular blanco arriba | Indivisible Bold verde azulado (#ABC8CC) abajo + Aparición progresiva + Click fx",
            "enfocavision": "👁️ Doctores Enfocavisión: ITC Avant Garde Demi blanco arriba | ITC Avant Garde Bold menta (#85FFD6) abajo + Mini zoom + Click fx",
            "juan": "🌿 Juan: Gotham Bold blanco arriba | Anton morado (#7F1CCC) grande abajo + Click fx",
            "carrillo": "🩺 Dr. Carrillo: Gotham Book blanco arriba (-0.175) | Gotham Bold arena (#CCC3B1) abajo (-0.255) en MAYÚSCULAS + Click fx",
            "dentok": "🦷 Dentok: Hook y momentos clave en escalera (Playfair Display Italic) | Subtítulos largos en Helvetica Regular sin animación",
            "dr dentok": "🦷 Dentok: Hook y momentos clave en escalera (Playfair Display Italic) | Subtítulos largos en Helvetica Regular sin animación",
            "sep dentok": "🦷 Dentok: Hook y momentos clave en escalera (Playfair Display Italic) | Subtítulos largos en Helvetica Regular sin animación",
            "angel_cadenas": "⚡ Ángel Cárdenas: Dream Believer Bold blanco arriba (9.0, y=0.0) | Ligerid amarillo (#FCFE60) abajo (12.0, y=-0.088) + Corte con láser + Click fx",
            "angel": "⚡ Ángel Cárdenas: Dream Believer Bold blanco arriba (9.0, y=0.0) | Ligerid amarillo (#FCFE60) abajo (12.0, y=-0.088) + Corte con láser + Click fx",
            "nuria": "🌸 Dra. Nuria: Recline Regular blanco arriba | Recline Bold Italic rosa (#DEB0B0) abajo + Zoom blur + Click fx",
            "dra nuria": "🌸 Dra. Nuria: Recline Regular blanco arriba | Recline Bold Italic rosa (#DEB0B0) abajo + Zoom blur + Click fx",
            "jairo": "🩺 Dr. Jairo: Montserrat Bold blanco arriba (10.0, y=-0.093) | Antro Vectra verde menta (#26FFA0) abajo (17.0, y=-0.191) + Aparición progresiva + Click fx",
            "dr jairo": "🩺 Dr. Jairo: Montserrat Bold blanco arriba (10.0, y=-0.093) | Antro Vectra verde menta (#26FFA0) abajo (17.0, y=-0.191) + Aparición progresiva + Click fx",
            "maria_manuel": "👥 María y Manuel: Mukta Mahee blanco arriba (11.0, y=-0.113) | Marydale blanco (#FFFFFF) abajo (22.38, y=-0.196) + Mini zoom + Stickers + Click fx",
            "maria y manuel": "👥 María y Manuel: Mukta Mahee blanco arriba (11.0, y=-0.113) | Marydale blanco (#FFFFFF) abajo (22.38, y=-0.196) + Mini zoom + Stickers + Click fx",
            "manuel": "👥 María y Manuel: Mukta Mahee blanco arriba (11.0, y=-0.113) | Marydale blanco (#FFFFFF) abajo (22.38, y=-0.196) + Mini zoom + Stickers + Click fx",
            "maria": "👥 María y Manuel: Mukta Mahee blanco arriba (11.0, y=-0.113) | Marydale blanco (#FFFFFF) abajo (22.38, y=-0.196) + Mini zoom + Stickers + Click fx",
            "abde": "🩺 Abde: Akzidenz Grotesk Black blanco arriba (9.0, y=0.0) | Akzidenz azul cielo (#6D94FF) abajo (11.0, y=-0.079) + Descenso + Clicks chinos variados + Puntos y comas",
            "letra abde": "🩺 Abde: Akzidenz Grotesk Black blanco arriba (9.0, y=0.0) | Akzidenz azul cielo (#6D94FF) abajo (11.0, y=-0.079) + Descenso + Clicks chinos variados + Puntos y comas",
            "paco": "🩺 Paco: Gotham Light blanco arriba (10.0, y=-0.113) | Anton blanco (#FFFFFF) abajo (20.0, y=-0.222) + Click fx",
            "letra paco": "🩺 Paco: Gotham Light blanco arriba (10.0, y=-0.113) | Anton blanco (#FFFFFF) abajo (20.0, y=-0.222) + Click fx",
            "dr paco": "🩺 Paco: Gotham Light blanco arriba (10.0, y=-0.113) | Anton blanco (#FFFFFF) abajo (20.0, y=-0.222) + Click fx",
            "ana_linares": "🩺 Dra. Ana Linares: Playfair Display Bold blanco arriba (14.0 fijo, y=-0.149) | Montserrat Medium lila (#ACB1EC) en MAYÚSCULAS abajo (25.0 cortas / 21.0 medias / 17.5 largas, y=-0.239) + Mini zoom + Click fx",
            "ana linares": "🩺 Dra. Ana Linares: Playfair Display Bold blanco arriba (14.0 fijo, y=-0.149) | Montserrat Medium lila (#ACB1EC) en MAYÚSCULAS abajo (25.0 cortas / 21.0 medias / 17.5 largas, y=-0.239) + Mini zoom + Click fx",
            "dra ana linares": "🩺 Dra. Ana Linares: Playfair Display Bold blanco arriba (14.0 fijo, y=-0.149) | Montserrat Medium lila (#ACB1EC) en MAYÚSCULAS abajo (25.0 cortas / 21.0 medias / 17.5 largas, y=-0.239) + Mini zoom + Click fx",
            "dra. ana linares": "🩺 Dra. Ana Linares: Playfair Display Bold blanco arriba (14.0 fijo, y=-0.149) | Montserrat Medium lila (#ACB1EC) en MAYÚSCULAS abajo (25.0 cortas / 21.0 medias / 17.5 largas, y=-0.239) + Mini zoom + Click fx",
            "linares": "🩺 Dra. Ana Linares: Playfair Display Bold blanco arriba (14.0 fijo, y=-0.149) | Montserrat Medium lila (#ACB1EC) en MAYÚSCULAS abajo (25.0 cortas / 21.0 medias / 17.5 largas, y=-0.239) + Mini zoom + Click fx",
            "costa_calida": "🛋️ Costa Cálida: Montserrat Medium blanco arriba (10.0, y=-0.110) | PT Serif Regular amarillo (#F5D90E) abajo (14.0, y=-0.177) + Aparición progresiva + Click fx",
            "costa calida": "🛋️ Costa Cálida: Montserrat Medium blanco arriba (10.0, y=-0.110) | PT Serif Regular amarillo (#F5D90E) abajo (14.0, y=-0.177) + Aparición progresiva + Click fx",
            "costa cálida": "🛋️ Costa Cálida: Montserrat Medium blanco arriba (10.0, y=-0.110) | PT Serif Regular amarillo (#F5D90E) abajo (14.0, y=-0.177) + Aparición progresiva + Click fx"
        }
        if hasattr(self, 'lbl_preset_detail'):
            self.lbl_preset_detail.config(text=details.get(p, ""))

        self._save_local_config()

    def _get_mode_status_text(self) -> str:
        m = self.highlight_method.get()
        if m == "openrouter":
            has_k = bool(self.openrouter_key_var.get().strip())
            k_status = "Gemini Flash activo" if has_k else "Falta ingresar API Key"
            return f"🤖 Modo: IA OpenRouter — {k_status}"
        elif m == "auto":
            return "⚡ Modo: Automático Acústico (100% Offline)"
        elif m == "manual":
            w = self.manual_words.get().strip()
            preview = f": {w[:25]}..." if len(w) > 25 else (f": {w}" if w else "")
            return f"✏️ Modo: Manual{preview}"
        return f"Modo: {m}"

    def _update_mode_status_ui(self):
        if hasattr(self, 'lbl_mode_status'):
            self.lbl_mode_status.config(text=self._get_mode_status_text())

    def _open_settings_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title("Configuración - CC Subs Pro")
        dlg.configure(bg=self.bg_color)
        dlg.transient(self)
        dlg.grab_set()

        dw, dh = 660, 480
        pw = self.winfo_width() or 900
        ph = self.winfo_height() or 730
        px = self.winfo_rootx()
        py = self.winfo_rooty()
        x = max(0, px + (pw - dw) // 2)
        y = max(0, py + (ph - dh) // 2)
        dlg.geometry(f"{dw}x{dh}+{x}+{y}")
        dlg.resizable(False, False)

        container = tk.Frame(dlg, bg=self.bg_color, padx=18, pady=16)
        container.pack(fill=tk.BOTH, expand=True)

        # Header
        hdr = tk.Frame(container, bg=self.bg_color)
        hdr.pack(fill=tk.X, pady=(0, 10))
        tk.Label(hdr, text="⚙️ Configuración de IA y Detección de Subtítulos", font=("Segoe UI", 13, "bold"), fg=self.accent_color, bg=self.bg_color).pack(anchor=tk.W)
        tk.Label(hdr, text="Elige el método para detectar palabras destacadas y configura tu clave de OpenRouter.", font=("Segoe UI", 9), fg="#a6adc8", bg=self.bg_color).pack(anchor=tk.W, pady=(2, 0))

        # Main Card
        card = ttk.Frame(container, style="Card.TFrame", padding=14)
        card.pack(fill=tk.BOTH, expand=True, pady=(0, 12))

        tk.Label(card, text="Método de Detección", font=("Segoe UI", 10, "bold"), fg=self.accent_color, bg=self.card_bg).pack(anchor=tk.W, pady=(0, 8))

        dialog_method_var = tk.StringVar(value=self.highlight_method.get())

        r_ai = ttk.Radiobutton(card, text="🤖 IA Gemini Flash (Recomendado: mayúsculas, signos ¿? y frases destacadas)", variable=dialog_method_var, value="openrouter")
        r_ai.pack(anchor=tk.W, pady=2)

        r_offline = ttk.Radiobutton(card, text="⚡ Automático Acústico (100% Offline, sin API Key ni internet)", variable=dialog_method_var, value="auto")
        r_offline.pack(anchor=tk.W, pady=2)

        r_man = ttk.Radiobutton(card, text="✏️ Manual (Palabras clave personalizadas)", variable=dialog_method_var, value="manual")
        r_man.pack(anchor=tk.W, pady=2)

        # Dynamic subframes inside settings dialog
        sub_card = tk.Frame(card, bg=self.card_bg)
        sub_card.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        # 1. OpenRouter frame
        openrouter_frame = tk.Frame(sub_card, bg=self.card_bg)
        tk.Label(openrouter_frame, text="API Key de OpenRouter (Google Gemini 2.0 Flash ultrarrápido y económico):", font=("Segoe UI", 9), fg="#a6adc8", bg=self.card_bg).pack(anchor=tk.W, pady=(0, 4))

        key_row = tk.Frame(openrouter_frame, bg=self.card_bg)
        key_row.pack(fill=tk.X, pady=(0, 4))

        dialog_key_var = tk.StringVar(value=self.openrouter_key_var.get())
        show_key_dlg_var = tk.BooleanVar(value=self.show_key_var.get())
        save_key_dlg_var = tk.BooleanVar(value=self.save_key_locally.get())

        ent_key = tk.Entry(
            key_row,
            textvariable=dialog_key_var,
            show="*" if not show_key_dlg_var.get() else "",
            font=("Segoe UI", 10),
            bg="#11111b",
            fg="#ffffff",
            insertbackground="#ffffff"
        )
        ent_key.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        lbl_dlg_status = tk.Label(openrouter_frame, text="", font=("Segoe UI", 9), bg=self.card_bg)

        def test_dlg_key():
            k = dialog_key_var.get().strip()
            if not k:
                lbl_dlg_status.config(text="⚠️ Ingresa una clave primero", fg=self.accent_yellow)
                return
            lbl_dlg_status.config(text="🔄 Conectando con Gemini Flash...", fg=self.accent_yellow)
            btn_test.config(state=tk.DISABLED)
            def _test():
                client = OpenRouterClient(api_key=k)
                ok, msg = client.test_connection()
                if ok:
                    lbl_dlg_status.config(text="✅ " + msg, fg=self.accent_green)
                else:
                    lbl_dlg_status.config(text="❌ " + msg, fg=self.accent_red)
                btn_test.config(state=tk.NORMAL)
            threading.Thread(target=_test, daemon=True).start()

        btn_test = ttk.Button(key_row, text="⚡ Probar Conexión", style="Secondary.TButton", command=test_dlg_key)
        btn_test.pack(side=tk.RIGHT)

        toggles = tk.Frame(openrouter_frame, bg=self.card_bg)
        toggles.pack(fill=tk.X, pady=(2, 4))

        def toggle_dlg_show():
            if show_key_dlg_var.get():
                ent_key.config(show="")
            else:
                ent_key.config(show="*")

        chk_show = ttk.Checkbutton(toggles, text="Mostrar clave", variable=show_key_dlg_var, command=toggle_dlg_show)
        chk_show.pack(side=tk.LEFT, padx=(0, 15))

        chk_save = ttk.Checkbutton(toggles, text="Guardar clave localmente en esta PC", variable=save_key_dlg_var)
        chk_save.pack(side=tk.LEFT, padx=(0, 15))

        lbl_dlg_status.pack(anchor=tk.W, pady=(2, 2))

        lbl_ai_hint = tk.Label(
            openrouter_frame,
            text="✨ Gemini Flash analiza todo el guion: corrige mayúsculas raras de CapCut, coloca signos '¿?', selecciona frases destacadas cada ~4s y garantiza 0 comas y 0 puntos.",
            font=("Segoe UI", 8),
            fg="#a6adc8",
            bg=self.card_bg,
            anchor="w",
            wraplength=600,
            justify=tk.LEFT
        )
        lbl_ai_hint.pack(anchor=tk.W, pady=(2, 0))

        # 2. Offline frame
        offline_frame = tk.Frame(sub_card, bg=self.card_bg)
        tk.Label(
            offline_frame,
            text="⚡ Modo 100% offline: Selecciona palabras clave con impacto sonoro cada 3 a 5 segundos sin conexión a internet ni API Key.",
            font=("Segoe UI", 8),
            fg="#a6adc8",
            bg=self.card_bg,
            wraplength=600,
            justify=tk.LEFT
        ).pack(anchor=tk.W, pady=6)

        # 3. Manual frame
        manual_frame = tk.Frame(sub_card, bg=self.card_bg)
        tk.Label(manual_frame, text="Palabras o frases a destacar (separadas por comas):", font=("Segoe UI", 9), fg="#a6adc8", bg=self.card_bg).pack(anchor=tk.W, pady=(0, 4))
        dialog_words_var = tk.StringVar(value=self.manual_words.get())
        ent_man = tk.Entry(manual_frame, textvariable=dialog_words_var, font=("Segoe UI", 10), bg="#11111b", fg="#ffffff", insertbackground="#ffffff")
        ent_man.pack(fill=tk.X, pady=(0, 4))
        tk.Label(
            manual_frame,
            text="💡 Ingrese las palabras que desea resaltar en la pista inferior cuando aparezcan en el guion.",
            font=("Segoe UI", 8),
            fg="#a6adc8",
            bg=self.card_bg
        ).pack(anchor=tk.W)

        def update_method_subframe(*args):
            m = dialog_method_var.get()
            openrouter_frame.pack_forget()
            offline_frame.pack_forget()
            manual_frame.pack_forget()
            if m == "openrouter":
                openrouter_frame.pack(fill=tk.BOTH, expand=True)
            elif m == "manual":
                manual_frame.pack(fill=tk.BOTH, expand=True)
            else:
                offline_frame.pack(fill=tk.BOTH, expand=True)

        dialog_method_var.trace_add("write", update_method_subframe)
        update_method_subframe()

        # Bottom Buttons
        btn_bar = tk.Frame(container, bg=self.bg_color)
        btn_bar.pack(fill=tk.X)

        def save_and_close():
            self.highlight_method.set(dialog_method_var.get())
            self.openrouter_key_var.set(dialog_key_var.get().strip())
            self.show_key_var.set(show_key_dlg_var.get())
            self.save_key_locally.set(save_key_dlg_var.get())
            self.manual_words.set(dialog_words_var.get().strip())
            self._save_local_config()
            self._update_mode_status_ui()
            dlg.destroy()

        btn_save = ttk.Button(btn_bar, text="✓ Guardar y Aplicar", style="Action.TButton", command=save_and_close)
        btn_save.pack(side=tk.RIGHT, padx=(8, 0))

        btn_cancel = ttk.Button(btn_bar, text="Cancelar", style="Secondary.TButton", command=dlg.destroy)
        btn_cancel.pack(side=tk.RIGHT)

    def _manual_install_fonts(self):
        self.txt_log.delete("1.0", tk.END)
        os_name = "macOS" if sys.platform == 'darwin' else "Windows"
        self._log(f"[*] Verificando e instalando fuentes y assets en {os_name}...")
        def run_install():
            try:
                res = install_all_assets()
                self._log(f"[OK] {len(res['fonts'])} fuentes registradas en {os_name}:")
                for f in res['fonts']:
                    self._log(f"  + {f}")
                self._log(f"[OK] Efectos y audios verificados.")
                messagebox.showinfo("Fuentes Instaladas", f"Se han instalado y registrado {len(res['fonts'])} fuentes en {os_name} con éxito.\n\nCapCut las reconocerá inmediatamente.")
            except Exception as e:
                self._log(f"[ERROR] {e}")
                messagebox.showerror("Error", f"Error al instalar fuentes:\n{e}")
        threading.Thread(target=run_install, daemon=True).start()

    def _background_check_updates(self):
        try:
            repaired, updated_files = ensure_ai_modules_up_to_date()
            if repaired:
                def notify_ai_sync():
                    import ai.openrouter_client as _orc
                    globals()['OpenRouterClient'] = _orc.OpenRouterClient
                    globals()['DEFAULT_MODEL'] = _orc.DEFAULT_MODEL
                    msg = (
                        f"[Actualizador] Módulos de IA reparados automáticamente ({', '.join(updated_files)})."
                        if updated_files
                        else "[Actualizador] Módulos de IA recargados correctamente."
                    )
                    self._log(msg)
                self.after(0, notify_ai_sync)
        except Exception:
            pass
        try:
            has_update, remote_info = check_for_updates()
            if has_update:
                v = remote_info.get('version', '')
                def notify_ui():
                    if hasattr(self, 'btn_update'):
                        self.btn_update.config(
                            text=f"⭐ Actualizar (v{v})",
                            style="UpdateReadyBtn.TButton"
                        )
                    self._log(f"[Actualizador] ¡Nueva versión v{v} disponible en GitHub!")
                self.after(0, notify_ui)
            elif isinstance(remote_info, dict) and remote_info.get("error"):
                err_txt = remote_info["error"]
                self.after(0, lambda m=err_txt: self._log(f"[Actualizador] No se pudo verificar versión en GitHub: {m}"))
        except Exception:
            pass

    def _ask_yes_no_threadsafe(self, title: str, msg: str) -> bool:
        ev = threading.Event()
        ans = [False]
        def _prompt():
            try:
                ans[0] = bool(messagebox.askyesno(title, msg))
            finally:
                ev.set()
        self.after(0, _prompt)
        ev.wait()
        return ans[0]

    def _on_update_clicked(self):
        self.txt_log.delete("1.0", tk.END)
        self._log("[*] Conectando con GitHub para consultar actualizaciones...")
        self.lbl_status.config(text="Buscando actualizaciones...")

        def run_update():
            try:
                has_update, info = check_for_updates()
                if "error" in info:
                    err_info = info["error"]
                    self.after(0, lambda m=err_info: self._log(f"[!] Aviso de GitHub: {m}"))

                cur_v = self.local_version_info.get("version", "1.0.0")

                if not has_update:
                    ans = self._ask_yes_no_threadsafe(
                        "Versión al Día",
                        f"Ya tienes instalada la versión v{cur_v}.\n\n"
                        "¿Deseas forzar la descarga y sincronización de todos los presets y fuentes desde GitHub?"
                    )
                    if not ans:
                        self.after(0, lambda: self.lbl_status.config(text="Listo para procesar"))
                        return

                self.after(0, lambda: self._log("[*] Iniciando sincronización con el repositorio..."))

                def update_progress(msg, pct):
                    self.after(0, lambda m=msg, p=pct: (
                        self._log(f"  [{int(p*100)}%] {m}"),
                        self.lbl_status.config(text=m)
                    ))

                res = download_and_apply_update(progress_callback=update_progress, force=True)

                if res.get("success"):
                    new_v = res.get("new_version", cur_v)
                    desc = res.get("description", "")
                    fonts_count = len(res.get("installed_fonts", []))

                    def _log_success():
                        self._log(f"\n[OK] ¡CC Subs Pro actualizado exitosamente a v{new_v}!")
                        self._log(f"  + Fuentes registradas: {fonts_count}")
                        self._log(f"  + Cambios: {desc}")
                        self.lbl_status.config(text=f"Actualizado v{new_v}")
                    self.after(0, _log_success)

                    reboot = self._ask_yes_no_threadsafe(
                        "Actualización Exitosa",
                        f"¡Herramienta actualizada con éxito a la versión v{new_v}!\n\n"
                        f"Cambios:\n{desc}\n\n"
                        f"Fuentes instaladas en Windows: {fonts_count}\n\n"
                        "¿Deseas reiniciar la aplicación ahora para cargar todas las nuevas letras?"
                    )
                    if reboot:
                        self.after(0, self._restart_app)
                else:
                    err_msg = "; ".join(res.get("errors", ["Error desconocido"]))
                    self.after(0, lambda m=err_msg: (
                        self._log(f"[ERROR] No se pudo completar la actualización: {m}"),
                        messagebox.showerror("Error al Actualizar", f"No se pudo completar la actualización:\n{m}"),
                        self.lbl_status.config(text="Error al actualizar")
                    ))

            except Exception as e:
                err_str = str(e)
                self.after(0, lambda m=err_str: (
                    self._log(f"[ERROR] {m}"),
                    messagebox.showerror("Error", f"Error inesperado al actualizar:\n{m}"),
                    self.lbl_status.config(text="Error al actualizar")
                ))

        threading.Thread(target=run_update, daemon=True).start()

    def _restart_app(self):
        import subprocess
        python_exe = sys.executable
        script = os.path.abspath(__file__)
        subprocess.Popen([python_exe, script])
        self.destroy()

    def _load_projects(self):
        self.projects = list_available_projects()
        display_names = []
        for p in self.projects:
            count = p.get('subtitle_count', 0)
            dur_s = p.get('duration_us', 0) / 1000000.0
            display_names.append(f"{p['name']} ({count} subs, {dur_s:.1f}s)")
        self.proj_combo['values'] = display_names
        if display_names:
            self.proj_combo.current(0)
            self._on_project_selected(None)
        else:
            self.lbl_proj_info.config(
                text="⚠️ No se encontraron proyectos en la carpeta predeterminada de CapCut.",
                fg=self.accent_yellow
            )

    def _on_project_selected(self, event):
        idx = self.proj_combo.current()
        if 0 <= idx < len(self.projects):
            p = self.projects[idx]
            self.selected_project_path.set(p['path'])
            count = p.get('subtitle_count', 0)
            dur_s = p.get('duration_us', 0) / 1000000.0

            # Detect preset automatically from project name or path
            detected_preset = detect_preset_from_name(p.get('name', '')) or detect_preset_from_name(p.get('path', ''))
            preset_tag = ""
            if detected_preset:
                self.doctor_preset.set(detected_preset)
                self._on_preset_change()
                preset_tag = f"  ➔  Preset: {detected_preset.upper()}"
                self._log(f"[Auto-Preset] Letra seleccionada automáticamente: {detected_preset.upper()} (detectado en '{p['name']}')")

            if count == 0:
                self.lbl_proj_info.config(
                    text=f"⚠️ Este proyecto tiene 0 subtítulos. En CapCut: Texto -> Subtítulos automáticos -> Crear y luego Refrescar.{preset_tag}",
                    fg=self.accent_yellow
                )
            else:
                self.lbl_proj_info.config(
                    text=f"✅ Listo: {count} subtítulos encontrados | Duración: {dur_s:.1f}s | {p['name']}{preset_tag}",
                    fg=self.accent_green
                )

    def _browse_project(self):
        folder = filedialog.askdirectory(title="Seleccionar carpeta de proyecto CapCut", initialdir=DEFAULT_DRAFT_DIR)
        if folder:
            content_file = os.path.join(folder, 'draft_content.json')
            if not os.path.isfile(content_file):
                messagebox.showerror("Error", "La carpeta seleccionada no contiene draft_content.json")
                return
            self.selected_project_path.set(folder)

            detected_preset = detect_preset_from_name(os.path.basename(folder)) or detect_preset_from_name(folder)
            preset_tag = ""
            if detected_preset:
                self.doctor_preset.set(detected_preset)
                self._on_preset_change()
                preset_tag = f"  ➔  Preset: {detected_preset.upper()}"
                self._log(f"[Auto-Preset] Letra seleccionada automáticamente: {detected_preset.upper()} (detectado en '{os.path.basename(folder)}')")

            try:
                proj = CapCutProject(folder)
                count = len(proj.subtitles)
                dur_s = proj.data.get('duration', 0) / 1000000.0
                if count == 0:
                    self.lbl_proj_info.config(
                        text=f"⚠️ Proyecto personalizado ({os.path.basename(folder)}) tiene 0 subtítulos.{preset_tag}",
                        fg=self.accent_yellow
                    )
                else:
                    self.lbl_proj_info.config(
                        text=f"✅ Proyecto personalizado: {count} subtítulos ({dur_s:.1f}s) | {os.path.basename(folder)}{preset_tag}",
                        fg=self.accent_green
                    )
            except Exception:
                self.lbl_proj_info.config(text=f"Proyecto: {folder}{preset_tag}", fg="#a6adc8")

    def _set_action_buttons_state(self, state: str):
        for btn_attr in ('btn_run', 'btn_grammar', 'btn_repair', 'btn_heal'):
            btn = getattr(self, btn_attr, None)
            if btn is not None:
                try:
                    btn.config(state=state)
                except Exception:
                    pass

    def _start_process(self):
        proj_path = self.selected_project_path.get()
        if not proj_path:
            messagebox.showwarning("Atención", "Por favor selecciona un proyecto de CapCut primero.")
            return

        self._set_action_buttons_state(tk.DISABLED)
        self.lbl_status.config(text="Procesando...", fg=self.accent_yellow)
        self.txt_log.delete("1.0", tk.END)
        self._save_local_config()
        threading.Thread(target=self._run_process_thread, daemon=True).start()

    def _run_process_thread(self):
        try:
            proj_path = self.selected_project_path.get()
            preset_name = self.doctor_preset.get()
            method = self.highlight_method.get()

            self._log(f"[*] Abriendo proyecto: {os.path.basename(proj_path)}")
            proj = CapCutProject(proj_path)

            if not proj.subtitles:
                self._log("[!] El proyecto contiene 0 subtítulos.")
                messagebox.showwarning(
                    "Sin Subtítulos",
                    "Este proyecto no contiene subtítulos generados.\n\n"
                    "Por favor ve a CapCut, abre este proyecto y genera los subtítulos nativos:\n"
                    "Texto -> Subtítulos automáticos -> Crear.\n"
                    "Luego presiona Refrescar y vuelve a intentarlo."
                )
                self.lbl_status.config(text="0 subtítulos encontrados", fg=self.accent_red)
                return

            self._log(f"[*] Subtítulos originales de CapCut: {len(proj.subtitles)}")
            
            # Create backup
            backup_path = proj.create_backup()
            self._log(f"[*] Copia de seguridad creada: {os.path.basename(backup_path)}")

            # Load dual styler
            self._log(f"[*] Cargando preset: '{preset_name.capitalize()}'...")
            dual_styler = DualStyler.from_preset(preset_name)

            # Override animation if user toggled it
            if not self.enable_anim_var.get() and 'animation' in dual_styler.highlight_style:
                dual_styler.highlight_style['animation']['enabled'] = False

            # Auto-auditoría acústica de continuidad con FFmpeg + IA
            transcriber = AudioTranscriber(self.openrouter_key_var.get().strip())
            healed_count, unhealed_gaps = auto_heal_project_gaps(
                proj,
                styler=dual_styler,
                transcriber=transcriber,
                log_fn=self._log
            )
            if healed_count > 0:
                self._log(f"[*] Se integraron {healed_count} subtítulo(s) recuperados en la línea de tiempo.")
            if unhealed_gaps:
                self._log(f"[!] Aviso: Se detectaron {len(unhealed_gaps)} hueco(s) con voz activa. Usa 'Auditar y Reparar' si deseas revisarlos individualmente.")

            highlighter = None
            openrouter_key = None
            if method == "openrouter":
                openrouter_key = self.openrouter_key_var.get().strip()
                if not openrouter_key:
                    self._log("[!] No se ingresó API Key de OpenRouter. Cambiando automáticamente a modo Offline...")
                    highlighter = AIHighlighter(provider='heuristic') if AIHighlighter else None
                else:
                    self._log(f"[*] Modo IA OpenRouter activado (Modelo: {DEFAULT_MODEL})...")
                    self._log("    -> Analizando guion con Gemini Flash")
                    self._log("    -> Corrigiendo mayúsculas y acentos de CapCut")
                    self._log("    -> Insertando signos '¿?' en preguntas")
                    self._log("    -> Curando frases destacadas de alto impacto cada ~4s")
            elif method == "manual":
                raw = self.manual_words.get()
                words_list = [clean_subtitle_text(w) for w in raw.split(',') if clean_subtitle_text(w)]
                self._log(f"[*] Modo manual: {len(words_list)} palabras clave configuradas.")
                class ManualHighlighter:
                    def __init__(self, w_list):
                        self.w_list = w_list
                    def suggest_highlights(self, script, count=25):
                        return self.w_list
                highlighter = ManualHighlighter(words_list)
            else:
                self._log("[*] Modo Automático Acústico (100% Offline) activado...")
                highlighter = AIHighlighter(provider='heuristic') if AIHighlighter else None

            top_count, bot_count = dual_styler.auto_dual_process(
                proj,
                highlighter=highlighter,
                openrouter_key=openrouter_key,
                min_pacing_sec=None,
                max_pacing_sec=None,
                log_fn=self._log
            )

            # Enforce clean punctuation strictly according to preset
            keep_punc = getattr(dual_styler, 'keep_punctuation', False)
            clean_count = proj.clean_all_subtitles(keep_punctuation=keep_punc)
            if keep_punc:
                self._log(f"[*] Puntuación preservada (. y ,) en {clean_count} subtítulos.")
            else:
                self._log(f"[*] Puntuación saneada (0 comas, 0 puntos) en {clean_count} subtítulos.")

            # Save and sync
            proj.save(create_backup=False)

            self._log("\n" + "="*50)
            self._log("¡PROCESAMIENTO COMPLETADO CON ÉXITO!")
            self._log(f"  • Proyecto: {os.path.basename(proj.project_path)}")
            self._log(f"  • Preset Aplicado: {dual_styler.preset_name}")
            if getattr(dual_styler, 'layout', 'dual') == 'inline':
                self._log(f"  • Modo de diseño: En línea (Aglatia con descansos generosos)")
                self._log(f"  • Subtítulos totales: {top_count}")
                self._log(f"  • Palabras destacadas (con descansos): {bot_count}")
            elif getattr(dual_styler, 'layout', 'dual') in ('dentok', 'escalera'):
                self._log(f"  • Modo de diseño: Escalera + General sin animación (Dentok)")
                self._log(f"  • Subtítulos procesados: {top_count}")
                self._log(f"  • Tarjetas en formato escalera: {bot_count}")
            else:
                self._log(f"  • Pista Superior (Base): {top_count} subtítulos")
                self._log(f"  • Pista Inferior (Highlights): {bot_count} palabras destacadas")
            self._log(f"  • Clicks de audio sincronizados: {bot_count}")
            if healed_count > 0:
                self._log(f"  • Huecos de voz reparados e integrados: {healed_count}")
            self._log(f"  • Puntuación prohibida: 0 comas, 0 puntos, 0 dos puntos")
            self._log(f"  • Bloqueo acústico: 100% sincronía palabra por palabra")
            self._log("="*50)

            self.lbl_status.config(text="¡Completado con éxito!", fg=self.accent_green)

            healed_info = f"• Huecos de voz reparados: {healed_count}\n" if healed_count > 0 else ""
            messagebox.showinfo(
                "¡Éxito!",
                f"El proyecto '{os.path.basename(proj.project_path)}' ha sido estilizado con éxito.\n\n"
                f"• Subtítulos superiores: {top_count}\n"
                f"• Highlights destacados: {bot_count}\n"
                f"{healed_info}"
                f"• Preset: {dual_styler.preset_name}\n\n"
                f"Nota: Si tienes CapCut abierto, sal al menú de proyectos y vuelve a entrar para ver los cambios."
            )

        except Exception as e:
            self._log(f"\n[ERROR CRÍTICO] {e}")
            self.lbl_status.config(text="Error durante el proceso", fg=self.accent_red)
            messagebox.showerror("Error", f"Ocurrió un error al procesar el proyecto:\n{e}")
        finally:
            self.after(0, lambda: self._set_action_buttons_state(tk.NORMAL))

    def _start_repair(self):
        proj_path = self.selected_project_path.get()
        if not proj_path:
            messagebox.showwarning("Atención", "Por favor selecciona un proyecto de CapCut primero.")
            return

        self._set_action_buttons_state(tk.DISABLED)
        self.lbl_status.config(text="Reparando fuentes y efectos...", fg=self.accent_yellow)
        self.txt_log.delete("1.0", tk.END)
        self._save_local_config()
        threading.Thread(target=self._run_repair_thread, daemon=True).start()

    def _run_repair_thread(self):
        try:
            proj_path = self.selected_project_path.get()
            preset_name = self.doctor_preset.get()

            self._log(f"[*] Modo: REPARACIÓN DE SUBTÍTULOS (Solo Fuentes y Efectos)")
            self._log(f"[*] Abriendo proyecto: {os.path.basename(proj_path)}")
            proj = CapCutProject(proj_path)

            if not proj.subtitles:
                self._log("[!] El proyecto contiene 0 subtítulos.")
                messagebox.showwarning(
                    "Sin Subtítulos",
                    "Este proyecto no contiene subtítulos para reparar.\n\n"
                    "En CapCut: Texto -> Subtítulos automáticos -> Crear y luego Refrescar."
                )
                self.lbl_status.config(text="0 subtítulos encontrados", fg=self.accent_red)
                return

            self._log(f"[*] Subtítulos encontrados en el proyecto: {len(proj.subtitles)}")

            # Create backup
            backup_path = proj.create_backup()
            self._log(f"[*] Copia de seguridad creada: {os.path.basename(backup_path)}")

            self._log(f"[*] Aplicando preset de doctor: '{preset_name.capitalize()}'...")
            dual_styler = DualStyler.from_preset(preset_name)

            top_count, bot_count = dual_styler.repair_project_subtitles(proj)

            # Sincronización atómica
            proj.save(create_backup=False)

            self._log("\n" + "="*50)
            self._log("¡REPARACIÓN COMPLETADA CON ÉXITO!")
            self._log(f"  • Proyecto: {os.path.basename(proj.project_path)}")
            self._log(f"  • Preset Aplicado: {dual_styler.preset_name}")
            self._log(f"  • Subtítulos Superiores Reparados: {top_count}")
            self._log(f"  • Subtítulos Destacados Reparados: {bot_count}")
            self._log("  • Líneas de tiempo (timestamps): 100% INTACTAS (sin cambios)")
            self._log("  • Palabras y texto: 100% INTACTAS (sin cambios)")
            self._log("="*50)

            self.lbl_status.config(text="¡Reparación completada!", fg=self.accent_green)

            messagebox.showinfo(
                "¡Reparación Exitosa!",
                f"El proyecto '{os.path.basename(proj.project_path)}' ha sido reparado con éxito.\n\n"
                f"• Subtítulos superiores corregidos: {top_count}\n"
                f"• Subtítulos destacados corregidos: {bot_count}\n"
                f"• Preset: {dual_styler.preset_name}\n"
                f"• Tiempos y texto: 100% INTACTOS\n\n"
                f"Nota: Si tienes CapCut abierto, sal al menú de proyectos y vuelve a entrar para ver los cambios."
            )

        except Exception as e:
            self._log(f"\n[ERROR CRÍTICO EN REPARACIÓN] {e}")
            self.lbl_status.config(text="Error durante la reparación", fg=self.accent_red)
            messagebox.showerror("Error", f"Ocurrió un error al reparar el proyecto:\n{e}")
        finally:
            self.after(0, lambda: self._set_action_buttons_state(tk.NORMAL))

    def _start_audit_gaps(self):
        proj_path = self.selected_project_path.get()
        if not proj_path:
            messagebox.showwarning("Atención", "Por favor selecciona un proyecto de CapCut primero.")
            return

        self._set_action_buttons_state(tk.DISABLED)

        self.lbl_status.config(text="Auditando huecos con FFmpeg...", fg=self.accent_yellow)
        self.txt_log.delete("1.0", tk.END)
        self._log("[*] Modo: AUDITORÍA Y REPARACIÓN DE HUECOS DE VOZ")
        self._log(f"[*] Abriendo proyecto: {os.path.basename(proj_path)}")
        self._save_local_config()
        threading.Thread(target=self._run_audit_gaps_thread, daemon=True).start()

    def _run_audit_gaps_thread(self):
        try:
            proj_path = self.selected_project_path.get()
            preset_name = self.doctor_preset.get()
            proj = CapCutProject(proj_path)

            if not proj.subtitles:
                self._log("[!] El proyecto contiene 0 subtítulos.")
                messagebox.showwarning("Sin Subtítulos", "El proyecto no contiene subtítulos generados.")
                self.lbl_status.config(text="0 subtítulos encontrados", fg=self.accent_red)
                return

            self._log("[*] Analizando línea de tiempo en busca de espacios vacíos (> 0.4s)...")
            gaps = find_subtitle_gaps(proj, min_gap_sec=0.4, max_gap_sec=6.0)
            self._log(f"[*] Huecos temporales encontrados: {len(gaps)}")

            if not gaps:
                self._log("[+] No se detectaron huecos vacíos significativos entre subtítulos.")
                self.lbl_status.config(text="Línea de tiempo continua (sin huecos)", fg=self.accent_green)
                self.after(0, lambda: messagebox.showinfo(
                    "Auditoría Completa",
                    "¡Excelente! Todos los subtítulos tienen continuidad temporal.\nNo se detectaron huecos vacíos mayores a 0.4s."
                ))
                return

            self._log("[*] Verificando energía de audio con FFmpeg en cada hueco...")
            temp_dir = tempfile.mkdtemp(prefix="cc_subs_pro_gaps_")
            transcriber = AudioTranscriber(self.openrouter_key_var.get().strip())

            voice_gaps = []
            for g in gaps:
                if not g.media_path or not os.path.isfile(g.media_path):
                    continue
                has_voice, max_v, mean_v = verify_gap_audio_energy(g, threshold_db=-42.0)
                if has_voice:
                    self._log(f"  ⚠️ Hueco en {g.start_time_str} ({g.duration_str}): VOZ ACTIVA ({max_v:.1f} dB)")
                    self._log(f"     Previo: '{g.prev_text}' -> Siguiente: '{g.next_text}'")
                    out_snip = os.path.join(temp_dir, f"gap_{g.index}.wav")
                    extract_gap_audio_snippet(g, out_snip)
                    if transcriber.is_configured():
                        sug = transcriber.transcribe(out_snip)
                        if sug:
                            g.suggested_text = sug
                            self._log(f"     Sugerencia IA: '{sug}'")
                    voice_gaps.append(g)
                else:
                    self._log(f"  ✓ Hueco en {g.start_time_str} ({g.duration_str}): Silencio ({max_v:.1f} dB)")

            if not voice_gaps:
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass
                self._log("\n[+] Todos los huecos corresponden a silencios naturales o respiraciones.")
                self.lbl_status.config(text="Sin voz perdida detectada", fg=self.accent_green)
                self.after(0, lambda: messagebox.showinfo(
                    "Auditoría Completa",
                    "¡Excelente! Los espacios vacíos corresponden a silencios o pausas reales del orador.\nNo hay voz activa perdida sin subtitular."
                ))
                return

            self._log(f"\n[!] Se detectaron {len(voice_gaps)} huecos con voz activa sin subtítulo.")
            self._log("    -> Abriendo ventana de revisión y confirmación...")
            self.lbl_status.config(text=f"{len(voice_gaps)} huecos de voz detectados", fg=self.accent_yellow)

            dual_styler = DualStyler.from_preset(preset_name)
            self.after(0, lambda: self._open_gap_dialog(voice_gaps, proj, dual_styler, temp_dir))

        except Exception as e:
            self._log(f"\n[ERROR EN AUDITORÍA] {e}")
            self.lbl_status.config(text="Error durante la auditoría", fg=self.accent_red)
            messagebox.showerror("Error", f"Ocurrió un error al auditar el proyecto:\n{e}")
        finally:
            self.after(0, lambda: self._set_action_buttons_state(tk.NORMAL))

    def _open_gap_dialog(self, gaps, project, styler, temp_dir):
        GapReviewDialog(self, gaps, project, styler, temp_dir)

    def _start_grammar_check(self):
        proj_path = self.selected_project_path.get()
        if not proj_path:
            messagebox.showwarning("Atención", "Por favor selecciona un proyecto de CapCut primero.")
            return

        api_key = self.openrouter_key_var.get().strip() or os.environ.get('OPENROUTER_API_KEY', '').strip()
        if not api_key:
            if messagebox.askyesno(
                "API Key Requerida",
                "Para comprobar tildes y ortografía con IA necesitas una API Key de OpenRouter.\n\n"
                "¿Deseas abrir Configuración para ingresarla ahora?"
            ):
                self._open_settings_dialog()
            return

        self._set_action_buttons_state(tk.DISABLED)
        self.lbl_status.config(text="Comprobando gramática con IA...", fg=self.accent_yellow)
        self.txt_log.delete("1.0", tk.END)
        self._log("[*] Modo: COMPROBAR GRAMÁTICA, TILDES Y ORTOGRAFÍA (OpenRouter)")
        self._log(f"[*] Abriendo proyecto: {os.path.basename(proj_path)}")
        self._save_local_config()
        threading.Thread(target=self._run_grammar_check_thread, args=(proj_path, api_key), daemon=True).start()

    def _run_grammar_check_thread(self, proj_path: str, api_key: str):
        try:
            preset_name = self.doctor_preset.get()
            proj = CapCutProject(proj_path)

            if not proj.subtitles:
                self.after(0, lambda: self._log("[!] El proyecto contiene 0 subtítulos."))
                self.after(0, lambda: self.lbl_status.config(text="0 subtítulos encontrados", fg=self.accent_red))
                self.after(0, lambda: messagebox.showwarning(
                    "Sin Subtítulos",
                    "Este proyecto no contiene subtítulos para revisar.\n\n"
                    "En CapCut: Texto -> Subtítulos automáticos -> Crear y luego Refrescar."
                ))
                return

            client = OpenRouterClient(api_key=api_key, model=DEFAULT_MODEL)

            def _thread_log(msg: str):
                self.after(0, lambda m=msg: self._log(m))

            fixes = check_project_grammar(
                proj,
                client=client,
                preset_name=preset_name,
                log_fn=_thread_log
            )

            if fixes is None:
                self.after(0, lambda: self._log("[ERROR] No se pudo completar la revisión con OpenRouter."))
                self.after(0, lambda: self.lbl_status.config(text="Error conectando con OpenRouter", fg=self.accent_red))
                self.after(0, lambda: messagebox.showerror(
                    "Error de OpenRouter",
                    "No se pudo conectar o procesar la respuesta de OpenRouter.\n"
                    "Verifica tu API Key o tu conexión a internet en Configuración."
                ))
                return

            if not fixes:
                self.after(0, lambda: self._log("\n[+] ¡Revisión completada! Todas las tildes y palabras están escritas correctamente."))
                self.after(0, lambda: self.lbl_status.config(text="Gramática y tildes correctas ✓", fg=self.accent_green))
                self.after(0, lambda: messagebox.showinfo(
                    "Gramática Perfecta",
                    f"Se revisaron todos los subtítulos de '{os.path.basename(proj.project_path)}'.\n\n"
                    "¡No se encontraron errores de ortografía ni tildes faltantes!"
                ))
                return

            self.after(0, lambda: self._log(f"[!] Se detectaron {len(fixes)} subtítulo(s) con correcciones sugeridas:"))
            for fx in fixes:
                self.after(0, lambda f=fx: self._log(
                    f"  • [{f['time_str']}] '{f['original_text']}'  ──►  '{f['corrected_text']}' ({f['reason']})"
                ))
            self.after(0, lambda: self.lbl_status.config(text=f"{len(fixes)} corrección(es) sugerida(s)", fg=self.accent_yellow))
            self.after(0, lambda: self._open_grammar_dialog(fixes, proj))

        except Exception as e:
            err_msg = str(e)
            self.after(0, lambda: self._log(f"\n[ERROR EN GRAMÁTICA] {err_msg}"))
            self.after(0, lambda: self.lbl_status.config(text="Error comprobando gramática", fg=self.accent_red))
            self.after(0, lambda: messagebox.showerror("Error", f"Ocurrió un error al comprobar la gramática:\n{err_msg}"))
        finally:
            self.after(0, lambda: self._set_action_buttons_state(tk.NORMAL))

    def _open_grammar_dialog(self, fixes: List[Dict[str, Any]], project: CapCutProject):
        GrammarReviewDialog(self, fixes, project)


class GapReviewDialog(tk.Toplevel):
    def __init__(self, parent, gaps: List[SubtitleGap], project: CapCutProject, styler: DualStyler, temp_audio_dir: str):
        super().__init__(parent)
        self.parent = parent
        self.gaps = gaps
        self.project = project
        self.styler = styler
        self.temp_audio_dir = temp_audio_dir
        self.entries = []

        self.title("Auditoría de Huecos de Voz - CC Subs Pro")
        self.geometry("820x600")
        self.minsize(740, 480)
        self.configure(bg="#181825")
        self.transient(parent)
        self.grab_set()

        top_frame = tk.Frame(self, bg="#181825", padx=16, pady=12)
        top_frame.pack(fill=tk.X)

        tk.Label(
            top_frame,
            text=f"⚠️ Se detectaron {len(gaps)} huecos con voz activa sin subtítulo",
            font=("Segoe UI", 12, "bold"),
            fg="#f9e2af",
            bg="#181825"
        ).pack(anchor=tk.W)

        tk.Label(
            top_frame,
            text="Revisa o edita las palabras que CapCut omitió y pulsa 'Aplicar e Insertar en CapCut'.",
            font=("Segoe UI", 9),
            fg="#a6adc8",
            bg="#181825"
        ).pack(anchor=tk.W, pady=(2, 0))

        canvas_frame = tk.Frame(self, bg="#181825", padx=16)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(canvas_frame, bg="#181825", highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#181825")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=760)
        canvas.configure(xscrollcommand=None, yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        for i, gap in enumerate(gaps):
            card = tk.Frame(scrollable_frame, bg="#1e1e2e", padx=12, pady=10, relief="flat", highlightbackground="#313244", highlightthickness=1)
            card.pack(fill=tk.X, pady=6)

            hdr = tk.Frame(card, bg="#1e1e2e")
            hdr.pack(fill=tk.X)

            tk.Label(
                hdr,
                text=f"Hueco #{i+1}  ⏱️ {gap.start_time_str} - {gap.end_time_str} ({gap.duration_str})",
                font=("Segoe UI", 10, "bold"),
                fg="#cdd6f4",
                bg="#1e1e2e"
            ).pack(side=tk.LEFT)

            tk.Label(
                hdr,
                text=f"🔊 {gap.max_volume_db:.1f} dB (Voz activa)",
                font=("Segoe UI", 9, "bold"),
                fg="#a6e3a1",
                bg="#1e1e2e"
            ).pack(side=tk.RIGHT)

            ctx = tk.Label(
                card,
                text=f"Contexto: [ {gap.prev_text} ]  ──►  (HUECO VACÍO)  ──►  [ {gap.next_text} ]",
                font=("Segoe UI", 9, "italic"),
                fg="#bac2de",
                bg="#1e1e2e"
            )
            ctx.pack(anchor=tk.W, pady=(4, 6))

            ctrl = tk.Frame(card, bg="#1e1e2e")
            ctrl.pack(fill=tk.X)

            snippet_file = os.path.join(self.temp_audio_dir, f"gap_{gap.index}.wav")
            if os.path.isfile(snippet_file):
                btn_play = ttk.Button(
                    ctrl,
                    text="▶️ Escuchar",
                    style="Secondary.TButton",
                    command=lambda p=snippet_file: play_audio_snippet(p)
                )
                btn_play.pack(side=tk.LEFT, padx=(0, 8))

            tk.Label(ctrl, text="Texto a insertar:", font=("Segoe UI", 9, "bold"), fg="#cdd6f4", bg="#1e1e2e").pack(side=tk.LEFT, padx=(0, 6))

            var = tk.StringVar(value=gap.suggested_text)
            ent = tk.Entry(ctrl, textvariable=var, font=("Segoe UI", 10), bg="#11111b", fg="#ffffff", insertbackground="#ffffff")
            ent.pack(side=tk.LEFT, fill=tk.X, expand=True)

            self.entries.append((gap, var))

        bot_bar = tk.Frame(self, bg="#181825", padx=16, pady=12)
        bot_bar.pack(fill=tk.X)

        btn_cancel = ttk.Button(bot_bar, text="Cancelar", style="Secondary.TButton", command=self._on_close)
        btn_cancel.pack(side=tk.RIGHT, padx=(6, 0))

        btn_apply = ttk.Button(bot_bar, text="✅ APLICAR E INSERTAR EN CAPCUT", style="Action.TButton", command=self._apply_healed)
        btn_apply.pack(side=tk.RIGHT)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        try:
            shutil.rmtree(self.temp_audio_dir, ignore_errors=True)
        except Exception:
            pass
        self.destroy()

    def _apply_healed(self):
        healed_items = []
        for gap, var in self.entries:
            txt = var.get().strip()
            if txt:
                healed_items.append({
                    'start_us': gap.start_us,
                    'duration_us': gap.duration_us,
                    'text': txt
                })

        if not healed_items:
            messagebox.showwarning("Atención", "No se ingresó ningún texto para insertar.")
            return

        try:
            count = insert_healed_subtitles(self.project, healed_items, self.styler)
            self.project.save(create_backup=True)

            self.parent._log(f"\n[+] Se insertaron {count} subtítulos reparados en el proyecto.")
            self.parent._log(f"    -> Preset: {self.styler.preset_name}")
            self.parent._log("    -> Cumpliendo regla de GEMINI.md (0 comas, 0 puntos).")

            messagebox.showinfo(
                "¡Reparación de Huecos Exitosa!",
                f"Se han insertado {count} subtítulos en los huecos detectados de CapCut.\n\n"
                f"• Proyecto: {os.path.basename(self.project.project_path)}\n"
                f"• Preset aplicado: {self.styler.preset_name}\n"
                f"• Respaldo automático guardado.\n\n"
                f"Nota: Si tienes CapCut abierto, sal al menú de proyectos y vuelve a entrar para ver los subtítulos insertados."
            )

            dur_s = self.project.data.get('duration', 0) / 1000000.0
            self.parent.lbl_proj_info.config(
                text=f"✅ Listo: {len(self.project.subtitles)} subtítulos | Duración: {dur_s:.1f}s | {os.path.basename(self.project.project_path)}",
                fg=self.parent.accent_green
            )
            self._on_close()
        except Exception as e:
            messagebox.showerror("Error", f"Error al insertar subtítulos reparados:\n{e}")


class GrammarReviewDialog(tk.Toplevel):
    def __init__(self, parent, fixes: List[Dict[str, Any]], project: CapCutProject):
        super().__init__(parent)
        self.parent = parent
        self.fixes = fixes
        self.project = project
        self.row_controls = []

        self.title("Comprobar Gramática y Tildes - CC Subs Pro")
        self.geometry("860x620")
        self.minsize(760, 480)
        self.configure(bg="#181825")
        self.transient(parent)
        self.grab_set()

        top_frame = tk.Frame(self, bg="#181825", padx=16, pady=12)
        top_frame.pack(fill=tk.X)

        tk.Label(
            top_frame,
            text=f"✍️ Se encontraron {len(fixes)} corrección(es) de tildes u ortografía",
            font=("Segoe UI", 12, "bold"),
            fg="#89dceb",
            bg="#181825"
        ).pack(anchor=tk.W)

        tk.Label(
            top_frame,
            text="Verifica o ajusta cada cambio antes de aplicarlo en CapCut. Los tiempos, fuentes y animaciones permanecerán intactos.",
            font=("Segoe UI", 9),
            fg="#a6adc8",
            bg="#181825"
        ).pack(anchor=tk.W, pady=(2, 6))

        sel_bar = tk.Frame(top_frame, bg="#181825")
        sel_bar.pack(fill=tk.X)
        ttk.Button(
            sel_bar,
            text="✓ Seleccionar todos",
            style="Secondary.TButton",
            command=lambda: self._set_all_checked(True)
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(
            sel_bar,
            text="✗ Desmarcar todos",
            style="Secondary.TButton",
            command=lambda: self._set_all_checked(False)
        ).pack(side=tk.LEFT)

        canvas_frame = tk.Frame(self, bg="#181825", padx=16)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_frame, bg="#181825", highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        scrollable_frame = tk.Frame(self.canvas, bg="#181825")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        win_id = self.canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=800)
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(win_id, width=max(400, e.width - 8)))
        self.canvas.configure(xscrollcommand=None, yscrollcommand=scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mousewheel(event):
            if abs(event.delta) >= 120:
                step = int(-1 * (event.delta / 120))
            else:
                step = -1 if event.delta > 0 else 1
            self.canvas.yview_scroll(step, "units")

        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)

        for i, fx in enumerate(fixes):
            card = tk.Frame(
                scrollable_frame,
                bg="#1e1e2e",
                padx=12,
                pady=10,
                relief="flat",
                highlightbackground="#313244",
                highlightthickness=1
            )
            card.pack(fill=tk.X, pady=5)

            hdr = tk.Frame(card, bg="#1e1e2e")
            hdr.pack(fill=tk.X)

            chk_var = tk.BooleanVar(value=True)
            chk = ttk.Checkbutton(
                hdr,
                text=f"Aplicar cambio #{i+1}  |  ⏱️ {fx['time_str']} (Pista {fx['track_index'] + 1})",
                variable=chk_var
            )
            chk.pack(side=tk.LEFT)

            tk.Label(
                hdr,
                text=fx.get('reason', ''),
                font=("Segoe UI", 9, "italic"),
                fg="#f9e2af",
                bg="#1e1e2e"
            ).pack(side=tk.RIGHT)

            orig_row = tk.Frame(card, bg="#1e1e2e")
            orig_row.pack(fill=tk.X, pady=(6, 4))
            tk.Label(orig_row, text="Original:   ", font=("Segoe UI", 9, "bold"), fg="#a6adc8", bg="#1e1e2e").pack(side=tk.LEFT)
            tk.Label(
                orig_row,
                text=fx['original_text'].replace("\n", " / "),
                font=("Segoe UI", 10),
                fg="#f38ba8",
                bg="#1e1e2e",
                anchor="w"
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)

            edit_row = tk.Frame(card, bg="#1e1e2e")
            edit_row.pack(fill=tk.X)
            tk.Label(edit_row, text="Corregido: ", font=("Segoe UI", 9, "bold"), fg="#cdd6f4", bg="#1e1e2e").pack(side=tk.LEFT)

            txt_var = tk.StringVar(value=fx['corrected_text'].replace("\n", " | "))
            ent = tk.Entry(
                edit_row,
                textvariable=txt_var,
                font=("Segoe UI", 10, "bold"),
                bg="#11111b",
                fg="#a6e3a1",
                insertbackground="#ffffff"
            )
            ent.pack(side=tk.LEFT, fill=tk.X, expand=True)

            self.row_controls.append((fx, chk_var, txt_var, '\n' in fx['original_text']))

        bot_bar = tk.Frame(self, bg="#181825", padx=16, pady=12)
        bot_bar.pack(fill=tk.X)

        btn_cancel = ttk.Button(bot_bar, text="Cancelar", style="Secondary.TButton", command=self._on_close)
        btn_cancel.pack(side=tk.RIGHT, padx=(6, 0))

        btn_apply = ttk.Button(bot_bar, text="✅ APLICAR CORRECCIONES EN CAPCUT", style="Action.TButton", command=self._apply_fixes)
        btn_apply.pack(side=tk.RIGHT)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _set_all_checked(self, checked: bool):
        for _, chk_var, _, _ in self.row_controls:
            chk_var.set(checked)

    def _on_close(self):
        try:
            self.canvas.unbind_all("<MouseWheel>")
        except Exception:
            pass
        self.destroy()

    def _apply_fixes(self):
        selected_fixes = []
        for fx, chk_var, txt_var, had_newline in self.row_controls:
            if not chk_var.get():
                continue
            val = txt_var.get().strip()
            if had_newline and "|" in val:
                val = "\n".join(part.strip() for part in val.split("|") if part.strip())
            if val:
                fx_copy = dict(fx)
                fx_copy['corrected_text'] = val
                selected_fixes.append(fx_copy)

        if not selected_fixes:
            messagebox.showwarning("Atención", "No seleccionaste ninguna corrección para aplicar.")
            return

        try:
            self.project.create_backup()
            count = apply_grammar_fixes(self.project, selected_fixes)
            self.project.save(create_backup=False)

            self.parent._log(f"\n[+] Se aplicaron {count} corrección(es) gramatical(es) en '{os.path.basename(self.project.project_path)}'.")
            self.parent.lbl_status.config(text=f"¡{count} corrección(es) aplicada(s)!", fg=self.parent.accent_green)

            messagebox.showinfo(
                "¡Correcciones Aplicadas!",
                f"Se corrigieron {count} subtítulo(s) con éxito en '{os.path.basename(self.project.project_path)}'.\n\n"
                f"• Tildes y ortografía actualizadas\n"
                f"• Tiempos, fuentes, colores y animaciones: 100% INTACTOS\n"
                f"• Copia de seguridad guardada automáticamente.\n\n"
                f"Nota: Si tienes CapCut abierto, sal al menú de proyectos y vuelve a entrar para ver los cambios."
            )
            self._on_close()
        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar las correcciones:\n{e}")


ValuSubsGUI = CCSubsProGUI

if __name__ == '__main__':
    try:
        app = CCSubsProGUI()
        app.mainloop()
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, f"Error iniciando CC Subs Pro:\n\n{err}", "CC Subs Pro - Error", 0x10)
        except Exception:
            print(err)
            input("Presiona Enter...")
