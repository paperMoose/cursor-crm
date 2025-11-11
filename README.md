# Your Cursor CRM & Project Manager

> **Quick Start:** Open this folder in Cursor, then just start talking to me in the AI chat. Say things like "I just met with John from Acme Corp" or "Show me my active leads" and I'll handle everything.

## What This Does

A simple CRM system that lives in Markdown files. Your AI assistant (me!) manages everything through conversation—no UI, no manual file management, no database setup.

**Core Idea:** You talk, I organize. That's it.

## How to Use (3 Steps)

1. **Open in Cursor:** Open this folder in the Cursor AI editor
2. **Talk to me:** Share updates, paste meeting notes, or ask questions in the chat
3. **Let me handle it:** I'll create files, update statuses, and keep things organized

### Example Conversations

```
You: "Just had a call with Sarah from TechCorp. They're interested 
      in our consulting services for a Q1 project."

Me: I'll create a lead file for TechCorp and a contact file for Sarah...
```

```
You: "What's the status of my projects?"

Me: *runs status report and shows you a table*
```

```
You: "Client X signed the contract!"

Me: Shall I convert that lead to an active project?
```

## What I Manage For You

- **`/people/`** - Contact files (one per person)
- **`/active_leads/`** - Potential clients/projects
- **`/projects/`** - Active work
- **`/outreach/`** - Cold outreach tracking

I'll suggest moving files between folders as things progress (leads → projects, projects → done, etc).

## Automation Scripts (Optional)

This system includes macOS automation scripts for:

- **Apple Reminders** - Add `@reminder(...)` tags in any file
- **Apple Calendar** - Add `@calendar(...)` tags for events  
- **iMessage** - Send/export messages, extract tasks
- **Apple Mail** - Filter inbox, clean up marketing emails
- **Task Management** - Audit incomplete tasks, track status

Just ask me to run them: "Set a reminder for this" or "What's in my inbox?"

---

## More Details

<details>
<summary><strong>File Structure Standards</strong></summary>

### Lead Files (`/active_leads/`)

    ```markdown
    ## Status
- **Stage:** Qualification | Proposal Sent | Negotiation | Needs Follow-up
- **Next Step:** [Specific action]
- **Last Updated:** YYYY-MM-DD
```

### Project Files (`/projects/`)

    ```markdown
    ## Status
- **Current Status:** Planning | In Progress | On Hold | Blocked | Done
- **Next Milestone:** [Description]
- **Due Date:** YYYY-MM-DD
- **Last Updated:** YYYY-MM-DD
```

</details>

<details>
<summary><strong>Script Documentation</strong></summary>

### Apple Reminders (`reminders_cli.py`)

**Tag format:**
```markdown
@reminder(message="Follow up with client", at="2025-08-16 09:30", list="Work")
```

**Time formats:**
- `YYYY-MM-DD HH:MM` (24-hour)
- `today 17:30` or `tomorrow 09:00`
- `+30m`, `+2h`, `+1d` (relative)

**Usage:**
```bash
python3 scripts/reminders_cli.py --file "path/to/file.md"
python3 scripts/reminders_cli.py --report-day today  # Check today's load
```

---

### Apple Calendar (`calendar_cli.py`)

**Tag format:**
```markdown
@calendar(message="Focus: Write proposal", at="2025-08-16 10:00", duration="90m", calendar="Work")
```

**Usage:**
```bash
python3 scripts/calendar_cli.py --file "path/to/file.md"
```

---

### iMessage Tools

**Send Messages** (`imessage_send.py`)
```markdown
@imessage(to="Contact Name", message="Quick note")
```

```bash
python3 scripts/imessage_send.py --file "path/to/file.md" --yes
```

**Export Conversations** (`imessage_dump.py`)
```bash
python3 scripts/imessage_dump.py --contacts "john smith" --since 2024-01-01
```

**Extract Tasks** (`imessage_ingest.py`)
```bash
python3 scripts/imessage_ingest.py --since today --dry-run
```

---

### Email Tools

**List Unread** (`email_cli.py`)
```bash
python3 scripts/email_cli.py
python3 scripts/email_cli.py --sender "example.com" --json
```

**Clean Up Marketing** (`targeted_cleanup.py`)
```bash
python3 scripts/email_cli.py --limit 500 --json | \
  python3 scripts/targeted_cleanup.py --dry-run
```

---

### Utility Scripts

**Status Report** (`status_reporter.py`)
```bash
python status_reporter.py
python status_reporter.py --dump-content leads
```

**Task Audit** (`audit_tasks.sh`)
```bash
./audit_tasks.sh
```

Shows incomplete tasks with color coding:
- ☐ (Red) = Incomplete
- ➡️ (Yellow) = Moved once  
- 🔁 (Orange) = Moved multiple times

**Filter Tasks** (`filter_tasks.sh`)
```bash
./filter_tasks.sh
```

Shows tasks by status: Complete, In Progress, Not Started, Blocked

---

### Focus Timer (`focus_timer.sh`)

```bash
./scripts/focus_timer.sh "Write blog post" 90 15
# 90 minutes total, notify every 15 minutes
```

</details>

<details>
<summary><strong>How the AI Assistant Works</strong></summary>

I use Cursor AI rules (`.cursor/rules/*.mdc`) to understand how to help you:

- **`use-every-time.mdc`** - Daily habits, weekly planning, task tracking
- **`reminders.mdc`** - Apple Reminders integration rules
- **`task_context.mdc`** - Task context system
- **`experiments.mdc`** - Networking experiments framework
- **`use-for-all-files-made.mdc`** - File creation standards
- **`update-target-profiles-rule.mdc`** - Target profile updates

These rules are automatically applied when you work with me in Cursor.

### What I Do Automatically

**When you mention new contacts/opportunities:**
- Create files in the right folders
- Extract key details from your conversation
- Set up standard status blocks

**When you share updates:**
- Find the relevant files
- Add notes to the appropriate sections
- Update status fields and dates
- Ask for confirmation on major changes

**When things progress:**
- Suggest moving leads to projects (when won)
- Suggest archiving leads (when lost)
- Suggest moving projects to done (when complete)

</details>

---

## Tips

- **Paste freely:** Drop meeting notes, call summaries, or email threads into chat
- **Just ask:** "What's stale?" "Who should I follow up with?" "Create a reminder for this"
- **Let me infer:** I'll figure out what needs updating from context
- **Use natural language:** No need to format things perfectly

**Remember:** The whole system is conversational. If you're ever unsure, just ask me!
