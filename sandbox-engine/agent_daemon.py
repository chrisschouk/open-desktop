"""
OpenDesktop Sandbox - Agent Control Daemon
Runs INSIDE each Docker container. Provides REST API for mouse/keyboard/screenshot control.
Uses xdotool + scrot for reliable X11 interaction (no pyautogui screenshot dependency).
"""
import os
import sys
import io
import time
import subprocess
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from PIL import Image

# Ensure DISPLAY is set
os.environ["DISPLAY"] = os.getenv("DISPLAY", ":1")

app = FastAPI(title="OpenDesktop Sandbox Agent Daemon", version="2.0.0")


class ActionRequest(BaseModel):
    action: str = Field(..., description="Action type: click, double_click, move, type, press_key, drag, scroll, right_click")
    x: Optional[int] = None
    y: Optional[int] = None
    text: Optional[str] = None
    key: Optional[str] = None
    button: Optional[str] = "left"
    clicks: Optional[int] = 1
    amount: Optional[int] = None
    drag_to_x: Optional[int] = None
    drag_to_y: Optional[int] = None


class BashRequest(BaseModel):
    command: str = Field(..., description="Shell command to execute inside sandbox")
    cwd: Optional[str] = "/home/agent"


def xdotool(*args):
    """Run xdotool command."""
    cmd = ["xdotool"] + list(args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5,
                                env={**os.environ, "DISPLAY": ":1"})
        return result.returncode == 0
    except Exception:
        return False


@app.get("/health")
def health_check():
    return {"status": "ok", "display": os.getenv("DISPLAY", ":1")}


@app.get("/cursor")
def get_cursor_position():
    try:
        result = subprocess.run(
            ["xdotool", "getmouselocation", "--shell"],
            capture_output=True, text=True, timeout=3,
            env={**os.environ, "DISPLAY": ":1"}
        )
        # Parse X=123\nY=456\n...
        pos = {}
        for line in result.stdout.strip().split("\n"):
            if "=" in line:
                k, v = line.split("=", 1)
                pos[k.lower()] = int(v)
        return {"x": pos.get("x", 0), "y": pos.get("y", 0)}
    except Exception as e:
        return {"error": str(e)}


@app.get("/screenshot")
def take_screenshot(format: str = "jpeg"):
    """Take a screenshot using scrot (reliable X11 screenshot tool)."""
    try:
        tmp_path = "/tmp/screenshot.png"
        result = subprocess.run(
            ["scrot", tmp_path, "--overwrite"],
            capture_output=True, text=True, timeout=5,
            env={**os.environ, "DISPLAY": ":1"}
        )

        if result.returncode != 0 or not os.path.exists(tmp_path):
            raise Exception(f"scrot failed: {result.stderr}")

        img = Image.open(tmp_path)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        img_bytes = io.BytesIO()
        if format.lower() in ("jpg", "jpeg"):
            img.save(img_bytes, format="JPEG", quality=80)
            media = "image/jpeg"
        else:
            img.save(img_bytes, format="PNG")
            media = "image/png"

        img_bytes.seek(0)
        return StreamingResponse(img_bytes, media_type=media)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Screenshot failed: {str(e)}")


@app.post("/action")
def execute_action(req: ActionRequest):
    act = req.action.lower()
    env = {**os.environ, "DISPLAY": ":1"}

    try:
        if act == "move":
            if req.x is not None and req.y is not None:
                xdotool("mousemove", str(req.x), str(req.y))
            return {"status": "success", "action": "move", "x": req.x, "y": req.y}

        elif act in ("click", "single_click"):
            if req.x is not None and req.y is not None:
                xdotool("mousemove", str(req.x), str(req.y))
            button_map = {"left": "1", "middle": "2", "right": "3"}
            btn = button_map.get(req.button or "left", "1")
            xdotool("click", btn)
            return {"status": "success", "action": "click", "x": req.x, "y": req.y}

        elif act == "double_click":
            if req.x is not None and req.y is not None:
                xdotool("mousemove", str(req.x), str(req.y))
            xdotool("click", "--repeat", "2", "1")
            return {"status": "success", "action": "double_click", "x": req.x, "y": req.y}

        elif act == "right_click":
            if req.x is not None and req.y is not None:
                xdotool("mousemove", str(req.x), str(req.y))
            xdotool("click", "3")
            return {"status": "success", "action": "right_click", "x": req.x, "y": req.y}

        elif act == "type":
            if req.text:
                # Use xdotool type for reliable typing
                xdotool("type", "--clearmodifiers", "--delay", "20", req.text)
            return {"status": "success", "action": "type", "text": req.text}

        elif act == "press_key":
            if req.key:
                # Map common key names to xdotool names
                key_map = {
                    "return": "Return", "enter": "Return",
                    "tab": "Tab", "escape": "Escape",
                    "backspace": "BackSpace", "delete": "Delete",
                    "up": "Up", "down": "Down", "left": "Left", "right": "Right",
                    "space": "space", "home": "Home", "end": "End",
                    "pageup": "Page_Up", "pagedown": "Page_Down",
                }
                # Handle combo keys like ctrl+a
                keys = req.key.split("+")
                if len(keys) > 1:
                    mapped = [key_map.get(k.strip().lower(), k.strip()) for k in keys]
                    xdotool("key", "+".join(mapped))
                else:
                    mapped_key = key_map.get(req.key.lower(), req.key)
                    xdotool("key", mapped_key)
            return {"status": "success", "action": "press_key", "key": req.key}

        elif act == "drag":
            if all(v is not None for v in [req.x, req.y, req.drag_to_x, req.drag_to_y]):
                xdotool("mousemove", str(req.x), str(req.y))
                subprocess.run([
                    "xdotool", "mousedown", "1",
                    "mousemove", "--sync", str(req.drag_to_x), str(req.drag_to_y),
                    "mouseup", "1"
                ], env=env, timeout=5)
            return {"status": "success", "action": "drag"}

        elif act == "scroll":
            amount = req.amount if req.amount is not None else -5
            direction = "5" if amount < 0 else "4"  # 5=down, 4=up
            for _ in range(abs(amount)):
                xdotool("click", direction)
            return {"status": "success", "action": "scroll", "amount": amount}

        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Action timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Action error: {str(e)}")


@app.post("/bash")
def execute_bash(req: BashRequest):
    try:
        working_dir = req.cwd if req.cwd and os.path.exists(req.cwd) else "/home/agent"
        env = {**os.environ, "DISPLAY": ":1"}
        process = subprocess.run(
            req.command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=working_dir,
            env=env,
        )
        return {
            "status": "completed",
            "exit_code": process.returncode,
            "stdout": process.stdout[:5000],  # Cap output size
            "stderr": process.stderr[:2000],
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "exit_code": 124, "stdout": "", "stderr": "Command timed out after 30s"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bash error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
