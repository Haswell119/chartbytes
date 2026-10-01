#!/usr/bin/env python3
"""Generate high-intent SEO landing pages for the now-indexed ChartBytes custom domain.

Targets generic, high-volume chart-image queries (not the low-volume brand term), each a
real working page: unique title/meta/canonical/og + FAQPage JSON-LD + a live demo image
tag pointing at the actual /chart endpoint + Pro CTA. Honest copy only (real chart types,
real free/pro limits). Follows the existing landing template (same CSS + footer badges).
"""
import os, json

BASE = "https://chartbytes.meridian-digital.pro"
LANDING = os.path.join(os.path.dirname(os.path.abspath(__file__)), "landing")

CSS = """<style>
 :root{color-scheme:light}
 *{box-sizing:border-box}
 body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:#1f2937;background:#fff;line-height:1.6}
 header{background:linear-gradient(135deg,#0f172a,#1e293b);color:#fff;padding:3.5rem 1.5rem 2.5rem;text-align:center}
 header h1{font-size:2.2rem;margin:0 0 .5rem;letter-spacing:-.02em}
 header p{font-size:1.15rem;color:#cbd5e1;max-width:640px;margin:0 auto 1.5rem}
 .cta{display:inline-block;background:#2dd4bf;color:#0f172a;font-weight:600;padding:.8rem 1.6rem;border-radius:8px;text-decoration:none;font-size:1.05rem}
 .cta.ghost{background:transparent;color:#e2e8f0;border:1px solid #475569;margin-left:.6rem}
 main{max-width:860px;margin:0 auto;padding:2.5rem 1.5rem 4rem}
 h2{font-size:1.5rem;margin-top:2.5rem}
 pre{background:#0f172a;color:#e2e8f0;padding:1rem 1.2rem;border-radius:8px;overflow-x:auto;font-size:.9rem}
 code{background:#f1f5f9;padding:.1rem .35rem;border-radius:4px;font-size:.9em}
 .demo{border:1px solid #e2e8f0;border-radius:10px;padding:1rem;margin:1rem 0;background:#f8fafc}
 .demo img{max-width:100%;height:auto}
 .muted{color:#64748b}
 footer{max-width:860px;margin:0 auto;padding:1.5rem;color:#94a3b8;font-size:.85rem;border-top:1px solid #e2e8f0}
 a{color:#0d9488}
</style>"""

FOOTER = """<footer>&copy; 2026 Meridian Digital &middot; ChartBytes is a chart image API for email, READMEs and reports.<br><a href="https://twelve.tools" target="_blank"><img src="https://twelve.tools/badge1-light.svg" alt="Featured on Twelve Tools" width="148" height="40"></a> &nbsp; <a href="https://thedevtoolsdir.com/product/chartbytes?ref=badge" rel="dofollow"><img src="https://thedevtoolsdir.com/badge/chartbytes.svg" alt="Featured on TheDevToolsDir" width="182" height="46"></a> &middot; <a href="https://indielineup.com/product/chartbytes?ref=badge" rel="dofollow"><img src="https://indielineup.com/badge/chartbytes.svg" alt="Featured on IndieLineup" width="182" height="46"></a> &middot; <a href="https://thesaasdir.com/product/chartbytes?ref=badge" rel="dofollow"><img src="https://thesaasdir.com/badge/chartbytes.svg" alt="Featured on TheSaaSDir" width="182" height="46"></a> &middot; <a href="https://themicrosaasdir.com/product/chartbytes?ref=badge" rel="dofollow"><img src="https://themicrosaasdir.com/badge/chartbytes.svg" alt="Featured on TheMicroSaaSDir" width="182" height="46"></a> &middot; <a href="https://thedevtoolsindex.com/product/chartbytes?ref=badge" rel="dofollow"><img src="https://thedevtoolsindex.com/badge/chartbytes.svg" alt="Featured on TheDevToolsIndex" width="182" height="46"></a> &middot; <a href="https://thedevtoolslist.com/product/chartbytes?ref=badge" rel="dofollow"><img src="https://thedevtoolslist.com/badge/chartbytes.svg" alt="Featured on TheDevToolsList" width="182" height="46"></a></footer>"""

