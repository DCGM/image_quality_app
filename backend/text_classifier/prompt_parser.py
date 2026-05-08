from __future__ import annotations

from pathlib import Path


def parse_prompt_file(path: Path) -> dict:
    text = path.read_text(encoding='utf-8')
    task_id = path.stem
    return {
        'id': task_id,
        'name': task_id.replace('_', ' ').title(),
        'description_md': text,
        'multi_choice': False,
        'max_choices': 1,
        'enabled': True,
        'classes': [
            {'id': 'yes', 'label_en': 'Yes', 'label_cs': 'ano'},
            {'id': 'no', 'label_en': 'No', 'label_cs': 'ne'},
        ],
    }


def load_prompts(prompts_dir: Path) -> list[dict]:
    return [parse_prompt_file(p) for p in sorted(prompts_dir.glob('*.md'))]
