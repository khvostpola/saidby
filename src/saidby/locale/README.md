# Message catalogs

Translated messages live here as `<language>/LC_MESSAGES/saidby.po`, compiled to `saidby.mo`
(committed, because the build does not compile them). saidby shows them for the language in
`--ui-lang`, `SAIDBY_UI_LANG` or the system locale, and falls back to English for anything not
translated. `saidby.pot` is the template extracted from the source.

Maintain them with `tools/i18n.py` (see CONTRIBUTING.md).
