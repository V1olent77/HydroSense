web: gunicorn api:app --bind 0.0.0.0:$PORT --workers 2 --timeout 60
release: python db/init_db.py && python scripts/seed_demo_data.py
