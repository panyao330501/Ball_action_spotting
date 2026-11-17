@echo off
cd /d "%~dp0"
"C:\ProgramData\miniconda3\Scripts\conda.exe" run -n ballspot-viz python scripts\serve_u18_eval_review.py --site-dir . --page artifacts/u18_pass_cv/20261117_pending_pass_identity_v2/index.html --port 8767 --open
if errorlevel 1 pause
