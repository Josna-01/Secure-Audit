import os
import shutil
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Secure Audit — Audio Intelligence Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {
        "status": "online",
        "service": "audio-intelligence",
        "info": "Boilerplate audio service. Add Whisper or alternative STT models here."
    }


@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """
    Accepts an audio file and transcribes it to text.
    The team member should implement speech-to-text here (e.g. using 'whisper' or 'faster-whisper').
    """
    temp_file_path = f"temp_{audio.filename}"
    try:
        # Save uploaded audio temporarily
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(audio.file, buffer)

        # Mock transcription response for testing the API connection
        mock_response = {
            "success": True,
            "filename": audio.filename,
            "transcript": "This is a placeholder transcript. Please integrate Whisper to perform actual speech-to-text transcription.",
            "duration_seconds": 15.4,
            "entities": [
                {"text": "Placeholder", "label": "KEYWORD", "timestamp": "00:02"}
            ]
        }
        return JSONResponse(content=mock_response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    finally:
        # Clean up temp file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8002))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
