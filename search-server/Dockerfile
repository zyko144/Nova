FROM python:3.12-slim
WORKDIR /app
COPY browser/nova_search /app/nova_search
RUN useradd --uid 10001 --create-home nova && mkdir /data && chown nova:nova /data
USER nova
EXPOSE 8787
CMD ["python","-m","nova_search","--db","/data/index.sqlite3","serve","--host","0.0.0.0","--port","8787"]
