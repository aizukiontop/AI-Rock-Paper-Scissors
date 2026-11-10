FROM node:22-slim AS frontend-build

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir gunicorn

COPY . .

COPY --from=frontend-build /app/static/app ./static/app

EXPOSE 8080

CMD ["gunicorn", "-w", "1", "--threads", "4", "--timeout", "60", "-b", "0.0.0.0:8080", "main:app"]
