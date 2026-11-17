@echo off
cd /d "%~dp0"
"C:\ProgramData\miniconda3\Scripts\conda.exe" run -n ballspot-viz python scripts\serve_u18_eval_review.py --site-dir artifacts\u18_evaluation\20261109_u18_zero_shot_masked_v1 --page review_site/index.html --open
if errorlevel 1 pause
