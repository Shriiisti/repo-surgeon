# 🩺 Repo Surgeon

An autonomous agent that repairs broken code until the tests pass.

Point it at a project with failing tests. Repo Surgeon runs the tests, reads the failures, asks an NVIDIA model for a fix, applies it, and checks the result. If a fix makes things worse, it undoes it and tries a different approach. It stops when every test passes, or when it runs out of attempts and says honestly that it gave up.

Built for the Nebius x NVIDIA Global AI Hackathon, in the **Coding and Agentic Engineering** track.

## How it works

1. **Run the tests.** The agent copies the project to a temporary folder (your original is never touched) and runs `pytest`.
2. **Read the evidence.** It collects the failure output and the project's source files.
3. **Ask the model.** It sends the evidence, plus the history of earlier attempts, to an NVIDIA model on Nebius Token Factory. The model replies with a structured JSON fix: a diagnosis, a hypothesis, a confidence score and the complete new file contents.
4. **Apply the fix and verify.** The agent writes the fix and re-runs the tests. The test runner, not the model, decides whether the fix worked.
5. **Undo if worse.** If more tests fail than before, the fix is reverted automatically and the model is told not to repeat that approach.
6. **Repeat** up to a set number of attempts.

Every attempt appears live in the web interface, with the diagnosis, a before/after diff, the model's confidence and a failing-test counter.

## Safety rails

- Test files are protected. The agent may fix the code but can never edit, skip or weaken a test.
- The agent can only write inside the project copy, never anywhere else on your computer.
- Every change is backed up, so a bad fix can always be undone.
- If the evidence is not enough to fix the bug safely, the agent gives up and explains what is missing.

## How Nebius and NVIDIA are used

- **Nebius Token Factory** hosts the model and serves it through its OpenAI-compatible inference API. Every repair step is a runtime call to it.
- **NVIDIA model:** [MODEL NAME AND ID: fill in after testing]
- The agent asks the model for strict JSON and validates it, retrying once if the reply is malformed.

## The demo projects

| Project | What is broken |
|---|---|
| `demo_project` | Shopping cart: one bug in one file |
| `demo_orders` | Order totals: two bugs in two files, so the agent needs several attempts |

## Run it yourself

You need Python 3.10 or newer and a Nebius Token Factory API key.

```bash
git clone https://github.com/shriiisti/repo-surgeon.git
cd repo-surgeon
pip install -r requirements.txt
```

Set your key and model (Windows PowerShell shown):

```powershell
$env:NEBIUS_API_KEY="your-key-here"
$env:NEBIUS_MODEL="the-model-id-from-your-dashboard"
```

Then start the app:

```bash
python -m streamlit run app.py
```

Pick a project from the dropdown and click **Repair it**. Never commit your API key. The `.gitignore` file already excludes `.env` files.

## Project layout

- `app.py`: the Streamlit interface
- `agent.py`: the repair loop
- `brain.py`: the system prompt and the model call
- `tools.py`: running tests, reading files, applying and undoing fixes
- `demo_project/`, `demo_orders/`: the broken example projects

## License

MIT. See `LICENSE`.