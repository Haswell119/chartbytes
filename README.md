# ChartBytes — chart image API

Turn a URL into a chart image. PNG or SVG, generated server-side — for **emails,
GitHub READMEs, Notion, Slack, PDF reports, and agent output**. No browser, no JS, no
account: a plain `<img src="...">` or `![chart](...)` is all it takes.

> **Live:** <https://chartbytes.meridian-digital.pro> · **Buy Pro:** <https://buy.stripe.com/fZu7sNdbW1HPgNSgOrgUM05>

## Example

```
https://chartbytes.meridian-digital.pro/chart?t=bar&d=12,19,8,24&labels=Q1,Q2,Q3,Q4&title=Sales
```

![example](https://chartbytes.meridian-digital.pro/chart?t=bar&d=12,19,8,24&labels=Q1,Q2,Q3,Q4&title=Sales)

In Markdown:

```markdown
![Sales](https://chartbytes.meridian-digital.pro/chart?t=bar&d=12,19,8,24&labels=Q1,Q2,Q3,Q4&title=Sales)
```

## Why a chart *image* API?

Charting libraries render in a browser. But email clients, READMEs, Notion, Slack
messages and report PDFs have no browser — you need a **static image URL**. ChartBytes
gives you that URL with zero setup, so a chart renders anywhere an `<img>` does.

## Chart types

| type | description |
|------|-------------|
| `bar` | vertical bar chart (grouped when multiple series) |
| `hbar` | horizontal bar chart |
| `stacked` | stacked bar chart |
| `pie` | pie chart |
| `donut` | donut chart |

## API

`GET /chart` (or `POST /chart` with JSON for long payloads)

| param | meaning | default |
|-------|---------|---------|
| `t` / `type` | chart type (above) | `bar` |
| `d` / `data` | comma-separated numbers; `\|` separates series | required |
| `labels` | comma-separated category labels | `1,2,3…` |
| `title` | chart title | — |
| `w` / `width`, `h` / `height` | size in px | `600` × `300` |
| `format` | `png` or `svg` | `png` |
| `theme` | `light` (free) · `dark`, `brand` (Pro) | `light` |

### POST example

```bash
curl -X POST https://chartbytes.meridian-digital.pro/chart \
  -H 'Content-Type: application/json' \
  -d '{"type":"donut","data":[12,19,8,24],"labels":["Q1","Q2","Q3","Q4"],"title":"Revenue"}'
```

### Multiple series (grouped / stacked)

```
.../chart?t=bar&d=4,8,6|2,3,4&labels=X,Y,Z      # grouped bars
.../chart?t=stacked&d=4,8,6|2,3,4&labels=X,Y,Z  # stacked bars
```

## Pricing

- **Free** — 500 renders/month, light theme, no watermark, no account.
- **Pro (one-time $9)** — dark + brand themes, 25,000 renders/month, immutable caching
  on content-addressed URLs. **<https://buy.stripe.com/fZu7sNdbW1HPgNSgOrgUM05>**

After checkout you receive a license key; pass it as `&lic=<key>` on any chart request.

## Self-host

```bash
pip install -r requirements.txt
STRIPE_SECRET_KEY=… STRIPE_PRICE_ID=… CHART_LICENSE_SECRET=… python server.py
```

Pure Python stdlib + Pillow (PNG); SVG rendering needs no dependencies. No database,
no accounts, stateless — the whole service is one file.

## License

MIT. Built by Meridian Digital.
