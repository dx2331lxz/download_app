FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p static/uploads

ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV DATABASE_PATH=/data/versions.db
ENV UPLOAD_FOLDER=/data/uploads

EXPOSE 5002

CMD ["python", "app.py"]