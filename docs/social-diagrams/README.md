# Social Diagram Exports

These files are rendered from `docs/deepfake-analyzer-article.md` so the diagrams work on platforms that do not support Mermaid, including X/Twitter.

Use `.png` for X/Twitter, LinkedIn, and thumbnails. Use `.svg` for websites, docs, and article platforms that preserve vector images.

Final article file:

- `docs/deepfake-analyzer-final-article.md` embeds the 5:2 header plus all eight rendered diagram PNGs using GitHub raw URLs.

Article image order:

0. `article-header-5x2.png`
1. `01-why-a-single-deepfake-score-is-not-enough.png`
2. `02-the-product-in-one-flow.png`
3. `03-the-input-boundary.png`
4. `04-the-evidence-bus.png`
5. `05-the-mixture-of-experts-design.png`
6. `06-the-report-is-the-product.png`
7. `07-the-verdict-policy.png`
8. `08-deployment-architecture.png`

All exported diagram files:

- Why a Single Deepfake Score Is Not Enough: `01-why-a-single-deepfake-score-is-not-enough.png`, `01-why-a-single-deepfake-score-is-not-enough.svg`, source `01-why-a-single-deepfake-score-is-not-enough.mmd`
- The Product in One Flow: `02-the-product-in-one-flow.png`, `02-the-product-in-one-flow.svg`, source `02-the-product-in-one-flow.mmd`
- The Input Boundary: `03-the-input-boundary.png`, `03-the-input-boundary.svg`, source `03-the-input-boundary.mmd`
- The Evidence Bus: `04-the-evidence-bus.png`, `04-the-evidence-bus.svg`, source `04-the-evidence-bus.mmd`
- The Mixture-of-Experts Design: `05-the-mixture-of-experts-design.png`, `05-the-mixture-of-experts-design.svg`, source `05-the-mixture-of-experts-design.mmd`
- The Report Is the Product: `06-the-report-is-the-product.png`, `06-the-report-is-the-product.svg`, source `06-the-report-is-the-product.mmd`
- The Verdict Policy: `07-the-verdict-policy.png`, `07-the-verdict-policy.svg`, source `07-the-verdict-policy.mmd`
- Deployment Architecture: `08-deployment-architecture.png`, `08-deployment-architecture.svg`, source `08-deployment-architecture.mmd`

Regenerate after editing the article:

```powershell
node scripts/export-article-diagrams.mjs
```
