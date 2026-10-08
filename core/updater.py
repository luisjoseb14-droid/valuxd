# -*- coding: utf-8 -*-
"""
CC Subs Pro - Auto-Updater Module
Permite consultar, descargar y aplicar actualizaciones directamente desde GitHub.
Instala fuentes automáticamente en Windows y recarga presets sin requerir Git.
"""

import os
import sys
import json
import zipfile
import shutil
import tempfile
import urllib.request
import urllib.error
import ssl
import subprocess
import logging
from typing import Dict, Any, Tuple, Optional, Callable

if __name__ == '__main__' and __package__ is None:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.platform_paths import get_base_dir
from core.font_installer import install_all_assets

logger = logging.getLogger('CCSubsPro.Updater')

GITHUB_USER = "luisjoseb14-droid"
GITHUB_REPO = "valuxd"
BRANCH = "main"

VERSION_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{BRANCH}/version.json"
ZIP_URL = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/archive/refs/heads/{BRANCH}.zip"
USER_AGENT = "CCSubsPro-Updater/1.0"


def _safe_urlopen(req, timeout=30):
    """
    Ejecuta urlopen intentando primero verificación SSL estándar,
    y si falla por CERTIFICATE_VERIFY_FAILED (problema común de certificados en Windows),
    reintenta automáticamente con contexto sin verificación para que la actualización nunca falle.
    """
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except (urllib.error.URLError, ssl.SSLError) as e:
        err_msg = str(e)
        if "CERTIFICATE_VERIFY_FAILED" in err_msg or "certificate verify failed" in err_msg.lower():
            logger.info("Aviso SSL detectado. Reintentando con contexto seguro sin verificación...")
            ctx = ssl._create_unverified_context()
            return urllib.request.urlopen(req, context=ctx, timeout=timeout)
        raise


def get_local_version_info() -> Dict[str, Any]:
    base_dir = get_base_dir()
    vpath = os.path.join(base_dir, 'version.json')
    if os.path.isfile(vpath):
        try:
            with open(vpath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error al leer local version.json: {e}")
    return {
        "version": "1.0.0",
        "version_code": 1,
        "date": "2026-09-30",
        "description": "Versión inicial",
        "repo_url": f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}"
    }


def check_for_updates() -> Tuple[bool, Dict[str, Any]]:
    """
    Verifica si existe una versión más reciente en GitHub.
    Retorna (hay_actualizacion: bool, info: dict)
    """
    local_info = get_local_version_info()
    local_code = local_info.get("version_code", 1)

    req = urllib.request.Request(
        VERSION_URL,
        headers={"User-Agent": USER_AGENT, "Cache-Control": "no-cache"}
    )

    try:
        with _safe_urlopen(req, timeout=7) as resp:
            if resp.status == 200:
                remote_info = json.loads(resp.read().decode('utf-8'))
                remote_code = remote_info.get("version_code", 1)
                has_update = remote_code > local_code
                return has_update, remote_info
    except urllib.error.HTTPError as e:
        logger.warning(f"HTTP error al consultar versión en GitHub: {e.code}")
        return False, {"error": f"Error del servidor de GitHub ({e.code})"}
    except urllib.error.URLError as e:
        logger.warning(f"Error de conexión al consultar GitHub: {e.reason}")
        return False, {"error": "Sin conexión a internet o repositorio no accesible"}
    except Exception as e:
        logger.warning(f"Error inesperado al buscar actualizaciones: {e}")
        return False, {"error": str(e)}

    return False, local_info


