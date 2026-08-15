FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Expose the health check port for continuous daemon
EXPOSE 8080
CMD ["python", "-m", "bot.main"]
