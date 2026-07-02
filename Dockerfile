FROM node:20-alpine AS ui
WORKDIR /app
COPY package.json package-lock.json tailwind.config.js ./
RUN npm ci
COPY assets ./assets
COPY templates ./templates
COPY accounts academics assessments attendance communications exams reports students timetables ./apps/
RUN mkdir -p static/css && npm run build:css

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY --from=ui /app/static/css/app.css /app/static/css/app.css
RUN useradd --create-home school && chown -R school:school /app
USER school
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120", "--access-logfile", "-"]
