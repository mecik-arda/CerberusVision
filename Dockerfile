FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libopenvino-dev \
    wget \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-wsl.txt .
RUN pip install --no-cache-dir -r requirements-wsl.txt

COPY package.json pnpm-lock.yaml ./
RUN npm install -g pnpm && pnpm install

RUN npx playwright install --with-deps chromium

COPY . .

RUN mkdir -p logs uploads models .openvino_cache

ENV OPENVINO_DEVICE=CPU

EXPOSE 18000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "18000"]