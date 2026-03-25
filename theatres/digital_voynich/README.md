# Digital Voynich Theatre

A living manuscript. The simulation runs. The output is encoded into glyphs before display.

The reader can open and close the book. Nothing else is accessible from the outside.

## What It Is

Seven agents — one per plane — run the WORLD13 simulation continuously. Every session
is encoded into a unique glyph alphabet and rendered as a manuscript page. No agent names,
K values, protocol names, or session text ever appear in the output.

The reader sees glyphs, illustrations, and page rhythm. The simulation is real.
The encoding is one-way. The manuscript accumulates.

## Running

```bash
make voynich
```

Open `http://localhost:8001/voynich` to read the book.

## Illustrations

Pages may contain illustrations that encode significant events:
- **Concentric circles** — liberation event
- **Nested rectangles with arrow** — intervention window
- **Nested triangles** — shadow session
- **Network graph** — contagion event
- **Wave pattern** — crisis phase

## Visual Register

Page appearance encodes the dominant register:
- **Light parchment** — standard sessions
- **Dark blue** — shadow sessions (denser text)
- **Cool dark** — transition/resolution
- **Warm parchment, sparse** — liberation events

Two different instances produce visually distinct but structurally similar manuscripts.
