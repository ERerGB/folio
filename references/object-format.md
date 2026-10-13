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
    <stem>-e001.sources.json
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
    {"id": "introduction", "title": "Introduction", "file": "chapters/01-introduction.md",
     "source_refs": [{"kind": "conversation", "id": "user-selected-source", "scope": "opening question"}],
     "revision_note": "Introduced the topic from the opening question"},
    {"id": "question", "title": "The Question", "file": "chapters/02-question.md",
     "source_refs": [{"kind": "conversation", "id": "user-selected-source", "scope": "clarifying turns"}],
     "revision_note": "Expanded after the user's clarification"}
  ]
}
```

Chapter IDs remain stable across editions. Use a new chapter when the argument actually gains a new section; otherwise edit the existing chapter. Optional chapter `source_refs` connect that chapter to its source turns or files; `revision_note` explains the current change. Each build saves a private `.sources.json` snapshot with chapter content hashes, sources, and revision notes. A later source or revision-note edit creates a new edition after delivery, even if the reading text stays the same. Old book objects without chapter metadata still work. A source reference records origin, not proof of a claim. The builder supports paragraphs, `##`/`###` headings, lists, blockquotes, emphasis, and HTTP(S) Markdown links. Convert tables and embedded app UI into readable prose or lists.

Typical commands, from this repository root:

```bash
python3 scripts/booklet.py init /path/to/books/sample-question --id sample-question --title 'A Sample Question' --language en
# Edit book.json and add chapter Markdown files.
python3 scripts/booklet.py build /path/to/books/sample-question
python3 scripts/booklet.py status /path/to/books/sample-question
python3 scripts/booklet.py send-booxdrop /path/to/books/sample-question --host 192.168.1.23:8085 --device 'ExampleModel'
python3 scripts/booklet.py archive /path/to/books/sample-question
```

`build --export-dir` copies only the current EPUB and HTML to a chosen output folder; source snapshots may contain private conversation IDs and stay in the local book object. The lifecycle ledger stores edition file paths relative to the object, so the folder can move. The first recorded external transfer freezes a pending edition; a later content or chapter-provenance edit becomes the next edition.

For a delivery made through a vendor app or USB, verify it at the destination, then record the observed result:

```bash
python3 scripts/booklet.py record-delivery /path/to/books/sample-question \
  --device 'Reader name' --transport 'vendor-app' \
  --remote-path 'My Books/sample-question-e001.epub' \
  --verified-size 12345 --stage library-indexed \
  --evidence 'Visible in the device My Books list'
```

Stages are ordered: `uploaded` means a receiver accepted the EPUB; `device-file` means the file is listed on the device; `library-indexed` means it appears in the reader's book library; `opened` means it opened in the reader. `--stage` defaults to `uploaded` when omitted. Record only the stage supported by the evidence. Call `record-delivery` again with the same edition, device, transport, path, and size to advance its stage; the history is preserved. Stage regression or a changed destination identity is rejected. Existing delivery records without a structured stage are retained and can be advanced after a new check.

The script checks that the reported size matches the built EPUB; it cannot independently verify manual evidence. Describe what was actually seen. `archive` and `resume` change only the local object's state. They do not touch a device or cloud account.
