FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for audio, websockets, etc.
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libssl-dev \
    libnacl-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose Flask default port (if using web dashboard)
EXPOSE 5000

# Run the bot
CMD ["python", "main.py"]
