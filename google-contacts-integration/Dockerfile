FROM python:3.11-slim

# Make logs appear instantly
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install minimal build deps required by some wheels
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency list and application code. Build context should be the repo root
COPY requirements.txt /app/requirements.txt
COPY google-contacts-integration /app/google-contacts-integration
COPY notion /app/notion

RUN pip install --no-cache-dir -r /app/requirements.txt

# Keep WORKDIR at /app so Python can resolve `import notion.notion_controller`
# The notion/ directory is a sibling to google-contacts-integration/

# Do NOT bake credentials/tokens into the image. Mount them at runtime.
# Default command runs the main sync script
CMD ["python", "google-contacts-integration/main.py"]
