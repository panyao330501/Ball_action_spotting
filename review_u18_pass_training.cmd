@echo off
cd /d "%~dp0"
"C:\ProgramData\miniconda3\Scripts\conda.exe" run -n ballspot-viz python scripts\serve_u18_eval_review.py --site-dir artifacts\u18_pass_cv\20261116_training_review_v1 --page review_site/index.html --port 8766 --open
if errorlevel 1 pause
