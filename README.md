# Your Cursor CRM & Project Manager

**IMPORTANT: This system is designed to be run and managed *exclusively* within the Cursor AI-native code editor. Your primary way of interacting with it is by talking to me, your AI assistant, directly in the Cursor chat.**

Welcome! This system helps you manage your contacts, leads, and projects using simple Markdown files. It is designed to be used within an AI-native code editor like Cursor, where your primary way of interacting with it is by talking to me, your AI assistant. I'm designed to be proactive and help you stay organized with minimal explicit instruction for routine tasks.

## How It Works: A Conversational Approach (It's Simple!)

Think of me as your operational assistant for this CRM. **You just talk to me, and I handle the file management.** You can provide information through conversation, paste meeting transcripts, share recollections, or give specific instructions. I'll interpret this information to:

*   **Identify and Capture:** When you mention new contacts, companies, or potential opportunities, I'll notice and offer to create the necessary files (`/people/`, `/active_leads/`, `/outreach/`) and populate them with the details you provide. **You don't need to manually create files.**
*   **Log Interactions & Infer Updates:** If you share a meeting summary, call notes, or even a casual update like "Just got off a call with X, and they said Y," I will:
    *   Identify the relevant lead, project, or person.
    *   Summarize key discussion points, decisions, and action items, adding them to the appropriate file(s).
    *   **Intelligently update status fields:** Based on the context of our conversation (e.g., "Proposal sent to Client X"), I'll infer if `Stage`, `Next Step` (for leads), or `Current Status`, `Next Milestone` (for projects) need updating. I'll always update the `Last Updated` date.
    *   *For straightforward updates (like adding notes), I'll proceed and then let you know what I did. For more significant inferred changes (like changing a project's core status), I'll state my understanding and intended update, asking for your confirmation before proceeding.*
