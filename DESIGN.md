# Design notes

## Why this doesn't look like the App Store copy described

The original copy (carried over from the Flutter app's listing) describes "a premium,
high-contrast newsprint palette (warm cream background, rich black ink, crimson accents)
and classic serif typography (Lora and Playfair Display)." That's a coherent pitch, but
it's also become the default look any AI design tool reaches for when asked to make
something "editorial" — cream/ivory background, black ink, a red or terracotta accent,
Playfair Display for headlines. It's the new generic, in the same way a certain shade of
purple-on-white became the default "modern SaaS" look a few years ago.

Quiet Feed's actual differentiator isn't "looks like a newspaper" — it's "your feeds get
sealed shut once a day, like mail arriving, not like a feed refreshing." That's a more
specific idea than "newspaper," and it suggested a more specific visual language.

## The signature device: the Seal

Instead of a masthead, Quiet Feed's signature mark is a postmark-style stamp — "the Seal"
(`src/lib/components/Seal.svelte`) — that appears once an edition is fully read and closed
for the day. It's deliberately not a perfect circle (slight rotation, a faint double ring)
to read as hand-stamped rather than vector-perfect. It's the one place in the UI that's
allowed to be a little theatrical; everything else stays quiet on purpose.

The accent palette follows from the same idea — airmail envelope stripes (the red-and-blue
diagonal border on old international mail) rather than newsprint crimson. Two accents
instead of one gives the postal motif somewhere to live (the Seal in stamp-red, links and
the reading-progress bar in airmail-blue) without it reading as "the app's brand color."

## Type system — three roles, not two

- **Fraunces** (display) — headlines, the masthead-equivalent "Today's edition" text, the
  Seal's "№" mark. Fraunces has enough optical-size personality to carry a few large
  moments without needing decoration around it. Not Playfair Display, deliberately — that
  pairing (cream + Playfair) is exactly the combination this is trying to avoid.
- **Source Serif 4** (body) — the actual reading face. Chosen for being a quieter,
  more neutral serif than Fraunces, so the two don't compete inside a single screen.
- **JetBrains Mono** (utility/"dateline") — issue numbers, timestamps, feed names, form
  labels. The conceit: a postmark or ledger stamp is typewritten, not hand-lettered, so the
  "metadata voice" of the app borrows that register. This is also what gives the UI most of
  its restraint — small caps-ish mono labels read as quiet annotations rather than UI noise.

## Palette

Defined as CSS custom properties in `src/app.css` under `@theme`, with a `.dark` variant:

| Token | Light | Role |
|---|---|---|
| `--color-paper` | `#E6E3DA` | Background — a cool, grey-leaning archival paper, not cream |
| `--color-ink` | `#20242C` | Primary text — a soft blue-black, not pure black |
| `--color-stamp` | `#A8392C` | The Seal, destructive actions, errors — postmark red |
| `--color-airmail` | `#2A4A6B` | Links, progress indicator, focus states — postal blue |
| `--color-line` | `#C7C3B6` | Hairline dividers |

Dark mode isn't an inverted light mode — it shifts toward a near-black ink background with
paper-toned text, and the accent colors lighten/desaturate slightly so they hold contrast
without turning neon.

## Layout choices

No bordered cards, no dense multi-column broadsheet grid (the other newspaper cliché worth
naming and avoiding deliberately). Articles are separated by a single hairline rule, full
width, generous vertical rhythm — closer to a well-set reading list than a newspaper page
layout. The one deliberately "designed" moment is the closed-edition state: a large Seal,
centered, with nothing else competing for attention — the calm payoff for finishing a day's
reading, instead of a badge count resetting to zero.
