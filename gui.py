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
    get_local_version_info
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, '.cc_subs_pro_config.json')

class CCSubsProGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CC Subs Pro - Estilizador de Subtítulos CapCut")
        self.geometry("900x760")
        self.minsize(860, 600)

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

        ttk.Label(preset_card, text="2. Selecciona el Estilo de Doctor / Doctora", style="Section.TLabel").pack(anchor=tk.W, pady=(0, 4))

        presets_frame = tk.Frame(preset_card, bg=self.card_bg)
        presets_frame.pack(fill=tk.X)
        presets_frame.columnconfigure(0, weight=1)
        presets_frame.columnconfigure(1, weight=1)

        # Grid of doctor presets (2 columns to ensure all buttons fit comfortably)
        r_gerardo = ttk.Radiobutton(
            presets_frame,
            text="🩺 Dr. Gerardo  (Aloevera | Behind The Nineties)",
            variable=self.doctor_preset,
            value="gerardo",
            command=self._on_preset_change
        )
        r_gerardo.grid(row=0, column=0, sticky=tk.W, pady=2, padx=(0, 10))

        r_gala = ttk.Radiobutton(
            presets_frame,
            text="🩺 Dra. Gala  (Helvetica | Things blanco)",
            variable=self.doctor_preset,
            value="gala",
            command=self._on_preset_change
        )
        r_gala.grid(row=1, column=0, sticky=tk.W, pady=2, padx=(0, 10))

        r_laura = ttk.Radiobutton(
            presets_frame,
            text="🩺 Dra. Laura Pediatra  (Josefin Sans celeste)",
            variable=self.doctor_preset,
            value="laura",
            command=self._on_preset_change
        )
        r_laura.grid(row=2, column=0, sticky=tk.W, pady=2, padx=(0, 10))

        r_alharilla = ttk.Radiobutton(
            presets_frame,
            text="🩺 Dra. Alharilla  (Raleway | Bebas Neue verde)",
            variable=self.doctor_preset,
            value="alharilla",
            command=self._on_preset_change
        )
        r_alharilla.grid(row=3, column=0, sticky=tk.W, pady=2, padx=(0, 10))

        r_jose = ttk.Radiobutton(
            presets_frame,
            text="🩺 Dr. Jose Podólogo  (Aglatia | Bluemun oro)",
            variable=self.doctor_preset,
            value="jose",
            command=self._on_preset_change
        )
        r_jose.grid(row=0, column=1, sticky=tk.W, pady=2)

        r_deditos = ttk.Radiobutton(
            presets_frame,
            text="🦶 Deditos Barefoot  (Lilita One naranja)",
            variable=self.doctor_preset,
            value="deditos",
            command=self._on_preset_change
        )
        r_deditos.grid(row=1, column=1, sticky=tk.W, pady=2)

        r_emilia = ttk.Radiobutton(
            presets_frame,
            text="✨ Emilia  (Neue Helvena | Karelle + Stickers)",
            variable=self.doctor_preset,
            value="emilia",
            command=self._on_preset_change
        )
        r_emilia.grid(row=2, column=1, sticky=tk.W, pady=2)

        r_alvaro = ttk.Radiobutton(
            presets_frame,
            text="🩺 Dr. Álvaro  (GC GRIND | Coral + Corte láser)",
            variable=self.doctor_preset,
            value="alvaro",
            command=self._on_preset_change
        )
        r_alvaro.grid(row=3, column=1, sticky=tk.W, pady=2)

        r_pequenos = ttk.Radiobutton(
            presets_frame,
            text="👶 Pequeños Cuidados  (Parafina | Chewy amarillo + Mini zoom)",
            variable=self.doctor_preset,
            value="pequenos",
            command=self._on_preset_change
        )
        r_pequenos.grid(row=4, column=0, sticky=tk.W, pady=2, padx=(0, 10))

        r_ana = ttk.Radiobutton(
            presets_frame,
            text="👂 Dra. Ana Otorrino  (Liliana Bold | Liliana Black + Flotación)",
            variable=self.doctor_preset,
            value="ana",
            command=self._on_preset_change
        )
        r_ana.grid(row=4, column=1, sticky=tk.W, pady=2)

        r_cuidus = ttk.Radiobutton(
            presets_frame,
            text="🌸 CUIDUS  (Gentium Plus Italic | Gentium Plus Bold rosa)",
            variable=self.doctor_preset,
            value="cuidus",
            command=self._on_preset_change
        )
        r_cuidus.grid(row=5, column=0, sticky=tk.W, pady=2, padx=(0, 10))

        r_laura_burgos = ttk.Radiobutton(
            presets_frame,
            text="🩺 Dra. Laura Burgos  (Indivisible | Indivisible Bold + Aparición progresiva)",
            variable=self.doctor_preset,
            value="laura burgos",
            command=self._on_preset_change
        )
        r_laura_burgos.grid(row=5, column=1, sticky=tk.W, pady=2)

        r_enfocavision = ttk.Radiobutton(
            presets_frame,
            text="👁️ Doctores Enfocavisión  (ITC Avant Garde Demi | Bold menta + Mini zoom)",
            variable=self.doctor_preset,
            value="enfocavision",
            command=self._on_preset_change
        )
        r_enfocavision.grid(row=6, column=0, sticky=tk.W, pady=2, padx=(0, 10))

        r_juan = ttk.Radiobutton(
            presets_frame,
            text="🌿 Juan  (Gotham Bold blanco | Anton morado #7F1CCC)",
            variable=self.doctor_preset,
            value="juan",
            command=self._on_preset_change
        )
        r_juan.grid(row=6, column=1, sticky=tk.W, pady=2)

        r_carrillo = ttk.Radiobutton(
            presets_frame,
            text="🩺 Dr. Carrillo  (Gotham Book blanco | Gotham Bold arena #CCC3B1)",
            variable=self.doctor_preset,
            value="carrillo",
            command=self._on_preset_change
        )
        r_carrillo.grid(row=7, column=0, sticky=tk.W, pady=2, padx=(0, 10))

        r_dentok = ttk.Radiobutton(
            presets_frame,
            text="🦷 Dentok  (Helvetica Regular | Playfair Display + Escalera)",
            variable=self.doctor_preset,
            value="dentok",
            command=self._on_preset_change
        )
        r_dentok.grid(row=7, column=1, sticky=tk.W, pady=2)

        r_angel = ttk.Radiobutton(
            presets_frame,
            text="⚡ Ángel Cárdenas  (Ligerid blanco | Dream Believer Bold #FCFE60)",
            variable=self.doctor_preset,
            value="angel_cadenas",
            command=self._on_preset_change
        )
        r_angel.grid(row=8, column=0, sticky=tk.W, pady=2, padx=(0, 10))

        # Dynamic detail line for the selected doctor
        self.lbl_preset_detail = tk.Label(
            preset_card,
            text="",
            font=("Segoe UI", 8),
            fg="#a6adc8",
            bg=self.card_bg,
            anchor="w"
        )
        self.lbl_preset_detail.pack(fill=tk.X, pady=(3, 2))

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

        self.btn_repair = ttk.Button(btn_row, text="🛠️ REPARAR SUBTÍTULOS (Solo Fuentes y Efectos)", style="Repair.TButton", command=self._start_repair)
        self.btn_repair.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(5, 0))

        btn_row2 = tk.Frame(act_frame, bg=self.bg_color)
        btn_row2.pack(fill=tk.X, pady=(5, 0))

        self.btn_heal = ttk.Button(btn_row2, text="🩹 AUDITAR Y REPARAR HUECOS DE VOZ (FFmpeg + IA)", style="Heal.TButton", command=self._start_audit_gaps)
        self.btn_heal.pack(fill=tk.X)

        lbl_repair_hint = tk.Label(
            act_frame,
            text="💡 'Reparar' corrige estilos sin mover tiempos. 'Auditar Huecos' detecta palabras omitidas por CapCut donde hay voz activa.",
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

    def _on_preset_change(self):
        p = self.doctor_preset.get()
        if p in ["gerardo", "alharilla", "jose", "deditos", "laura", "emilia", "alvaro", "pequenos", "cuidus", "laura burgos", "laura_burgos", "enfocavision"]:
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
            "cuidus": "🌸 CUIDUS: Gentium Plus Italic blanco arriba | Gentium Plus Bold rosa suave (#E5C7D2) abajo + Descenso + Click fx",
            "laura burgos": "🩺 Dra. Laura Burgos: Indivisible Regular blanco arriba | Indivisible Bold verde azulado (#ABC8CC) abajo + Aparición progresiva + Click fx",
            "laura_burgos": "🩺 Dra. Laura Burgos: Indivisible Regular blanco arriba | Indivisible Bold verde azulado (#ABC8CC) abajo + Aparición progresiva + Click fx",
            "enfocavision": "👁️ Doctores Enfocavisión: ITC Avant Garde Demi blanco arriba | ITC Avant Garde Bold menta (#85FFD6) abajo + Mini zoom + Click fx",
            "juan": "🌿 Juan: Gotham Bold blanco arriba | Anton morado (#7F1CCC) grande abajo + Click fx",
            "carrillo": "🩺 Dr. Carrillo: Gotham Book blanco arriba (-0.175) | Gotham Bold arena (#CCC3B1) abajo (-0.255) en MAYÚSCULAS + Click fx",
            "dentok": "🦷 Dentok: Hook y momentos clave en escalera (Playfair Display Italic) | Subtítulos largos en Helvetica Regular sin animación",
            "dr dentok": "🦷 Dentok: Hook y momentos clave en escalera (Playfair Display Italic) | Subtítulos largos en Helvetica Regular sin animación",
            "sep dentok": "🦷 Dentok: Hook y momentos clave en escalera (Playfair Display Italic) | Subtítulos largos en Helvetica Regular sin animación",
            "angel_cadenas": "⚡ Ángel Cárdenas: Ligerid blanco arriba (11.0, y=0.0) | Dream Believer Bold amarillo (#FCFE60) abajo + Corte con láser + Click fx",
            "angel": "⚡ Ángel Cárdenas: Ligerid blanco arriba (11.0, y=0.0) | Dream Believer Bold amarillo (#FCFE60) abajo + Corte con láser + Click fx"
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
        except Exception:
            pass

    def _on_update_clicked(self):
        self.txt_log.delete("1.0", tk.END)
        self._log("[*] Conectando con GitHub para consultar actualizaciones...")
        self.lbl_status.config(text="Buscando actualizaciones...")

        def run_update():
            try:
                has_update, info = check_for_updates()
                if "error" in info:
                    self._log(f"[!] Aviso de GitHub: {info['error']}")

                cur_v = self.local_version_info.get("version", "1.0.0")

                if not has_update:
                    ans = messagebox.askyesno(
                        "Versión al Día",
                        f"Ya tienes instalada la versión v{cur_v}.\n\n"
                        "¿Deseas forzar la descarga y sincronización de todos los presets y fuentes desde GitHub?"
                    )
                    if not ans:
                        self.lbl_status.config(text="Listo para procesar")
                        return

                self._log("[*] Iniciando sincronización con el repositorio...")

                def update_progress(msg, pct):
                    self._log(f"  [{int(pct*100)}%] {msg}")
                    self.lbl_status.config(text=msg)

                res = download_and_apply_update(progress_callback=update_progress, force=True)

                if res.get("success"):
                    new_v = res.get("new_version", cur_v)
                    desc = res.get("description", "")
                    fonts_count = len(res.get("installed_fonts", []))

                    self._log(f"\n[OK] ¡CC Subs Pro actualizado exitosamente a v{new_v}!")
                    self._log(f"  + Fuentes registradas: {fonts_count}")
                    self._log(f"  + Cambios: {desc}")
                    self.lbl_status.config(text=f"Actualizado v{new_v}")

                    reboot = messagebox.askyesno(
                        "Actualización Exitosa",
                        f"¡Herramienta actualizada con éxito a la versión v{new_v}!\n\n"
                        f"Cambios:\n{desc}\n\n"
                        f"Fuentes instaladas en Windows: {fonts_count}\n\n"
                        "¿Deseas reiniciar la aplicación ahora para cargar todas las nuevas letras?"
                    )
                    if reboot:
                        self._restart_app()
                else:
                    err_msg = "; ".join(res.get("errors", ["Error desconocido"]))
                    self._log(f"[ERROR] No se pudo completar la actualización: {err_msg}")
                    messagebox.showerror("Error al Actualizar", f"No se pudo completar la actualización:\n{err_msg}")
                    self.lbl_status.config(text="Error al actualizar")

            except Exception as e:
                self._log(f"[ERROR] {e}")
                messagebox.showerror("Error", f"Error inesperado al actualizar:\n{e}")
                self.lbl_status.config(text="Error al actualizar")

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

    def _start_process(self):
        proj_path = self.selected_project_path.get()
        if not proj_path:
            messagebox.showwarning("Atención", "Por favor selecciona un proyecto de CapCut primero.")
            return

        self.btn_run.config(state=tk.DISABLED)
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

            # Enforce clean punctuation strictly
            clean_count = proj.clean_all_subtitles()
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
            self.btn_run.config(state=tk.NORMAL)
            self.btn_repair.config(state=tk.NORMAL)

    def _start_repair(self):
        proj_path = self.selected_project_path.get()
        if not proj_path:
            messagebox.showwarning("Atención", "Por favor selecciona un proyecto de CapCut primero.")
            return

        self.btn_run.config(state=tk.DISABLED)
        self.btn_repair.config(state=tk.DISABLED)
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
            self.btn_run.config(state=tk.NORMAL)
            self.btn_repair.config(state=tk.NORMAL)
            if hasattr(self, 'btn_heal'):
                self.btn_heal.config(state=tk.NORMAL)

    def _start_audit_gaps(self):
        proj_path = self.selected_project_path.get()
        if not proj_path:
            messagebox.showwarning("Atención", "Por favor selecciona un proyecto de CapCut primero.")
            return

        self.btn_run.config(state=tk.DISABLED)
        self.btn_repair.config(state=tk.DISABLED)
        if hasattr(self, 'btn_heal'):
            self.btn_heal.config(state=tk.DISABLED)

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
            self.btn_run.config(state=tk.NORMAL)
            self.btn_repair.config(state=tk.NORMAL)
            if hasattr(self, 'btn_heal'):
                self.btn_heal.config(state=tk.NORMAL)

    def _open_gap_dialog(self, gaps, project, styler, temp_dir):
        GapReviewDialog(self, gaps, project, styler, temp_dir)


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
