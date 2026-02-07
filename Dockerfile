FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 5000

ENV MONITOR_BASE_DIR=/opt/monitor_os
RUN mkdir -p /opt/monitor_os/logs /opt/monitor_os/tmp

CMD ["python", "app/main.py"]
