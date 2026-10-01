import os
import sys
from typing import Optional, List

def get_base_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_mac_capcut_roots() -> List[str]:
    """Returns candidate CapCut User Data directories on macOS in order of preference."""
    return [
        os.path.expanduser('~/Movies/CapCut/User Data'),
        os.path.expanduser('~/Library/Containers/com.lemon.capcut/Data/Movies/CapCut/User Data'),
        os.path.expanduser('~/Library/Application Support/CapCut/User Data')
    ]

def get_default_draft_dir() -> str:
    if sys.platform == 'darwin':
        for root in get_mac_capcut_roots():
            draft_dir = os.path.join(root, 'Projects', 'com.lveditor.draft')
            if os.path.isdir(draft_dir):
                return draft_dir
        # Default fallback
        return os.path.expanduser('~/Movies/CapCut/User Data/Projects/com.lveditor.draft')
    else:
        return os.path.expandvars(r'%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft')

def get_capcut_cache_dirs() -> List[str]:
    """Returns all existing or candidate CapCut cache directories."""
    dirs = []
    if sys.platform == 'darwin':
        for root in get_mac_capcut_roots():
            cache_dir = os.path.join(root, 'Cache')
            if os.path.isdir(cache_dir) and cache_dir not in dirs:
                dirs.append(cache_dir)
        if not dirs:
            dirs.append(os.path.expanduser('~/Movies/CapCut/User Data/Cache'))
    else:
        dirs.append(os.path.expandvars(r'%LOCALAPPDATA%\CapCut\User Data\Cache'))
    return dirs

def resolve_font_path(font_path_or_name: str) -> str:
    if not font_path_or_name:
        return font_path_or_name

    fname = os.path.basename(font_path_or_name)
    if not fname:
        return font_path_or_name.replace('\\', '/')

    # 1. Prioritize OS installed fonts (Windows/Mac) so CapCut's UI dropdown detects the font name
    if sys.platform == 'darwin':
        mac_dirs = [
            os.path.expanduser('~/Library/Fonts'),
            '/Library/Fonts',
            '/System/Library/Fonts'
        ]
        for md in mac_dirs:
            p = os.path.join(md, fname)
            if os.path.isfile(p):
                return p
    else:
        win_dirs = [
            os.path.expandvars(r'%LOCALAPPDATA%\Microsoft\Windows\Fonts'),
            r'C:\Windows\Fonts'
        ]
        for wd in win_dirs:
            p = os.path.join(wd, fname)
            if os.path.isfile(p):
                return p.replace('\\', '/')

    # 2. If directly pointing to an existing file
    if os.path.isfile(font_path_or_name):
        return font_path_or_name.replace('\\', '/')

    # 3. Fallback to bundled CC Subs Pro assets folder
    base_dir = get_base_dir()
    bundled = os.path.join(base_dir, 'assets', 'fonts', fname)
    if os.path.isfile(bundled):
        return bundled.replace('\\', '/')

    return font_path_or_name.replace('\\', '/')

def get_default_click_sound_path() -> str:
    base_dir = get_base_dir()
    bundled = os.path.join(base_dir, 'assets', 'audio', 'click_mouse_02.mp3')
    
    # Check CapCut music cache on current platform
    for cache_dir in get_capcut_cache_dirs():
        cached_mp3 = os.path.join(cache_dir, 'music', '33f11a55221681b3fefec3346290169e.mp3')
        if os.path.isfile(cached_mp3):
            return cached_mp3.replace('\\', '/')
            
    if os.path.isfile(bundled):
        return bundled.replace('\\', '/')
    return bundled.replace('\\', '/')

def resolve_effect_path(resource_id: str, default_subpath: str = "") -> str:
    if not resource_id:
        return ""
    base_dir = get_base_dir()
    
    # 1. Check CapCut effect cache on current platform
    for cache_dir in get_capcut_cache_dirs():
        eff_cache = os.path.join(cache_dir, 'effect', resource_id)
        if os.path.isdir(eff_cache):
            subdirs = [os.path.join(eff_cache, d) for d in os.listdir(eff_cache) if os.path.isdir(os.path.join(eff_cache, d)) and not d.endswith('_tmp')]
            if subdirs:
                return subdirs[0].replace('\\', '/')
            return eff_cache.replace('\\', '/')

    # 2. Check bundled assets
    bundled_dir = os.path.join(base_dir, 'assets', 'effects', resource_id)
    if os.path.isdir(bundled_dir):
        subdirs = [os.path.join(bundled_dir, d) for d in os.listdir(bundled_dir) if os.path.isdir(os.path.join(bundled_dir, d)) and not d.endswith('_tmp')]
        if subdirs:
            return subdirs[0].replace('\\', '/')
        return bundled_dir.replace('\\', '/')

    return default_subpath.replace('\\', '/')

def resolve_sticker_path(resource_id: str, default_subpath: str = "") -> str:
    if not resource_id:
        return ""
    base_dir = get_base_dir()

    # 1. Check CapCut artistEffect cache on current platform
    for cache_dir in get_capcut_cache_dirs():
        stk_cache = os.path.join(cache_dir, 'artistEffect', resource_id)
        if os.path.isdir(stk_cache):
            subdirs = [os.path.join(stk_cache, d) for d in os.listdir(stk_cache) if os.path.isdir(os.path.join(stk_cache, d)) and not d.endswith('_tmp')]
            if subdirs:
                return subdirs[0].replace('\\', '/')
            return stk_cache.replace('\\', '/')

    # 2. Check bundled assets
    bundled_dir = os.path.join(base_dir, 'assets', 'stickers', resource_id)
    if os.path.isdir(bundled_dir):
        subdirs = [os.path.join(bundled_dir, d) for d in os.listdir(bundled_dir) if os.path.isdir(os.path.join(bundled_dir, d)) and not d.endswith('_tmp')]
        if subdirs:
            return subdirs[0].replace('\\', '/')
        return bundled_dir.replace('\\', '/')

    # 3. If default_subpath exists, return normalized
    if default_subpath and os.path.exists(default_subpath):
        return default_subpath.replace('\\', '/')

    return default_subpath.replace('\\', '/')
