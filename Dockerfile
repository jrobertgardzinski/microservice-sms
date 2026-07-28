# SMS channel — Python stdlib only, no dependencies. Stub-sends unless SMS_PROVIDER is set.
FROM python:3.12-slim
WORKDIR /app
COPY server.py .
# Drop root, like the image encoder this service is modelled on. The divergence was an
# oversight, not a decision — and this is the layer the header-injection fix above lives in.
RUN useradd --system --no-create-home sms
USER sms
EXPOSE 8088
CMD ["python", "server.py"]
