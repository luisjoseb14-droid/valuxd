#!/usr/bin/env bash
# ==============================================================================
# CC Subs Pro - Instalador y Configurador de Assets para macOS
# ==============================================================================
cd "$(dirname "$0")"

echo -ne "\033]0;CC Subs Pro - Instalador Mac\007"

echo "======================================================="
echo "       CC SUBS PRO - INSTALADOR PARA MACOS"
echo "  Estilizador de Subtítulos para CapCut (Doctores)"
echo "======================================================="
echo ""

# 1. Detectar Python 3
PYTHON_BIN=""
if command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif [ -f "/opt/homebrew/bin/python3" ]; then
    PYTHON_BIN="/opt/homebrew/bin/python3"
elif [ -f "/usr/local/bin/python3" ]; then
    PYTHON_BIN="/usr/local/bin/python3"
elif [ -f "/Library/Frameworks/Python.framework/Versions/Current/bin/python3" ]; then
    PYTHON_BIN="/Library/Frameworks/Python.framework/Versions/Current/bin/python3"
fi

if [ -z "$PYTHON_BIN" ]; then
    echo "======================================================="
    echo " [!] No se encontró Python 3 en este Mac."
    echo " Por favor instala Python 3 desde https://www.python.org"
    echo " o ejecuta: brew install python python-tk"
    echo "======================================================="
    read -p "Presiona Enter para salir..."
    exit 1
fi

echo "[OK] Python 3 detectado: $("$PYTHON_BIN" --version)"

# 2. Verificar Tkinter
"$PYTHON_BIN" -c "import tkinter" &>/dev/null
if [ $? -ne 0 ]; then
    echo ""
    echo "[!] Advertencia: Tu Python no tiene el módulo Tkinter habilitado."
    echo "    Si usas Homebrew, ejecuta en la Terminal:"
    echo "      brew install python-tk"
    echo "    (La GUI requiere Tkinter para abrir su ventana)"
    echo ""
fi

# 3. Otorgar permisos de ejecución a los scripts .command
chmod +x Iniciar_CC_Subs_Pro.command 2>/dev/null
chmod +x Instalar_Mac.command 2>/dev/null

# 4. Remover atributo de cuarentena de macOS si vino por descarga o AirDrop
xattr -dr com.apple.quarantine . 2>/dev/null || true

# 5. Instalar fuentes en ~/Library/Fonts y assets en CapCut Cache
echo ""
echo "[*] Instalando fuentes de doctores y assets en CapCut Cache..."
"$PYTHON_BIN" -m core.font_installer

echo ""
echo "======================================================="
echo "          INSTALACIÓN COMPLETADA EN MACOS"
echo "  1. 41 fuentes instaladas en ~/Library/Fonts"
echo "  2. Stickers, efectos de animación y clicks en Cache"
echo "  3. Puedes abrir la aplicación haciendo doble clic en:"
echo "     'Iniciar_CC_Subs_Pro.command'"
echo "======================================================="
echo ""
read -p "Presiona Enter para abrir CC Subs Pro ahora..."
exec "$PYTHON_BIN" gui.py
