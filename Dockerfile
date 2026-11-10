FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt && useradd -u 10001 -m library && mkdir /data && chown library:library /data
COPY backend backend
COPY web web
ENV DB_PATH=/data/library.db
USER library
EXPOSE 8000
CMD ["uvicorn","backend.app:app","--host","0.0.0.0","--port","8000","--no-proxy-headers"]
