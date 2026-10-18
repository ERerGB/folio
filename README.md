# Folio

A reusable Codex skill for turning a selected conversation, note series, or webpage into a chaptered, versioned EPUB booklet and delivering it to an e-reader. It also supports parallel-text editions. The content workflow is shared; the transfer route depends on the brand and model. The repository is named `folio`, and the skill entry is `$folio`.

**中文简介：** 用 `$folio` 把指定对话整理成分章节 EPUB，并默认传到阅读器、核实交付。后续补充内容会沿用同一本小册的章节和版次。只有明确说“只要草稿／文件”时才跳过传送。

## Install

Clone this repository into your Codex skills directory as `folio`, or copy its root files into a directory named `folio` under that directory. Restart or refresh Codex if the skill is not yet listed.

```bash
git clone https://github.com/ERerGB/folio.git ~/.codex/skills/folio
```

Then invoke it in a Codex task:

> `$folio` Turn this conversation into a short booklet for my Kobo.

> `$folio` 把这段讨论续写进原来的小册，给我的 BOOX 看。

The skill can locate and update an existing booklet object. An explicit `$folio` invocation includes delivery by default, even if the request does not repeat "send." It looks for a known reader in the conversation or delivery history and asks for missing connection details early. Tell it which conversation or local notes to use and which device you intend to read on when that is not already known. A plain ChatGPT conversation may not have access to local Codex skills; start the task in Codex and reference that conversation when available.

You can ask Folio to preserve the original wording of a source article or note. It will keep the text in order, record provenance, and identify media that could not be included in the EPUB.

For a webpage URL, Folio uses the browser's Print / Save as PDF interface through computer use to capture a source snapshot. It checks the print preview and saved PDF for clipping or missing sections, choosing paper size and scale for the actual page rather than assuming A4. A request for an English–Chinese or other parallel-text edition keeps original and translated passages aligned; when you specify Astra, Folio uses that model or tells you if a model switch is needed.

If you previously installed this skill as `ebook`, remove the old skill folder after installing `folio` so Codex does not show two entries for the same workflow. Existing booklet objects and edition identifiers remain valid.

## What it maintains

An object contains `book.json` for identity, chapter order, and per-chapter source references; Markdown chapter files for editable text; `editions/` for EPUB, HTML, and private source snapshots; and `lifecycle.json` for releases and staged deliveries. This repository contains the skill and helper only; keep private book objects outside the repository.

The standard-library helper supports:

```text
init → edit chapters → build → inspect/validate → deliver → record delivery
                                      ↘ revise pending edition
after delivery + new content → next numbered edition
```

Run `python3 scripts/booklet.py --help` for commands. `build` can export the EPUB and HTML to a chosen folder while keeping source snapshots private. `send-booxdrop` is an optional adapter for a currently observed BOOXDrop LAN interface; other brands use their documented app, cloud, local Wi-Fi, or USB route and `record-delivery` after destination verification. A delivery advances through `uploaded`, `device-file`, `library-indexed`, and `opened` as evidence becomes available. The [object format](references/object-format.md) shows exact commands.

## Seven-brand route survey

| Brand | Practical entry for a personal EPUB | Special check |
| --- | --- | --- |
| BOOX | BOOXDrop on the same LAN | Confirm the reader model and file in Library |
| Kindle | Send to Kindle | Confirm conversion and sync in Kindle Library |
| Kobo | USB; Google Drive/Dropbox on supported models | Confirm model eligibility and My Books import |
| PocketBook | Send-to-PocketBook, cloud, Dropbox, or USB | Confirm synchronized Library folder |
| reMarkable | Web/desktop/mobile app or USB web interface | Confirm document list after sync |
| Supernote | Browse & Access over LAN, cloud, or USB | Confirm device destination folder |
| tolino | tolino webreader/app cloud upload | Confirm download into My books |

Routes and model caveats are linked to vendor documentation in [device routes](references/device-routes.md). Research last checked 2026-10-13.

## Virtual environments

Existing tools cover different parts of the workflow: [EPUBCheck](https://github.com/w3c/epubcheck) validates the EPUB package and offers a Docker route; [Kindle Previewer](https://kdp.amazon.com/en_US/help/topic/G202131170) previews Kindle layout; [KOReader's emulator](https://github.com/koreader/koreader-base#device-emulation) previews generic reading at device-like dimensions; [calibre Content server](https://manual.calibre-ebook.com/server.html), [Calibre-Web](https://github.com/janeczku/calibre-web), and [Komga](https://github.com/gotson/komga) provide browser libraries, with container options for the latter two. These do not emulate each vendor's stock library or prove successful transfer. See [virtual environments](references/virtual-environments.md) for when each is useful.

## Boundaries

- Only BOOXDrop's observed LAN endpoint is automated here. It is not a vendor-supported public API and can change with firmware.
- A delivery record states what was verified: cloud upload, device listing, library indexing, or opening the book. These are distinct stages. Device delivery remains unconfirmed while only an upload is visible.
- Never publish private source conversations, device IP addresses, account tokens, or booklet objects in this repository.
- Older editions are retained; removing or replacing device files is a separate user decision because reading positions and annotations may depend on them.

Licensed under Apache-2.0. This repository is independent of the listed reader brands and services.
