FROM node:22-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home --uid 10001 kado
COPY backend/ ./backend/
COPY kado_bridge/ ./kado_bridge/
COPY --from=frontend /build/frontend/dist ./frontend/dist/
RUN mkdir -p /app/data/workspace && chown -R kado:kado /app/data
ENV KADO_DATA_DIR=/app/data KADO_WORKSPACE_ROOT=/app/data/workspace
USER kado
EXPOSE 8765
CMD ["python", "-m", "uvicorn", "company.api:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8765"]
