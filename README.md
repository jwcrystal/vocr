# vocr — Multi-Model Document OCR Tool

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.12+-green.svg)
![Platform](https://img.shields.io/badge/platform-macOS%20Apple%20Silicon-silver.svg)
![Models](https://img.shields.io/badge/models-PaddleOCR--VL%20%7C%20GLM--OCR-orange.svg)
![ONNX](https://img.shields.io/badge/layout-PP--DocLayoutV3-red.svg)
![Status](https://img.shields.io/badge/status-active-brightgreen.svg)

Local document OCR pipeline for macOS (Apple Silicon). Supports pluggable OCR models (PaddleOCR-VL, GLM-OCR) via MLX, with PP-DocLayoutV3 (ONNX) for layout detection and optional LLM layer for semantic understanding.

## Table of Contents

- [Supported Models](#supported-models)
- [Architecture](#architecture)
- [Components](#components)
- [Directory Structure](#directory-structure)
- [Setup](#setup)
- [Usage](#usage)
  - [Server](#server)
  - [OCR Modes](#ocr-modes)
  - [Semantic Modes](#semantic-modes-requires-llm-config)
  - [Model Profiles](#model-profiles)
  - [Custom Options](#custom-options)
- [Performance](#performance)
- [Prompt Reference](#prompt-reference)
- [Dependencies](#dependencies)
- [Files](#files)
- [Model Sources](#model-sources)
- [Layout Detection Labels](#layout-detection-labels)
- [License](#license)

## Supported Models

| Profile | Model | Params | OmniDocBench | Memory | Notes |
|---------|-------|--------|-------------|--------|-------|
| `paddleocr-vl` (default) | `PaddlePaddle/PaddleOCR-VL-1.6` | 0.9B | 94.50 | ~4.1GB | Cell marker table parsing |
| `glm-ocr` | `mlx-community/GLM-OCR-bf16` | 0.9B | 94.62 | ~3.6GB | Native output, lower memory |

Switch models with `--profile`:

```bash
vocr IMG.png --profile glm-ocr
```

## Architecture

```
Image
  ├─ vocr IMG.png              → PaddleOCR-VL (mlx-vlm server) → text
  ├─ vocr IMG.png --table      → PaddleOCR-VL → cell markers → markdown table
  ├─ vocr IMG.png --layout     → PP-DocLayoutV3 (ONNX) → region detect → per-region OCR
  ├─ vocr IMG.png --ask "..."  → OCR text → LLM → natural language answer
  └─ vocr IMG.png --extract    → OCR text → LLM → structured JSON
```

## Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| OCR engine | PaddleOCR-VL / GLM-OCR via mlx-vlm | Text extraction (pluggable via profiles) |
| Inference server | mlx_vlm.server | Keeps model in memory (1-2s/call vs 3-5s subprocess) |
| Layout detection | PP-DocLayoutV3 ONNX (124MB) | Detects text/table/formula/chart regions |
| Table parser | paddleocr_vl.py | Converts PaddleOCR-VL cell markers to markdown |
| Semantic layer | External LLM API (OpenAI-compatible) | Q&A and structured field extraction |

## Directory Structure

```
vocr/
├── bin/
│   ├── vocr              # Main CLI (Python, multi-model profiles)
│   └── vocr-server       # Server manager (Bash)
├── lib/
│   └── paddleocr_vl.py   # PaddleOCR-VL cell marker → markdown parser
├── models/
│   └── PP-DocLayoutV3.onnx   # Layout detection model (not in git)
├── venv/                     # Python 3.12 + onnxruntime + opencv (not in git)
├── server.pid                # Server PID (not in git)
├── server.log                # Server log (not in git)
├── .gitignore
└── README.md
```

## Setup

### 1. Install mlx-vlm (global)

```bash
uv tool install mlx-vlm --force
```

### 2. Create venv for layout detection

```bash
uv venv venv --python 3.12
uv pip install --python venv/bin/python onnxruntime opencv-python numpy
```

### 3. Download PP-DocLayoutV3 ONNX model

```bash
mkdir -p models
# Download from https://huggingface.co/alex-dinh/PP-DocLayoutV3-ONNX
# Save to: models/PP-DocLayoutV3.onnx (124MB)
```

### 4. (Optional) Create symlinks

```bash
ln -sf <your-vocr-path>/bin/vocr ~/.local/bin/vocr
ln -sf <your-vocr-path>/bin/vocr-server ~/.local/bin/vocr-server
```

### 5. (Optional) Configure LLM for --ask / --extract

```bash
export VOCR_LLM_API="https://your-api-endpoint/v1/chat/completions"
export VOCR_LLM_KEY="sk-your-key"
export VOCR_LLM_MODEL="gpt-4o-mini"
```

## Usage

### Server

```bash
vocr-server start     # Launch inference server (loads model once)
vocr-server stop      # Stop server
vocr-server status    # Check status
```

### OCR modes

```bash
vocr IMG.png                                    # Plain text OCR (~3s, default profile)
vocr IMG.png --table                            # Table → markdown table
vocr IMG.png --formula                          # Formula → LaTeX
vocr IMG.png --layout                           # Layout detect + per-region OCR
vocr IMG.png --layout --dry-run                 # Show detected regions only
vocr IMG1.png IMG2.png                          # Batch (separated by ---)
```

### Semantic modes (requires LLM config)

```bash
vocr IMG.png --ask "這張圖片在說明什麼？"          # Natural language Q&A
vocr invoice.png --extract invoice_no,date,amt  # Structured JSON extraction
vocr IMG.png --layout --ask "第三段的重點？"      # Layout + Q&A combined
```

### Model Profiles

```bash
vocr IMG.png                                    # Default: paddleocr-vl
vocr IMG.png --profile glm-ocr                  # Switch to GLM-OCR
vocr IMG.png --profile paddleocr-vl             # Explicit paddleocr-vl

# Server with specific profile
VOCR_PROFILE=glm-ocr vocr-server start
VOCR_PROFILE=glm-ocr vocr-server restart
```

Set default profile via env var:

```bash
export VOCR_PROFILE=glm-ocr   # all vocr calls use GLM-OCR by default
```

### Custom options

```bash
vocr IMG.png --prompt "Seal Recognition:"       # Custom prompt (overrides profile)
vocr IMG.png --model PaddlePaddle/PaddleOCR-VL-1.6  # Override model directly
vocr IMG.png --tokens 8000                      # Max tokens
```

## Performance

| Mode | Server (model cached) | Subprocess (cold start) |
|------|----------------------|------------------------|
| OCR | ~3s | ~6s |
| --layout | ~5s | ~8s |
| --ask | ~5-8s (OCR + LLM) | ~8-12s |
| --table | ~3s | ~6s |

Without server: auto-fallback to subprocess. First call loads model (~4s), subsequent calls are faster due to OS cache.

## Prompt Reference

Each model profile uses different prompts:

| Task | PaddleOCR-VL | GLM-OCR |
|------|-------------|---------|
| Text | `OCR:` | `Text Recognition:` |
| Table | `Table Recognition:` | `Table Recognition:` |
| Formula | `Formula Recognition:` | `Formula Recognition:` |
| Chart | `Chart Recognition:` | `Chart Recognition:` |
| Seal | `Seal Recognition:` | `Text Recognition:` |
| Spotting | `Spotting:` | `Text Recognition:` |

## Dependencies

- **mlx-vlm** (global, via `uv tool install`) — MLX inference for PaddleOCR-VL
- **onnxruntime + opencv-python** (in `venv/`) — Layout detection
- **External LLM API** (optional) — OpenAI-compatible endpoint for --ask/--extract

## Files

| File | Description |
|------|-------------|
| `bin/vocr` | Main CLI — server/subprocess OCR, layout, table parse, LLM Q&A |
| `bin/vocr-server` | Bash script — start/stop/status for mlx_vlm.server |
| `lib/paddleocr_vl.py` | Parses PaddleOCR-VL cell markers (`<fcel>`/`<lcel>`/`<nl>`) → markdown |
| `models/PP-DocLayoutV3.onnx` | ONNX layout detection model (25 classes, 800x800 input) |

## Model Sources

| Model | Source | Format |
|-------|--------|--------|
| PaddleOCR-VL 1.6 | `PaddlePaddle/PaddleOCR-VL-1.6` (HuggingFace) | HF safetensors (auto-loaded by mlx-vlm) |
| GLM-OCR | `mlx-community/GLM-OCR-bf16` (HuggingFace) | MLX bf16 |
| PP-DocLayoutV3 | `alex-dinh/PP-DocLayoutV3-ONNX` (HuggingFace) | ONNX |

## Layout Detection Labels

PP-DocLayoutV3 detects 25 region types. Key mappings:

| Label | PaddleOCR-VL Prompt | Notes |
|-------|-------------------|-------|
| text, doc_title, paragraph_title | `OCR:` | Batched as whole-image OCR |
| table | `Table Recognition:` | Cropped, parsed to markdown |
| display_formula, inline_formula | `Formula Recognition:` | Cropped |
| chart | `Chart Recognition:` | Cropped |
| seal | `Seal Recognition:` | Cropped |
| image, header_image, footer_image | `OCR:` | May contain text (diagrams) |

## License

[MIT](LICENSE) — Copyright (c) 2026 jwcrystal
