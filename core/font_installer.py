"""
CC Subs Pro - Font & Asset Installer for Windows and macOS
Installs all doctor fonts, click sounds, animation effects and stickers
into macOS / Windows and CapCut without requiring administrator privileges.
"""

import os
import sys
import shutil
import logging
from typing import Dict, List, Any

if __name__ == '__main__' and __package__ is None:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.platform_paths import get_base_dir, get_capcut_cache_dirs

logger = logging.getLogger('CCSubsPro.Installer')

FONT_REGISTRY_MAP = {
    'AloeveraDisplay-Regular.otf': 'Aloevera Display Regular (TrueType)',
    'Behind The Nineties Medium Italic.ttf': 'Behind The Nineties Medium Italic (TrueType)',
    'Helvetica Regular.otf': 'Helvetica (TrueType)',
    'things.otf': 'Things (TrueType)',
    'JosefinSans-Regular.ttf': 'Josefin Sans (TrueType)',
    'JosefinSans-SemiBold.ttf': 'Josefin Sans SemiBold (TrueType)',
    'JosefinSans-Bold.ttf': 'Josefin Sans Bold (TrueType)',
    'Raleway-Medium.ttf': 'Raleway Medium (TrueType)',
    'BebasNeue-Regular.ttf': 'Bebas Neue (TrueType)',
    'Aglatia.ttf': 'Aglatia (TrueType)',
    'Bluemun-SemiBold.ttf': 'Bluemun SemiBold (TrueType)',
    'NeueHelvena-Semibold-Exfont7e79.otf': 'Neue Helvena Semibold (TrueType)',
    'Karelle DEMO.otf': 'Karelle DEMO (TrueType)',
    'Merriweather_36pt-MediumItalic.ttf': 'Merriweather Medium Italic (TrueType)',
    'GC GRIND.otf': 'GC GRIND Extra Bold (TrueType)',
    'Chewy-Regular.ttf': 'Chewy Regular (TrueType)',
    'Parafina Bold S.ttf': 'Parafina Bold S (TrueType)',
    'Parafina Medium S.ttf': 'Parafina Medium S (TrueType)',
    'Liliana-Bold.otf': 'Liliana Bold (TrueType)',
    'Liliana-Black.otf': 'Liliana Black (TrueType)',
    'GentiumPlus-Italic.ttf': 'Gentium Plus Italic (TrueType)',
    'GentiumPlus-Bold.ttf': 'Gentium Plus Bold (TrueType)',
    'fonnts.com-Indivisible.otf': 'Indivisible (TrueType)',
    'fonnts.com-Indivisible_Bold.otf': 'Indivisible Bold (TrueType)',
    'ITC Avant Garde Gothic Std Demi.otf': 'ITCAvantGardeStd-Demi (TrueType)',
    'ITC Avant Garde Gothic Std Bold.otf': 'ITCAvantGardeStd-Bold (TrueType)',
    'Gotham Bold.otf': 'Gotham-Bold (TrueType)',
    'Anton-Regular.ttf': 'Anton Regular (TrueType)',
}

