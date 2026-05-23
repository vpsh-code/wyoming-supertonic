# Wyoming Supertonic

Home Assistant Wyoming TTS server powered by **[Supertonic 3](https://github.com/supertone-inc/supertonic)** — on-device, no cloud, 31 languages.

> **Using Home Assistant OS?** The easiest path is the [HAOS add-on](https://github.com/vpsh-code/ha-addons-supertonic) — it handles everything automatically.  
> This repo is for **HA Container / Core / Supervised** users running the Wyoming server directly on their host machine.

---

## Hardware Requirements & Performance

Supertonic 3 runs 4 ONNX neural network models in sequence. Performance depends heavily on your CPU.

| Setup | Inference time (~10 words) | Notes |
|---|---|---|
| Modern x86-64 with AVX2 (native) | ~1–2 s | i5/i7/Ryzen desktop/laptop |
| Apple Silicon (M1/M2/M3) | ~1–2 s | Excellent via NEON |
| Proxmox VM — CPU type `host` | ~2–4 s | AVX2 passed through |
| Proxmox VM — CPU type `kvm64` | ~15–30 s | ❌ No AVX, scalar fallback |
| Raspberry Pi 4 (aarch64) | ~20–40 s | Slow but functional |
| Raspberry Pi 3 / armv7 | ❌ | No onnxruntime wheel |

### 🖥️ Proxmox users — two settings matter

**1. CPU type → `host`** *(critical)*

In Proxmox web UI → select your VM → **Hardware → Processors → CPU Type: `host`**

This exposes AVX2/FMA to the VM. Without it, onnxruntime falls back to scalar math and is **5–10× slower**.

**2. RAM → at least 6 GiB**

Supertonic peaks at ~1.5 GB during inference. If running on the same VM as HAOS, allocate **8 GiB** total:

| Component | RAM |
|---|---|
| HAOS + HA core | ~1.2 GB |
| Other add-ons | ~0.5–1.5 GB |
| Supertonic peak | ~1.5 GB |
| Headroom | ~2 GB |
| **Recommended total** | **8 GiB** |

---

## Quick Start (without Docker)

```bash
cd wyoming-supertonic
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python server.py \
  --onnx-dir  ../supertonic-demo/public/assets/onnx \
  --voice-dir ../supertonic-demo/public/assets/voice_styles \
  --port 10200
```

## Quick Start (Docker)

```bash
# Edit docker-compose.yml to point volumes at your model paths, then:
docker compose up -d
```

## Home Assistant Setup

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Wyoming Protocol**
3. Enter:
   - **Host**: IP of the machine running this server (or `localhost`)
   - **Port**: `10200`
4. Select it as your TTS engine in **Voice Assistants**

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--voice` | `M1` | Default voice (M1–M5, F1–F5) |
| `--lang` | `en` | Default language |
| `--steps` | `8` | Denoising steps (higher = better quality, slower) |
| `--speed` | `1.05` | Speech rate (0.7–1.8) |
| `--port` | `10200` | TCP port |

## Models

Download once and reuse across the web demo and Wyoming server:

```bash
# Option A — use the web demo's already-downloaded models
python server.py \
  --onnx-dir  ../supertonic-demo/public/assets/onnx \
  --voice-dir ../supertonic-demo/public/assets/voice_styles

# Option B — download to a standalone folder
mkdir -p models/onnx models/voice_styles
BASE=https://huggingface.co/Supertone/supertonic-3/resolve/main
for f in duration_predictor.onnx text_encoder.onnx vector_estimator.onnx vocoder.onnx tts.json unicode_indexer.json; do
  curl -L "$BASE/onnx/$f" -o "models/onnx/$f"
done
for v in M1 M2 M3 M4 M5 F1 F2 F3 F4 F5; do
  curl -L "$BASE/voice_styles/${v}.npy" -o "models/voice_styles/${v}.npy"
done
```

---

## Quality Guide

| `--steps` | Speed | Quality | Recommended for |
|---|---|---|---|
| 2 | Fastest | Acceptable | Low-RAM machines (≤ 4 GB) |
| 4 | Fast | Good | Daily use |
| 8 | Moderate | Very good | Default |
| 16 | Slow | Excellent | High-quality recordings |

---

## Platform Notes

### macOS (Intel or Apple Silicon)
Works natively. Run the server in the background with auto-restart on login using launchd:

```bash
# Create ~/Library/LaunchAgents/com.wyoming.supertonic.plist
# (see docs for template)
launchctl load ~/Library/LaunchAgents/com.wyoming.supertonic.plist
```

Or simply keep it running in a `screen`/`tmux` session.

### Ubuntu / Debian
```bash
# Install dependencies
sudo apt install python3.12 python3.12-venv

# Run as a systemd service (optional but recommended)
sudo cp wyoming-supertonic.service /etc/systemd/system/
sudo systemctl enable --now wyoming-supertonic
```

### Home Assistant Container / Core
Use Docker Compose — edit `docker-compose.yml` to mount your model folders:
```yaml
volumes:
  - /path/to/models/onnx:/data/onnx:ro
  - /path/to/models/voice_styles:/data/voice_styles:ro
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `RuntimeError: NumPy was built with X86_V2` | Set Proxmox CPU type to `host`, or pin `numpy<2.0` |
| Very slow inference (30 s+) | CPU lacks AVX2 — set Proxmox CPU type to `host` |
| OOM / Python killed | Increase RAM; use `--steps 2` to reduce memory |
| HA can't connect | Use machine IP, not `localhost`; check firewall on port 10200 |
| Numbers read incorrectly | Decimal comma? Use `--lang en` and write `23.1` not `23,1` |

---

## Related

- 🏠 [HAOS Add-on](https://github.com/vpsh-code/ha-addons-supertonic) — install directly from HA add-on store
- 🌐 [Web Demo](https://github.com/vpsh-code/supertonic-demo) — browser-based TTS with animated UI
- 🤖 [Supertonic 3](https://github.com/supertone-inc/supertonic) — upstream models by Supertone Inc. (MIT)
