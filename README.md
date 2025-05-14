# Your Cursor CRM & Project Manager

Welcome! This system helps you manage your contacts, leads, and projects using simple Markdown files. It is designed to be used within an AI-native code editor like Cursor, where your primary way of interacting with it is by talking to me, your AI assistant. I'm designed to be proactive and help you stay organized with minimal explicit instruction for routine tasks.

## How It Works: A Conversational Approach

Think of me as your operational assistant for this CRM. You can provide information through conversation, paste meeting transcripts, share recollections, or give specific instructions. I'll interpret this information to:

*   **Identify and Capture:** When you mention new contacts, companies, or potential opportunities, I'll offer to create the necessary files (`/people/`, `/active_leads/`, `/outreach/`) and populate them with the details you provide.
*   **Log Interactions & Infer Updates:** If you share a meeting summary, call notes, or even a casual update like "Just got off a call with X, and they said Y," I will:
    *   Identify the relevant lead, project, or person.
    *   Summarize key discussion points, decisions, and action items, adding them to the appropriate file(s).
    *   **Intelligently update status fields:** Based on the context of our conversation (e.g., "Proposal sent to Client X"), I'll infer if `Stage`, `Next Step` (for leads), or `Current Status`, `Next Milestone` (for projects) need updating. I'll always update the `Last Updated` date.
    *   *For straightforward updates (like adding notes), I'll proceed and then let you know what I did. For more significant inferred changes (like changing a project's core status), I'll state my understanding and intended update, asking for your confirmation before proceeding.*
*   **Proactively Manage File Lifecycles:**
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

## Using the `status_reporter.py` Script (Via Me)

I can run a helpful Python script (`status_reporter.py`) for you:

1.  **Getting a Status Table:**
    *   **How to ask:** "Can you run the status reporter?" or "What's the status of my leads and projects?"
    *   **What I do:** I run `python status_reporter.py`, which scans active leads and projects.
    *   **Output & My Proactive Follow-up:** I'll show you a table with a "Staleness" column. 
        *   If any items are marked `>7d old` (not updated in over a week), I **must** proactively ask if you want to provide an update, archive the lead, or mark the project as done.
        *   If any items show `Staleness: No Date` (because the `Last Updated` date in the file was unclear), I will point this out and ask if you can provide an update or a correct "Last Updated" date for that item.
        *   Based on your response, I'll then update the file or use commands to move it, following our established rules.

2.  **Getting Full Content for Summarization (e.g., for a larger LLM context window):
    *   **How to ask:** "Dump all active leads for summarization." or "I need the text of all people files."
    *   **What I do:** I use `python status_reporter.py --dump-content [leads|projects|people]`.
        *   `python status_reporter.py --dump-content leads` (for active leads)
        *   `python status_reporter.py --dump-content projects` (for active projects)
        *   `python status_reporter.py --dump-content people` (for all people files)
    *   **Output:** I provide the full Markdown content of each relevant file, clearly separated, which you can then copy.

---

Just start talking, and I'll help you keep things in order!