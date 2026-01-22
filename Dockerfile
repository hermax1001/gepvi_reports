FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set PYTHONPATH to include the project root
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8008

# Run FastAPI
CMD ["uvicorn", "web.main:app", "--host", "0.0.0.0", "--port", "8008"]
