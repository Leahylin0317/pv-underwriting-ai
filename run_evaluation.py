"""Run the local evaluation UI with its own model selection.

The API key remains in the shared server-side configuration file.
"""

import os
import sys
from pathlib import Path

import uvicorn
from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parent
SHARED_CONFIG = Path("/Users/fangchengdemac/Documents/软件开发知识/.env")
MODEL = "qwen3.8-flash"


def configure_model() -> None:
    values = dotenv_values(SHARED_CONFIG) if SHARED_CONFIG.is_file() else {}
    api_key = values.get("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY is missing from shared configuration")

    os.environ["PV_VLM_BASE_URL"] = (
        "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    os.environ["PV_VLM_API_KEY"] = api_key
    os.environ["PV_VLM_MODEL"] = MODEL
    amap_key = values.get("PV_AMAP_WEB_KEY")
    if amap_key:
        os.environ["PV_AMAP_WEB_KEY"] = amap_key


if __name__ == "__main__":
    configure_model()
    sys.path.insert(0, str(PROJECT_ROOT / "backend"))
    print(f"Evaluation: http://localhost:8768/evaluation · Model: {MODEL}", flush=True)
    uvicorn.run("app.main:app", host="127.0.0.1", port=8768, log_level="warning")
