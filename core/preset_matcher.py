# -*- coding: utf-8 -*-
"""
CC Subs Pro - Detector Automático de Presets por Nombre de Proyecto
Permite identificar instantáneamente la letra/preset correspondiente
al seleccionar un proyecto de CapCut en la GUI o por CLI.
"""

import os
import re
from typing import Optional, List, Tuple

# Patrones ordenados por especificidad (más específicos primero)
PRESET_PATTERNS: List[Tuple[str, List[str]]] = [
    # 1. Dra. Laura Burgos (debe evaluarse antes de 'laura' general)
    ("laura burgos", [
        r'\b(laura\s*burgos|burgos)\b',
        r'\blaura\s*10\b',
    ]),
    # 2. Dra. Laura Pediatra
    ("laura", [
        r'\b(laura\s*pediatra|pediatra|pediatr[ií]a)\b',
        r'\blaura\b',
    ]),
    # 3. CUIDUS
    ("cuidus", [
        r'\bcuidus\b',
    ]),
    # 4. Dr. Gerardo
    ("gerardo", [
        r'\bgerardo\b',
    ]),
    # 5. Dra. Gala
    ("gala", [
        r'\bgala\b',
    ]),
    # 6. Dra. Ana Otorrino
    ("ana", [
        r'\b(ana|otorrino|otorrinolaringolog[ií]a)\b',
    ]),
    # 7. Dr. Jose Podólogo
    ("jose", [
        r'\b(jose|jos[eé]|pod[oó]log[oa]|podolog[ií]a)\b',
    ]),
    # 8. Deditos Barefoot
    ("deditos", [
        r'\b(deditos|barefoot)\b',
    ]),
    # 9. Emilia
    ("emilia", [
        r'\bemilia\b',
    ]),
    # 10. Dr. Álvaro
    ("alvaro", [
        r'\b(alvaro|[aá]lvaro)\b',
    ]),
    # 11. Pequeños Cuidados
    ("pequenos", [
        r'\b(peque[nñ]os?(\s*cuidados)?|cuidados)\b',
    ]),
    # 12. Dra. Alharilla
    ("alharilla", [
        r'\balharilla\b',
    ]),
    # 13. Doctores Enfocavisión
    ("enfocavision", [
        r'\b(enfocavisi[oó]n|enfocavision)\b',
    ]),
    # 14. Juan
    ("juan", [
        r'\bjuan\b',
    ]),
]


def detect_preset_from_name(name_or_path: str) -> Optional[str]:
    """
    Detecta automáticamente la clave del preset de doctor a partir del nombre
    o ruta de una carpeta de proyecto CapCut.

    Retorna la clave del preset (ej: 'cuidus', 'gerardo', 'laura burgos', 'laura', 'ana', etc.)
    o None si no se reconoce ningún doctor en el nombre.
    """
    if not name_or_path or not isinstance(name_or_path, str):
        return None

    # Extraer el nombre base de la carpeta
    base_name = os.path.basename(name_or_path.rstrip(r'\/'))

    # Reemplazar guiones y guiones bajos por espacios para respetar límites de palabras (\b)
    cleaned_base = re.sub(r'[_\-]+', ' ', base_name).strip()
    cleaned_full = re.sub(r'[_\-]+', ' ', name_or_path).strip()

    for preset_key, patterns in PRESET_PATTERNS:
        for pat in patterns:
            # 1. Búsqueda prioritaria en el nombre base de la carpeta
            if re.search(pat, cleaned_base, re.IGNORECASE):
                return preset_key
            # 2. Búsqueda secundaria en la ruta completa
            if re.search(pat, cleaned_full, re.IGNORECASE):
                return preset_key

    return None
