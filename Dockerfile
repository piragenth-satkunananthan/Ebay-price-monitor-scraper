FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive


WORKDIR /app
COPY . .

RUN apt-get update && apt-get install -y \
    libxcb-shm0 \
    libx11-xcb1 \
    libx11-6 \
    libxcb1 \
    libxext6 \
    libxrandr2 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxfixes3 \
    libxi6 \
    libgtk-3-0 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libatk1.0-0 \
    libcairo-gobject2 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libglib2.0-0 \
    libxrender1 \
    libasound2 \
    libfreetype6 \
    libfontconfig1 \
    libdbus-1-3
#    python3 \
#    python3-pip \
#    python3-venv \
    wget \
    && rm -rf /var/lib/apt/lists/*


RUN ln -s /usr/bin/python3 /usr/bin/python
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/


#ENV VIRTUAL_ENV=/opt/venv
#RUN uv venv $VIRTUAL_ENV
#ENV PATH="$VIRTUAL_ENV/bin:$PATH"


#COPY requirements.txt .
RUN uv sync


RUN uv run playwright install chromium firefox
RUN uv run playwright install-deps


#COPY . .


EXPOSE 8501
