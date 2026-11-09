#!/usr/bin/env python3
"""
MAMMON-7 V7 — Termux task worker + Mistral chat.
Standard-library only. Does not submit applications, spend money, or make payments.
"""
import os, sys, json, hashlib, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path.home() / "mammon7_v7"
TASKS = ROOT / "tasks"
OUTPUTS = ROOT / "outputs"
STATE = ROOT / "state"
LEDGER = ROOT / "ledger.jsonl"
CHAT_FILE = STATE / "chat_history.json"
MODEL = os.environ.get("MISTRAL_MODEL", "mistral-small-latest")
API_URL = "https://api.mistral.ai/v1/chat/completions"

SYSTEM = """You are the planning and coding assistant inside MAMMON-7 V7.
Help complete legitimate, lawful tasks and create useful deliverables.
Be practical and concise. Never claim a task was completed unless there is evidence.
For income tasks, distinguish potential revenue from confirmed payment.
Do not help with malware, credential theft, unauthorized access, spam, fraud,
fake reviews, or bypassing a site's rules. For bug bounty work, require explicit
authorization and stay within the published scope.
Do not request or expose secrets. Do not tell the local program to spend money,
make payments, submit applications, or contact people without human approval.
When asked to create a deliverable, provide the actual content, not merely advice.
"""

for folder in (TASKS, OUTPUTS, STATE):
    folder.mkdir(parents=True, exist_ok=True)
os.chmod(ROOT, 0o700)
for folder in (TASKS, OUTPUTS, STATE):
    try:
        os.chmod(folder, 0o700)
    except OSError:
        pass


def stamp():
    return datetime.now(timezone.utc).isoformat()


def log(event):
    record = {"time": stamp(), **event}
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    try:
        os.chmod(LEDGER, 0o600)
    except OSError:
        pass


