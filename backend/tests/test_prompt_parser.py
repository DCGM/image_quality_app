import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from text_classifier.prompt_parser import parse_prompt_file


def test_parse_prompt_file(tmp_path: Path):
    p = tmp_path / 'style.md'
    p.write_text('# Style\nSome instructions', encoding='utf-8')
    out = parse_prompt_file(p)
    assert out['id'] == 'style'
    assert out['name'] == 'Style'
    assert out['enabled'] is True
