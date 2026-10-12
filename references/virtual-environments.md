# Virtual reading and library environments

There is no single virtual device that reproduces all seven brands' firmware, account sync, library indexing, and reading behavior. Use the environment that answers the current question:

| Need | Available environment | What it can establish | What it cannot establish |
| --- | --- | --- | --- |
| EPUB specification conformance | [W3C EPUBCheck](https://github.com/w3c/epubcheck), including its documented Docker build/run path | EPUB package and markup validity | Brand library ingestion or reading layout |
| Kindle layout preview | [Amazon Kindle Previewer](https://kdp.amazon.com/en_US/help/topic/G202131170) desktop app; KDP Online Previewer is tied to the publishing workflow | How an EPUB converts/displays across Kindle-like sizes and settings | Personal-document sync or exact physical device behavior |
| Generic e-ink reading preview | [KOReader desktop emulator](https://github.com/koreader/koreader-base#device-emulation) | Typography and pagination in an open reader at selected resolution/DPI | Any vendor's stock UI or cloud |
| Self-hosted browser bookshelf | [calibre Content server](https://manual.calibre-ebook.com/server.html) or [Calibre-Web](https://github.com/janeczku/calibre-web) with its documented Docker image | Browsing, downloading, and browser reading from a local collection | Automatic import into a proprietary device library |
| Self-hosted multi-reader server | [Komga](https://github.com/gotson/komga) and its [Docker instructions](https://komga.org/docs/installation/docker/) | Web reading, OPDS, and its documented Kobo/KOReader integrations | Official Kobo cloud sync or universal device support |
| Vendor-hosted storage alternative | [Supernote private cloud beta](https://support.supernote.com/en_US/setting-up-your-own-supernote-private-cloud-beta) | A documented self-hosted Supernote sync path where supported | A Supernote device emulator or a general EPUB distribution service |

Use a virtual bookshelf to rehearse collection organization, and a reader simulator to inspect the book. Neither is a substitute for checking a real device after delivery. A Docker service that offers OPDS may help compatible reader apps, but the device must actually support or run one of those apps.

For a portable conformance check, follow the current EPUBCheck repository's Docker instructions or run its released command-line version. For a quick browser review, open the HTML companion generated beside the EPUB. Do not upload private source material to an online preview site without the user's authorization.
