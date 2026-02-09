FROM python:3.14-slim

# 安裝 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# 複製依賴定義
COPY pyproject.toml uv.lock ./

# 安裝依賴（不含可選依賴）
RUN uv sync --frozen --no-dev

# 複製專案程式碼
COPY src/ src/
COPY run.sh .
RUN chmod +x run.sh

# 掛載點：data 目錄（資料庫、備份、日誌）與 .env
VOLUME ["/app/data", "/app/.env"]

ENV PYTHONPATH=src
ENTRYPOINT ["uv", "run", "python", "-m", "music_collector"]
CMD []
