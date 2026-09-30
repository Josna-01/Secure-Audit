from objectdetection import app

if __name__ == "__main__":
    import uvicorn
    # Original code (Alisha):
    # uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=True)
    # Updated: Port 8003 to prevent collision with BNS service on 8001
    uvicorn.run("main:app", host="127.0.0.1", port=8003, reload=True)

