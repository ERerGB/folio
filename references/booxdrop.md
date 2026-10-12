# BOOXDrop local delivery

[BOOX's computer transfer guide](https://help.boox.com/hc/en-us/articles/10701399613076-Transfer-with-Your-Computer) instructs users to put computer and reader on the same LAN, open BOOXDrop on the reader, and use the URL it displays in a computer browser. `send2boox` is a separate account-based route.

The bundled helper was built from one observed BOOXDrop local page, not a published stable API. That page identified itself as `BOOX Drop`, exposed device model at `GET /api/device`, accepted multipart `POST /api/library/upload` with `parent=null`, `sender`, and `file`, and listed the result at `GET /api/library`. Recheck a different device or firmware rather than assuming those endpoints remain identical.

`send-booxdrop` accepts only an RFC 1918 IPv4 address with port. It checks page identity and expected model, checks for a same-named file, sends the EPUB, then verifies filename, size, and path in the library listing before recording the delivery. If the endpoint differs, use the current BOOXDrop UI and then `record-delivery` with observed evidence. The helper's library check does not prove the home UI has refreshed.

[BOOX's Library display guide](https://help.boox.com/hc/en-us/articles/8569338166932-Choose-a-Book-Display-Mode) distinguishes Scan Mode, Directory Mode, and Recent Files. If a transferred file is absent from the home list, check Directory Mode and the receiving folder first; then inspect scan settings if needed. Do not reset a device or remove old editions just to refresh a listing.
