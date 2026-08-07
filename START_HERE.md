# Start here

## 1. Run the dashboard

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## 2. Run the API

```bash
uvicorn vcscout.api:app --app-dir src --reload
```

Open `http://localhost:8000/docs`.

## 3. Put it on GitHub

Create an empty repository named `vcscout-ai`, then push this folder:

```bash
git init
git add .
git commit -m "Build VCScout AI MVP"
git branch -M main
git remote add origin https://github.com/adejumotosin/vcscout-ai.git
git push -u origin main
```

## 4. Phase 2

Do not display a "funding probability" until real timestamped funding outcomes have been joined. Use `data/funding_labels_template.csv` and `src/vcscout/modeling.py` to build the labelled panel first.
