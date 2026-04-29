FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY simulator.py modbus_server.py ./

CMD ["python", "simulator.py"]
