#!/usr/bin/env bash
# ==============================================================================
# CC Subs Pro - Lanzador para macOS
# ==============================================================================
cd "$(dirname "$0")"

# Título de ventana de Terminal en macOS
echo -ne "\033]0;CC Subs Pro\007"

# 1. Detectar ejecutable de Python 3
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
    echo " o mediante Homebrew en Terminal: brew install python python-tk"
    echo "======================================================="
    read -p "Presiona Enter para salir..."
    exit 1
fi

# 2. Verificar soporte de Tkinter para la interfaz gráfica
"$PYTHON_BIN" -c "import tkinter" &>/dev/null
if [ $? -ne 0 ]; then
    echo "======================================================="
    echo " [!] Tu instalación de Python 3 no tiene soporte Tkinter."
    echo ""
    echo " Si usas Homebrew, ejecuta en la Terminal:"
    echo "   brew install python-tk"
    echo ""
    echo " O instala Python oficial (con Tkinter incluido) desde:"
    echo "   https://www.python.org/downloads/macos/"
    echo "======================================================="
    read -p "Presiona Enter para salir..."
    exit 1
fi

# 3. Lanzar la aplicación
exec "$PYTHON_BIN" gui.py
