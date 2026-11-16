# VOXGATE — Local Authorization Gate Lab

This package adds a research-only, single-browser-session UI for reviewing the **saved local-model decisions** from WaitWise. It does not call Ollama, OpenAI, or any external network service. All action IDs are fictional; **nothing is ever executed**.

## Setup

In Terminal 2, from `~/Desktop/voxgate` with `.venv` enabled:

```bash
unzip -o ~/Downloads/voxgate_web_lab_update.zip
python -m unittest core.test_web_gate -q
python manage.py test core.test_web_gate_django -v 1
```

Leave your Django development server running in Terminal 1. Open **http://127.0.0.1:8000/lab/** (or use the new link on the home page).

The lab reads a fixed report path: `~/Desktop/voxgate-balanced-reports/balanced_decisions.csv`. If it is missing, run the earlier free local experiment:

```bash
python balanced_local_waitwise_agent.py --run-local --limit 24
```

### How to explore

1. Choose a constructed scenario and a gate policy.
2. Read the *complete* transcript and the candidate **symbolic** action. A `HOLD` is not permission to execute the candidate; it means the original policy withheld it.
3. Click **Create a reviewable symbolic proposal**. The original transcript and exact candidate are bound to a session-specific, 15-minute token.
4. Review it, then choose **Approve symbolic action only** or **Reject proposal**. The token is consumed even if confirmation fails. Approval is stored only as a session label; no real operation is performed.

The proposal never uses gold/reference labels to select an action. Gold annotations remain in the evaluation CSV and are not displayed to the reviewer. No model inference, real user consent study, or actual agent integration occurs in this UI. A human click on a fictional scenario does not demonstrate that an agent has interpreted or respected a real person's authorization.

The web page deliberately uses Django's CSRF protection, session storage, exact-action matching, report consistency checks and a fixed global action catalog. The **session history is ephemeral** and not suitable as research data. For publication, collect explicit consent and independent annotations under a separate ethics and data protocol.

### Safety boundary

This prototype must remain a local development site. `DEBUG=True` and local secret-file settings are not deployment-ready. Never expose it to the internet without production security, authentication, logging/retention policies, and a threat model.

### Research status

This UI addresses the *confirmation-interface gap* in the 24-case gate replay. The best exploratory combined gate withheld 9 of 24 cases and still proposed 5 wrong actions. User review is a separate intervention and has **not** yet been measured as an improvement in correctness or safety.
