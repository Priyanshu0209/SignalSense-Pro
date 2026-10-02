import os
import sys
import uvicorn

if __name__ == "__main__":
    os.chdir("backend")
    sys.path.insert(0, os.getcwd())
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, log_level="info")
