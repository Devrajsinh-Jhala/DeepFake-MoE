import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  BadgeCheck,
  BrainCircuit,
  CheckCircle2,
  Cpu,
  Database,
  Download,
  Eye,
  EyeOff,
  FileJson,
  FileText,
  Gauge,
  ImageUp,
  Layers3,
  Link,
  Loader2,
  Lock,
  KeyRound,
  RefreshCw,
  ShieldCheck,
  ShieldAlert,
  Trash2,
  Workflow,
} from 'lucide-react';

const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  (window.location.port === '5173' || window.location.port === '4173' ? 'http://127.0.0.1:8000' : window.location.origin);
const ACCESS_TOKEN_ENABLED = import.meta.env.VITE_REQUIRE_ACCESS_TOKEN === 'true';

const verdictCopy = {
  likely_real: 'Likely Real',
  likely_ai_generated: 'Likely AI Generated',
  likely_manipulated_or_deepfake: 'Likely Manipulated',
  inconclusive: 'Inconclusive',
};

const architectureStages = [
  {
    title: 'Private Intake',
    detail: 'Upload or public URL, consent gate, MIME validation, SSRF protection, and encrypted temporary media.',
    checks: ['15 MB and pixel limits', 'Public URL restrictions', '15-minute media TTL'],
    icon: Lock,
  },
  {
    title: 'Provenance First',
    detail: 'EXIF/XMP, C2PA content credentials, software markers, source context, and cryptographic hashes.',
    checks: ['Missing metadata stays neutral', 'C2PA claims are verified', 'GPS is redacted in reports'],
    icon: Database,
  },
  {
    title: 'Calibrated MoE',
    detail: 'Community Forensics runs across three image views, then two independent models provide counter-opinions.',
    checks: ['Model-specific thresholds', 'Three-view stability check', 'Raw logits never equal truth'],
    icon: BrainCircuit,
  },
  {
    title: 'Safety Arbiter',
    detail: 'Calibrated stances are combined with provenance and forensic counter-evidence before any verdict is emitted.',
    checks: ['Primary-anchored consensus', 'Real-vote false-positive guard', 'Abstention when evidence conflicts'],
    icon: ShieldAlert,
  },
  {
    title: 'Evidence Report',
    detail: 'A victim-friendly summary and technical PDF/JSON ledger preserve the reasoning, caveats, and reproducibility data.',
    checks: ['Decision and counter-evidence', 'Model and layer ledgers', 'Early deletion endpoint'],
    icon: FileText,
  },
];

const expertPanels = [
  {
    title: 'Broad Primary',
    detail: 'Community Forensics checks the original, a 92% center crop, and a controlled JPEG view.',
    signals: ['Three-view median', 'Transform stability', 'Broad generator coverage'],
    guardrail: 'A stable primary score still cannot decide the verdict alone.',
  },
  {
    title: 'Counter-Models',
    detail: 'Two independently trained classifiers challenge the primary with different data and decision boundaries.',
    signals: ['Hard AI vote', 'Real/human vote', 'Abstention-band vote'],
    guardrail: 'A real vote or strong disagreement blocks an overconfident accusation.',
  },
  {
    title: 'Forensic Residuals',
    detail: 'Image layers are decomposed into compression, noise, edge, frequency, and tile-level evidence.',
    signals: ['ELA score', 'Noise inconsistency', 'Regional anomaly severity'],
    guardrail: 'Forensics are weak supporting signals, never final proof alone.',
  },
  {
    title: 'Provenance',
    detail: 'Metadata and content credentials are checked before pixel-based conclusions are trusted.',
    signals: ['EXIF/XMP fields', 'C2PA status', 'SHA/perceptual hashes'],
    guardrail: 'Missing metadata is treated as neutral, not proof of AI generation.',
  },
];

const moeExperts = [
  {
    title: 'Community Forensics',
    detail: 'Broad ViT primary trained on a highly diverse synthetic-image corpus and evaluated across three views.',
    output: 'Primary stance + stability',
    icon: Cpu,
  },
  {
    title: 'Ateeqq Counter-Model',
    detail: 'Independent visual classifier with a strict AI threshold and reduced reliability weight.',
    output: 'Hard AI / real / abstain',
    icon: BrainCircuit,
  },
  {
    title: 'Distilled Counter-Model',
    detail: 'A lightweight detector with a different boundary that widens model diversity.',
    output: 'Independent counter-opinion',
    icon: Gauge,
  },
  {
    title: 'Forensic Expert',
    detail: 'Noise, ELA, frequency, edge, and regional-map evidence that supports or challenges model scores.',
    output: 'Non-model evidence',
    icon: Layers3,
  },
  {
    title: 'Provenance Expert',
    detail: 'EXIF/XMP, C2PA status, generative markers, public URL context, and hashes.',
    output: 'Source context',
    icon: Database,
  },
];