def install_all_assets() -> Dict[str, Any]:
    """
    Installs:
    1. All doctor fonts into user fonts directory (~/Library/Fonts on Mac, %LOCALAPPDATA%\\Microsoft\\Windows\\Fonts on Win)
    2. Click sound into CapCut music cache
    3. Animation effects into CapCut effect cache
    4. Stickers into CapCut artistEffect cache
    """
    base_dir = get_base_dir()
    results = {
        'fonts': [],
        'audio': [],
        'effects': [],
        'stickers': [],
        'errors': []
    }

    # 1. Install Fonts
    bundled_fonts_dir = os.path.join(base_dir, 'assets', 'fonts')
    if sys.platform == 'win32':
        import winreg
        import ctypes
        
        user_fonts_dir = os.path.expandvars(r'%LOCALAPPDATA%\Microsoft\Windows\Fonts')
        os.makedirs(user_fonts_dir, exist_ok=True)
        reg_key_path = r'Software\Microsoft\Windows NT\CurrentVersion\Fonts'
        
        try:
            reg_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_key_path, 0, winreg.KEY_SET_VALUE)
        except Exception as e:
            logger.warning(f"Could not open font registry key: {e}")
            reg_key = None

        if os.path.isdir(bundled_fonts_dir):
            for font_file in os.listdir(bundled_fonts_dir):
                if font_file.lower().endswith(('.ttf', '.otf')):
                    src = os.path.join(bundled_fonts_dir, font_file)
                    dst = os.path.join(user_fonts_dir, font_file)
                    
                    should_copy = not os.path.exists(dst) or os.path.getsize(src) != os.path.getsize(dst)
                    if should_copy:
                        try:
                            shutil.copy2(src, dst)
                        except Exception as e:
                            results['errors'].append(f"Error al copiar fuente {font_file}: {e}")
                            continue

                    font_title = FONT_REGISTRY_MAP.get(font_file, f"{os.path.splitext(font_file)[0]} (TrueType)")
                    if reg_key:
                        try:
                            winreg.SetValueEx(reg_key, font_title, 0, winreg.REG_SZ, dst)
                        except Exception as e:
                            logger.warning(f"Error registering font {font_title}: {e}")

                    try:
                        ctypes.windll.gdi32.AddFontResourceW(dst)
                    except Exception:
                        pass
                    
                    results['fonts'].append(font_file)

            if reg_key:
                winreg.CloseKey(reg_key)

            try:
                HWND_BROADCAST = 0xFFFF
                WM_FONTCHANGE = 0x001D
                SMTO_ABORTIFHUNG = 0x0002
                ctypes.windll.user32.SendMessageTimeoutW(
                    HWND_BROADCAST, WM_FONTCHANGE, 0, 0, SMTO_ABORTIFHUNG, 1000, None
                )
            except Exception:
                pass
    else:
        # macOS / Linux
        mac_fonts_dir = os.path.expanduser('~/Library/Fonts')
        os.makedirs(mac_fonts_dir, exist_ok=True)
        if os.path.isdir(bundled_fonts_dir):
            for font_file in os.listdir(bundled_fonts_dir):
                if font_file.lower().endswith(('.ttf', '.otf')):
                    src = os.path.join(bundled_fonts_dir, font_file)
                    dst = os.path.join(mac_fonts_dir, font_file)
                    should_copy = not os.path.exists(dst) or os.path.getsize(src) != os.path.getsize(dst)
                    if should_copy:
                        try:
                            shutil.copy2(src, dst)
                        except Exception as e:
                            results['errors'].append(f"Error al copiar fuente {font_file}: {e}")
                            continue
                    results['fonts'].append(font_file)

    # Cache target directories across Windows / macOS
    target_cache_dirs = get_capcut_cache_dirs()

    # 2. Install Audio Click to CapCut cache
    src_sound = os.path.join(base_dir, 'assets', 'audio', 'click_mouse_02.mp3')
    if os.path.isfile(src_sound):
        for cache_dir in target_cache_dirs:
            music_dir = os.path.join(cache_dir, 'music')
            os.makedirs(music_dir, exist_ok=True)
            dst_sound = os.path.join(music_dir, '33f11a55221681b3fefec3346290169e.mp3')
            if not os.path.exists(dst_sound) or os.path.getsize(src_sound) != os.path.getsize(dst_sound):
                try:
                    shutil.copy2(src_sound, dst_sound)
                except Exception as e:
                    results['errors'].append(f"Error al copiar sonido de click en {music_dir}: {e}")
        results['audio'].append('Click_Mouse_Click_02(864360)')

    # 3. Install Effect Animations to CapCut cache
    bundled_effects = os.path.join(base_dir, 'assets', 'effects')
    if os.path.isdir(bundled_effects):
        for eff_id in os.listdir(bundled_effects):
            src_eff = os.path.join(bundled_effects, eff_id)
            if os.path.isdir(src_eff):
                for cache_dir in target_cache_dirs:
                    eff_dir = os.path.join(cache_dir, 'effect', eff_id)
                    os.makedirs(os.path.dirname(eff_dir), exist_ok=True)
                    try:
                        if not os.path.exists(eff_dir):
                            shutil.copytree(src_eff, eff_dir)
                    except Exception as e:
                        results['errors'].append(f"Error al copiar efecto {eff_id}: {e}")
                results['effects'].append(eff_id)

    # 4. Install Stickers to CapCut artistEffect cache
    bundled_stickers = os.path.join(base_dir, 'assets', 'stickers')
    if os.path.isdir(bundled_stickers):
        for stk_id in os.listdir(bundled_stickers):
            src_stk = os.path.join(bundled_stickers, stk_id)
            if os.path.isdir(src_stk):
                for cache_dir in target_cache_dirs:
                    stk_dir = os.path.join(cache_dir, 'artistEffect', stk_id)
                    os.makedirs(os.path.dirname(stk_dir), exist_ok=True)
                    try:
                        if not os.path.exists(stk_dir):
                            shutil.copytree(src_stk, stk_dir)
                    except Exception as e:
                        results['errors'].append(f"Error al copiar sticker {stk_id}: {e}")
                results['stickers'].append(stk_id)

    return results

def main():
    platform_name = "macOS" if sys.platform == 'darwin' else "Windows"
    print("\n=======================================================")
    print(f"      CC SUBS PRO - INSTALADOR DE FUENTES Y ASSETS ({platform_name})")
    print("=======================================================\n")
    print("[*] Instalando fuentes tipográficas de doctores...")
    res = install_all_assets()
    
    print(f"\n[OK] {len(res['fonts'])} fuentes registradas en {platform_name}:")
    for f in res['fonts']:
        print(f"  + {f}")
        
    print(f"\n[OK] Sonidos de click verificados:")
    for a in res['audio']:
        print(f"  + {a}")

    print(f"\n[OK] {len(res['effects'])} efectos de animación verificados:")
    for e in res['effects']:
        print(f"  + ID {e}")

    print(f"\n[OK] {len(res['stickers'])} paquetes de stickers verificados:")
    for s in res['stickers']:
        print(f"  + ID {s}")

    if res['errors']:
        print("\n[!] Advertencias:")
        for err in res['errors']:
            print(f"  - {err}")
    else:
        print(f"\n>>> ¡TODAS LAS FUENTES Y ASSETS SE INSTALARON CON ÉXITO EN {platform_name.upper()}! <<<")
    print("=======================================================\n")

if __name__ == '__main__':
    main()
