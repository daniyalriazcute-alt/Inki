# Aura — AI Career & Skills Navigator

A production-oriented single-agent Streamlit application using CrewAI, Groq GPT-OSS 120B, FAISS RAG, short-term memory, four controlled external tools, Firebase authentication/FCM, output sanitization and selective human-in-the-loop approval checkpoints.

## Architecture

```text
User
  ↓
Streamlit UI
  ↓
Firebase Authentication
  ↓
Short-term Memory + FAISS Retrieval
  ↓
CrewAI Aura Agent
  ↓
GOAL → DECIDE → HUMAN APPROVAL when required → ACT → OBSERVE → CONTINUE/COMPLETE
  ↓
Retry exactly once on CrewAI execution failure
  ↓
Sanitize output
  ↓
Streamlit Chat
```

## Requirements

- Python **3.12.0**
- Groq API key
- Firebase project
- Firebase Email/Password authentication enabled
- Optional Firebase Admin service account for Firestore/FCM

## Groq

The project uses the exact requested model identifier:

```text
openai/gpt-oss-120b
```

CrewAI/LiteLLM receives it as:

```text
groq/openai/gpt-oss-120b
```

Set:

```toml
GROQ_API_KEY = "your_groq_key"
```

in Streamlit Secrets.

## Firebase setup

1. Create a Firebase project.
2. Enable Authentication → Sign-in method → Email/Password.
3. Create a Web App in Project Settings.
4. Copy its Web API key.
5. For Firestore/FCM, create a Firebase Admin service account.
6. Store the service account JSON in Streamlit Secrets rather than GitHub.

Example:

```toml
GROQ_API_KEY = "..."

[firebase]
api_key = "AIza..."
service_account = 