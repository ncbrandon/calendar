FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/data
WORKDIR /app
RUN groupadd --gid 10001 calendar && useradd --uid 10001 --gid calendar --no-create-home calendar && mkdir /data && chown calendar:calendar /data
COPY --chown=calendar:calendar server.py domain.py ./
COPY --chown=calendar:calendar static ./static
COPY --chown=calendar:calendar scripts ./scripts
USER calendar
VOLUME /data
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=3)"
CMD ["python", "server.py"]