# Each page: filename, title, h1, meta description, og desc, intro paragraphs (list),
# demo chart URL (relative query), demo alt, h2 sections as (heading, body-html) list,
# FAQ list of (q, a), closing muted links line.
PAGES = [
 dict(
  f="chart-to-png.html",
  title="Chart to PNG Image — ChartBytes",
  h1="Turn any chart into a PNG image",
  meta="Convert a chart to a PNG image from a URL — no JavaScript, no screenshot, no browser. ChartBytes renders bar, line, pie and more as a PNG you can embed anywhere.",
  og="Turn a chart into a PNG (or SVG) image from a plain URL — for email, READMEs, Notion, Slack and reports.",
  intro=[
   "A charting library draws in a browser, but most places you need a chart &mdash; an email, a PDF report, a <code>README.md</code>, a Notion page, a Slack message &mdash; have no browser. To get a chart there you need an <strong>image</strong>, not a canvas. ChartBytes converts chart data to a PNG image server-side from a single URL.",
  ],
  demo="chart?t=bar&d=12,19,8,24&labels=Q1,Q2,Q3,Q4&title=Sales",
  demo_alt="Example bar chart rendered to PNG by ChartBytes",
  sections=[
   ("The URL", 'Point an <code>&lt;img&gt;</code> or Markdown image at a chart URL and the PNG renders automatically. <pre>&lt;img src="{base}/chart?t=bar&amp;d=12,19,8,24&amp;labels=Q1,Q2,Q3,Q4&amp;title=Sales" alt="Sales chart"&gt;</pre>'),
   ("PNG vs SVG", "PNG renders identically everywhere and needs no renderer &mdash; the safe default for email and PDF. SVG is crisp, small and scales, but some clients block it; use it for web pages and documentation."),
   ("What you can chart", "Bar, horizontal bar, stacked bar, line, area, scatter, pie and donut &mdash; each as a PNG (or SVG), with labels, titles and multiple series."),
   ("Free &mdash; then Pro", "The free tier gives 500 chart renders a month, no watermark, no account. Pro is a one-time $9 for dark and brand themes, 25,000 renders/month and immutable caching."),
  ],
  faq=[
   ("How do I convert a chart to PNG?", "Use a chart image URL. ChartBytes renders the chart server-side and returns a PNG, so a plain img tag or Markdown image is all you need &mdash; no screenshot tool, no browser, no client library."),
   ("Can I make a PNG chart without coding?", "Yes. Open the chart builder, pick a chart type, type your data, and copy the PNG URL &mdash; or just edit the URL parameters directly."),
   ("Is the PNG free of watermarks?", "Yes. The free tier renders clean PNG charts with no watermark and no account required."),
  ],
  cross="chart-image-api.html|Chart image API&nbsp;&middot;&nbsp;chart-generator.html|Chart generator&nbsp;&middot;&nbsp;line-chart-generator.html|Line chart generator",
 ),
 dict(
  f="line-chart-generator.html",
  title="Line Chart Image Generator — ChartBytes",
  h1="Line chart image generator",
  meta="Generate a line chart image (PNG or SVG) from a URL — no JavaScript, no signup. ChartBytes renders multi-series line and area charts for email, READMEs and reports.",
  og="Generate a line chart image (PNG/SVG) from a URL. Multi-series, no signup, free tier.",
  intro=[
   "Line charts are the default way to show a trend, and they're the most-requested chart type. ChartBytes renders a line chart as a PNG or SVG image from a URL &mdash; so you can drop a trend chart into an email, a report or a README without a JavaScript charting library.",
  ],
  demo="chart?t=line&d=12,19,8,24&labels=Q1,Q2,Q3,Q4&title=Growth",
  demo_alt="Example line chart generated by ChartBytes",
  sections=[
   ("One URL, one line chart", '<pre>&lt;img src="{base}/chart?t=line&amp;d=12,19,8,24&amp;labels=Q1,Q2,Q3,Q4&amp;title=Growth" alt="Growth chart"&gt;</pre>'),
   ("Multiple series", "Separate series with a pipe: <code>d=12,19,8,24|9,15,20,26</code>. Multiple series render as overlaid lines."),
   ("Area charts too", "Use <code>t=area</code> for a filled line chart &mdash; same parameters, filled under the line."),
   ("Where it works", "Email clients, GitHub READMEs, Notion, Slack and PDF reports &mdash; anywhere a static image renders."),
  ],
  faq=[
   ("How do I make a line chart image?", "Use a line chart URL: /chart?t=line&d=<values>&labels=<labels>. ChartBytes renders it server-side to a PNG (or SVG) image."),
   ("Can I plot multiple lines?", "Yes &mdash; separate each series' values with a pipe (d=1,2,3|4,5,6) to overlay multiple lines."),
   ("Is it free?", "Yes &mdash; 500 renders/month free with no watermark. Pro ($9 one-time) adds dark/brand themes and 25,000 renders/month."),
  ],
  cross="chart-to-png.html|Chart to PNG&nbsp;&middot;&nbsp;bar-chart-generator.html|Bar chart generator&nbsp;&middot;&nbsp;pie-chart-maker.html|Pie chart maker",
 ),
 dict(
  f="bar-chart-generator.html",
  title="Bar Chart Image Generator — ChartBytes",
  h1="Bar chart image generator",
  meta="Generate a bar chart image (PNG or SVG) from a URL — vertical, horizontal or stacked bars, no JavaScript, no signup. For email, READMEs, Notion and reports.",
  og="Generate a bar chart image (PNG/SVG) from a URL. Vertical, horizontal and stacked bars, no signup.",
  intro=[
   "Bar charts compare categories at a glance, and they're everywhere: sales by quarter, signups by month, response times by endpoint. ChartBytes turns bar-chart data into a PNG or SVG image from a URL, so the chart works anywhere an image does.",
  ],
  demo="chart?t=bar&d=12,19,8,24&labels=Q1,Q2,Q3,Q4&title=Revenue",
  demo_alt="Example bar chart generated by ChartBytes",
  sections=[
   ("One URL, one bar chart", '<pre>&lt;img src="{base}/chart?t=bar&amp;d=12,19,8,24&amp;labels=Q1,Q2,Q3,Q4&amp;title=Revenue" alt="Revenue chart"&gt;</pre>'),
   ("Horizontal &amp; stacked", "Use <code>t=hbar</code> for horizontal bars and <code>t=stacked</code> for stacked bars (multiple series) &mdash; same simple URL."),
   ("Grouped bars", "Pass multiple series (<code>d=4,8,6|2,3,4</code>) for grouped vertical bars."),
   ("Free &mdash; then Pro", "500 renders/month free, no watermark, no account. Pro ($9 one-time) adds dark and brand themes, 25,000 renders/month and immutable caching."),
  ],
  faq=[
   ("How do I make a bar chart image?", "Use a bar chart URL: /chart?t=bar&d=<values>&labels=<labels>. ChartBytes renders it server-side to a PNG or SVG."),
   ("Can I make a horizontal bar chart?", "Yes &mdash; use t=hbar for horizontal bars and t=stacked for stacked bars."),
   ("Is the bar chart PNG watermarked?", "No. The free tier renders clean, unwatermarked bar charts with no account."),
  ],
  cross="line-chart-generator.html|Line chart generator&nbsp;&middot;&nbsp;pie-chart-maker.html|Pie chart maker&nbsp;&middot;&nbsp;chart-to-png.html|Chart to PNG",
 ),
 dict(
  f="pie-chart-maker.html",
  title="Pie Chart Maker — ChartBytes",
  h1="Pie chart maker (image, no signup)",
  meta="Make a pie chart image (PNG or SVG) from a URL — no signup, no JavaScript. ChartBytes renders pie and donut charts for email, READMEs, Notion and reports.",
  og="Make a pie chart image (PNG/SVG) from a URL. Pie and donut charts, no signup, free tier.",
  intro=[
   "A pie chart shows proportions, and a donut chart is its modern, cleaner sibling. ChartBytes renders both as a PNG or SVG image from a URL &mdash; no signup, no JavaScript charting library, ready to embed anywhere.",
  ],
  demo="chart?t=pie&d=12,19,8,24&labels=Q1,Q2,Q3,Q4&title=Share",
  demo_alt="Example pie chart generated by ChartBytes",
  sections=[
   ("One URL, one pie chart", '<pre>&lt;img src="{base}/chart?t=pie&amp;d=12,19,8,24&amp;labels=Q1,Q2,Q3,Q4&amp;title=Share" alt="Share chart"&gt;</pre>'),
   ("Donut charts", "Use <code>t=donut</code> for a donut chart &mdash; the same data and labels, with a hole in the middle."),
   ("Labels &amp; titles", "Pass <code>labels=</code> for slice labels and <code>title=</code> for a chart title &mdash; both optional."),
   ("Free &mdash; then Pro", "500 renders/month free with no watermark. Pro is a one-time $9 for dark/brand themes, 25,000 renders/month and immutable caching."),
  ],
  faq=[
   ("How do I make a pie chart image?", "Use a pie chart URL: /chart?t=pie&d=<values>&labels=<labels>. ChartBytes renders it server-side to a PNG or SVG."),
   ("Can I make a donut chart?", "Yes &mdash; use t=donut for a donut chart with the same parameters."),
   ("Do I need to sign up?", "No. The free tier works with no account and no watermark; Pro is an optional one-time $9 upgrade."),
  ],
  cross="bar-chart-generator.html|Bar chart generator&nbsp;&middot;&nbsp;line-chart-generator.html|Line chart generator&nbsp;&middot;&nbsp;chart-generator.html|Chart generator",
 ),
 dict(
  f="chart-image-api.html",
  title="Chart Image API — ChartBytes",
  h1="Chart image API",
  meta="A free chart image API: turn a URL into a PNG or SVG chart with no signup and no JavaScript. ChartBytes is a simpler, cheaper Image-Charts and QuickChart alternative.",
  og="A free chart image API: URL in, PNG/SVG chart out. No signup, 500 renders/month free.",
  intro=[
   "A chart image API returns a static PNG or SVG of a chart from a URL. It's the cleanest way to put charts into anything that can't run JavaScript &mdash; email, PDF reports, GitHub READMEs, Notion, Slack, dashboards, static sites and more. ChartBytes is a minimal, free-to-start chart image API with a one-time Pro upgrade instead of a monthly subscription.",
  ],
  demo="chart?t=bar&d=12,19,8,24&labels=Q1,Q2,Q3,Q4&title=Sales",
  demo_alt="Example chart returned by the ChartBytes image API",
  sections=[
   ("GET /chart", '<pre>GET {base}/chart?t=bar&amp;d=12,19,8,24&amp;labels=Q1,Q2,Q3,Q4&amp;title=Sales</pre>Returns a PNG (default) or SVG (<code>&amp;f=svg</code>).'),
   ("POST /chart (JSON)", 'POST a JSON body <code>{{"type":"bar","data":[12,19,8,24],"labels":["Q1","Q2","Q3","Q4"]}}</code> when the URL would get too long.'),
   ("Chart types", "bar, hbar, stacked, line, area, scatter, pie and donut &mdash; PNG and SVG, with labels, titles and multiple series."),
   ("Pricing", "Free: 500 renders/month, light theme, no watermark, no account. Pro: one-time $9 &mdash; dark and brand themes, 25,000 renders/month, immutable caching."),
  ],
  faq=[
   ("What is a chart image API?", "An API that returns a static PNG/SVG chart from a URL, so you can embed charts in places that can't run JavaScript &mdash; email, READMEs, Notion, Slack and PDF reports."),
   ("Is there a free chart image API?", "Yes. ChartBytes is free for 500 renders/month with no watermark and no account. Pro is an optional one-time $9."),
   ("What are the alternatives?", "Image-Charts and QuickChart are the established options. ChartBytes is a simpler, cheaper alternative: no watermark on the free tier and a one-time payment instead of a subscription."),
  ],
  cross="chart-to-png.html|Chart to PNG&nbsp;&middot;&nbsp;chart-generator.html|Chart generator&nbsp;&middot;&nbsp;image-charts-alternative.html|Image-Charts alternative&nbsp;&middot;&nbsp;quickchart-alternative.html|QuickChart alternative",
 ),
 dict(
  f="chart-generator.html",
  title="Chart Generator — ChartBytes",
  h1="Chart generator (image, no signup)",
  meta="Generate a chart as a PNG or SVG image from a URL — bar, line, pie and more, no signup, no JavaScript. Free chart generator for email, READMEs, Notion and reports.",
  og="Generate a chart image (PNG/SVG) from a URL. Bar, line, area, scatter, pie and donut &mdash; free, no signup.",
  intro=[
   "Need a chart image without spinning up a JavaScript charting library? ChartBytes is a chart generator that renders a PNG or SVG from a URL &mdash; type your data (or use the interactive builder) and get a chart image you can embed in email, a README, Notion, Slack or a PDF report. No signup, no code required.",
  ],
  demo="chart?t=bar&d=12,19,8,24&labels=Q1,Q2,Q3,Q4&title=Sales",
  demo_alt="Example chart generated by ChartBytes",
  sections=[
   ("Try the live builder", 'Open <a href="{base}/builder.html">the chart builder</a> &mdash; pick a chart type, type your data, see the live chart, then copy the exact chart URL or a Markdown snippet. No signup.'),
   ("Or build the URL directly", '<pre>{base}/chart?t=bar&amp;d=12,19,8,24&amp;labels=Q1,Q2,Q3,Q4&amp;title=Sales</pre>'),
   ("Chart types", "bar, hbar, stacked, line, area, scatter, pie and donut &mdash; PNG (default) or SVG (<code>&amp;f=svg</code>)."),
   ("Free &mdash; then Pro", "500 renders/month free, no watermark, no account. Pro: one-time $9 for dark/brand themes, 25,000 renders/month and immutable caching."),
  ],
  faq=[
   ("How do I generate a chart image?", "Use the interactive chart builder, or point an img tag / Markdown image at a chart URL. ChartBytes renders the chart server-side to a PNG or SVG."),
   ("Can I generate a chart without code?", "Yes &mdash; the chart builder needs no code and no signup; type your data and copy the URL."),
   ("Is the chart generator free?", "Yes &mdash; 500 renders/month free with no watermark. Pro is an optional one-time $9."),
  ],
  cross="chart-image-api.html|Chart image API&nbsp;&middot;&nbsp;chart-to-png.html|Chart to PNG&nbsp;&middot;&nbsp;line-chart-generator.html|Line chart generator&nbsp;&middot;&nbsp;pie-chart-maker.html|Pie chart maker",
 ),
]

