# Booklet object

Keep each booklet in a durable folder, separate from this skill repository:

```text
books/<object-id>/
  book.json
  lifecycle.json
  chapters/
    01-introduction.md
    02-question.md
  editions/
    <stem>-e001.epub
    <stem>-e001.html
```

Example `book.json`:

```json
{
  "id": "sample-question",
  "title": "A Sample Question",
  "filename_stem": "sample-question",
  "subtitle": "A short research booklet",
  "language": "en",
  "description": "An exploratory booklet; claims require review.",
  "source_refs": [
    {"kind": "conversation", "id": "user-selected-source", "scope": "original discussion"}
  ],
  "chapters": [
    {"id": "introduction", "title": "Introduction", "file": "chapters/01-introduction.md"},
    {"id": "question", "title": "The Question", "file": "chapters/02-question.md"}
  ]
}
```

Chapter IDs remain stable across editions. Use a new chapter when the argument actually gains a new section; otherwise edit the existing chapter. A source reference records origin, not proof of a claim. The builder supports paragraphs, `##`/`###` headings, lists, blockquotes, emphasis, and HTTP(S) Markdown links. Convert tables and embedded app UI into readable prose or lists.

Typical commands, from this repository root:

```bash
python3 scripts/booklet.py init /path/to/books/sample-question --id sample-question --title 'A Sample Question' --language en
# Edit book.json and add chapter Markdown files.
python3 scripts/booklet.py build /path/to/books/sample-question
python3 scripts/booklet.py status /path/to/books/sample-question
python3 scripts/booklet.py send-booxdrop /path/to/books/sample-question --host 192.168.1.23:8085 --device 'ExampleModel'
python3 scripts/booklet.py archive /path/to/books/sample-question
```

`build --export-dir` copies the current EPUB and HTML to a chosen output folder. The lifecycle ledger stores edition file paths relative to the object, so the folder can move. The first verified delivery moves a pending edition into releases; a later content edit becomes the next edition.

For a delivery made through a vendor app or USB, verify it at the destination, then record the observed result:

```bash
python3 scripts/booklet.py record-delivery /path/to/books/sample-question \
  --device 'Reader name' --transport 'vendor-app' \
  --remote-path 'My Books/sample-question-e001.epub' \
  --verified-size 12345 --evidence 'Visible in the device My Books list'
```

The script checks that the reported size matches the built EPUB; it cannot independently verify manual evidence. Describe what was actually seen. `archive` and `resume` change only the local object's state. They do not touch a device or cloud account.
