FROM python:3.12-slim
WORKDIR /app
COPY server.py /app/server.py
RUN useradd --system --uid 10001 nova && mkdir /data && chown nova:nova /data
USER nova
ENV NOVA_DB=/data/nova-sync.sqlite3
EXPOSE 8766
CMD ["python", "server.py", "--host", "0.0.0.0"]
