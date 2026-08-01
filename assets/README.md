# Brand assets

Approved Shiroe brand assets. Each motion SVG embeds its PNG as a base64
data URI — no JavaScript, no web fonts, no external requests, no network
dependency of any kind.

| File | Use |
|---|---|
| `shiroe-banner-motion.svg` | README header. 2172×724. |
| `shiroe-banner.png` | Static fallback for contexts that strip SVG. |
| `shiroe-character-snapshot-motion.svg` | Character snapshot. 1672×941. |
| `shiroe-character-snapshot.png` | Static fallback. |

## Motion

Animation is CSS `@keyframes` — 13 per file, no SMIL, no script. GitHub
renders these through `<img>`, where an external SVG is its own document
and its stylesheet applies, so the motion runs.

`prefers-reduced-motion: reduce` sets `animation: none` and freezes every
layer. It does not strip the design — the static treatment is retained in
full.

## The xlink:href dedup

The approved source embedded the same base64 PNG **twice** on one `<image>`
element, once as `href` and once as `xlink:href`. That is an SVG 1.1
back-compat pattern, but duplicating a multi-megabyte payload doubles the
file for no rendering benefit: every renderer that matters resolves SVG2
`href`.

The duplicate was removed. The banner went 4.93 MB → 2.47 MB and the
snapshot 5.77 MB → 2.89 MB, which also puts both under GitHub's image-proxy
size ceiling — the 5.77 MB original was close enough to it to risk simply
not loading.

The embedded PNG is unchanged. Its SHA-256 still matches the standalone PNG
beside it byte for byte, so the package's identity guarantee holds:

```bash
shasum -a 256 assets/*.png
```

Rendering was verified in a browser before and after the dedup — identical.