def download_and_apply_update(
    progress_callback: Optional[Callable[[str, float], None]] = None,
    force: bool = False
) -> Dict[str, Any]:
    """
    Descarga el zip de la rama principal de GitHub, actualiza los archivos locales
    (styles, assets/fonts, core, gui.py) e instala cualquier fuente nueva en Windows.
    """
    base_dir = get_base_dir()
    result = {
        "success": False,
        "new_version": "",
        "description": "",
        "installed_fonts": [],
        "errors": []
    }

    if progress_callback:
        progress_callback("Conectando con GitHub...", 0.1)

    # 1. Descargar el zip
    req = urllib.request.Request(
        ZIP_URL,
        headers={"User-Agent": USER_AGENT}
    )

    temp_dir = tempfile.mkdtemp(prefix="ccsubs_update_")
    zip_path = os.path.join(temp_dir, "update.zip")

    try:
        downloaded_ok = False
        try:
            with _safe_urlopen(req, timeout=40) as resp, open(zip_path, 'wb') as out_f:
                total_size = resp.getheader('Content-Length')
                total_size = int(total_size) if total_size and total_size.isdigit() else 0
                downloaded = 0
                chunk_size = 64 * 1024

                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    out_f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0 and progress_callback:
                        pct = 0.25 + 0.35 * (downloaded / total_size)
                        progress_callback(f"Descargando ({downloaded // 1024} KB)...", min(0.6, pct))
            downloaded_ok = os.path.exists(zip_path) and os.path.getsize(zip_path) > 1000
        except Exception as dl_err:
            logger.warning(f"Error en descarga urllib: {dl_err}. Intentando fallback con curl...")

        # Fallback ultra-robusto con curl.exe de Windows
        if not downloaded_ok:
            if progress_callback:
                progress_callback("Descargando actualización (curl)...", 0.35)
            try:
                curl_cmd = ["curl.exe", "-k", "-s", "-L", "-A", USER_AGENT, "-o", zip_path, ZIP_URL]
                res_curl = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=60)
                downloaded_ok = os.path.exists(zip_path) and os.path.getsize(zip_path) > 1000
                if not downloaded_ok:
                    raise RuntimeError(f"Fallo al descargar actualización con curl: {res_curl.stderr or res_curl.stdout}")
            except Exception as curl_err:
                raise RuntimeError(f"Error al descargar la actualización: {curl_err}")

        if progress_callback:
            progress_callback("Extrayendo archivos...", 0.65)

        # 2. Descomprimir
        extract_dir = os.path.join(temp_dir, "extracted")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)

        # La carpeta raíz dentro del zip es valuxd-main
        extracted_roots = [
            os.path.join(extract_dir, d) for d in os.listdir(extract_dir)
            if os.path.isdir(os.path.join(extract_dir, d))
        ]
        if not extracted_roots:
            raise RuntimeError("El archivo de actualización no contiene una carpeta válida.")
        src_root = extracted_roots[0]

        if progress_callback:
            progress_callback("Aplicando presets y código nuevo...", 0.75)

        # 3. Copiar styles/
        src_styles = os.path.join(src_root, 'styles')
        dst_styles = os.path.join(base_dir, 'styles')
        if os.path.isdir(src_styles):
            os.makedirs(dst_styles, exist_ok=True)
            for f in os.listdir(src_styles):
                if f.endswith('.json'):
                    shutil.copy2(os.path.join(src_styles, f), os.path.join(dst_styles, f))

        # 4. Copiar assets/
        src_assets = os.path.join(src_root, 'assets')
        dst_assets = os.path.join(base_dir, 'assets')
        if os.path.isdir(src_assets):
            # fonts
            src_fonts = os.path.join(src_assets, 'fonts')
            dst_fonts = os.path.join(dst_assets, 'fonts')
            if os.path.isdir(src_fonts):
                os.makedirs(dst_fonts, exist_ok=True)
                for f in os.listdir(src_fonts):
                    if f.lower().endswith(('.ttf', '.otf')):
                        shutil.copy2(os.path.join(src_fonts, f), os.path.join(dst_fonts, f))

            # audio
            src_audio = os.path.join(src_assets, 'audio')
            dst_audio = os.path.join(dst_assets, 'audio')
            if os.path.isdir(src_audio):
                os.makedirs(dst_audio, exist_ok=True)
                for f in os.listdir(src_audio):
                    shutil.copy2(os.path.join(src_audio, f), os.path.join(dst_audio, f))

            # effects
            src_effects = os.path.join(src_assets, 'effects')
            dst_effects = os.path.join(dst_assets, 'effects')
            if os.path.isdir(src_effects):
                os.makedirs(dst_effects, exist_ok=True)
                for eff_id in os.listdir(src_effects):
                    src_eff = os.path.join(src_effects, eff_id)
                    dst_eff = os.path.join(dst_effects, eff_id)
                    if os.path.isdir(src_eff) and not os.path.exists(dst_eff):
                        shutil.copytree(src_eff, dst_eff)

            # stickers
            src_stickers = os.path.join(src_assets, 'stickers')
            dst_stickers = os.path.join(dst_assets, 'stickers')
            if os.path.isdir(src_stickers):
                os.makedirs(dst_stickers, exist_ok=True)
                for stk_id in os.listdir(src_stickers):
                    src_stk = os.path.join(src_stickers, stk_id)
                    dst_stk = os.path.join(dst_stickers, stk_id)
                    if os.path.isdir(src_stk) and not os.path.exists(dst_stk):
                        shutil.copytree(src_stk, dst_stk)

        # 5. Copiar core/
        src_core = os.path.join(src_root, 'core')
        dst_core = os.path.join(base_dir, 'core')
        if os.path.isdir(src_core):
            os.makedirs(dst_core, exist_ok=True)
            for f in os.listdir(src_core):
                if f.endswith('.py'):
                    shutil.copy2(os.path.join(src_core, f), os.path.join(dst_core, f))

        # 6. Copiar gui.py y archivos clave
        for root_file in ['gui.py', 'cc_subs_pro.py', 'version.json', 'README.md']:
            src_file = os.path.join(src_root, root_file)
            if os.path.isfile(src_file):
                shutil.copy2(src_file, os.path.join(base_dir, root_file))

        if progress_callback:
            progress_callback("Instalando fuentes en el sistema Windows...", 0.88)

        # 7. Ejecutar instalador de fuentes en el sistema Windows
        try:
            asset_res = install_all_assets()
            result["installed_fonts"] = asset_res.get("fonts", [])
            if asset_res.get("errors"):
                result["errors"].extend(asset_res["errors"])
        except Exception as e:
            logger.warning(f"Error al registrar fuentes: {e}")
            result["errors"].append(f"Registro de fuentes: {e}")

        # 8. Leer info de la nueva versión
        new_info = get_local_version_info()
        result["success"] = True
        result["new_version"] = new_info.get("version", "1.0.0")
        result["description"] = new_info.get("description", "")

        if progress_callback:
            progress_callback("¡Actualización finalizada con éxito!", 1.0)

    except Exception as e:
        logger.error(f"Fallo durante la actualización: {e}", exc_info=True)
        result["errors"].append(str(e))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return result


