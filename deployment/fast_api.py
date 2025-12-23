from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os, json, logging, time
import numpy as np
import joblib

app = FastAPI(title="Model Runtime")

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
@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": model is not None,
        "framework": model_info.get("framework")
    }

@app.post("/predict")
def predict(req: PredictRequest):
    global model, model_info
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        fw = model_info.get("framework")

        if fw in ["sklearn", "unknown"]:
            X = np.array(req.features).reshape(1, -1)
            preds = model.predict(X)
            response = {"prediction": preds.tolist()}
            if hasattr(model, "predict_proba"):
                response["probabilities"] = model.predict_proba(X).tolist()
            return response

        if fw == "pytorch":
            import torch
            model.eval()
            with torch.no_grad():
                arr = np.array(req.features, dtype=np.float32)
                tensor = torch.from_numpy(arr).unsqueeze(0)
                out = model(tensor)
                if isinstance(out, (tuple, list)):
                    out = out[0]
                preds = out.cpu().numpy()
                return {"prediction": preds.tolist()}

        if fw == "tensorflow":
            arr = np.array(req.features).reshape(1, -1)
            preds = model.predict(arr)
            return {"prediction": preds.tolist()}

        if fw == "onnx":
            sess = model
            input_name = sess.get_inputs()[0].name
            arr = np.array(req.features).astype(np.float32).reshape(1, -1)
            out = sess.run(None, {input_name: arr})
            return {"prediction": [o.tolist() for o in out]}

        # Fallback
        X = np.array(req.features).reshape(1, -1)
        preds = model.predict(X)
        return {"prediction": preds.tolist()}

    except Exception as e:
        logger.exception("Prediction error")
        raise HTTPException(status_code=500, detail=str(e))