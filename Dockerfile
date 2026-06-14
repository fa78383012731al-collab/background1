FROM python:3.11-slim

# System deps: Tesseract + Arabic lang pack + OpenCV libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-ara \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p uploads outputs

EXPOSE 5000

CMD ["streamlit", "run", "app.py", "--server.port=5000", "--server.address=0.0.0.0"]
