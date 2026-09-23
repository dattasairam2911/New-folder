from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
import requests
import json
import uuid
import os
import websocket
import urllib.request
import urllib.parse

app = FastAPI(title="Identity-Preserving Image Editor Backend")

COMFYUI_HOST = "127.0.0.1:8188"
UPLOAD_DIR = "./uploads"
OUTPUT_DIR = "./outputs"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

def query_comfyui_and_wait(workflow: dict) -> str:
    """Executes workflow graph in ComfyUI and waits for output image via WebSocket"""
    client_id = str(uuid.uuid4())
    ws = websocket.WebSocket()
    ws.connect(f"ws://{COMFYUI_HOST}/ws?clientId={client_id}")

    # Queue the prompt in ComfyUI
    payload = {"prompt": workflow, "client_id": client_id}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"http://{COMFYUI_HOST}/prompt", data=data)
    response = json.loads(urllib.request.urlopen(req).read())
    prompt_id = response["prompt_id"]

    # Monitor execution progress
    filename = None
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message.get("type") == "executing":
                data = message.get("data", {})
                if data.get("node") is None and data.get("prompt_id") == prompt_id:
                    break  # Workflow complete

    # Retrieve history to get output image filename
    with urllib.request.urlopen(f"http://{COMFYUI_HOST}/history/{prompt_id}") as resp:
        history = json.loads(resp.read())
        outputs = history[prompt_id]["outputs"]
        for node_id, node_output in outputs.items():
            if "images" in node_output:
                filename = node_output["images"][0]["filename"]
                break

    ws.close()
    return filename

@app.post("/edit")
async def edit_image(
    prompt: str = Form(...),
    reference_image: UploadFile = File(...)
):
    # 1. Save uploaded reference image locally
    ext = reference_image.filename.split(".")[-1]
    saved_filename = f"{uuid.uuid4()}.{ext}"
    saved_filepath = os.path.abspath(os.path.join(UPLOAD_DIR, saved_filename))
    
    with open(saved_filepath, "wb") as f:
        f.write(await reference_image.read())

    # 2. Load API workflow schema
    if not os.path.exists("workflow_api.json"):
        raise HTTPException(status_code=500, detail="workflow_api.json file missing in root directory")
        
    with open("workflow_api.json", "r") as f:
        workflow = json.load(f)

    # 3. Dynamic Override: Update Prompt & Reference Image Path
    workflow["1"]["inputs"]["text"] = prompt
    workflow["2"]["inputs"]["image"] = saved_filepath

    # 4. Trigger ComfyUI Execution
    try:
        output_filename = query_comfyui_and_wait(workflow)
        
        # Download image from ComfyUI output directory
        image_url = f"http://{COMFYUI_HOST}/view?filename={output_filename}&type=output"
        img_bytes = urllib.request.urlopen(image_url).read()
        
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        with open(output_path, "wb") as f:
            f.write(img_bytes)

        return FileResponse(output_path, media_type="image/png")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")