def bump_version(new_description: str = "") -> Dict[str, Any]:
    """
    Incrementa la versión local antes de hacer push a GitHub.
    """
    base_dir = get_base_dir()
    vpath = os.path.join(base_dir, 'version.json')
    info = get_local_version_info()

    code = info.get("version_code", 1) + 1
    v_str = info.get("version", "1.0.0")
    parts = v_str.split('.')
    if len(parts) == 3:
        try:
            parts[2] = str(int(parts[2]) + 1)
            v_str = ".".join(parts)
        except ValueError:
            v_str = f"1.0.{code}"
    else:
        v_str = f"1.0.{code}"

    import datetime
    today = datetime.date.today().isoformat()

    info["version"] = v_str
    info["version_code"] = code
    info["date"] = today
    if new_description:
        info["description"] = new_description

    with open(vpath, 'w', encoding='utf-8') as f:
        json.dump(info, f, indent=2, ensure_ascii=False)

    return info


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--bump':
        desc = sys.argv[2] if len(sys.argv) > 2 else "Actualización de presets y herramientas"
        new_v = bump_version(desc)
        print(f"[OK] Versión incrementada a {new_v['version']} (code {new_v['version_code']}): {new_v['description']}")
        return

    print("Verificando actualizaciones en GitHub...")
    has_up, info = check_for_updates()
    if has_up:
        print(f"Nueva versión disponible: {info.get('version')} - {info.get('description')}")
        print("Descargando e instalando...")
        res = download_and_apply_update(lambda msg, pct: print(f"[{int(pct*100)}%] {msg}"))
        if res["success"]:
            print(f"\n[OK] ¡Actualizado exitosamente a {res['new_version']}!")
        else:
            print(f"\n[!] Error: {res['errors']}")
    else:
        print(f"Tu versión ya está al día ({get_local_version_info().get('version')}).")


if __name__ == '__main__':
    main()
