# Task Definitions and Prompt Import

Task definitions are the central configuration object for annotation. A task controls the annotator-facing name, markdown prompt, allowed class choices, whether multiple classes may be selected, and the maximum number of selected classes.

## Canonical task JSON

```json
{
  "id": "style",
  "name": "Style",
  "description_md": "# Task\nCharacterise the register/style…",
  "multi_choice": true,
  "max_choices": 2,
  "enabled": true,
  "classes": [
    {"id": "formal", "label_en": "Formal", "label_cs": "formální", "description": "elevated, conventionally polished language"},
    {"id": "neutral", "label_en": "Neutral", "label_cs": "neutrální", "description": null}
  ]
}
```

## Markdown prompt format

Each prompt in `prompts/{task_id}.md` should contain a classes section. The importer accepts either heading:

- `# Classes`
- `# Possible classes`

Class lines must use backticked IDs. Czech labels are optional and can be written after a slash.

```markdown
# Task - text mode / slohový postup
- Choose one primary class.
- Optionally choose a second class only if it is clearly present.

# Classes
- `narration` / `vyprávěcí` — recounts events, actions, or happenings over time
- `description` / `popisný` — depicts persons, objects, places, situations, or qualities
- `uncertain` — cannot be determined reliably
```

The imported classes become:

| Markdown | Imported field |
|---|---|
| Backticked class ID | `classes[].id` |
| Humanized class ID | `classes[].label_en` |
| Backticked label after `/` | `classes[].label_cs` |
| Missing Czech label | Falls back to the class ID |
| Text after `—` | `classes[].description` (shown as tooltip; `null` if absent) |

## Single-choice versus multi-choice

The importer marks a task as multi-choice when prompt text contains instructions such as:

- `one or two class labels`
- `Optionally choose a second class`
- `choose up to two`
- `multiple classes`

Imported multi-choice tasks currently default to `max_choices: 2`. All other tasks are imported as single-choice with `max_choices: 1`.

Administrators can adjust this in the web application after importing prompts.

## Validation rules

- A task must have at least one class choice.
- Single-choice tasks must have `max_choices = 1`.
- `max_choices` cannot exceed the number of available class choices.
- Annotator submissions must select only class IDs present in the task definition.
- Multi-choice submissions must include at least one class and no more than `max_choices` classes.
