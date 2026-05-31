# Administrator Guide

## Importing prompt tasks

1. Log in as a superuser.
2. Open the Admin page and go to the **Import** tab.
3. Click **Import prompts/*.md**.
4. Review imported task definitions before annotation begins.

The import operation upserts tasks by ID, so re-importing a prompt updates the existing database task (including class descriptions) while preserving the same task ID and all existing annotations.

## Editing tasks in the application

On the Admin page **Tasks** tab, click the edit icon on any task row to open the task editor:

- **Task name**: Short annotator-facing label.
- **Enabled**: Disabled tasks are hidden from annotators and rejected in submissions.
- **Multi-choice**: Switches the annotation widget between radio buttons and checkboxes.
- **Max choices**: Limits checkbox selections for multi-choice tasks.
- **Prompt markdown**: Full task instructions shown or stored for downstream context.
- **Choices**: Class IDs, English labels, Czech labels, and optional descriptions. Descriptions are shown as tooltips next to class labels during annotation.

New tasks can be created with the **New task** button (task ID is editable only on creation). Existing tasks can be enabled/disabled with the toggle button or permanently deleted.

## Uploading and managing texts

In the Admin page **Texts** tab:

- **Upload**: Select a `.jsonl` file and click **Upload**. Each line must include:

| Field | Type | Description |
|---|---|---|
| `id` | string | Stable unique text identifier. |
| `text` | string | Text shown to annotators. |
| `language` | string | ISO 639-3 language code such as `eng` or `ces`. |

Any additional JSON fields are stored unchanged for export and analysis. Re-uploading a file with the same IDs upserts (updates) the records.

- **Browse and search**: Use the search box to filter texts. Results are paginated (50 per page).
- **Suspend / unsuspend**: Click the pause/play icon on a text row to toggle its suspended state. Suspended texts are excluded from the annotation queue without being deleted.

## Operational checklist

- Import prompts after changing files in `prompts/`. This also refreshes per-class descriptions.
- Confirm that tasks expected to allow two answers are marked **Multi-choice**.
- Keep class IDs stable once annotation has started.
- Disable rather than delete tasks if historical annotations should remain interpretable.
- Suspend rather than delete texts if they should be temporarily removed from the annotation queue.
- Use strong production values for authentication secrets and admin credentials.
