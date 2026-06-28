FROM python:3.10-slim

# Install system dependencies for OpenCV, YOLOv8, and PyTorch (using libgl1 instead of deprecated libgl1-mesa-glx)
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install python packages first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Use Skyfield's native downloader to fetch de421.bsp during build (16MB)
RUN python -c "from skyfield.api import load; load('de421.bsp')"

# Copy the rest of the application files
COPY . .

# Expose port 7860
EXPOSE 7860

# Start FastAPI backend
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