const moeRules = [
  'The broad primary must remain stable across original, crop, and JPEG views.',
  'Each raw score enters a model-specific AI, real, or abstention band.',
  'Primary-anchored model-only consensus requires every counter-expert to lean AI.',
  'A real/human vote, poor input quality, or disagreement lowers the evidence score.',
  'The safety arbiter preserves inconclusive when independent evidence does not agree.',
];

const deploymentControls = [
  {
    title: 'Ephemeral Storage',
    detail: 'Encrypted temp media, short TTLs, early delete endpoint, no raw media returned.',
    checks: ['15-minute raw-media TTL', '24-hour job/report metadata', 'User-triggered deletion'],
  },
  {
    title: 'Public Safety',
    detail: 'No face search, no doxxing, no login scraping, no private identity inference.',
    checks: ['Public links only', 'No identity attribution', 'Sensitive-preview blur'],
  },
  {
    title: 'Runtime Guardrails',
    detail: 'Rate limits, privacy-safe audit identifiers, readiness checks, security headers, and background execution.',
    checks: ['Health and readiness probes', 'Per-client rate limiting', 'No raw media in logs'],
  },
  {
    title: 'Scale Profile',
    detail: 'The same API supports PostgreSQL and Redis/RQ when deployed across multiple workers and instances.',
    checks: ['Server database validation', 'Queue-backed workers', 'Deployment-time safety checks'],
  },
];

const reportFeatures = [
  {
    title: 'Victim Summary',
    detail: 'Plain-language verdict, confidence band, strongest evidence, and practical next steps.',
    includes: ['Verdict and confidence', 'Strongest evidence', 'Limitations and next steps'],
    icon: FileText,
  },
  {
    title: 'Evidence Ledger',
    detail: 'Layer-by-layer metadata, provenance, forensic, model, and uncertainty findings.',
    includes: ['Layer conclusion', 'AI/manipulation signal', 'Method and limitations'],
    icon: Layers3,
  },
  {
    title: 'Model Arbitration',
    detail: 'Primary and counter-model scores, transform stability, calibrated stances, disagreement, and arbiter policy.',
    includes: ['Raw and calibrated scores', 'Primary-anchored alignment', 'Abstention rationale'],
    icon: BrainCircuit,
  },
  {
    title: 'Technical Export',
    detail: 'JSON and PDF downloads with hashes, detector scores, regional map, and reproducibility notes.',
    includes: ['SHA/perceptual hashes', 'Detector scores', 'Reproducibility notes'],
    icon: Download,
  },
];

const heroHighlights = [
  ['Calibrated', 'Model-specific gates turn raw logits into AI, real, or abstain stances.'],
  ['Victim-safe', 'The arbiter preserves uncertainty instead of turning weak signals into accusations.'],
  ['Private', 'Raw media expires after 15 minutes and is never used for face or identity search.'],
];

const methodFacts = [
  ['3 views', 'Primary stability check', Cpu],
  ['3 models', 'One primary, two counter-experts', BrainCircuit],
  ['10 layers', 'Provenance, pixels, residuals, regions', Layers3],
  ['15 min', 'Raw-media deletion window', Lock],
  ['PDF + JSON', 'Human and machine-readable evidence', FileText],
];

