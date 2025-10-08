# Papervista: AI Research Paper Explorer

---

## Setup (Windows)

### 1. Activate Virtual Environment

Open terminal in your project folder (`ai-paper-explorer/`) and run:

```bash
.venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Usage

Run two terminals — one for the server and one for the client.

### 1. Start the Server

Activate your virtual environment first:

```bash
.venv\Scripts\activate
```

Then start the server:

```bash
uvicorn main:app --reload
```

Wait until you see “Application startup complete.”

---

### 2. Open a New Terminal (Client)

Activate the virtual environment again in the new terminal:

```bash
.venv\Scripts\activate
```

#### Search Papers

```bash
python explorer_cli.py search "Gemini LLM"
```

Displays the latest papers with unique ArXiv IDs (e.g., `2510.06190`).

#### Generate Citation

```bash
python explorer_cli.py cite <cite-id> --style apa
```


