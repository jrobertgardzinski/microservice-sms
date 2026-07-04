# SMS channel — Python stdlib only, no dependencies. Stub-sends unless SMS_PROVIDER is set.
FROM python:3.12-slim
WORKDIR /app
COPY server.py .
EXPOSE 8088
CMD ["python", "server.py"]
