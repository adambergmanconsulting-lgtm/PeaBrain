# Python + Node: ESLint 8 + Prettier for the verification loop
FROM node:20-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package.linters.json package.json
RUN npm install

COPY requirements.txt .
RUN python3 -m venv /venv && /venv/bin/pip install --no-cache-dir -r requirements.txt

COPY linters/ /app/linters/
COPY demo/ /app/demo/
COPY nadirclaw/ ./nadirclaw/
# Fallback when /app/demo is empty or a bad bind mount hides index.html; resolver uses this last.
COPY demo/index.html nadirclaw/bundled_peabrain.html
ENV PATH="/venv/bin:$PATH" PYTHONUNBUFFERED=1 NADIR_NODE_CWD=/app
EXPOSE 8765
CMD ["uvicorn", "nadirclaw.main:app", "--host", "0.0.0.0", "--port", "8765"]
