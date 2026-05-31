from __future__ import annotations

import re
from pathlib import Path

_CLASS_HEADING_RE = re.compile(r"^#\s+(?:Possible\s+)?Classes\s*$", re.IGNORECASE)
_HEADING_RE = re.compile(r"^#\s+")
_CLASS_LINE_RE = re.compile(
    r"^\s*-\s*`(?P<id>[^`]+)`(?:\s*/\s*`(?P<label_cs>[^`]+)`)?\s*(?:[—-]\s*(?P<description>.*))?$"
)
_TASK_TITLE_RE = re.compile(r"^#\s+Task\s*(?:[-–—:]\s*(?P<title>.+))?$", re.IGNORECASE)


def _humanize(identifier: str) -> str:
    return identifier.replace('_', ' ').strip().capitalize()


def _extract_name(text: str, fallback: str) -> str:
    for line in text.splitlines():
        match = _TASK_TITLE_RE.match(line.strip())
        if match and match.group('title'):
            return match.group('title').strip().capitalize()
    return _humanize(fallback).title()


def _extract_classes(text: str) -> list[dict[str, str]]:
    classes: list[dict[str, str]] = []
    in_classes = False
    for line in text.splitlines():
        stripped = line.strip()
        if _CLASS_HEADING_RE.match(stripped):
            in_classes = True
            continue
        if in_classes and _HEADING_RE.match(stripped):
            break
        if not in_classes:
            continue
        match = _CLASS_LINE_RE.match(line)
        if match:
            class_id = match.group('id').strip()
            label_cs = (match.group('label_cs') or class_id).strip()
            description = (match.group('description') or '').strip() or None
            classes.append({
                'id': class_id,
                'label_en': _humanize(class_id),
                'label_cs': label_cs,
                'description': description,
            })
    if not classes:
        raise ValueError('No classes found in prompt file')
    return classes


def _infer_choice_limits(text: str) -> tuple[bool, int]:
    lower = text.lower()
    multi_markers = (
        'one or two class labels',
        'one or two class label',
        'optionally choose a second class',
        'optionally choose a second',
        'choose up to two',
        'select up to two',
        'multiple classes',
        'multiple options',
    )
    if any(marker in lower for marker in multi_markers):
        return True, 2
    return False, 1


def parse_prompt_file(path: Path) -> dict:
    text = path.read_text(encoding='utf-8')
    task_id = path.stem
    multi_choice, max_choices = _infer_choice_limits(text)
    return {
        'id': task_id,
        'name': _extract_name(text, task_id),
        'description_md': text,
        'multi_choice': multi_choice,
        'max_choices': max_choices,
        'enabled': True,
        'classes': _extract_classes(text),
    }


def load_prompts(prompts_dir: Path) -> list[dict]:
    return [parse_prompt_file(p) for p in sorted(prompts_dir.glob('*.md'))]
