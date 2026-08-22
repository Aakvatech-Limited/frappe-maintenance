#!/usr/bin/env python3
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path.cwd()
BRANCH = __import__('os').environ.get('GITHUB_REF_NAME', '')

m = re.search(r'(?:version-|v)(14|15|16)(?:$|[^0-9])', BRANCH)
if not m:
    raise SystemExit(f'Unsupported branch name for automatic Frappe major detection: {BRANCH!r}')
major = int(m.group(1))
next_major = major + 1

# Detect app module by hooks.py.
hooks_files = [p for p in ROOT.glob('*/hooks.py') if p.is_file()]
if len(hooks_files) != 1:
    raise SystemExit(f'Expected exactly one app hooks.py at */hooks.py, found {len(hooks_files)}')
hooks_path = hooks_files[0]
app_name = hooks_path.parent.name

# Read metadata from hooks.py without importing the app.
hooks_text = hooks_path.read_text(encoding='utf-8')

def assigned_string(tree: ast.AST, name: str) -> str | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return node.value.value
    return None


def assigned_string_list(tree: ast.AST, name: str) -> list[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            if isinstance(node.value, (ast.List, ast.Tuple)):
                out = []
                for elt in node.value.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        out.append(elt.value.rsplit('/', 1)[-1])
                return out
    return []

hooks_tree = ast.parse(hooks_text, filename=str(hooks_path))
description = assigned_string(hooks_tree, 'app_description') or 'Frappe application'
author = assigned_string(hooks_tree, 'app_publisher') or ''
email = assigned_string(hooks_tree, 'app_email') or ''
required_apps = assigned_string_list(hooks_tree, 'required_apps')

# Prefer a literal __version__ from the package; otherwise use branch major.
version = f'{major}.0.0'
init_path = ROOT / app_name / '__init__.py'
if init_path.exists():
    try:
        init_tree = ast.parse(init_path.read_text(encoding='utf-8'), filename=str(init_path))
        detected = assigned_string(init_tree, '__version__')
        if detected:
            version = detected
    except SyntaxError:
        pass

# For version-* maintenance branches, normalize an obviously old major version.
try:
    current_major = int(version.split('.', 1)[0])
except Exception:
    current_major = major
if current_major != major:
    version = f'{major}.0.0'

requirements_file = ROOT / 'requirements.txt'
if not requirements_file.exists():
    requirements_file.write_text('', encoding='utf-8')

# Generate deterministic modern packaging metadata.
authors = ''
if author and email:
    authors = f'authors = [\n    {{ name = {author!r}, email = {email!r} }}\n]\n'
elif author:
    authors = f'authors = [\n    {{ name = {author!r} }}\n]\n'

# TOML strings require double quotes; repr() emits single quotes, normalize carefully.
def tq(value: str) -> str:
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'

authors = ''
if author and email:
    authors = f'authors = [\n    {{ name = {tq(author)}, email = {tq(email)} }}\n]\n'
elif author:
    authors = f'authors = [\n    {{ name = {tq(author)} }}\n]\n'

deps = {'frappe': f'>={major}.0.0,<{next_major}.0.0'}
for dep in required_apps:
    if dep != 'frappe':
        deps[dep] = f'>={major}.0.0,<{next_major}.0.0'

dep_lines = '\n'.join(f'{name} = {tq(spec)}' for name, spec in sorted(deps.items()))

pyproject = f'''[build-system]\nrequires = ["setuptools>=61.0"]\nbuild-backend = "setuptools.build_meta"\n\n[project]\nname = {tq(app_name)}\nversion = {tq(version)}\ndescription = {tq(description)}\n{authors}requires-python = ">=3.10"\ndynamic = ["dependencies"]\n\n[tool.setuptools.dynamic]\ndependencies = {{ file = ["requirements.txt"] }}\n\n[tool.setuptools.packages.find]\nwhere = ["."]\n\n[tool.bench.frappe-dependencies]\n{dep_lines}\n'''

(ROOT / 'pyproject.toml').write_text(pyproject, encoding='utf-8')
(ROOT / 'setup.py').write_text('from setuptools import setup\n\nsetup()\n', encoding='utf-8')

print(f'Modernized {app_name} for Frappe {major}')
print(f'Version: {version}')
print(f'Dependencies: {deps}')