function App() {
  const [mode, setMode] = useState('upload');
  const [file, setFile] = useState(null);
  const [url, setUrl] = useState('');
  const [consent, setConsent] = useState(false);
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [accessToken, setAccessToken] = useState(() => window.localStorage.getItem('aida_access_token') || '');
  const [previewBlurred, setPreviewBlurred] = useState(true);
  const previewUrl = useMemo(() => (file ? URL.createObjectURL(file) : ''), [file]);
  const pollRef = useRef(null);

  const authHeaders = useCallback(() => (
    ACCESS_TOKEN_ENABLED && accessToken.trim() ? { 'X-AIDA-Access-Token': accessToken.trim() } : {}
  ), [accessToken]);

  const refreshAnalysis = useCallback(async (id, options = {}) => {
    try {
      const response = await fetch(`${API_BASE}/analyses/${id}`, { headers: authHeaders() });
      const payload = await parseResponse(response);
      setAnalysis(payload);
    } catch (err) {
      if (!options.quiet) setError(err.message);
    }
  }, [authHeaders]);

  useEffect(() => () => previewUrl && URL.revokeObjectURL(previewUrl), [previewUrl]);

  useEffect(() => {
    if (!ACCESS_TOKEN_ENABLED) return;
    if (accessToken.trim()) {
      window.localStorage.setItem('aida_access_token', accessToken.trim());
    } else {
      window.localStorage.removeItem('aida_access_token');
    }
  }, [accessToken]);

  useEffect(() => {
    if (!analysis?.id || !['pending', 'running'].includes(analysis.status)) return undefined;
    pollRef.current = window.setInterval(() => {
      refreshAnalysis(analysis.id, { quiet: true });
    }, 1600);
    return () => window.clearInterval(pollRef.current);
  }, [analysis?.id, analysis?.status, refreshAnalysis]);

  async function submitAnalysis(event) {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    setAnalysis(null);

    try {
      const form = new FormData();
      form.append('consent_confirmed', consent ? 'true' : 'false');
      if (mode === 'upload') {
        if (!file) throw new Error('Choose an image file.');
        form.append('file', file);
      } else {
        if (!url.trim()) throw new Error('Enter a public URL.');
        form.append('url', url.trim());
      }

      const response = await fetch(`${API_BASE}/analyses`, { method: 'POST', body: form, headers: authHeaders() });
      const payload = await parseResponse(response);
      setAnalysis(payload);
      await refreshAnalysis(payload.id, { quiet: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function downloadReport(format) {
    if (!analysis?.id) return;
    try {
      const response = await fetch(`${API_BASE}/analyses/${analysis.id}/report?format=${format}`, { headers: authHeaders() });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || `Download failed with HTTP ${response.status}`);
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `analysis-${analysis.id}.${format}`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    }
  }

  async function deleteAnalysis() {
    if (!analysis?.id) return;
    try {
      const response = await fetch(`${API_BASE}/analyses/${analysis.id}`, { method: 'DELETE', headers: authHeaders() });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || `Delete failed with HTTP ${response.status}`);
      }
      setAnalysis(null);
      setError('');
    } catch (err) {
      setError(err.message);
    }
  }

  const result = analysis?.result;
  const verdict = result?.verdict;

  return (
    <main>
      <LandingPage />
      <section className="shell" id="analyzer">
        <div className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Privacy-first authenticity analysis</p>
            <h1>AI Deepfake Analyzer</h1>
          </div>
          <div className="status-pill">
            <Lock size={16} />
            Ephemeral media
          </div>
        </header>

        <div className="grid">
          <form className="panel input-panel" onSubmit={submitAnalysis}>
            <div className="segmented" aria-label="Input type">
              <button type="button" className={mode === 'upload' ? 'active' : ''} onClick={() => setMode('upload')}>
                <ImageUp size={17} />
                Upload
              </button>
              <button type="button" className={mode === 'url' ? 'active' : ''} onClick={() => setMode('url')}>
                <Link size={17} />
                Public URL
              </button>
            </div>

            {ACCESS_TOKEN_ENABLED && (
              <label className="field compact-field">
                <span>Access token</span>
                <div className="token-input">
                  <KeyRound size={17} />
                  <input
                    value={accessToken}
                    onChange={(event) => setAccessToken(event.target.value)}
                    type="password"
                    autoComplete="off"
                    placeholder="Private beta token"
                  />
                </div>
              </label>
            )}

            {mode === 'upload' ? (
              <label className="dropzone">
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp,image/gif,image/bmp,image/tiff"
                  onChange={(event) => setFile(event.target.files?.[0] || null)}
                />
                {previewUrl ? (
                  <div className="preview-wrap">
                    <img className={previewBlurred ? 'blurred preview' : 'preview'} src={previewUrl} alt="" />
                    <button type="button" className="icon-action" onClick={(event) => {
                      event.preventDefault();
                      setPreviewBlurred((value) => !value);
                    }}>
                      {previewBlurred ? <Eye size={18} /> : <EyeOff size={18} />}
                      {previewBlurred ? 'Reveal' : 'Blur'}
                    </button>
                  </div>
                ) : (
                  <div className="drop-empty">
                    <ImageUp size={28} />
                    <span>Choose image</span>
                  </div>
                )}
              </label>
            ) : (
              <label className="field">
                <span>Public post or image URL</span>
                <input value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://example.com/post" />
              </label>
            )}

            <label className="check-row">
              <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} />
              <span>I have the right to submit this media for analysis.</span>
            </label>

            {error && (
              <div className="alert">
                <AlertTriangle size={18} />
                {error}
              </div>
            )}

            <button className="primary" type="submit" disabled={submitting}>
              {submitting ? <Loader2 className="spin" size={18} /> : <ShieldCheck size={18} />}
              Analyze
            </button>
          </form>

          <section className="panel result-panel">
            {!analysis && <EmptyState />}
            {analysis && !result && (
              <div className="running">
                <Loader2 className="spin" size={30} />
                <h2>{analysis.status === 'failed' ? 'Analysis failed' : 'Analysis running'}</h2>
                <p>{analysis.error || 'Preparing the evidence layers.'}</p>
                <button type="button" className="secondary" onClick={() => refreshAnalysis(analysis.id)}>
                  <RefreshCw size={16} />
                  Refresh
                </button>
              </div>
            )}
            {result && (
              <div className="report">
                <div className={`verdict ${verdict.label}`}>
                  <p>{verdictCopy[verdict.label] || verdict.label}</p>
                  <h2>{Math.round(verdict.ai_probability * 100)}% AI evidence score</h2>
                  <span>{verdict.confidence} confidence</span>
                </div>

                <div className="meter-group">
                  <Metric label="AI evidence score" value={verdict.ai_probability} />
                  <Metric label="Manipulation evidence" value={verdict.manipulation_probability} />
                  <Metric label="Cross-layer disagreement" value={verdict.disagreement} />
                </div>

                <p className="score-disclaimer">
                  This is calibrated evidence strength, not the probability that a person or image is fake.
                </p>

                <div className="actions">
                  <button type="button" className="secondary" onClick={() => downloadReport('json')}>
                    <FileJson size={17} />
                    JSON
                  </button>
                  <button type="button" className="secondary" onClick={() => downloadReport('pdf')}>
                    <FileText size={17} />
                    PDF
                  </button>
                  <button type="button" className="secondary" onClick={() => downloadReport('pdf')}>
                    <Download size={17} />
                    Save
                  </button>
                  <button type="button" className="secondary danger-action" onClick={deleteAnalysis}>
                    <Trash2 size={17} />
                    Delete
                  </button>
                </div>

                <DecisionSummary explainability={result.explainability} />
                <ExpertOpinions opinions={result.explainability?.expert_opinions || []} />
                <EvidenceLayers layers={result.layers} />
                <Explainability explainability={result.explainability} />
                <RegionEvidenceMap map={result.explainability?.regional_evidence_map} />
                <AnalyticalLayers layers={result.analytical_layers || result.explainability?.layer_ledger?.layers || []} />
                <TechnicalAppendix appendix={result.technical_appendix} />
              </div>
            )}
          </section>
        </div>
        </div>
      </section>
    </main>
  );
}

