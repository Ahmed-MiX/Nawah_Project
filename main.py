# Nawah Entry Point — run via: streamlit run main.py
# Executes ui/app.py as a flat script (not as an import)
import runpy
runpy.run_path("ui/app.py", run_name="__main__")
