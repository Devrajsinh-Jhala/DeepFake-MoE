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
  Server,
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
  { title: 'Input Boundary', detail: 'Upload or public URL, consent gate, type limits, SSRF protection, encrypted temporary media.', icon: Lock },
  { title: 'Evidence Layers', detail: 'EXIF/XMP, C2PA, hashes, compression, noise, frequency, and regional anomaly maps.', icon: Layers3 },
  { title: 'Mixture Of Experts', detail: 'Generic detectors, portrait-gated specialist, provenance expert, and forensic residual expert.', icon: BrainCircuit },
  { title: 'Safety Arbiter', detail: 'Reliability weighting, disagreement handling, confidence caps, and abstention before accusation.', icon: ShieldAlert },
  { title: 'Report Export', detail: 'Victim-friendly summary, JSON/PDF appendix, reproducibility notes, and early deletion.', icon: FileText },
];

const expertPanels = [
  ['Visual Ensemble', 'Three generic AI-image detectors with reliability-weighted votes.'],
  ['Portrait Specialist', 'Runs only after a portrait-likelihood gate to reduce real portrait false positives.'],
  ['Forensic Residuals', 'Compression, ELA, noise, frequency, and regional tile consistency checks.'],
  ['Provenance', 'Metadata markers, C2PA status, public-source context, and perceptual hashes.'],
];

const deploymentControls = [
  ['Ephemeral Storage', 'Encrypted temp media, short TTLs, early delete endpoint, no raw media returned.'],
  ['Public Safety', 'No face search, no doxxing, no login scraping, no private identity inference.'],
  ['Production Guardrails', 'PostgreSQL, Redis/RQ, rate limits, audit hashing, readiness checks, security headers.'],
  ['Calibration Gate', 'Golden-set benchmark blocks launch when false positives or high-confidence errors fail gates.'],
];

const reportFeatures = [
  ['Victim Summary', 'Plain-language verdict, confidence band, strongest evidence, and practical next steps.', FileText],
  ['Evidence Ledger', 'Layer-by-layer metadata, provenance, forensic, model, and uncertainty findings.', Layers3],
  ['Expert Opinions', 'Visual ensemble, portrait specialist, forensic residuals, provenance, and safety arbiter votes.', BrainCircuit],
  ['Technical Export', 'JSON and PDF downloads with hashes, detector scores, regional map, and reproducibility notes.', Download],
];

const heroHighlights = [
  ['Explainable', 'Every verdict has model, metadata, forensic, and uncertainty evidence.'],
  ['Victim-safe', 'The arbiter abstains when evidence is weak instead of overclaiming.'],
  ['Private', 'Media is ephemeral, blurred by default, and never used for identity search.'],
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
                  <h2>{Math.round(verdict.ai_probability * 100)}% AI probability</h2>
                  <span>{verdict.confidence} confidence</span>
                </div>

                <div className="meter-group">
                  <Metric label="AI probability" value={verdict.ai_probability} />
                  <Metric label="Manipulation probability" value={verdict.manipulation_probability} />
                  <Metric label="Detector disagreement" value={verdict.disagreement} />
                </div>

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
            <p className="eyebrow hero-eyebrow">Public evidence triage for synthetic media abuse</p>
            <h1>AI Deepfake Analyzer</h1>
            <p>
              A privacy-first authenticity platform that explains every verdict through calibrated model opinions,
              forensic layers, provenance checks, and victim-safe abstention.
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

      <section className="landing-band architecture-band" id="architecture">
        <div className="section-head">
          <p className="eyebrow">Layered pipeline</p>
          <h2>Evidence moves through separate, explainable stages before the final verdict.</h2>
        </div>
        <div className="pipeline-grid">
          {architectureStages.map((stage, index) => {
            const Icon = stage.icon;
            return (
              <article className="pipeline-card" style={{ '--delay': `${index * 110}ms` }} key={stage.title}>
                <Icon size={22} />
                <h3>{stage.title}</h3>
                <p>{stage.detail}</p>
              </article>
            );
          })}
        </div>
      </section>

      <section className="landing-band expert-band" id="experts">
        <div className="section-head">
          <p className="eyebrow">Mixture of experts</p>
          <h2>Raw model confidence is not trusted alone.</h2>
          <p>
            Each expert produces an opinion, and the safety arbiter decides whether the evidence is strong enough
            for likely real, likely AI-generated, likely manipulated, or inconclusive.
          </p>
        </div>
        <div className="expert-grid">
          {expertPanels.map(([title, detail]) => (
            <article className="expert-card" key={title}>
              <BrainCircuit size={21} />
              <h3>{title}</h3>
              <p>{detail}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-band reports-band" id="reports">
        <div className="reports-layout">
          <div>
            <div className="section-head">
              <p className="eyebrow">Downloadable reports</p>
              <h2>Every analysis becomes a readable report and a technical evidence package.</h2>
              <p>
                The public view is calm and victim-friendly. The appendix is detailed enough for reviewers,
                platform moderators, and technical helpers to understand how the conclusion was reached.
              </p>
            </div>
            <div className="report-feature-grid">
              {reportFeatures.map(([title, detail, icon]) => {
                const FeatureIcon = icon;
                return (
                  <article className="report-feature" key={title}>
                    <FeatureIcon size={20} />
                    <div>
                      <h3>{title}</h3>
                      <p>{detail}</p>
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
          <p className="eyebrow">Public launch posture</p>
          <h2>Built for sensitive-media handling, not casual image guessing.</h2>
        </div>
        <div className="deployment-grid">
          {deploymentControls.map(([title, detail]) => (
            <article className="deployment-item" key={title}>
              <CheckCircle2 size={20} />
              <div>
                <h3>{title}</h3>
                <p>{detail}</p>
              </div>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}

function ReportPreviewScene() {
  return (
    <div className="report-preview-scene" aria-hidden="true">
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
          <strong>79%</strong>
          <span>medium confidence</span>
        </div>
        <div className="report-bars">
          <span />
          <span />
          <span />
        </div>
        <div className="report-layer-list">
          {['Model consensus', 'Metadata and C2PA', 'Noise and ELA', 'Regional anomaly map'].map((item, index) => (
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
  );
}

function ArchitectureScene() {
  const nodes = [
    ['Metadata', 'EXIF/XMP scan', Database],
    ['C2PA', 'Credential check', BadgeCheck],
    ['Forensics', 'Noise and ELA', Layers3],
    ['Models', 'MoE detector vote', BrainCircuit],
    ['Arbiter', 'Confidence gate', Gauge],
    ['Report', 'JSON/PDF export', FileText],
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
          <strong>Layered analysis</strong>
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
        <span><Database size={16} /> Hash</span>
        <span><Cpu size={16} /> Models</span>
        <span><Gauge size={16} /> Gate</span>
        <span><BadgeCheck size={16} /> Report</span>
        <span><Server size={16} /> Worker</span>
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
          <li>{consensus.real_votes || 0} model votes for real or human-origin.</li>
          <li>Reliability-weighted model AI probability: {Math.round((consensus.average_ai_probability || 0) * 100)}%.</li>
          <li>Raw average model AI probability: {Math.round((consensus.raw_average_ai_probability || 0) * 100)}%.</li>
          <li>Disagreement range: {Math.round((consensus.disagreement_range || 0) * 100)}%.</li>
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
