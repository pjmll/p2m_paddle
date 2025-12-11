#!/usr/bin/env python3
"""
Smoke test for Knowledge Graph generation.

- Looks for export/<base>_structured.md (base derived from test.pdf if present)
- If not present, writes a small test markdown to export/test_structured.md
- Calls KnowledgeGraphGenerator.generate_knowledge_graph and prints the output path
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.knowledge_graph_generator import KnowledgeGraphGenerator

EXPORT_DIR = ROOT / 'export'
EXPORT_DIR.mkdir(exist_ok=True)

# Try to find an existing structured md
candidates = list(EXPORT_DIR.glob('*_structured.md'))
if candidates:
    md_path = candidates[0]
else:
    # create a simple test markdown
    md_path = EXPORT_DIR / 'test_structured.md'
    md_content = """# Test Document\n\nThis is a test document for Knowledge Graph generation.\n\n## Entities\n\n- Alice: a researcher\n- Bob: a collaborator\n\n## Relationships\n\n- Alice collaborates_with Bob\n"""
    md_path.write_text(md_content, encoding='utf-8')

print(f"Using markdown: {md_path}")
md_text = md_path.read_text(encoding='utf-8')

try:
    kg = KnowledgeGraphGenerator()
    out = kg.generate_knowledge_graph(md_text, EXPORT_DIR, md_path.stem)
    print(f"KG generated: {out}")
except Exception as e:
    print(f"KG generation failed: {e}")
    raise