*   **Proactively Manage File Lifecycles (I'll suggest these things!):**
    *   **Lead to Project Conversion:** If our conversation indicates a lead has been won (e.g., "Client Y signed the SOW"), I'll recognize this and propose: "It sounds like [Lead Name] has converted to a project. Shall I move the file to `/projects/` and update its status to 'Planning' (or similar)?" Upon your confirmation, I'll handle the move and file updates.
    *   **Archiving Leads:** If a lead seems unlikely to convert (e.g., "Client A has been unresponsive for a month"), I'll propose: "It sounds like [Lead Name] is unlikely to convert. Shall I archive it? If so, what's the primary reason?" With your go-ahead, I'll move it to `/active_leads/archive/` and update its status.
    *   **Completing Projects:** If we discuss a project being finished (e.g., "We've delivered the final version of Project X"), I'll propose: "It sounds like [Project Name] is complete. Shall I move it to `/projects/done/` and mark its status as 'Done'?" and proceed upon your confirmation.

## Directory Structure (Where I Keep Things)

*   **`./README.md`**: This guide.
*   **`./target-profiles.md`**: Defines your ideal client profiles. I can refer to this when you're discussing outreach or new leads. You can also ask me to help update this file by analyzing successful (and unsuccessful) leads, projects, and the people involved, using the `--dump-content` feature of the `status_reporter.py` script to gather data.
*   **`/people/`**: Individual files for each key contact, filled with info from our conversations.
*   **`/projects/`**: Files for active, confirmed projects, including their status, participants, overview, and action items I've gathered.
    *   `/projects/done/`: Where I'll move completed project files.
*   **`/active_leads/`**: Files for potential projects/clients, with standardized status sections and discussion summaries.
    *   `/active_leads/archive/`: Where I'll move leads that are no longer active.
*   **`/outreach/`**: For tracking initial outreach and prospecting efforts before they become active leads.
*   **`/scripts/`**: Automation scripts for reminders, calendar, iMessage, email, and more (see Scripts section below).
*   **`/.cursor/rules/`**: Cursor AI rules that guide how I work with your files (see Cursor Rules section below).

## Standard File Structures (How I Organize Information Within Files)

To keep things consistent and easy for me to process (and for you to read!):

*   **Consistent Headings:** I use standard Markdown headings like `## Status`, `## Overview`, `## Action Items`.
*   **`/active_leads/` File Status Block:**
    ```markdown
    ## Status
    - **Stage:** [e.g., Qualification, Proposal Sent, Negotiation, Needs Follow-up, Archived - No Conversion]
    - **Next Step:** [Specific action item, or N/A if archived]
    - **Last Updated:** [YYYY-MM-DD]
    - **Reason (if Archived):** [Brief reason, e.g., Unresponsive, Went with competitor, Not a good fit]
    ```
*   **`/projects/` File Status Block:**
    ```markdown
    ## Status
    - **Current Status:** [e.g., Planning, In Progress, On Hold, Awaiting Feedback, Blocked, Done]
    - **Next Milestone:** [Description of next major goal, or N/A if done]
    - **Due Date:** [YYYY-MM-DD, if applicable]
    - **Completion Date (if Done):** [YYYY-MM-DD]
    - **Last Updated:** [YYYY-MM-DD]
    ```

## Scripts

This repository includes a suite of automation scripts that integrate with macOS native apps (Reminders, Calendar, Messages, Mail) to help you stay organized and automate routine tasks.

### Apple Reminders Integration (`reminders_cli.py`)

Creates and updates Apple Reminders from `@reminder(...)` tags in markdown files. Designed to be idempotent—re-running won't create duplicates.

**Tag format:**
```markdown
@reminder(message="Draft LinkedIn post", at="2025-08-16 09:30", list="Work", note="weeks/week of 2025-08-11.md", priority=1, flagged=true, id="draft-li-post")
```

**Supported fields:**
- `message` (required): Reminder text
- `at` (required): Time in one of these formats:
  - `YYYY-MM-DD HH:MM` (24h, local time)
  - `today HH:MM` or `tomorrow HH:MM`
  - `+<N>m`, `+<N>h`, `+<N>d` (relative time)
- `list` (optional): Reminders list name (defaults to default list)
- `note` (optional): Additional context appended to reminder body
- `priority` (optional): `1` (high), `5` (medium), `9` (low)
- `flagged` (optional): `true` or `false`
- `id` (optional): Stable identifier for idempotency

**Usage:**
```bash
python3 scripts/reminders_cli.py --file "path/to/file.md" [--dry-run] [--verbose]
python3 scripts/reminders_cli.py --report-day today  # Check reminder load for today
```

### Apple Calendar Integration (`calendar_cli.py`)

Creates or updates Apple Calendar events from `@calendar(...)` tags in markdown files.

**Tag format:**
```markdown
@calendar(message="Focus block: Write PRD", at="2025-08-16 10:00", duration="90m", calendar="Work", location="Desk", note="task_context/prd.md")
```

**Supported fields:**
- `message` (required): Event title
- `at` (required): Start time (same formats as reminders)
- `duration` (optional): `"30m"`, `"1h"`, `"90m"` (default: `60m`)
- `calendar` (optional): Calendar name (defaults to system default)
- `location` (optional): Location string
- `note` (optional): Context included in description

**Usage:**
```bash
python3 scripts/calendar_cli.py --file "path/to/file.md" [--dry-run] [--verbose]
```

### iMessage Integration

#### Send Messages (`imessage_send.py`)

Sends iMessages via the Messages app from `@imessage(...)` tags. **Dry-run by default**—requires `--yes` to actually send.

**Tag format:**
```markdown
@imessage(to="+14155551234|user@example.com|Contact Name", message="Short text to send", id="unique-id")
```

**Usage:**
```bash
# Dry run (default)
python3 scripts/imessage_send.py --file "path/to/file.md"

# Actually send
python3 scripts/imessage_send.py --file "path/to/file.md" --yes --verbose

# Resend after moving tags
python3 scripts/imessage_send.py --file "path/to/file.md" --reset-log
```

**Note:** Requires Accessibility permission for terminal to control Messages via AppleScript.

#### Dump Conversations (`imessage_dump.py`)

Read-only exporter for iMessage conversations filtered by contact(s). Never writes to the live Messages database.

**Usage:**
```bash
# Print conversation history
python3 scripts/imessage_dump.py --contacts "david corbitt" --since 2001-01-01

# Save as markdown
python3 scripts/imessage_dump.py --contacts "david corbitt" \
  --since 2018-01-01 --output "/tmp/david_corbitt_imessage.md"

# Multiple handles/tokens
python3 scripts/imessage_dump.py --contacts "+14155551234,david@example.com,corbitt" --since yesterday
```

**Note:** Requires Full Disk Access (FDA) for your terminal app to read `~/Library/Messages/chat.db`.

#### Ingest Messages (`imessage_ingest.py`)

Read-only iMessage ingestion that scans recent messages for lightweight task cues (e.g., "todo:", "task:") and emits `@reminder`/`@calendar` tags.

**Usage:**
```bash
# Dry-run: print inferred reminders from today
python3 scripts/imessage_ingest.py --since "today" --dry-run

# Append results to a weekly file and generate calendar blocks
python3 scripts/imessage_ingest.py --since "2025-08-15" \
  --output-file "weeks/week of 2025-08-18.md" \
  --add-calendar --default-at "today 10:00" --calendar "Work"
```

**Note:** Requires Full Disk Access (FDA) for your terminal app.

### Email Integration

#### Email CLI (`email_cli.py`)

Lists unread emails from Apple Mail via JXA (JavaScript for Automation). Can filter by date, subject, sender, and output as table, JSON, or count.

**Usage:**
```bash
# List unread emails (default)
python3 scripts/email_cli.py

# Filter by date
python3 scripts/email_cli.py --since 2025-01-01 --until 2025-01-31

# Filter by sender
python3 scripts/email_cli.py --sender "example.com"

# Output as JSON
python3 scripts/email_cli.py --json

# Count only
python3 scripts/email_cli.py --count
```

**Note:** Requires Apple Mail configured on this Mac.

#### Targeted Cleanup (`targeted_cleanup.py`)

Deletes product updates, event invites, marketing/promos from Apple Mail. Keeps important senders (configurable blocklist).

**Usage:**
```bash
# Dry run (default)
python3 scripts/email_cli.py --limit 500 --json | python3 scripts/targeted_cleanup.py --dry-run

# Actually delete
python3 scripts/email_cli.py --limit 500 --json | python3 scripts/targeted_cleanup.py --delete --yes
```

### Focus Timer (`focus_timer.sh`)

macOS focus timer that sends periodic notifications during a work session.

**Usage:**
```bash
./scripts/focus_timer.sh "Task description" <total_minutes> <interval_minutes>

# Example: 90-minute session with 15-minute intervals
./scripts/focus_timer.sh "Write blog post" 90 15
```

### Utility Scripts

#### Status Reporter (`status_reporter.py`)

Scans active leads and projects and generates a status table with staleness indicators.

**Usage:**
```bash
# Get status table
python status_reporter.py

# Dump full content for summarization
python status_reporter.py --dump-content leads
python status_reporter.py --dump-content projects
python status_reporter.py --dump-content people
```

#### Task Audit (`audit_tasks.sh`)

Scans weekly plan files and reports incomplete tasks, highlighting tasks that have been moved multiple times.

**Color coding:**
- ☐ (Red): Incomplete task
- ➡️ (Yellow): Task moved once
- 🔁 (Orange): Task moved multiple times

**Usage:**
```bash
./audit_tasks.sh
```

#### Filter Tasks (`filter_tasks.sh`)

Scans task context files and displays their status (Complete, In Progress, Not Started, Blocked).

**Usage:**
```bash
./filter_tasks.sh
```

## Cursor Rules

This repository includes Cursor AI rules (`.cursor/rules/*.mdc`) that guide how I work with your files. These rules ensure consistent behavior and help me understand your preferences.

### Available Rules

- **`use-every-time.mdc`**: Core rules for daily habits, weekly planning, task tracking, and column layouts
- **`reminders.mdc`**: Rules for Apple Reminders integration, including opt-in policy and load checks
- **`task_context.mdc`**: Task context system with specification gulf prevention
- **`experiments.mdc`**: Networking experiments framework
- **`use-for-all-files-made.mdc`**: File creation standards
- **`update-target-profiles-rule.mdc`**: Target profile update rules

These rules are automatically applied when you work with me in Cursor, ensuring consistent behavior across all interactions.

## Using the `status_reporter.py` Script (Via Me)

I can run a helpful Python script (`status_reporter.py`) for you. **You don't need to run this script yourself; just ask me to do it.**

1.  **Getting a Status Table:**
    *   **How to ask:** "Can you run the status reporter?" or "What's the status of my leads and projects?"
    *   **What I do:** I run `python status_reporter.py`, which scans active leads and projects.
    *   **Output & My Proactive Follow-up:** I'll show you a table with a "Staleness" column. 
        *   If any items are marked `>7d old` (not updated in over a week), I **must** proactively ask if you want to provide an update, archive the lead, or mark the project as done.
        *   If any items show `Staleness: No Date` (because the `Last Updated` date in the file was unclear), I will point this out and ask if you can provide an update or a correct "Last Updated" date for that item.
        *   Based on your response, I'll then update the file or use commands to move it, following our established rules.

2.  **Getting Full Content for Summarization (e.g., for a larger LLM context window):**
    *   **How to ask:** "Dump all active leads for summarization." or "I need the text of all people files."
    *   **What I do:** I use `python status_reporter.py --dump-content [leads|projects|people]`.
        *   `python status_reporter.py --dump-content leads` (for active leads)
        *   `python status_reporter.py --dump-content projects` (for active projects)
        *   `python status_reporter.py --dump-content people` (for all people files)
    *   **Output:** I provide the full Markdown content of each relevant file, clearly separated, which you can then copy.

---

## Getting Started

**Remember: Just start talking to me in Cursor, and I'll help you keep things in order!**

The system is designed to be conversational and proactive—you don't need to remember all these details. I'll handle the file management, status updates, and automation based on our conversations.

For automation scripts, you can ask me to run them or use them directly from the command line. The Cursor rules ensure I follow your preferences automatically, so you can focus on the work rather than the system.
