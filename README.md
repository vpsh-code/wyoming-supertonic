# Wyoming Supertonic

Home Assistant Wyoming TTS server powered by **Supertonic 3** — on-device, no cloud, 31 languages.

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

Models are shared with the web demo — download them once:
```bash
cd ../supertonic-demo && ./setup-assets.sh
```
Then point `--onnx-dir` and `--voice-dir` at `supertonic-demo/public/assets/`.
