#!/usr/bin/env bash
# Render build script — runs once during deployment

set -o errexit  # exit on error

pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --no-input

# Run migrations (applies to Supabase)
python manage.py migrate

echo "Build complete ✅"