def load_history():
    try:
        data = json.loads(CHAT_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data[-24:]
    except (OSError, ValueError):
        pass
    return []


def save_history(history):
    CHAT_FILE.write_text(
        json.dumps(history[-24:], ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    try:
        os.chmod(CHAT_FILE, 0o600)
    except OSError:
        pass


def mistral(messages, max_tokens=1800):
    key = os.environ.get("MISTRAL_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "MISTRAL_API_KEY is not set. Set it in Termux first; do not paste the key into chat."
        )

    payload = json.dumps({
        "model": MODEL,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": max_tokens
    }).encode()

    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"]

    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:1200]
        if e.code in (401, 403):
            raise RuntimeError(
                "Mistral rejected the key or access. Check API key/account access. " + detail
            )
        if e.code == 429:
            raise RuntimeError(
                "Mistral rate limit or quota reached. Check your account limits. " + detail
            )
        raise RuntimeError(f"Mistral HTTP {e.code}: {detail}")

    except (urllib.error.URLError, TimeoutError) as e:
        raise RuntimeError(f"Network/API connection failed: {e}")


def chat_loop():
    history = load_history()

    if not history:
        history = [{"role": "system", "content": SYSTEM}]
    elif history[0].get("role") != "system":
        history.insert(0, {"role": "system", "content": SYSTEM})

    print(f"\nMAMMON-7 V7 chat | model={MODEL}")
    print("Talk normally. Commands: /task <goal>, /clear, /help, /quit")

    while True:
        try:
            line = input("\nYou > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nChat ended.")
            break

        if not line:
            continue

        if line.lower() in ("/quit", "/exit"):
            break

        if line.lower() == "/help":
            print("/task <goal>  create a task plan and deliverable")
            print("/clear         clear saved conversation")
            print("/quit          exit")
            continue

        if line.lower() == "/clear":
            history = [{"role": "system", "content": SYSTEM}]
            save_history(history)
            print("Saved conversation cleared.")
            continue

        if line.lower().startswith("/task "):
            run_task(line[6:].strip())
            continue

        history.append({"role": "user", "content": line})

        try:
            answer = mistral(history)
            history.append({"role": "assistant", "content": answer})
            save_history(history)
            print("\nMistral > " + answer)

            log({
                "type": "chat",
                "model": MODEL,
                "prompt_sha256": hashlib.sha256(line.encode()).hexdigest(),
                "answer_sha256": hashlib.sha256(answer.encode()).hexdigest()
            })

        except Exception as e:
            history.pop()
            print(f"\n[ERROR] {e}")


def run_task(goal):
    if not goal:
        print("Usage: /task describe what you want done")
        return

    task_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    task = {
        "id": task_id,
        "goal": goal,
        "status": "planning",
        "created_at": stamp(),
        "model": MODEL
    }

    try:
        task_dir = None
        for attempt in range(100):
            candidate = TASKS / (task_id if attempt == 0 else f"{task_id}_{attempt}")
            try:
                candidate.mkdir(parents=True, exist_ok=False)
                task_dir = candidate
                break
            except FileExistsError:
                continue
        if task_dir is None:
            raise RuntimeError("could not create a unique task directory")

        plan = mistral([
            {
                "role": "system",
                "content": SYSTEM + """
Return a concise task plan with:
GOAL, DELIVERABLE, STEPS, RISKS, ACCEPTANCE CHECKS.
Do not claim to have performed any steps. Keep the plan executable on a $0 budget."""
            },
            {"role": "user", "content": goal}
        ], max_tokens=1400)

        (task_dir / "plan.md").write_text(plan + "\n", encoding="utf-8")
        print("\n=== PLAN ===\n" + plan)

        try:
            approval = input("\nCreate a deliverable from this plan? [y/N] ").strip().lower()
        except EOFError:
            approval = "n"

        if approval != "y":
            task["status"] = "planned_not_started"
            task["plan_file"] = str(task_dir / "plan.md")
            print(f"Saved plan: {task_dir / 'plan.md'}")

        else:
            deliverable = mistral([
                {
                    "role": "system",
                    "content": SYSTEM + """
Now produce the best concrete first deliverable for the task. Output only the deliverable content,
not a preamble. If code is appropriate, provide one complete source file and include comments/tests
where useful. Do not claim you ran tests or contacted anyone. Do not include shell commands that
delete files, access credentials, make payments, or submit external forms."""
                },
                {
                    "role": "user",
                    "content": "Task goal:\n" + goal + "\n\nApproved plan:\n" + plan
                }
            ], max_tokens=3500)

            # Save model output as a plain text/Markdown artifact; no automatic execution.
            out = OUTPUTS / f"{task_id}_deliverable.md"
            out.write_text(deliverable + "\n", encoding="utf-8")

            task["status"] = "deliverable_created_not_externally_verified"
            task["deliverable_file"] = str(out)
            task["deliverable_sha256"] = hashlib.sha256(out.read_bytes()).hexdigest()

            print(f"\nDeliverable saved: {out}")
            print("It has NOT been submitted, run, or externally verified.")

        task["finished_at"] = stamp()
        (task_dir / "task.json").write_text(
            json.dumps(task, indent=2), encoding="utf-8"
        )
        log({"type": "task", **task})

    except Exception as e:
        task["status"] = "error"
        task["error"] = str(e)
        task["finished_at"] = stamp()

        (task_dir / "task.json").write_text(
            json.dumps(task, indent=2), encoding="utf-8"
        )
        log({"type": "task_error", **task})
        print(f"[TASK ERROR] {e}")


def status():
    print("MAMMON-7 V7 status")
    print("Project:", ROOT)
    print("Python:", sys.version.split()[0])
    print("Model:", MODEL)
    print(
        "Mistral key configured:",
        "yes" if os.environ.get("MISTRAL_API_KEY") else "no"
    )
    print("Tasks:", sum(1 for p in TASKS.iterdir() if p.is_dir()))
    print("Deliverables:", sum(1 for p in OUTPUTS.iterdir() if p.is_file()))
    print("Ledger:", LEDGER)
    print("API status: not checked by status; run 'test' to verify.")


def main():
    cmd = sys.argv[1].lower() if len(sys.argv) > 1 else "chat"

    if cmd in ("--help", "-h", "help"):
        print(
            "Usage: python ~/mammon7_v7.py [chat|task|status|test]\n"
            "chat: talk to Mistral; /task <goal> creates a plan/deliverable\n"
            "task: create a task from the remaining command-line arguments\n"
            "status: show local setup\n"
            "test: send a small test request to Mistral"
        )

    elif cmd == "status":
        status()

    elif cmd == "test":
        try:
            answer = mistral(
                [
                    {"role": "system", "content": SYSTEM},
                    {
                        "role": "user",
                        "content": "Reply with exactly: MAMMON-7 V7 API TEST OK"
                    }
                ],
                max_tokens=30
            )
            print("API response:", answer)
            print("Mistral API connection succeeded.")

        except Exception as e:
            print("API TEST FAILED:", e)
            sys.exit(1)

    elif cmd == "task":
        goal = " ".join(sys.argv[2:]).strip()

        if not goal:
            try:
                goal = input("What task should MAMMON-7 complete? ").strip()
            except EOFError:
                print("No task goal provided.")
                return

        run_task(goal)

    elif cmd == "chat":
        chat_loop()

    else:
        print("Unknown command. Run: python ~/mammon7_v7.py --help")
        sys.exit(2)


if __name__ == "__main__":
    main()
