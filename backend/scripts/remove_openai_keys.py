#!/usr/bin/env python3
import re
from pathlib import Path

# Arquivo alvo
p = Path('backend/ai-service/app/config.py')
if not p.exists():
    # nada a fazer
    import re
    from pathlib import Path

    # Arquivo alvo
    p = Path('backend/ai-service/app/config.py')
    if not p.exists():
        # nada a fazer
        exit(0)

    text = p.read_text(encoding='utf-8')
    # Substitui chaves OpenAI que começam com sk- e seguem por letras/numeros
    pattern = re.compile(r"sk-[A-Za-z0-9]{16,}")
    new_text, n = pattern.subn("REDACTED_OPENAI_KEY", text)
    if n > 0:
        p.write_text(new_text, encoding='utf-8')
        print(f"Replaced {n} OpenAI key(s) in {p}")
    else:
        print("No OpenAI key patterns found in target file.")
