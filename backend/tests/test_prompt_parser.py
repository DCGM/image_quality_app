import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from text_classifier.prompt_parser import parse_prompt_file


def test_parse_prompt_file_extracts_classes_and_multi_choice(tmp_path: Path):
    p = tmp_path / 'communicative_mode.md'
    p.write_text(
        '''# Task context
Context.

# Task - text mode / slohový postup
- Optionally choose a second class only if it is present.

# Classes
- `narration` / `vyprávěcí` — recounts events
- `other_mode` — recognizable communicative mode not covered
- `uncertain` — cannot be determined

# Output
Write one or two class labels.
''',
        encoding='utf-8',
    )
    out = parse_prompt_file(p)
    assert out['id'] == 'communicative_mode'
    assert out['name'] == 'Text mode / slohový postup'
    assert out['enabled'] is True
    assert out['multi_choice'] is True
    assert out['max_choices'] == 2
    assert out['classes'] == [
            {'id': 'narration', 'label_en': 'Narration', 'label_cs': 'vyprávěcí', 'description': 'recounts events'},
            {'id': 'other_mode', 'label_en': 'Other mode', 'label_cs': 'other_mode', 'description': 'recognizable communicative mode not covered'},
            {'id': 'uncertain', 'label_en': 'Uncertain', 'label_cs': 'uncertain', 'description': 'cannot be determined'},
        ]


def test_parse_prompt_file_extracts_possible_classes_as_single_choice(tmp_path: Path):
    p = tmp_path / 'style.md'
    p.write_text(
        '''# Task
Some instructions.

# Possible classes
- `formal` — polished register
- `neutral` — neutral register
''',
        encoding='utf-8',
    )
    out = parse_prompt_file(p)
    assert out['name'] == 'Style'
    assert out['multi_choice'] is False
    assert out['max_choices'] == 1
    assert [item['id'] for item in out['classes']] == ['formal', 'neutral']


def test_parse_prompt_file_requires_classes(tmp_path: Path):
    p = tmp_path / 'broken.md'
    p.write_text('# Task\nNo classes here.', encoding='utf-8')
    with pytest.raises(ValueError, match='No classes found'):
        parse_prompt_file(p)
