#!/usr/bin/env bash
# install.sh — one-command setup for vocr
# Requirements: macOS Apple Silicon, Homebrew, uv

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN_DIR="${HOME}/.local/bin"

echo "=== vocr setup ==="

# 1. Check dependencies
echo "[1/5] Checking dependencies..."

if ! command -v uv &>/dev/null; then
  echo "  ERROR: uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi

if ! command -v mlx_vlm.generate &>/dev/null; then
  echo "  Installing mlx-vlm..."
  uv tool install mlx-vlm --force
else
  echo "  mlx-vlm: OK"
fi

# 2. Create venv for layout detection
echo "[2/5] Setting up Python venv..."
if [ ! -d "$SCRIPT_DIR/venv" ]; then
  uv venv "$SCRIPT_DIR/venv" --python 3.12
  uv pip install --python "$SCRIPT_DIR/venv/bin/python" \
    onnxruntime opencv-python numpy
  echo "  venv created"
else
  echo "  venv exists: OK"
fi

# 3. Download PP-DocLayoutV3 ONNX model
echo "[3/5] Checking layout model..."
MODEL_PATH="$SCRIPT_DIR/models/PP-DocLayoutV3.onnx"
if [ ! -f "$MODEL_PATH" ]; then
  echo "  Downloading PP-DocLayoutV3 ONNX (124MB)..."
  mkdir -p "$SCRIPT_DIR/models"
  python3 -c "
import urllib.request, os
url = 'https://huggingface.co/alex-dinh/PP-DocLayoutV3-ONNX/resolve/main/PP-DocLayoutV3.onnx'
urllib.request.urlretrieve(url, '$MODEL_PATH')
print('  Downloaded')
"
else
  echo "  Model exists: OK"
fi

# 4. Update vocr shebang to point to project venv
echo "[4/5] Configuring paths..."
VENV_PYTHON="$SCRIPT_DIR/venv/bin/python3"
sed -i.bak "1s|.*|#!$VENV_PYTHON|" "$SCRIPT_DIR/bin/vocr"
rm -f "$SCRIPT_DIR/bin/vocr.bak"
echo "  Shebang updated"

# 5. Create symlinks
echo "[5/5] Creating symlinks..."
mkdir -p "$BIN_DIR"
ln -sf "$SCRIPT_DIR/bin/vocr" "$BIN_DIR/vocr"
ln -sf "$SCRIPT_DIR/bin/vocr-server" "$BIN_DIR/vocr-server"
echo "  Linked: $BIN_DIR/vocr"
echo "  Linked: $BIN_DIR/vocr-server"

echo ""
echo "=== Setup complete ==="
echo ""
echo "Quick start:"
echo "  vocr-server start       # start inference server"
echo "  vocr image.png          # OCR"
echo "  vocr image.png --layout # layout-aware OCR"
echo "  vocr image.png --ask 'summarize'  # Q&A (needs VOCR_LLM_* env vars)"
echo ""
echo "Optional: Set up LLM for --ask/--extract in ~/.secrets/local.env"
