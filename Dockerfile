FROM python:3.11-slim

# Installer Ghostscript
RUN apt-get update && apt-get install -y ghostscript && rm -rf /var/lib/apt/lists/*

# Dossier de travail
WORKDIR /app

# Dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code de l'app
COPY . .

# Port Render
EXPOSE 10000

CMD gunicorn app:app --bind 0.0.0.0:10000
