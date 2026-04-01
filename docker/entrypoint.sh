#!/bin/sh
set -e

echo "Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}..."
while ! nc -z "${DB_HOST}" "${DB_PORT}"; do
  sleep 1
done

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Starting Django development server..."
python manage.py runserver 0.0.0.0:8000
