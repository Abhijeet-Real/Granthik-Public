FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY backend/app /app/app

# Expose port
EXPOSE 8802

# Run FastAPI with Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8802", "--reload"]