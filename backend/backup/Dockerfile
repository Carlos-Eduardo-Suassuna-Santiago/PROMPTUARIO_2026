FROM python:3.12-alpine

# postgresql-client para pg_dump; mongodb-tools para mongodump
RUN apk add --no-cache postgresql-client mongodb-tools curl

# Dependências Python
RUN pip install --no-cache-dir boto3==1.35.0 schedule==1.2.2

WORKDIR /app
COPY backup/backup_runner.py .

CMD ["python", "backup_runner.py"]