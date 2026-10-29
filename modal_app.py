"""Modal deploy for flowcheck. Local-only inputs/outputs become a Volume."""

import subprocess

import modal

app = modal.App("flowcheck")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("openai==3.40.0", "python-dotenv==1.2.4", "pdfplumber==0.11.10")
    .add_local_dir(
        ".",
        "/app",
        copy=True,
        ignore=[".venv", ".git", "__pycache__", "node_modules",
                "output", "input", "workspace"],
    )
)

vol = modal.Volume.from_name("flowcheck-data", create_if_missing=True)


@app.function(
    image=image,
    volumes={"/app/output": vol},
    secrets=[modal.Secret.from_name("flowcheck-secrets")],
    timeout=3600,
)
@modal.web_server(8000)
def serve():
    import os

    env = dict(os.environ, HOST="0.0.0.0", PORT="8000")
    subprocess.Popen(["python", "server.py", "8000"], cwd="/app", env=env)
