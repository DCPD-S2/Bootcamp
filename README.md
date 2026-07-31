# Local AI Assistant

Local AI Assistant este un asistent AI construit în Python, bazat pe Ollama și LangGraph, care utilizează o arhitectură multi-agent pentru rezolvarea diferitelor tipuri de cereri.

## Funcționalități

- Conversație generală
- Căutare web
- Informații despre vreme
- Calculator
- Informații despre sistem
- Speech-to-Text (Faster Whisper)
- Text-to-Speech (Piper)
- Voice Activity Detection (Silero VAD)
- Flux cooperativ pentru redactarea emailurilor
- Trimitere email prin SMTP

## Arhitectură

Aplicația folosește LangGraph pentru orchestrarea agenților.

### Agenți disponibili

- Conversation Agent
- Search Agent
- Weather Agent
- Calculator Agent
- System Agent
- Email Writer Agent
- Email Reviewer Agent
- Email Reviser Agent
- Email Sender Agent

## Cerințe

- Python 3.10+
- Ollama
- Modelul `llama3.1:8b`

## Instalare

### 1. Clone repository

```bash
git clone https://github.com/DCPD-S2/Bootcamp.git
```

### 2. Creează mediul virtual

Windows

```bash
python -m venv venv
venv\Scripts\activate
```

Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalează dependențele

```bash
pip install -r requirements.txt
```

### 4. Instalează modelul Ollama dacă nu există

Verificare:

```bash
ollama list
```

```bash
ollama pull llama3.1:8b
```


### 5. Creează fișierul `.env`

Pleacă de la:

```
.env.example
```

și completează datele SMTP dacă dorești trimiterea emailurilor.

Exemplu:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_SENDER=
```

Dacă aceste câmpuri nu sunt completate, aplicația funcționează în continuare, însă trimiterea emailurilor este dezactivată.

### 6. Rulează aplicația

```bash
python app.my
python main.py
```


