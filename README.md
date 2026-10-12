# ebook

A reusable Codex skill for turning a selected conversation or note series into a chaptered, versioned EPUB booklet and delivering it to an e-reader. The content workflow is shared; the transfer route depends on the brand and model. The repository is named `ebook`, and the skill entry is `$ebook`.

**中文简介：** 用 `$ebook` 把指定对话整理成分章节 EPUB。后续补充内容会沿用同一本小册的章节和版次；传到阅读器时按品牌选择官方路径，并记录实际验证到的交付状态。

## Install

Clone this repository into your Codex skills directory as `ebook`, or copy its root files into a directory named `ebook` under that directory. Restart or refresh Codex if the skill is not yet listed.

```bash
git clone https://github.com/ERerGB/ebook.git ~/.codex/skills/ebook
```

Then invoke it in a Codex task:

> `$ebook` Turn this conversation into a short booklet and send the next edition to my Kobo.

> `$ebook` 把这段讨论续写进原来的小册，并准备传到我的 BOOX。

The skill can locate and update an existing booklet object; tell it which conversation or local notes to use and which device you intend to read on. A plain ChatGPT conversation may not have access to local Codex skills; start the task in Codex and reference that conversation when available.

## What it maintains

An object contains `book.json` for identity and chapter order, Markdown chapter files for editable text, `editions/` for EPUB and HTML, and `lifecycle.json` for releases and deliveries. This repository contains the skill and helper only; keep private book objects outside the repository.

The standard-library helper supports:

```text
init → edit chapters → build → inspect/validate → deliver → record delivery
                                      ↘ revise pending edition
after delivery + new content → next numbered edition
```

Run `python3 scripts/booklet.py --help` for commands. `build` can export the EPUB and HTML to a chosen folder. `send-booxdrop` is an optional adapter for a currently observed BOOXDrop LAN interface; other brands use their documented app, cloud, local Wi-Fi, or USB route and `record-delivery` after destination verification. The [object format](references/object-format.md) shows exact commands.

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
- A delivery record states what was verified: cloud upload, device listing, library indexing, or opening the book. These are distinct events.
- Never publish private source conversations, device IP addresses, account tokens, or booklet objects in this repository.
- Older editions are retained; removing or replacing device files is a separate user decision because reading positions and annotations may depend on them.

MIT licensed. This repository is independent of the listed reader brands and services.