function LandingPage() {
  return (
    <>
      <section className="landing-hero" id="top">
        <ArchitectureScene />
        <nav className="landing-nav" aria-label="Primary">
          <a className="landing-brand" href="#top">
            <ShieldCheck size={18} />
            AIDA
          </a>
          <div className="landing-nav-links">
            <a href="#architecture">Architecture</a>
            <a href="#experts">Experts</a>
            <a href="#reports">Reports</a>
            <a href="#deployment">Deployment</a>
            <a className="nav-action" href="#analyzer">Analyze</a>
          </div>
        </nav>
        <div className="hero-content">
          <div className="hero-copy">
            <div className="hero-status">
              <span />
              <strong>Public analyzer deployed</strong>
              <em>Evidence score, not certainty</em>
            </div>
            <p className="eyebrow hero-eyebrow">Public evidence triage for synthetic media abuse</p>
            <h1>AI Deepfake Analyzer</h1>
            <p>
              A privacy-first authenticity platform that combines a multi-view visual ensemble, provenance checks,
              pixel forensics, and a false-positive-aware safety arbiter. Every result shows what supported it,
              what contradicted it, and why the system may still be wrong.
            </p>
            <div className="hero-actions">
              <a className="hero-primary" href="#analyzer">
                <ShieldCheck size={18} />
                Start Analysis
              </a>
              <a className="hero-secondary" href="#architecture">
                <Workflow size={18} />
                View Architecture
              </a>
            </div>
            <div className="hero-proof-grid">
              {heroHighlights.map(([title, detail]) => (
                <article key={title}>
                  <BadgeCheck size={17} />
                  <div>
                    <strong>{title}</strong>
                    <span>{detail}</span>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="method-strip" aria-label="Current analysis method">
        <div className="method-strip-inner">
          {methodFacts.map(([value, label, icon]) => {
            const FactIcon = icon;
            return (
              <article key={value}>
                <FactIcon size={18} />
                <strong>{value}</strong>
                <span>{label}</span>
              </article>
            );
          })}
        </div>
      </section>

      <section className="landing-band architecture-band" id="architecture">
        <div className="section-head">
          <p className="eyebrow">System architecture</p>
          <h2>One image enters. Independent evidence lanes return to a calibrated safety arbiter.</h2>
          <p>
            Provenance, visual models, and low-level forensics are deliberately separated so one noisy family of
            signals cannot silently dominate the conclusion.
          </p>
        </div>
        <ArchitectureFlowchart />
        <div className="pipeline-grid">
          {architectureStages.map((stage, index) => {
            const Icon = stage.icon;
            return (
              <article className="pipeline-card" style={{ '--delay': `${index * 110}ms` }} key={stage.title}>
                <Icon size={22} />
                <h3>{stage.title}</h3>
                <p>{stage.detail}</p>
                <ul>
                  {stage.checks.map((check) => (
                    <li key={check}>{check}</li>
                  ))}
                </ul>
              </article>
            );
          })}
        </div>
      </section>

      <section className="landing-band expert-band" id="experts">
        <div className="section-head">
          <p className="eyebrow">Calibrated mixture of experts</p>
          <h2>Raw model outputs are converted into stances before they can influence a person.</h2>
          <p>
            The primary detector checks three transformed views. Two counter-models challenge it, while provenance
            and forensic experts contribute independent evidence. The arbiter can still abstain.
          </p>
        </div>
        <MoEFlowDiagram />
        <div className="expert-grid">
          {expertPanels.map((panel) => (
            <article className="expert-card" key={panel.title}>
              <BrainCircuit size={21} />
              <h3>{panel.title}</h3>
              <p>{panel.detail}</p>
              <div className="detail-tags">
                {panel.signals.map((signal) => (
                  <span key={signal}>{signal}</span>
                ))}
              </div>
              <strong>{panel.guardrail}</strong>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-band reports-band" id="reports">
        <div className="reports-layout">
          <div>
            <div className="section-head">
              <p className="eyebrow">Downloadable reports</p>
              <h2>Every result becomes a decision brief and a reproducible technical evidence package.</h2>
              <p>
                The six-section PDF begins with a victim-friendly summary, then exposes calibration, expert votes,
                layer evidence, the regional map, file facts, limitations, and responsible next steps.
              </p>
            </div>
            <div className="report-feature-grid">
              {reportFeatures.map((feature) => {
                const FeatureIcon = feature.icon;
                return (
                  <article className="report-feature" key={feature.title}>
                    <FeatureIcon size={20} />
                    <div>
                      <h3>{feature.title}</h3>
                      <p>{feature.detail}</p>
                      <ul>
                        {feature.includes.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  </article>
                );
              })}
            </div>
            <a className="reports-action" href="#analyzer">
              <Download size={18} />
              Generate a report
            </a>
          </div>
          <ReportPreviewScene />
        </div>
      </section>

      <section className="landing-band deployment-band" id="deployment">
        <div className="section-head">
          <p className="eyebrow">Public deployment posture</p>
          <h2>Designed for sensitive evidence handling, with a clear path from public beta to multi-worker scale.</h2>
          <p>
            The current public runtime enforces privacy, limits, health checks, and deletion. PostgreSQL and Redis/RQ
            are supported for a scaled deployment, but the interface never claims that pixels alone prove authenticity.
          </p>
        </div>
        <div className="deployment-grid">
          {deploymentControls.map((control) => (
            <article className="deployment-item" key={control.title}>
              <CheckCircle2 size={20} />
              <div>
                <h3>{control.title}</h3>
                <p>{control.detail}</p>
                <ul>
                  {control.checks.map((check) => (
                    <li key={check}>{check}</li>
                  ))}
                </ul>
              </div>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}

function MoEFlowDiagram() {
  return (
    <div className="moe-diagram" aria-label="Mixture of experts model architecture">
      <div className="moe-flow-shell">
        <div className="moe-stage-card moe-input-card">
          <span>01</span>
          <ImageUp size={24} />
          <h3>Preprocess</h3>
          <p>Validate, normalize color, measure quality risk, compute hashes, and prepare independent evidence inputs.</p>
        </div>

        <div className="moe-stage-card moe-gate-card">
          <span>02</span>
          <Gauge size={24} />
          <h3>Multi-view Gate</h3>
          <p>Create original, 92% center-crop, and JPEG-85 views for the broad primary stability check.</p>
        </div>

        <section className="moe-expert-panel" aria-label="Expert detector panel">
          <div className="moe-panel-head">
            <span>03</span>
            <div>
              <h3>Expert Panel</h3>
              <p>One broad primary, two counter-models, and independent forensic and provenance experts.</p>
            </div>
          </div>
          <div className="moe-expert-stack">
          {moeExperts.map((expert, index) => {
            const ExpertIcon = expert.icon;
            return (
              <article className="moe-expert-node" style={{ '--index': index }} key={expert.title}>
                <ExpertIcon size={18} />
                <div>
                  <h4>{expert.title}</h4>
                  <p>{expert.detail}</p>
                  <strong>{expert.output}</strong>
                </div>
              </article>
            );
          })}
          </div>
        </section>

        <div className="moe-stage-card moe-normalizer-card">
          <span>04</span>
          <BadgeCheck size={24} />
          <h3>Stance Calibrator</h3>
          <p>Apply per-model AI/real thresholds. Scores in between become abstentions, then reliability weights are applied.</p>
        </div>

        <div className="moe-stage-card danger moe-arbiter-card">
          <span>05</span>
          <ShieldAlert size={24} />
          <h3>Safety Arbiter</h3>
          <p>Require provenance, independent support, unanimous strong votes, or primary-anchored alignment before a strong AI claim.</p>
        </div>

        <div className="moe-verdict-stack">
          <span className="real">likely real</span>
          <span className="ai">likely AI generated</span>
          <span className="manipulated">likely manipulated</span>
          <span className="unknown">inconclusive</span>
        </div>
      </div>
      <div className="moe-rule-grid">
        {moeRules.map((rule) => (
          <div className="moe-rule" key={rule}>
            <CheckCircle2 size={16} />
            <span>{rule}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ArchitectureFlowchart() {
  const laneGroups = [
    ['Provenance lane', [
      ['Metadata', 'EXIF/XMP, software markers, GPS redaction', Database],
      ['C2PA', 'Content credentials and signed generation claims', BadgeCheck],
    ]],
    ['Visual-model lane', [
      ['Broad Primary', 'Community Forensics across three stable views', Cpu],
      ['Counter-Models', 'Ateeqq plus an independent distilled classifier', BrainCircuit],
    ]],
    ['Forensic lane', [
      ['Pixel Residuals', 'ELA, noise, luminance, chroma, edge, frequency', Layers3],
      ['Regional Map', 'A 4x4 anomaly grid with explicit limitations', Gauge],
    ]],
  ];
  const flowSteps = [
    ['01', 'Private Intake', 'Consent, type and pixel limits, SSRF defense, encryption, and short media TTL.', Lock],
    ['02', 'Evidence Bus', 'Fork the validated packet into provenance, model, and forensic lanes.', Workflow],
    ['03', 'Expert Routing', 'Run only the evidence methods that are available and appropriate for this file.', BrainCircuit],
    ['04', 'Safety Arbiter', 'Calibrate stances, record disagreement, cap scores, or abstain.', ShieldAlert],
    ['05', 'Evidence Report', 'Return a plain-language verdict plus PDF and JSON technical ledgers.', FileText],
  ];

  return (
    <div className="architecture-map" aria-label="Deepfake analysis architecture flow">
      <div className="architecture-flow-grid">
        <span className="flow-packet packet-one" />
        <span className="flow-packet packet-two" />
        {flowSteps.map(([index, title, detail, icon]) => {
          const StepIcon = icon;
          return (
            <article className={`flow-step ${title === 'Evidence Bus' ? 'hub-step' : ''}`} key={title}>
              <span className="node-index">{index}</span>
              <div className="node-orb"><StepIcon size={24} /></div>
              <h3>{title}</h3>
              <p>{detail}</p>
            </article>
          );
        })}
      </div>

      <div className="evidence-lanes">
        {laneGroups.map(([lane, items]) => (
          <section className="layer-cluster" key={lane}>
            <span className="cluster-label">{lane}</span>
            {items.map(([title, detail, icon]) => {
              const LayerIcon = icon;
              return (
                <article className="layer-chip" key={title}>
                  <LayerIcon size={18} />
                  <div>
                    <strong>{title}</strong>
                    <span>{detail}</span>
                  </div>
                </article>
              );
            })}
          </section>
        ))}

        <div className="decision-stack">
          <span>likely real</span>
          <span>likely AI generated</span>
          <span>likely manipulated</span>
          <span>inconclusive</span>
        </div>
      </div>
    </div>
  );
}

function ReportPreviewScene() {
  return (
    <div className="report-preview-scene" aria-hidden="true">
      <div className="report-preview-frame">
        <div className="report-sheet">
          <div className="report-sheet-head">
            <div>
              <span />
              <strong>Authenticity Report</strong>
            </div>
            <BadgeCheck size={20} />
          </div>
          <div className="report-verdict-preview">
            <p>Likely AI generated</p>
            <strong>72%</strong>
            <span>medium confidence</span>
          </div>
          <div className="report-bars">
            <span />
            <span />
            <span />
          </div>
          <div className="report-layer-list">
            {['Primary-anchored alignment', 'Metadata and C2PA', 'Cross-layer disagreement', 'Regional anomaly map'].map((item, index) => (
              <div className="report-layer-row" style={{ '--index': index }} key={item}>
                <i />
                <span>{item}</span>
                <strong>{index === 0 ? 'supports AI' : index === 1 ? 'neutral' : 'weak signal'}</strong>
              </div>
            ))}
          </div>
        </div>
        <div className="export-stack">
          <span><FileJson size={17} /> JSON</span>
          <span><FileText size={17} /> PDF</span>
          <span><Download size={17} /> Save</span>
        </div>
      </div>
    </div>
  );
}

function ArchitectureScene() {
  const nodes = [
    ['Primary', '3-view stability', Cpu],
    ['Counters', '2 independent votes', BrainCircuit],
    ['Provenance', 'EXIF/XMP + C2PA', Database],
    ['Forensics', '10 evidence layers', Layers3],
    ['Arbiter', 'Abstention gate', Gauge],
    ['Report', 'PDF + JSON ledger', FileText],
  ];
  return (
    <div className="architecture-scene" aria-hidden="true">
      <div className="scene-rail rail-one" />
      <div className="scene-rail rail-two" />
      <div className="scene-rail rail-three" />
      <div className="evidence-workflow">
        <div className="workflow-header">
          <span />
          <span />
          <span />
          <strong>Calibrated evidence pipeline</strong>
        </div>
        <div className="workflow-body">
          <div className="media-pane">
            <div className="media-thumbnail">
              <span className="scan-beam" />
              <i />
              <i />
              <i />
            </div>
            <div className="heat-map">
              {Array.from({ length: 16 }, (_, index) => <span key={index} />)}
            </div>
          </div>
          <div className="signal-stack">
            {nodes.map(([title, sub, icon], index) => {
              const NodeIcon = icon;
              return (
                <div className="signal-node" style={{ '--index': index }} key={title}>
                  <NodeIcon size={16} />
                  <strong>{title}</strong>
                  <span>{sub}</span>
                </div>
              );
            })}
          </div>
        </div>
        <div className="confidence-row">
          <span />
          <span />
          <span />
        </div>
      </div>
      <div className="telemetry-strip">
        <span><Cpu size={16} /> 3 views</span>
        <span><BrainCircuit size={16} /> 3 models</span>
        <span><Layers3 size={16} /> 10 layers</span>
        <span><Lock size={16} /> 15 min TTL</span>
        <span><FileText size={16} /> PDF + JSON</span>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="empty">
      <ShieldCheck size={34} />
      <h2>Ready</h2>
      <p>Upload an image or submit a public URL.</p>
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="metric">
      <div className="metric-head">
        <span>{label}</span>
        <strong>{Math.round(value * 100)}%</strong>
      </div>
      <div className="bar">
        <span style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
    </div>
  );
}

function DecisionSummary({ explainability }) {
  const decision = explainability?.decision_support;
  if (!decision) return null;
  return (
    <div className="section-list">
      <h3>Decision Summary</h3>
      <article className="decision-card">
        <p>{decision.plain_summary}</p>
        <div className="decision-grid">
          <DecisionColumn title="Primary drivers" items={decision.primary_drivers} />
          <DecisionColumn title="Counter-evidence" items={decision.counter_evidence} />
          <DecisionColumn title="Uncertainty" items={decision.uncertainty_factors} />
          <DecisionColumn title="What would help" items={decision.what_would_help} />
        </div>
      </article>
    </div>
  );
}

function DecisionColumn({ title, items = [] }) {
  return (
    <div className="decision-column">
      <h4>{title}</h4>
      <ul>
        {items.slice(0, 4).map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function ExpertOpinions({ opinions }) {
  if (!opinions.length) return null;
  return (
    <div className="section-list">
      <h3>Mixture Of Experts</h3>
      {opinions.map((opinion) => (
        <article className="layer" key={opinion.expert}>
          <div>
            <h4>{opinion.expert}</h4>
            <span>{opinion.stance}</span>
          </div>
          <p className="layer-method">
            {opinion.opinion} - {opinion.confidence} confidence
            {typeof opinion.score === 'number' ? ` - ${Math.round(opinion.score * 100)}%` : ''}
          </p>
          <ul>
            {(opinion.evidence || []).slice(0, 3).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>
      ))}
    </div>
  );
}

function EvidenceLayers({ layers }) {
  return (
    <div className="section-list">
      <h3>Evidence Layers</h3>
      {layers.map((layer) => (
        <article className="layer" key={layer.name}>
          <div>
            <h4>{layer.name}</h4>
            <span>{layer.status}</span>
          </div>
          <ul>
            {layer.findings.slice(0, 4).map((finding) => (
              <li key={finding}>{finding}</li>
            ))}
          </ul>
        </article>
      ))}
    </div>
  );
}

function Explainability({ explainability }) {
  if (!explainability) return null;
  const consensus = explainability.model_consensus || {};
  const standard = explainability.decision_standard || {};
  const strongest = explainability.strongest_evidence || [];
  const trace = explainability.decision_trace || [];
  return (
    <div className="section-list">
      <h3>Explainability</h3>
      {!!trace.length && (
        <article className="layer">
          <div>
            <h4>Decision Trace</h4>
            <span>{trace.length} steps</span>
          </div>
          <ul>
            {trace.slice(0, 5).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>
      )}
      <article className="layer">
        <div>
          <h4>Model Consensus</h4>
          <span>{consensus.enabled_models || 0} models</span>
        </div>
        <ul>
          <li>{consensus.ai_votes || 0} model votes for AI-generated.</li>
          <li>{consensus.lean_ai_votes || 0} of {consensus.enabled_models || 0} experts lean AI after their model-specific gates.</li>
          <li>{consensus.real_votes || 0} model votes for real or human-origin.</li>
          <li>Primary-anchored alignment: {consensus.primary_anchored_alignment ? 'yes' : 'no'}.</li>
          <li>Calibrated model evidence score: {Math.round((consensus.average_ai_probability || 0) * 100)}%.</li>
          <li>Raw average model output: {Math.round((consensus.raw_average_ai_probability || 0) * 100)}%.</li>
          <li>Disagreement range: {Math.round((consensus.disagreement_range || 0) * 100)}%.</li>
          <li>Scores inside each model&apos;s abstention band contribute neutral evidence.</li>
        </ul>
      </article>
      {!!standard.policy && (
        <article className="layer">
          <div>
            <h4>Calibration Gate</h4>
            <span>{standard.policy}</span>
          </div>
          <ul>
            {(standard.false_positive_controls || []).slice(0, 4).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>
      )}
      <article className="layer">
        <div>
          <h4>Strongest Evidence</h4>
          <span>{strongest.length} signals</span>
        </div>
        <ul>
          {strongest.slice(0, 5).map((item) => (
            <li key={`${item.source}-${item.label}`}>
              {item.source}: {item.label}
            </li>
          ))}
        </ul>
      </article>
    </div>
  );
}

function RegionEvidenceMap({ map }) {
  if (!map?.tiles?.length) return null;
  const cols = map.grid?.cols || 4;
  const tiles = [...map.tiles].sort((a, b) => (a.row - b.row) || (a.col - b.col));
  return (
    <div className="section-list">
      <h3>Region Evidence Map</h3>
      <article className="region-card">
        <p>{map.interpretation}</p>
        <div className="region-grid" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}>
          {tiles.map((tile) => (
            <div
              className={`region-tile ${tile.severity_band || 'low'}`}
              key={`${tile.row}-${tile.col}`}
              title={`Row ${tile.row}, column ${tile.col}. Anomaly ${Math.round((tile.severity || 0) * 100)}%. Brightness ${tile.brightness}; noise ${tile.noise}; edge ${tile.edge}.`}
            >
              <span>R{tile.row} C{tile.col}</span>
              <strong>{Math.round((tile.severity || 0) * 100)}%</strong>
            </div>
          ))}
        </div>
        <div className="region-legend">
          <span><i className="low" /> Low</span>
          <span><i className="medium" /> Medium</span>
          <span><i className="high" /> High</span>
          <strong>{map.high_severity_tile_count || 0} high-severity tiles</strong>
        </div>
        <p className="layer-method">
          Max regional score {map.max_score}; mean regional score {map.mean_score}. This map is relative to the submitted image.
        </p>
      </article>
    </div>
  );
}

function AnalyticalLayers({ layers }) {
  if (!layers.length) return null;
  return (
    <div className="section-list">
      <h3>Analytical Layer Ledger</h3>
      {layers.map((layer) => (
        <article className="layer" key={layer.id}>
          <div>
            <h4>{layer.name}</h4>
            <span>{layer.conclusion}</span>
          </div>
          <p className="layer-method">{layer.method}</p>
          <div className="mini-meters">
            <Metric label="AI signal" value={layer.ai_signal || 0} />
            <Metric label="Manipulation signal" value={layer.manipulation_signal || 0} />
          </div>
          <ul>
            {(layer.evidence || []).slice(0, 3).map((finding) => (
              <li key={finding}>{finding}</li>
            ))}
          </ul>
        </article>
      ))}
    </div>
  );
}

function TechnicalAppendix({ appendix }) {
  const detectors = appendix.detectors || [];
  return (
    <details className="appendix">
      <summary>Technical Appendix</summary>
      <div className="appendix-grid">
        <div>
          <h4>Hashes</h4>
          <code>{appendix.hashes.sha256}</code>
          <code>{appendix.hashes.average_hash}</code>
        </div>
        <div>
          <h4>Detectors</h4>
          {detectors.map((detector) => (
            <p key={detector.name}>
              <strong>{detector.name}</strong>: {detector.label} ({detector.status})
              {detector.weight ? `, weight ${Number(detector.weight).toFixed(2)}` : ''}
            </p>
          ))}
        </div>
      </div>
    </details>
  );
}

async function parseResponse(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || `Request failed with HTTP ${response.status}`);
  return payload;
}

export default App;
