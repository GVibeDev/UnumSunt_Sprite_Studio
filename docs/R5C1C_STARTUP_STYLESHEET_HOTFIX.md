# R5c1c — Startup Stylesheet Hotfix

## Symptom
Application startup stopped in `ExportStudio._update_background_swatch()` with:

`NameError: name 'color' is not defined`

## Cause
A dynamic Qt stylesheet inside an f-string contained unescaped QSS braces after the R5c1c readability pass. Python therefore interpreted the contents of the QSS block as an f-string expression.

## Fix
The stylesheet now escapes the Qt block braces correctly while preserving the white status/swatch text rule:

`QLabel {{ color: #f4f6f8; background: rgb(...); border: 1px solid #777; }}`

## Scope
No theme logic, workflow logic, export behavior or build/runtime bootstrap behavior was changed.
