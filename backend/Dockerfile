FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--ssl-keyfile", "/certs/server/server.key", \
     "--ssl-certfile", "/certs/server/server.crt", \
     "--ssl-ca-certs", "/certs/ca/ca.crt", \
     "--ssl-cert-reqs", "2"]
