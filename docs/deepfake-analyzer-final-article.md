# Building an Explainable AI Deepfake Analyzer for Sensitive Media Abuse

> Publication-ready version with rendered diagrams. Use this file for platforms that do not render Mermaid diagrams.

![AI Deepfake Analyzer article header](https://raw.githubusercontent.com/Devrajsinh-Jhala/DeepFake-MoE/main/docs/social-diagrams/article-header-5x2.png)

*Header image: A privacy-first evidence pipeline for explainable deepfake analysis, with media input, expert signals, safety arbiter, and report output.*

There is a painful gap between how quickly synthetic media can be created and how slowly victims can defend themselves. A fake intimate image, a manipulated portrait, or a deepfake-style post can spread before the person affected even understands what happened. Most people do not need a black-box score that says "82% AI" and leaves them confused. They need an evidence report that explains what was checked, what was found, what was uncertain, and what they can safely do next.

That is the motivation behind this project: AI Deepfake Analyzer, a privacy-first web application for layered image authenticity analysis. The app accepts either an uploaded image or a public URL, runs several independent evidence checks, and returns a victim-friendly report with a technical appendix. It does not train a custom model in version one. Instead, it uses pretrained open-source detectors as one evidence layer, then surrounds them with metadata analysis, provenance checks, forensic heuristics, input-quality guards, calibrated aggregation, and report generation.

The most important design choice is that the system does not pretend that image authenticity is a solved binary problem. It can classify an image as likely real, likely AI generated, likely manipulated, or inconclusive, but it always shows why. When the evidence is weak or the detectors disagree, the app is allowed to abstain. For a tool that may be used by people facing harassment, that caution is not a weakness. It is part of the safety model.

## Why a Single Deepfake Score Is Not Enough

The first instinct when building this kind of product is to look for the best available AI detector, pass an image through it, and show the returned probability. That approach is simple, but it is not good enough for high-stakes use.

Real photos can look synthetic after compression, denoising, screenshotting, cropping, resizing, beautification filters, or heavy platform recompression. AI images can be intentionally post-processed to look more natural. Some model families leave artifacts that one detector catches and another detector misses. Portraits are especially sensitive because many fake-image detectors have learned patterns from benchmark datasets that do not always match everyday profile photos, ID-style photos, or social-media exports.

So the app treats model output as an opinion, not a verdict. The detector panel can say "this looks AI-like," but the final decision also asks whether metadata agrees, whether provenance exists, whether forensic residuals support or contradict the model, whether the image quality is reliable enough, and whether the model panel is internally consistent.

The product goal is not just detection. It is explainable triage.

![Why a Single Deepfake Score Is Not Enough](https://raw.githubusercontent.com/Devrajsinh-Jhala/DeepFake-MoE/main/docs/social-diagrams/01-why-a-single-deepfake-score-is-not-enough.png)

*Figure 1: A single deepfake score is not enough. The app separates model opinions, metadata, forensic layers, and input-quality checks before the final verdict.*

## The Product in One Flow

At a user level, the app is intentionally simple. A person opens the analyzer, chooses an image upload or a public URL, confirms they have the right to submit the media, and starts the analysis. The frontend blurs sensitive previews by default. The backend validates the input, stores temporary media in an ephemeral path, runs analysis, and returns a report. The user can download JSON or PDF, save the result, or delete the analysis early.

Underneath that simple flow, the system is layered. It has a React/Vite frontend, a FastAPI backend, optional Redis/RQ background processing, SQLAlchemy-backed job metadata, encrypted temporary media storage, pretrained Hugging Face detector adapters, and report generation through JSON and PDF exports. For the current public demo, the app can run as a single Docker service on Hugging Face Spaces. For a production deployment, the same architecture can move to a web service plus worker plus PostgreSQL plus Redis.

![The Product in One Flow](https://raw.githubusercontent.com/Devrajsinh-Jhala/DeepFake-MoE/main/docs/social-diagrams/02-the-product-in-one-flow.png)

*Figure 2: The product flow starts simple for the user, then expands into backend validation, analysis layers, report generation, and privacy-safe runtime storage.*

## The Input Boundary

The input boundary is the first serious part of the architecture because the app is designed for sensitive media. A detection tool that carelessly logs raw files, fetches private URLs, or stores images forever creates a new risk for the same people it is supposed to help.

The app accepts direct image uploads and public URLs. Upload validation checks file type, file size, and image readability before analysis. Public URL fetching is intentionally narrow. It is not a scraper for private platforms, login-only pages, internal networks, or hidden identities. It rejects unsafe targets such as local, private, multicast, link-local, and reserved IP ranges. It follows public-link boundaries rather than trying to discover a person's identity.

The privacy posture is deliberately conservative. Raw files are not returned by the API. Sensitive previews are blurred in the UI. Temporary media is short-lived. Users can delete an analysis early. Audit logs use privacy-safe identifiers rather than storing raw media or raw private context.

This matters because the app's target user may be a victim of harassment. The product should not ask them to trade one privacy risk for another.

![The Input Boundary](https://raw.githubusercontent.com/Devrajsinh-Jhala/DeepFake-MoE/main/docs/social-diagrams/03-the-input-boundary.png)

*Figure 3: The input boundary is designed for sensitive media: consent, validation, URL safety, ephemeral storage, analysis, reporting, and early deletion.*

## The Evidence Bus

Once the input is accepted, the app treats the image as a media packet that can be decomposed into independent evidence lanes. These lanes are intentionally different from each other. If every layer is just another model score, the report becomes fragile. If the layers examine different kinds of evidence, the final decision becomes easier to explain.

The metadata and provenance lane looks for EXIF, XMP, PNG text chunks, software markers, editing markers, generative markers, and C2PA/content credentials when tooling is available. This layer can be strong when a file honestly carries generative metadata or signed credentials. It can also be neutral, because many social platforms strip metadata and missing EXIF is not proof of AI generation.

The hash lane produces a SHA-256 hash and perceptual hashes. The cryptographic hash identifies the exact file, while perceptual hashes help compare visually similar versions later. These hashes do not prove authenticity, but they are useful for documentation, reproducibility, deduplication, and future reverse-image-search integrations.

The forensic lane checks compression and residual signals: error-level analysis, noise consistency, edge behavior, frequency structure, and regional anomaly maps. These are not magic proof. ELA and noise analysis can be fooled by normal editing, screenshots, and recompression. In this app, they act as supporting or counter-evidence rather than final authority.

The model lane runs pretrained open-source detectors. The current approach is a mixture of experts: several generic image detectors, a portrait-gated specialist, and non-model expert opinions. Each detector has thresholds and reliability weights instead of being treated as equally calibrated.

The safety lane receives all of those signals and decides whether the evidence is strong enough to emit a confident label. If the image is low quality, the model panel disagrees, or the non-model evidence does not support the model score, the safety lane can reduce confidence or return inconclusive.

![The Evidence Bus](https://raw.githubusercontent.com/Devrajsinh-Jhala/DeepFake-MoE/main/docs/social-diagrams/04-the-evidence-bus.png)

*Figure 4: The evidence bus splits one media packet into independent metadata, provenance, hash, forensic, detector, and quality lanes.*

## The Mixture-of-Experts Design

The app's model architecture is best understood as a mixture of experts, but not in the sense of training a huge neural network router. This is an application-level MoE. Different evidence experts produce opinions, and the safety arbiter combines those opinions under a calibrated decision policy.

The generic detector experts look for broad AI-vs-real signals. The portrait specialist is gated, which means it only runs when the input appears portrait-like enough. That prevents a portrait-tuned model from dominating landscapes, objects, screenshots, or unrelated scenes. The forensic expert produces non-model evidence based on residual artifacts. The provenance expert examines container metadata, C2PA status, generation markers, editing markers, source context, and hashes. The input-quality guard is also an expert in practice: it does not say "real" or "AI," but it can cap confidence when the input is too compressed, too small, or too altered for a strong conclusion.

After those opinions are collected, the normalizer converts raw model labels into a shared stance: supports AI, supports real, supports manipulation, neutral, or limits confidence. The safety arbiter then weighs reliability, disagreement, input quality, and non-model counter-evidence before choosing a final label.

![The Mixture-of-Experts Design](https://raw.githubusercontent.com/Devrajsinh-Jhala/DeepFake-MoE/main/docs/social-diagrams/05-the-mixture-of-experts-design.png)

*Figure 5: The mixture-of-experts architecture routes evidence through generic detectors, a portrait-gated specialist, forensic/provenance experts, and a safety arbiter.*

This is also where the app became much more usable. Early detector-only versions could mislabel real portraits as AI-generated because one model was overconfident. The MoE approach reduces that risk by allowing real/human votes, detector disagreement, and quality guards to push the result back toward likely real or inconclusive. That is the right behavior for a victim-facing tool. It is better to say "I cannot safely conclude this is fake" than to make a confident accusation from a noisy signal.

## What "Layer-by-Layer" Analysis Means

When people say they want the app to "strip the layers" of an image, it is easy to imagine literal Photoshop layers. Most uploaded images do not contain editable layers. A JPEG, PNG, or WebP is usually a flattened output. So the app interprets layer-by-layer analysis as analytical decomposition.

The image is decomposed into questions. Does the file container expose generative metadata? Does it have signed provenance? Is the input quality reliable enough? Do pretrained detectors agree? Are luminance and chroma statistics unusual? Are edge patterns inconsistent? Does the noise residual look uneven across regions? Does recompression create suspicious error patterns? Does the frequency spectrum look overly smooth or abnormal? Do some image tiles show stronger anomaly scores than others?

The result is an evidence ledger rather than a single opaque score.

| Analytical layer | What it asks | How it is used |
| --- | --- | --- |
| Source, metadata, and provenance | Does the file carry generation, editing, camera, or credential information? | Strong when present, neutral when missing, never treated as proof by absence. |
| Input quality and robustness | Is the image reliable enough for automated detection? | Caps confidence for small, compressed, cropped, or screenshot-like media. |
| Visual model consensus | Do pretrained detectors agree that the image looks synthetic or real? | Important evidence, but calibrated and checked for disagreement. |
| Luminance layer | Are brightness, contrast, entropy, or clipping patterns unusual? | Weak supporting signal because lighting and compression can dominate. |
| Chroma and color layer | Are color-channel statistics or saturation patterns suspicious? | Weak signal that can support or challenge other evidence. |
| Edge and geometry layer | Are edges overly clean, inconsistent, or locally unnatural? | Used as anomaly evidence, not as identity evidence. |
| Noise residual layer | Is sensor-like noise consistent across the image? | Helps identify suspicious regional differences, but denoising can distort it. |
| Compression and ELA layer | Do recompression artifacts suggest editing or pasted regions? | Useful as supporting evidence, fragile under platform recompression. |
| Frequency spectrum layer | Does the image have unusual high-frequency or smooth spectral structure? | Helps detect over-regularized synthetic patterns. |
| Regional tile map | Which 4x4 regions are more anomalous than others? | Shows where the image deserves attention without rendering raw sensitive media in the report. |

This ledger is the foundation of explainability. Even when the final verdict is wrong or inconclusive, the report can still show which layers pushed the system in that direction.

## The Report Is the Product

For this app, the report is not an afterthought. It is the product.

A victim-friendly interface cannot be written like a machine-learning debug log. It needs to start with a plain-language verdict, confidence, strongest evidence, limitations, and next steps. At the same time, a platform moderator, journalist, security reviewer, or technical helper may need more detail. That is why the app produces both a readable summary and a technical appendix.

The JSON report is meant for machines and advanced reviewers. It includes the full structured result: verdict, probabilities, detector disagreement, source context, evidence layers, explainability trace, expert opinions, analytical layer breakdown, regional evidence map, hashes, detector outputs, metadata summaries, C2PA status, forensics, runtime, and reproducibility notes.

The PDF report is meant for sharing. It contains the headline, plain-language verdict, key probabilities, decision summary, calibration gate, mixture-of-experts table, evidence layers, explainable AI trace, regional evidence map, analytical layer breakdown, limitations, and technical appendix. It avoids embedding the raw uploaded image, which is important when the submitted media may be sensitive.

![The Report Is the Product](https://raw.githubusercontent.com/Devrajsinh-Jhala/DeepFake-MoE/main/docs/social-diagrams/06-the-report-is-the-product.png)

*Figure 6: The report is the actual product: victim summary, evidence ledger, explainable AI trace, technical appendix, PDF export, and JSON export.*

The report is also where the app communicates humility. It says that pixels alone cannot prove authenticity. It explains that missing EXIF is not proof of AI generation. It records detector disagreement. It distinguishes model evidence from non-model evidence. It shows when a result is low confidence. That language matters because people may use the report during stressful, reputationally serious moments.

## The Verdict Policy

The app has four final labels.

`likely_real` means the available evidence is more consistent with real or camera-origin media than with synthetic generation. This does not prove the image is authentic. It means the system did not find enough AI or manipulation evidence to safely say otherwise, and the model/provenance/forensic evidence leaned real.

`likely_ai_generated` means the image has evidence consistent with AI-generated or synthetic media. In the safer version of the app, this requires more than a single model screaming "AI." The decision can be supported by model consensus, generative metadata, provenance claims, and the absence of strong counter-evidence.

`likely_manipulated_or_deepfake` means the strongest evidence is not necessarily full-image generation, but manipulation-like behavior: regional inconsistency, compression artifacts, unusual residuals, or other editing signals.

`inconclusive` means the system is preserving uncertainty. This is returned when the evidence is too weak, the detectors disagree too much, the input quality is poor, or the layers do not support a confident result. For public use, this label is essential. A serious tool must be able to say "I do not know."

![The Verdict Policy](https://raw.githubusercontent.com/Devrajsinh-Jhala/DeepFake-MoE/main/docs/social-diagrams/07-the-verdict-policy.png)

*Figure 7: The verdict policy allows four outcomes, including inconclusive, so the app can preserve uncertainty instead of forcing a risky binary answer.*

## Public URL Context Without Doxxing

The app supports public URLs because victims often discover harmful media as a post, not as a clean file. But there is a hard boundary: version one does not do face search, private identity inference, login scraping, or doxxing. It only reports public context visible from the submitted link, such as final URL, domain, page title, visible metadata fields, and public source context where available.

That design is intentional. "Where was this posted?" is a useful question. "Who is this person really?" is a dangerous one. The app should help users document public evidence and understand media authenticity without becoming an identity-hunting tool.

Future reverse-image-search integrations can be added through a pluggable adapter, but they should stay bounded. Global discovery cannot be guaranteed without indexed providers, and any public attribution feature needs careful abuse review.

## Deployment Architecture

The current deployment path supports two realities: a low-friction public demo and a stronger production topology.

For the public demo, Hugging Face Spaces with Docker is practical because it can run the FastAPI app, serve the built React frontend, and download Hugging Face model weights in one container. The tradeoff is that free demo environments may sleep, rebuild, or lose local cache. That is acceptable for demonstrations and early feedback.

For production, the architecture should separate durable metadata, queueing, and worker execution. PostgreSQL stores job metadata and report state. Redis/RQ handles analysis jobs. A worker process performs heavier detector inference. A persistent data volume stores short-lived encrypted media and cached model weights. A reverse proxy or platform layer enforces HTTPS, request-size limits, timeouts, and extra abuse controls.

![Deployment Architecture](https://raw.githubusercontent.com/Devrajsinh-Jhala/DeepFake-MoE/main/docs/social-diagrams/08-deployment-architecture.png)

*Figure 8: The production architecture separates the public web service, durable metadata, queueing, worker inference, encrypted temp storage, model cache, metrics, and audit logs.*

The production readiness checklist is not just "does the page load?" It includes frontend build, backend tests, readiness checks, rate limiting, CORS restrictions, private calibration sets, real-photo controls, generated-image controls, log sampling, deletion behavior, and deployment-specific secrets. For an app handling sensitive media, operations are part of product quality.

## Accuracy, Calibration, and Honesty

No app can honestly promise perfect detection for every photo. Any article, demo, or landing page for this tool should say that clearly. The stronger claim is not "we solved deepfake detection." The stronger claim is "we built a layered, explainable, privacy-first analysis workflow that reduces blind reliance on one model and shows its evidence."

Accuracy improves through calibration. The app already has a golden-set evaluation path. Before serious public launch, the calibration set should include real phone photos, real portraits, ID-style images, screenshots, heavily compressed social-media exports, cropped images, edited images, known AI images from multiple generators, and benign NSFW-like controls that do not expose real victims. The launch gate should watch false positives on real photos very closely. A false accusation can hurt someone, especially when the subject is already dealing with harassment.

The app's confidence system should also be judged separately from its label. A high-confidence wrong answer is worse than a low-confidence inconclusive answer. The safety arbiter is designed to reduce that risk by capping confidence when the input quality is weak, models disagree, or non-model evidence does not support the detector panel.

## Why the PDF Report Matters

The PDF report gives the analysis a stable shape. A victim can download it, preserve it, share it with a trusted helper, or attach it to a platform report. A moderator can scan the summary and then inspect the technical appendix. A developer can compare the PDF with the JSON export to reproduce or debug the pipeline.

The PDF should not be treated as a legal certificate. It is an evidence summary. That distinction is important. The report can say what the app observed, what methods were used, what limitations apply, and what would improve confidence. It should not pretend to identify a perpetrator, prove a crime, or guarantee authenticity.

In this project, the PDF is structured to keep both audiences in mind. The first page is plain-language and direct. The later sections provide detector outputs, evidence layers, regional map interpretation, hashes, and reproducibility notes. This makes the report useful without forcing a stressed user to interpret raw machine-learning outputs first.

## What Makes the App Public-Use Ready

Public-use readiness is a combination of product design, security design, model behavior, and operational discipline.

The product design is victim-centered: sensitive previews are blurred, reports are written in plain language, and the app avoids identity inference. The security design rejects unsafe URL fetches, limits file inputs, uses short-lived media storage, exposes early deletion, and avoids raw media logging. The model design uses multiple opinions rather than one raw detector score. The operational design includes readiness checks, rate limiting, audit hashing, deployment validation, and calibration gates.

The app is strongest when used as a triage and documentation tool. It can help a person understand whether an image has synthetic or manipulation signals. It can help them preserve evidence. It can give platform moderators a structured report. It can show uncertainty instead of pretending certainty exists.

That is exactly the kind of tool this problem needs.

## The Next Version

The image-first version is the right MVP because images are the most common starting point and they let the evidence/reporting workflow mature. Video analysis should come next, but it should not be rushed. Video requires frame sampling, face and region crops, temporal consistency checks, audio separation, lip-sync analysis, shot-level aggregation, and a timeline report. The same philosophy should carry over: multiple evidence lanes, calibrated experts, visible uncertainty, and no identity-hunting features.

Other future improvements include a real C2PA runtime in production, a pluggable reverse-image-search adapter, larger private calibration sets, user-facing takedown resources, better report templates, organization dashboards for trusted reviewers, and manual review workflows for high-stakes cases.

## Closing

Deepfake detection should not be a black box, especially when the people using it may already be in a vulnerable position. A responsible tool needs to be careful with files, careful with claims, and careful with language. It should explain what it knows, what it does not know, and why it reached its conclusion.

That is what AI Deepfake Analyzer is trying to do. It is not a promise of perfect truth. It is a privacy-first evidence workflow: upload or submit a public URL, analyze multiple layers, collect expert opinions, calibrate the verdict, and produce a report that a human can actually understand.

Live demo: https://devraj1990-deepfake-moe.hf.space

GitHub repository: https://github.com/Devrajsinh-Jhala/DeepFake-MoE

