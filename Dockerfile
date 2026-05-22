FROM python:3.11-slim

WORKDIR /app

# Install deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY server.py tts_engine.py text_normalize.py ./

# Models and voices are mounted at runtime — see docker-compose.yml
# Default port
EXPOSE 10200

ENTRYPOINT ["python", "server.py", \
            "--onnx-dir",  "/models/onnx", \
            "--voice-dir", "/models/voice_styles"]