def render_page(p):
    og_title = p["title"].split("—")[0].strip()
    cross_links = " &middot; ".join(
        f'<a href="./{h}">{t}</a>' for h, t in
        [c.split("|") for c in p["cross"].split("&nbsp;&middot;&nbsp;")]
    )
    demo_url = f"{BASE}/{p['demo']}"
    sections_html = []
    for heading, body in p["sections"]:
        body = body.replace("{base}", BASE)
        sections_html.append(f"<h2>{heading}</h2>\n{body}")
    faq_entities = []
    faq_html = []
    for q, a in p["faq"]:
        faq_entities.append({"@type": "Question", "name": q,
                             "acceptedAnswer": {"@type": "Answer", "text": a}})
        faq_html.append(f"<p><strong>{q}</strong> {a}</p>")
    ld = json.dumps({"@context": "https://schema.org", "@type": "FAQPage",
                     "mainEntity": faq_entities})
    intro = "\n<p>".join(p["intro"])
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{p['title']}</title>
<meta name="description" content="{p['meta']}">
<link rel="canonical" href="{BASE}/{p['f']}">
<meta property="og:type" content="website">
<meta property="og:title" content="{og_title}">
<meta property="og:description" content="{p['og']}">
<meta property="og:url" content="{BASE}/{p['f']}">
<meta name="twitter:card" content="summary">
<script type="application/ld+json">
{ld}
</script>
{CSS}
</head>
<body>
<header>
 <h1>{p['h1']}</h1>
 <p>{intro}</p>
 <a class="cta" href="{BASE}/api/checkout">Get Pro &mdash; $9 once</a>
 <a class="cta ghost" href="{BASE}/builder.html">Try the live builder &rarr;</a>
</header>
<main>
<div class="demo"><img src="{demo_url}" alt="{p['demo_alt']}"></div>
{''.join(sections_html)}
<h2>FAQ</h2>
{''.join(faq_html)}
<p class="muted">Built by Meridian Digital &middot; <a href="./index.html">ChartBytes home</a> &middot; {cross_links}</p>
</main>
{FOOTER}
</body>
</html>"""

def main():
    os.makedirs(LANDING, exist_ok=True)
    written = []
    for p in PAGES:
        out = os.path.join(LANDING, p["f"])
        with open(out, "w") as fh:
            fh.write(render_page(p))
        written.append(p["f"])
    print("Wrote", len(written), "pages:")
    for w in written:
        print(" -", w)

if __name__ == "__main__":
    main()
