import os
from fastapi import UploadFile
from uuid import uuid4

UPLOAD_DIR = "uploaded_docs"

def save_file(uploaded_file: UploadFile) -> str:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_id = str(uuid4())
    file_path = os.path.join(UPLOAD_DIR, file_id + "_" + uploaded_file.filename)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.file.read())
    return file_path