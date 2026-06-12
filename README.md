# Bill and Subscription Triage

An AI-powered Gmail automation project that reads recent emails, classifies them as bills or subscriptions, determines urgency, and routes urgent items for human action before any action is taken.

## Features

- Reads emails from Gmail.
- Classifies emails into `bill` or `subscription`.
- Extracts company name, amount, due date, urgency, and confidence.
- Flags urgent items for human-in-the-loop action.
- Lists the most recent bills and subscriptions.
- Supports workflow orchestration using LangGraph.

## Project Structure

- `emailagent.py` — main workflow graph and email processing logic.
- `gmail_tool.py` — Gmail access and bill/subscription extraction.
- `.env` — local environment variables, not committed to Git.
- `credentials.json` — Google OAuth client file, not committed to Git.
- `token.json` — saved Google token, not committed to Git.
- agent_diagram.png - mermaid diagram
- emailagent.mp4 - recorded output

## Requirements

- Python 3.10+
- Google Cloud project with Gmail APIs enabled
- OAuth desktop client credentials
- OpenAI API key

## Setup

1. Clone the repository.
2. Create a virtual environment.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create a `.env` file with your API key:

```env
OPENAI_API_KEY=your_openai_key_here
```

5. Add your Google OAuth files locally:
- `credentials.json`
- `token.json` will be created automatically after login

## How to Run

Run the main agent:

```bash
python emailagent.py
```

The script will:
- scan Gmail,
- find bill/subscription emails,
- classify them,
- send urgent items for human action,
- and print a summary of the results.

## Google Setup

To use Gmail access, you need:
- Google API enabled,
- OAuth consent screen configured in **Testing** mode during development,
- your Gmail account added as a test user,
- a **Desktop app** OAuth client for local login.

## Notes

- Secret files such as `.env`, `credentials.json`, and token files should not be pushed to GitHub.
- The project is designed to help organize recurring payments and subscriptions with a human action step for urgent cases.

