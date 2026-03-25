
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN apt-get update -y \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        unzip \
    && curl -fsSL https://deno.land/install.sh | sh \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --upgrade -r /app/requirements.txt \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV DENO_INSTALL=/root/.deno
ENV PATH="${DENO_INSTALL}/bin:${PATH}"

COPY . /app

CMD ["bash", "start"]
