# Leaflet 1.9.4

The map on the base station's page. It is stored here compressed and served from the board's flash, so the page needs no
script from anywhere else. Only the map imagery comes from the internet, fetched by the browser.

- From the npm package `leaflet@1.9.4`, `dist/leaflet.js` and `dist/leaflet.css`.
- Checked against the hashes on Leaflet's download page before compressing:
  - `leaflet.js` sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=
  - `leaflet.css` sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=
- Compressed with gzip level 9, with no file name or time in the header, so the same input gives the same bytes.
- BSD 2-Clause, see [LICENSE](./LICENSE).

To check a file: `gunzip -c leaflet.js.gz | openssl dgst -sha256 -binary | openssl base64`
