install:
	pip install -e '.[dev]'

test:
	pytest -q

app:
	streamlit run app.py

api:
	uvicorn vcscout.api:app --app-dir src --reload
