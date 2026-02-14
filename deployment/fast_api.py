from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.responses import HTMLResponse
import os, json, logging, time, base64
from io import BytesIO
from typing import Optional, List
import numpy as np
import joblib

app = FastAPI(title="Model Runtime", redoc_url=None)

# Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn.error")

# Config
MODEL_PATH = os.environ.get("MODEL_PATH", "model.pkl")
MODEL_META_PATH = os.environ.get("MODEL_META", "model_meta.json")
model = None
model_info = {}

# Request schema
class PredictRequest(BaseModel):
    features: list


class PredictTextRequest(BaseModel):
    text: str


class PredictImageRequest(BaseModel):
    image_base64: str
    target_size: Optional[List[int]] = None  # [width, height]
    normalize: bool = True


# --- Loaders ---
def load_pickle(path):
    import pickle
    try:
        return joblib.load(path)
    except Exception:
        with open(path, "rb") as f:
            return pickle.load(f)

def load_pytorch(path):
    import torch
    try:
        return torch.jit.load(path)
    except Exception:
        return torch.load(path, map_location="cpu")

def load_tensorflow(path):
    import tensorflow as tf
    return tf.keras.models.load_model(path)

def load_onnx(path):
    import onnxruntime as ort
    return ort.InferenceSession(path)

def detect_and_load(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in [".pkl", ".joblib"]:
        return load_pickle(path), {"framework": "sklearn"}
    if ext in [".pt", ".pth"]:
        return load_pytorch(path), {"framework": "pytorch"}
    if ext in [".h5", ".keras"]:
        return load_tensorflow(path), {"framework": "tensorflow"}
    if ext == ".onnx":
        return load_onnx(path), {"framework": "onnx"}
    return load_pickle(path), {"framework": "unknown"}


def _to_jsonable(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if hasattr(value, "tolist"):
        try:
            return value.tolist()
        except Exception:
            return value
    return value


def _infer_from_array(arr: np.ndarray):
    fw = model_info.get("framework")

    if fw in ["sklearn", "unknown"]:
        preds = model.predict(arr)
        response = {"prediction": _to_jsonable(preds)}
        if hasattr(model, "predict_proba"):
            response["probabilities"] = _to_jsonable(model.predict_proba(arr))
        return response

    if fw == "pytorch":
        import torch
        model.eval()
        with torch.no_grad():
            tensor = torch.from_numpy(arr.astype(np.float32))
            out = model(tensor)
            if isinstance(out, (tuple, list)):
                out = out[0]
            return {"prediction": _to_jsonable(out.cpu().numpy())}

    if fw == "tensorflow":
        preds = model.predict(arr)
        return {"prediction": _to_jsonable(preds)}

    if fw == "onnx":
        sess = model
        input_name = sess.get_inputs()[0].name
        out = sess.run(None, {input_name: arr.astype(np.float32)})
        return {"prediction": _to_jsonable(out)}

    preds = model.predict(arr)
    return {"prediction": _to_jsonable(preds)}


def _infer_from_text(text: str):
    fw = model_info.get("framework")
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="text cannot be empty")

    # Most sklearn NLP pipelines (e.g., TfidfVectorizer + classifier) support raw text list input.
    if fw in ["sklearn", "unknown"]:
        try:
            preds = model.predict([text])
            response = {"prediction": _to_jsonable(preds)}
            if hasattr(model, "predict_proba"):
                response["probabilities"] = _to_jsonable(model.predict_proba([text]))
            return response
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Text inference failed. Ensure the model expects raw text input "
                    "(for example a sklearn text pipeline). "
                    f"Error: {e}"
                ),
            )

    raise HTTPException(
        status_code=400,
        detail=(
            f"Text inference is not configured for framework '{fw}'. "
            "Use a text-ready model/pipeline or extend runtime preprocessing."
        ),
    )


