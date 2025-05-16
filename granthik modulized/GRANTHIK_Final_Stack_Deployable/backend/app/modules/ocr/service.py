import requests

UNSTRUCTURED_API_URL = "http://localhost:9500/general/v0/general"

def process_file_with_ocr(file_path: str) -> dict:
    with open(file_path, "rb") as f:
        files = {"files": (file_path, f, "application/octet-stream")}
        response = requests.post(UNSTRUCTURED_API_URL, files=files)

    if response.status_code != 200:
        raise Exception(f"OCR processing failed with status {response.status_code}: {response.text}")

    return response.json()