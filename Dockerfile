FROM python:3.11-slim

# gcc needed for some packages (bcrypt, cryptography)
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install in groups so HF logs show exactly which package fails
RUN pip install --no-cache-dir fastapi==0.115.5 "uvicorn[standard]==0.32.1" python-multipart==0.0.12
RUN pip install --no-cache-dir "pydantic-settings==2.6.1" "pydantic[email]==2.10.3"
RUN pip install --no-cache-dir "supabase>=2.30.0"
RUN pip install --no-cache-dir "qdrant-client==1.12.1"
RUN pip install --no-cache-dir redis==5.2.1
RUN pip install --no-cache-dir "openai==1.57.4" "httpx>=0.26,<0.29"
RUN pip install --no-cache-dir "python-jose[cryptography]==3.3.0" "passlib[bcrypt]==1.7.4" aiofiles==24.1.0
RUN pip install --no-cache-dir tiktoken==0.8.0 langdetect==1.0.9

COPY . .

EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
