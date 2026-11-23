FROM python:3.12-slim
WORKDIR /app
COPY server.py /app/server.py
COPY google_login.py requirements.txt /app/
COPY google_desktop.py /app/
RUN pip install --no-cache-dir -r requirements.txt
RUN useradd --system --uid 10001 nova && mkdir /data && chown nova:nova /data
USER nova
ENV NOVA_DB=/data/nova-sync.sqlite3
EXPOSE 8766
CMD ["python", "server.py", "--host", "0.0.0.0"]
