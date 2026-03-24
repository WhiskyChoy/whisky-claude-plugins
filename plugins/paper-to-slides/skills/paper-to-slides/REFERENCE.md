# Paper-to-Slides Reference

Detailed reference material for the `paper-to-slides` skill. Read on-demand when specific steps require it — not loaded into context by default.

## OOXML Image Transforms (Template Extraction)

PowerPoint applies visual transforms to embedded images via XML child elements inside `<a:blip>`. The raw image blob from `python-pptx` does **NOT** include these — you get the original untransformed image.

| XML Element | Effect | Example |
|-------------|--------|---------|
| `<a:grayscl/>` | Convert to grayscale | Orange JPEG → gray appearance |
| `<a:duotone>` | Two-color gradient map | Color photo → branded duotone |
| `<a:biLevel thresh="50000"/>` | Black & white threshold | Photo → high-contrast B&W |
| `<a:lum bright="20000"/>` | Brightness/contrast adjustment | Darken/lighten background |
| `<a:alphaModFix amt="50000"/>` | Transparency | Semi-transparent watermark |

**`<a:grayscl/>` is extremely common** in corporate/academic templates where a colorful stock image is intentionally desaturated as a neutral background. If missed, the extracted background appears colorful when the actual presentation renders it gray — a 100%-fidelity violation.

The `extract_pptx_template.py` script handles this automatically:
1. Parses `<a:blip>` for each image shape
2. Detects transform children (`grayscl`, `biLevel`, `lum`, `alphaModFix`, `duotone`)
3. Applies equivalent Pillow operations before saving
4. Logs all transforms in `style_report.json` → `image_transforms_detected`

Manual fallback (without the script):
```python
from lxml.etree import tostring
pic_el = shape._element
blip = pic_el.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}blip')
print(tostring(blip, pretty_print=True).decode())  # Look for <a:grayscl/> etc.
```

---

## CSS Transformation Rules (Dual Aspect Ratio)

When converting between 16:9 and 4:3 versions:

| Element | 16:9 → 4:3 | 4:3 → 16:9 |
|---------|-------------|-------------|
| Stage wrapper | Add `.slide-stage` with `height:100vh; width:calc(100vh*4/3); margin:0 auto` | Remove wrapper, use `100vw/100vh` |
| Font units | `vw` → `vh` (narrower viewport needs height-based sizing) | `vh` → `vw` |
| Media query | `min-width:2500px` → `min-height:1400px` | Reverse |
| Figure slides | Full-width h2 above fig-row | h2 inside text-panel (side-by-side) |
| Content padding | Increase vertical padding (more height available) | Increase horizontal padding |

**Naming convention**: Primary = `slides.html`, secondary = `slides_{ratio}.html` (e.g., `slides_4_3.html`, `slides_16_9.html`).

---

## Slide Outline Templates

### Academic (15-25 slides)
1. Title (title, authors, affiliation, venue/date)
2. Motivation / Problem statement
3. Related work (brief positioning)
4. Key contributions (numbered)
5-8. Method overview (2-4 slides)
9-12. Experimental setup & Results
13. Ablation / Analysis
14. Conclusion & Future work
15. Thank you / Q&A

### Popular Science (10-15 slides)
1. Title (catchy subtitle)
2. The big question / hook
3. Why it matters (real-world impact)
4. How it works (simplified, visual)
5-7. Key findings (one per slide)
8. What's next
9. Thank you

### Pitch (8-12 slides)
1. Title (one-liner value prop)
2. The problem (pain point)
3. Current limitations
4. Our approach (high-level)
5. Key result / demo
6-8. Impact numbers (one per slide)
9. Vision / next steps
10. Call to action / Thank you

### Tutorial (15-30 slides)
1. Title
2. Prerequisites / What you'll learn
3. Problem setup
4-8. Step-by-step method (one concept per slide)
9-12. Worked example with results
13. Common pitfalls
14. Resources & references
15. Q&A

---

## Style Presets

| Style | Slides | Density | Tone | Visual Direction |
|-------|--------|---------|------|------------------|
| **academic** | 15-25 | Medium-high | Formal, precise | Clean, structured, data-heavy |
| **popular-science** | 10-15 | Low | Conversational | Bold colors, large imagery, minimal text |
| **pitch** | 8-12 | Low | Persuasive | Strong typography, dramatic contrast |
| **tutorial** | 15-30 | Medium | Instructional | Step markers, code/diagram focus |

### Audience Adaptation Examples

Same result, four styles:

- **Academic**: "Our method achieves 94.2% accuracy on COCO-val, outperforming the previous SOTA by 3.1 pp (Table 2)."
- **Popular science**: "Our system correctly identifies objects in photos 94% of the time — better than any previous approach."
- **Pitch**: "94% accuracy. 3 points above the competition. State of the art."
- **Tutorial**: "After training for 50 epochs, you should see accuracy around 94% on the validation set."

---

## Multi-Paper Merge Guidelines

When combining multiple papers into one deck, watch for:

- **Terminology collisions**: Different papers may use the same term differently (e.g., "agent", "score"). Disambiguate explicitly.
- **Notation conflicts**: Variables like `x`, `α`, `N` may differ. Introduce each paper's notation before use.
- **Contradictory claims**: Papers may report conflicting results. Never silently merge — flag differences.
- **Uneven depth**: Balance coverage proportionally or let the user decide the split.
- **Lost attribution**: Every slide must show which paper the content comes from.

### Pre-generation checklist
- [ ] Each paper's contribution is clearly separated and attributed
- [ ] No terminology or notation conflicts unresolved
- [ ] Slide count split is proportional (or user-approved)
- [ ] Transition slides mark paper switches
- [ ] Common themes synthesized, not concatenated
- [ ] Combined narrative is coherent

---

## Template Fidelity Requirements

| Element | Requirement |
|---------|-------------|
| **Title slide background** | Exact background image/gradient from template. Copy to `assets/` as CSS `background-image`. |
| **End/Thank-you background** | Exact background from template's last slide. |
| **Content slide backgrounds** | Consistent background (gradient, pattern, image) applied identically. |
| **Organization logo** | Exact position, size. Appears on every slide where template shows it. |
| **Banner / decorative bar** | Exact color, position, and dimensions. |
| **Color palette** | Exact hex/RGB values. No "close enough". |
| **Font families** | Same fonts. If unavailable, closest match with documented substitution. |
| **Aspect ratio** | Match template exactly (16:9, 4:3, custom). |

### Common Template Mistakes
- Ignoring OOXML image transforms → colorful JPEG when PowerPoint renders gray
- Extracting colors but not background images → "vaguely similar" deck
- Logo in wrong corner or size
- Solid-color background when template has gradient/image
- Forgetting end slide's unique background
- Reading scheme colors without resolving against theme → wrong hex values

---

## PPTX Export Notes

The `html_to_pptx.py` script handles:
- **Math**: Renders LaTeX/KaTeX as 300 DPI PNG via matplotlib
- **Figures**: Auto-scales to fit slide boundaries with proper aspect ratio
- **Backgrounds**: Applies background images as full-slide background shapes
- **Logos**: Positions from style report coordinates

Known limitations of naive HTML→PPTX (the script works around these):
- Raw text copy of formulas produces `x_1` instead of proper subscript
- Images at original size may overflow slide boundaries
- Background images may be lost without explicit handling

Dimension flags:
- 4:3: `--width 10 --height 7.5`
- 16:9: `--width 13.333 --height 7.5` (defaults)
