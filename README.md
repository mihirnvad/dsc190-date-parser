# nldate

`nldate` is a small, dependency-free Python package for turning common
natural-language date phrases into `datetime.date` objects.

```python
from datetime import date
from nldate import parse

assert parse("5 days before December 1st, 2025") == date(2025, 11, 26)
assert parse("two weeks from tomorrow", today=date(2026, 5, 13)) == date(2026, 5, 28)
```

## Development

```bash
uv run pytest
uv run ruff check
uv run mypy
```
