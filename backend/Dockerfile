FROM python:3.12-slim

WORKDIR /app
RUN mkdir -p /app/data /app/credentials

COPY . /app
RUN pip install --no-cache-dir -r /app/requirements.txt

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]