def _decode_image_from_base64(image_base64: str):
    try:
        raw = base64.b64decode(image_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image_base64 payload")

    try:
        from PIL import Image
    except Exception:
        raise HTTPException(
            status_code=500,
            detail=(
                "Image inference requires Pillow in runtime environment. "
                "Install with `pip install pillow` and redeploy."
            ),
        )

    try:
        return Image.open(BytesIO(raw)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Could not decode image data")


def _infer_from_image(image_base64: str, target_size: Optional[List[int]], normalize: bool):
    fw = model_info.get("framework")
    img = _decode_image_from_base64(image_base64)

    if target_size and len(target_size) == 2:
        w, h = int(target_size[0]), int(target_size[1])
        if w > 0 and h > 0:
            img = img.resize((w, h))

    arr = np.array(img, dtype=np.float32)
    if normalize:
        arr = arr / 255.0

    # Convert image into framework-appropriate input shape
    if fw in ["sklearn", "unknown"]:
        input_arr = arr.reshape(1, -1)
    elif fw == "pytorch":
        input_arr = np.transpose(arr, (2, 0, 1))[None, ...]  # [1, C, H, W]
    else:
        input_arr = arr[None, ...]  # [1, H, W, C] for tf/onnx default

    try:
        result = _infer_from_array(input_arr)
        result["input_shape"] = list(input_arr.shape)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=(
                "Image inference failed. Ensure model input shape/preprocessing matches runtime "
                "(resize/normalize/channels). "
                f"Error: {e}"
            ),
        )

# --- Startup ---
@app.on_event("startup")
def startup_event():
    global model, model_info
    logger.info(f"Starting runtime. Looking for model at {MODEL_PATH}")
    if not os.path.exists(MODEL_PATH):
        logger.error(f"Model file not found at {MODEL_PATH}")
        raise RuntimeError("Model file not found")

    model, info = detect_and_load(MODEL_PATH)
    model_info = info

    if os.path.exists(MODEL_META_PATH):
        try:
            with open(MODEL_META_PATH, "r") as f:
                meta = json.load(f)
                model_info.update(meta)
        except Exception:
            logger.warning("Failed to load model_meta.json")

    logger.info(f"Model loaded. Detected framework: {model_info.get('framework')}")

# --- Endpoints ---
@app.get("/", response_class=HTMLResponse)
@app.get("/ui", response_class=HTMLResponse)
def ui_page():
    return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Model Runtime Console</title>
  <style>
    :root {
      --bg: #f8f7f4;
      --panel: #fffdf7;
      --border: #d8d2c4;
      --text: #1f2933;
      --muted: #5f6b76;
      --brand: #0d7f7a;
      --brand-strong: #0a5f5b;
      --good: #1f8f47;
      --bad: #c0392b;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", Tahoma, Verdana, sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at 20% 0%, #f4eee1 0%, transparent 40%),
        radial-gradient(circle at 100% 0%, #e6f2ef 0%, transparent 35%),
        var(--bg);
    }
    .wrap {
      max-width: 980px;
      margin: 0 auto;
      padding: 22px;
    }
    .hero {
      border: 1px solid var(--border);
      background: var(--panel);
      border-radius: 14px;
      padding: 18px;
      margin-bottom: 14px;
      box-shadow: 0 6px 20px rgba(17, 24, 39, 0.05);
    }
    h1 {
      margin: 0;
      font-size: 26px;
      letter-spacing: 0.2px;
    }
    .sub {
      margin-top: 6px;
      color: var(--muted);
      font-size: 14px;
    }
    .status-pill {
      display: inline-block;
      margin-top: 12px;
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: #fff;
      font-size: 13px;
      color: var(--muted);
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .card {
      border: 1px solid var(--border);
      background: var(--panel);
      border-radius: 14px;
      padding: 14px;
      box-shadow: 0 4px 16px rgba(17, 24, 39, 0.04);
    }
    .card h3 {
      margin: 0 0 10px 0;
      font-size: 16px;
    }
    .links {
      display: grid;
      gap: 8px;
      margin-bottom: 8px;
    }
    .links a {
      color: var(--brand-strong);
      text-decoration: none;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 8px 10px;
      background: #fff;
      transition: all .15s ease;
    }
    .links a:hover {
      border-color: var(--brand);
      transform: translateY(-1px);
    }
    .controls {
      display: grid;
      grid-template-columns: auto auto 1fr auto;
      gap: 8px;
      align-items: center;
      margin-bottom: 10px;
    }
    select, input, textarea, button {
      font: inherit;
    }
    select, input, textarea {
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 8px 10px;
      background: #fff;
    }
    textarea {
      min-height: 150px;
      font-family: Consolas, "Courier New", monospace;
      font-size: 13px;
      line-height: 1.45;
      resize: vertical;
    }
    button {
      border: 1px solid var(--brand);
      background: var(--brand);
      color: #fff;
      border-radius: 8px;
      padding: 8px 12px;
      cursor: pointer;
      white-space: nowrap;
    }
    button:hover { background: var(--brand-strong); }
    button.ghost {
      background: #fff;
      color: var(--brand-strong);
    }
    .meta {
      margin: 8px 0;
      color: var(--muted);
      font-size: 13px;
    }
    .meta .ok { color: var(--good); font-weight: 600; }
    .meta .fail { color: var(--bad); font-weight: 600; }
    pre {
      margin: 0;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: #fdfdfd;
      padding: 10px;
      min-height: 90px;
      overflow: auto;
      font-family: Consolas, "Courier New", monospace;
      font-size: 13px;
      line-height: 1.45;
      white-space: pre-wrap;
      word-break: break-word;
    }
    @media (max-width: 860px) {
      .grid { grid-template-columns: 1fr; }
      .controls { grid-template-columns: 1fr; }
      button { width: 100%; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <h1>Model Runtime Console</h1>
      <div class="sub">Local fallback UI for testing runtime endpoints when docs pages are blocked or blank.</div>
      <div id="liveHealth" class="status-pill">Health: unknown</div>
    </div>

    <div class="grid">
      <div class="card">
        <h3>Service Links</h3>
        <div class="links">
          <a href="/ui" target="_blank">Runtime UI (/ui)</a>
          <a href="/docs" target="_blank">Swagger Docs (/docs)</a>
          <a href="/redoc" target="_blank">ReDoc (/redoc)</a>
          <a href="/health" target="_blank">Health JSON (/health)</a>
          <a href="/openapi.json" target="_blank">OpenAPI JSON (/openapi.json)</a>
        </div>
      </div>

      <div class="card">
        <h3>Health Probe</h3>
        <div class="controls">
          <button onclick="checkHealth()">Check Health</button>
          <button class="ghost" onclick="clearBox('healthOut')">Clear</button>
        </div>
        <pre id="healthOut">{}</pre>
      </div>

      <div class="card" style="grid-column: 1 / -1;">
        <h3>Request Runner</h3>
        <div class="controls">
          <select id="method">
            <option value="POST">POST</option>
            <option value="GET">GET</option>
          </select>
          <input id="path" value="/predict" />
          <button onclick="runRequest()">Send Request</button>
          <button class="ghost" onclick="setPredictTemplate()">Predict Template</button>
        </div>
        <div class="controls">
          <button class="ghost" onclick="setTextTemplate()">Text Template</button>
          <button class="ghost" onclick="setImageTemplate()">Image Template</button>
          <input id="imageFile" type="file" accept="image/*" />
          <button class="ghost" onclick="loadImageToPayload()">Load Image -> Payload</button>
        </div>
        <textarea id="payload">{ "features": [0.1, 0.2, 0.3] }</textarea>
        <div id="requestMeta" class="meta"></div>
        <pre id="resultOut">{}</pre>
      </div>
    </div>
  </div>

  <script>
    const healthPill = document.getElementById('liveHealth');

    function setHealthPill(ok, text) {
      if (ok === true) {
        healthPill.innerHTML = 'Health: <span class="ok">' + text + '</span>';
      } else if (ok === false) {
        healthPill.innerHTML = 'Health: <span class="fail">' + text + '</span>';
      } else {
        healthPill.textContent = 'Health: ' + text;
      }
    }

    function clearBox(id) {
      document.getElementById(id).textContent = '{}';
    }

    function pretty(text) {
      try {
        return JSON.stringify(JSON.parse(text), null, 2);
      } catch {
        return text;
      }
    }

    function setPredictTemplate() {
      document.getElementById('method').value = 'POST';
      document.getElementById('path').value = '/predict';
      document.getElementById('payload').value = '{ "features": [0.1, 0.2, 0.3] }';
    }

    function setTextTemplate() {
      document.getElementById('method').value = 'POST';
      document.getElementById('path').value = '/predict-text';
      document.getElementById('payload').value = '{ "text": "This product is excellent." }';
    }

    function setImageTemplate() {
      document.getElementById('method').value = 'POST';
      document.getElementById('path').value = '/predict-image';
      document.getElementById('payload').value =
`{
  "image_base64": "",
  "target_size": [224, 224],
  "normalize": true
}`;
    }

    async function loadImageToPayload() {
      const fileInput = document.getElementById('imageFile');
      const meta = document.getElementById('requestMeta');
      if (!fileInput.files || fileInput.files.length === 0) {
        meta.textContent = 'Select an image file first.';
        return;
      }
      const file = fileInput.files[0];
      const reader = new FileReader();
      reader.onload = function() {
        try {
          const dataUrl = String(reader.result || '');
          const base64 = dataUrl.includes(',') ? dataUrl.split(',')[1] : dataUrl;
          const payloadObj = {
            image_base64: base64,
            target_size: [224, 224],
            normalize: true
          };
          document.getElementById('method').value = 'POST';
          document.getElementById('path').value = '/predict-image';
          document.getElementById('payload').value = JSON.stringify(payloadObj, null, 2);
          meta.textContent = 'Image loaded into payload as base64.';
        } catch (e) {
          meta.textContent = 'Failed to prepare image payload: ' + e;
        }
      };
      reader.onerror = function() {
        meta.textContent = 'Failed to read image file.';
      };
      reader.readAsDataURL(file);
    }

    async function checkHealth() {
      const out = document.getElementById('healthOut');
      out.textContent = 'Loading...';
      try {
        const r = await fetch('/health');
        const txt = await r.text();
        out.textContent = pretty(txt);
        if (r.ok) {
          setHealthPill(true, 'ok');
        } else {
          setHealthPill(false, 'http ' + r.status);
        }
      } catch (e) {
        out.textContent = 'Health request failed: ' + e;
        setHealthPill(false, 'unreachable');
      }
    }

    async function runRequest() {
      const out = document.getElementById('resultOut');
      const meta = document.getElementById('requestMeta');
      const method = document.getElementById('method').value;
      const path = document.getElementById('path').value || '/predict';
      const started = performance.now();
      out.textContent = 'Loading...';
      meta.textContent = '';
      try {
        const requestInit = { method };
        if (method === 'POST') {
          const raw = document.getElementById('payload').value || '{}';
          JSON.parse(raw); // Validate early for clearer feedback
          requestInit.headers = { 'Content-Type': 'application/json' };
          requestInit.body = raw;
        }
        const r = await fetch(path, requestInit);
        const txt = await r.text();
        const took = Math.round(performance.now() - started);
        out.textContent = pretty(txt);
        meta.innerHTML = 'Status: <strong>' + r.status + '</strong> | Time: <strong>' + took + ' ms</strong> | Path: <strong>' + path + '</strong>';
      } catch (e) {
        out.textContent = 'Request failed: ' + e;
        meta.textContent = 'Request error';
      }
    }

    checkHealth();
  </script>
</body>
</html>
"""


@app.get("/redoc", response_class=HTMLResponse)
def redoc_fallback():
    return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>API Reference (Local)</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; max-width: 900px; color: #1f2933; }
    .card { border: 1px solid #d7d7d7; border-radius: 10px; padding: 14px; margin-bottom: 12px; }
    a { color: #0b57d0; text-decoration: none; }
    code, pre { font-family: Consolas, "Courier New", monospace; }
    pre { background: #f6f8fa; border: 1px solid #ddd; border-radius: 8px; padding: 10px; overflow: auto; }
  </style>
</head>
<body>
  <h1>API Reference (Local Fallback)</h1>
  <p>ReDoc JS could not be loaded in this environment, so this local page is shown instead.</p>

  <div class="card">
    <h3>Documentation Links</h3>
    <div><a href="/ui" target="_blank">Runtime UI Console (/ui)</a></div>
    <div><a href="/docs" target="_blank">Swagger UI (/docs)</a></div>
    <div><a href="/openapi.json" target="_blank">OpenAPI Spec (/openapi.json)</a></div>
  </div>

  <div class="card">
    <h3>Key Endpoints</h3>
    <div><code>GET /health</code> - Runtime health and model info</div>
    <div><code>POST /predict</code> - Prediction endpoint</div>
    <h4>Example payload</h4>
    <pre>{
  "features": [0.1, 0.2, 0.3]
}</pre>
  </div>
</body>
</html>
"""


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": model is not None,
        "framework": model_info.get("framework")
    }


@app.get("/capabilities")
def capabilities():
    return {
        "framework": model_info.get("framework"),
        "supported_endpoints": [
            "POST /predict (tabular numeric features)",
            "POST /predict-text (text models/pipelines)",
            "POST /predict-image (computer vision image_base64)",
        ],
        "notes": [
            "predict-text is best with sklearn text pipelines.",
            "predict-image expects base64-encoded image bytes.",
        ],
    }

@app.post("/predict")
def predict(req: PredictRequest):
    global model, model_info
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        arr = np.array(req.features, dtype=np.float32).reshape(1, -1)
        return _infer_from_array(arr)

    except Exception as e:
        logger.exception("Prediction error")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict-text")
def predict_text(req: PredictTextRequest):
    global model
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return _infer_from_text(req.text)


@app.post("/predict-image")
def predict_image(req: PredictImageRequest):
    global model
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return _infer_from_image(
        image_base64=req.image_base64,
        target_size=req.target_size,
        normalize=req.normalize,
    )
