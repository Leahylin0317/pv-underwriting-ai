"""Portable launcher: use the team member's own project .env."""
import os
import sys
from pathlib import Path
import uvicorn
from dotenv import load_dotenv
root = Path(__file__).resolve().parent
os.chdir(root)
load_dotenv(root / ".env", override=False)
sys.path.insert(0, str(root / "backend"))
if __name__ == "__main__":
    print("工作台：http://localhost:8768/evaluation", flush=True)
    uvicorn.run("app.main:app", host="127.0.0.1", port=8768)
