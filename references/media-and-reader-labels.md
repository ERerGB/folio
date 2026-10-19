# Booklet media and reader labels

Keep all book-specific images and provenance in the private booklet object. The Folio skill repository contains only the reusable workflow and builder.

## Figures in the reading flow

Put source figures near the source passage they explain, using standalone local Markdown image lines in a chapter. Preserve their reading order and caption or alt text. Do not move all figures to an appendix merely to simplify conversion. The builder resolves image paths relative to the chapter file, packages PNG, JPEG, or GIF images, and includes their bytes in the edition identity. Missing, unsupported, or outside-object images stop the build. Review whether text baked into a figure remains untranslated in a parallel-text edition.

## Cover choice and review

Choose a cover from the user's material, a source image with appropriate reuse rights, or a newly generated image. Web search can help find visual references or licensed assets; it does not grant reuse rights by itself. A cover should help distinguish the book at a small bookshelf size, especially in grayscale on an e-ink reader. Check that its imagery does not imply a source, author, or endorsement that the work does not have. Record the final cover file, generation or source method, and usage notes privately in `book.json`. Do not put private source artwork or generated book assets in this repository.

The builder reads `cover.file`, hashes the image, embeds it with EPUB `cover-image` metadata, and adds an opening cover page. If `cover.sha256` is supplied, it must match the file. Replacing a cover after delivery creates a new edition; keep the prior edition and its reading position intact.

## Device-facing title

Use `title` for the full work title and `reader_title` for a concise shelf label. Make the shelf label distinctive enough to tell similar books apart at a glance: retain the subject or publication cue, then a language cue when useful. `filename_stem` controls the versioned file name independently and should be short and filesystem-safe. The EPUB metadata uses `reader_title`; the full title remains in the opening page and description. Device libraries may use filename, EPUB metadata, or cached values, so inspect the target's actual bookshelf and open the book when possible. A browser mockup is a design check, not device verification.
