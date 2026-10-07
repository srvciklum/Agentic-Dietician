"""
HTTP API for Agentic Dietician.
Run:  python api_server.py
  or: uvicorn api_server:app --host 0.0.0.0 --port 8000
"""
from typing import Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from orchestrator_core import (
    get_protocol_statuses,
    get_session_messages,
    parse_user_id,
    process_message,
    process_message_with_optional_image,
    thread_id_for_user,
)
from vision_food import analyze_food_image_bytes

app = FastAPI(title="Agentic Dietician API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class NutrientStatusModel(BaseModel):
    name: str
    limit: float
    unit: str
    consumed_today: float
    remaining: float
    is_violated: bool


class ChatRequest(BaseModel):
    user_id: str
    message: str
    thread_id: Optional[str] = None


class ChatResponse(BaseModel):
    thread_id: str
    response: str
    action_type: str
    protocol_statuses: List[NutrientStatusModel]
    debug_today_consumption: Dict[str, float] = {}


class SessionStateResponse(BaseModel):
    thread_id: str
    messages: List[Dict[str, str]]
    today_consumption: Dict[str, float] = {}
    protocol_statuses: List[NutrientStatusModel] = []


class VisionAnalyzeResponse(BaseModel):
    analysis: str


@app.get("/health")
def health():
    return {"status": "ok"}


def _chat_response(result: dict) -> ChatResponse:
    return ChatResponse(
        thread_id=result["thread_id"],
        response=result["response"],
        action_type=result["action_type"],
        protocol_statuses=[NutrientStatusModel(**s) for s in result["protocol_statuses"]],
        debug_today_consumption=result.get("debug_today_consumption") or {},
    )


@app.post("/api/v1/chat/message", response_model=ChatResponse)
def chat_message(request: ChatRequest):
    """Text-only chat (unchanged)."""
    try:
        result = process_message(request.user_id, request.message, request.thread_id)
        return _chat_response(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/chat/message-with-image", response_model=ChatResponse)
async def chat_message_with_image(
    user_id: str = Form(...),
    message: str = Form(""),
    thread_id: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    """
    Chat with optional meal photo.
    Image alone → ask user for a text prompt.
    Image + text → Gemini Flash breakdown, then usual meal workflow.
    """
    try:
        image_bytes: Optional[bytes] = None
        filename = "upload.jpg"
        if file is not None and file.filename:
            if file.content_type and not file.content_type.startswith("image/"):
                raise HTTPException(status_code=400, detail="Please upload an image file.")
            image_bytes = await file.read()
            filename = file.filename or "upload.jpg"
            if not image_bytes:
                image_bytes = None

        result = process_message_with_optional_image(
            user_id,
            message,
            thread_id,
            image_bytes=image_bytes,
            image_filename=filename,
        )
        return _chat_response(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/chat/session-state", response_model=SessionStateResponse)
def session_state(user_id: str, thread_id: Optional[str] = None):
    try:
        uid = parse_user_id(user_id)
        tid = thread_id_for_user(uid, thread_id)
        statuses = get_protocol_statuses(uid)
        messages = get_session_messages(uid, tid)
        from nutrient_utils import get_today_nutrient_totals

        return SessionStateResponse(
            thread_id=tid,
            messages=messages,
            today_consumption=get_today_nutrient_totals(uid) or {},
            protocol_statuses=[NutrientStatusModel(**s) for s in statuses],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/vision/analyze-food", response_model=VisionAnalyzeResponse)
async def analyze_food_vision(file: UploadFile = File(...)):
    """POC: upload a food photo; Gemini Flash returns items / portion analysis."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload an image file.")
    try:
        data = await file.read()
        if not data:
            raise HTTPException(status_code=400, detail="Empty file.")
        analysis = analyze_food_image_bytes(data, file.filename or "upload.jpg")
        return VisionAnalyzeResponse(analysis=analysis)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


if __name__ == "__main__":
    import uvicorn

    print("Starting Agentic Dietician API on http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
