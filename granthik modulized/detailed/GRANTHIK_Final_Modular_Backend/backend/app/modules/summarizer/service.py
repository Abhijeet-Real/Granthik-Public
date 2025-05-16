from langchain.llms import Ollama
from pathlib import Path
import json

# Use a lightweight summarization-capable model
llm = Ollama(model="mistral")

# Three summarization templates
SUMMARY_PROMPTS = {
    "brief": "Summarize the following in a brief bullet-point format:

{text}",
    "detailed": "Provide a detailed summary of this document content:

{text}",
    "executive": "Give an executive-level summary with key insights and takeaways:

{text}"
}

def summarize_text(text: str, mode: str = "brief") -> str:
    prompt = SUMMARY_PROMPTS.get(mode, SUMMARY_PROMPTS["brief"]).replace("{text}", text[:4000])
    return llm.invoke(prompt)

def summarize_from_ocr(filepath: str, mode: str = "brief") -> str:
    json_path = Path(filepath)
    if not json_path.exists():
        raise FileNotFoundError("OCR output file not found.")

    with open(json_path, "r") as f:
        ocr_output = json.load(f)

    combined_text = "\n".join([block.get("text", "") for block in ocr_output if isinstance(block, dict)])
    return summarize_text(combined_text, mode)