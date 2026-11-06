# SignalLab Theme Pair Demo

This is a lightweight public demo for Streamlit Community Cloud.

It contains a self-contained SQLite database with 28 theme pairs, seven generations, five candidate proposals per generation, and fourteen demonstration validation periods per pair. The values are prebuilt demonstration data. The app does not call a model or run a backtest.

## Local run

```powershell
python -m pip install -r requirements.txt
streamlit run dashboard/theme_pair_demo_app.py
```

## Streamlit Community Cloud

1. Create a public GitHub repository and upload this folder's contents.
2. Choose `dashboard/theme_pair_demo_app.py` as the app file.
3. Select `requirements.txt` as the dependency file.
4. Deploy.

The app uses only relative paths inside this folder. Do not add API keys, raw CSMAR files, `.env` files, or the local virtual environment.
