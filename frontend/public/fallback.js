(function () {
  var API_BASE = window.location.port === "5173" || window.location.port === "4173" ? "http://127.0.0.1:8000" : window.location.origin;
  var ACCESS_TOKEN_ENABLED = window.AIDA_REQUIRE_ACCESS_TOKEN === true;
  var state = {
    mode: "upload",
    file: null,
    url: "",
    consent: false,
    analysis: null,
    error: "",
    submitting: false,
    accessToken: ACCESS_TOKEN_ENABLED ? window.localStorage.getItem("aida_access_token") || "" : "",
    previewBlurred: true,
    previewUrl: "",
    pollTimer: null
  };

  function bootFallback() {
    var root = document.getElementById("root");
    if (!root) return;
    if (root.children.length > 0 && !document.getElementById("initial-shell")) return;
    root.setAttribute("data-fallback-mounted", "true");
    render();
  }

  window.setTimeout(bootFallback, 700);
  window.addEventListener("error", function () {
    window.setTimeout(bootFallback, 50);
  });

  function render() {
    var root = document.getElementById("root");
    if (!root) return;
    root.innerHTML =
      '<main class="shell">' +
      '<section class="workspace">' +
      '<header class="topbar">' +
      '<div><p class="eyebrow">Privacy-first authenticity analysis</p><h1>AI Deepfake Analyzer</h1></div>' +
      '<div class="status-pill"><span aria-hidden="true">[]</span> Ephemeral media</div>' +
      '</header>' +
      '<div class="grid">' +
      '<form class="panel input-panel" id="fallback-form">' +
      '<div class="segmented" aria-label="Input type">' +
      '<button type="button" id="fallback-upload" class="' + (state.mode === "upload" ? "active" : "") + '">Upload</button>' +
      '<button type="button" id="fallback-url-mode" class="' + (state.mode === "url" ? "active" : "") + '">Public URL</button>' +
      '</div>' +
      renderAccessTokenField() +
      renderInput() +
      '<label class="check-row"><input id="fallback-consent" type="checkbox" ' + (state.consent ? "checked" : "") + '><span>I have the right to submit this media for analysis.</span></label>' +
      (state.error ? '<div class="alert">' + escapeHtml(state.error) + '</div>' : "") +
      '<button class="primary" type="submit" ' + (state.submitting ? "disabled" : "") + ">" + (state.submitting ? "Analyzing..." : "Analyze") + "</button>" +
      "</form>" +
      '<section class="panel result-panel">' + renderResult() + "</section>" +
      "</div>" +
      "</section>" +
      "</main>";
    bind();
  }

  function renderAccessTokenField() {
    if (!ACCESS_TOKEN_ENABLED) return "";
    return '<label class="field compact-field"><span>Access token</span><div class="token-input"><span aria-hidden="true">#</span><input id="fallback-access-token" type="password" autocomplete="off" value="' + escapeAttr(state.accessToken) + '" placeholder="Private beta token"></div></label>';
  }

  function renderInput() {
    if (state.mode === "url") {
      return '<label class="field"><span>Public post or image URL</span><input id="fallback-url" value="' + escapeAttr(state.url) + '" placeholder="https://example.com/post"></label>';
    }
    if (state.previewUrl) {
      return '<label class="dropzone"><input id="fallback-file" type="file" accept="image/png,image/jpeg,image/webp,image/gif,image/bmp,image/tiff">' +
        '<div class="preview-wrap"><img class="' + (state.previewBlurred ? "blurred preview" : "preview") + '" src="' + escapeAttr(state.previewUrl) + '" alt="">' +
        '<button type="button" class="icon-action" id="fallback-blur">' + (state.previewBlurred ? "Reveal" : "Blur") + "</button></div></label>";
    }
    return '<label class="dropzone"><input id="fallback-file" type="file" accept="image/png,image/jpeg,image/webp,image/gif,image/bmp,image/tiff">' +
      '<div class="drop-empty"><span>Choose image</span></div></label>';
  }

  function renderResult() {
    var analysis = state.analysis;
    if (!analysis) {
      return '<div class="empty"><h2>Ready</h2><p>Upload an image or submit a public URL.</p></div>';
    }
    if (!analysis.result) {
      return '<div class="running"><h2>' + (analysis.status === "failed" ? "Analysis failed" : "Analysis running") + "</h2><p>" +
        escapeHtml(analysis.error || "Preparing the evidence layers.") +
        '</p><button type="button" class="secondary" id="fallback-refresh">Refresh</button></div>';
    }

    var result = analysis.result;
    var verdict = result.verdict;
    var label = verdictLabel(verdict.label);
    return '<div class="report">' +
      '<div class="verdict ' + escapeAttr(verdict.label) + '"><p>' + escapeHtml(label) + '</p><h2>' + pct(verdict.ai_probability) + ' AI probability</h2><span>' + escapeHtml(verdict.confidence) + " confidence</span></div>" +
      '<div class="meter-group">' +
      metric("AI probability", verdict.ai_probability) +
      metric("Manipulation probability", verdict.manipulation_probability) +
      metric("Detector disagreement", verdict.disagreement) +
      "</div>" +
      '<div class="actions"><button type="button" class="secondary" id="fallback-json">JSON</button><button type="button" class="secondary" id="fallback-pdf">PDF</button><button type="button" class="secondary danger-action" id="fallback-delete">Delete</button></div>' +
      renderDecisionSummary(result.explainability || {}) +
      renderLayers(result.layers || []) +
      renderExplainability(result.explainability || {}) +
      renderRegionEvidenceMap((result.explainability || {}).regional_evidence_map) +
      renderAnalyticalLayers(result.analytical_layers || (result.explainability && result.explainability.layer_ledger && result.explainability.layer_ledger.layers) || []) +
      renderAppendix(result.technical_appendix || {}) +
      "</div>";
  }

  function metric(label, value) {
    var percent = pct(value);
    return '<div class="metric"><div class="metric-head"><span>' + escapeHtml(label) + "</span><strong>" + percent + '</strong></div><div class="bar"><span style="width:' + percent + '"></span></div></div>';
  }

  function renderDecisionSummary(explainability) {
    var decision = explainability.decision_support;
    if (!decision) return "";
    var html = '<div class="section-list"><h3>Decision Summary</h3><article class="decision-card"><p>' + escapeHtml(decision.plain_summary || "") + '</p><div class="decision-grid">';
    html += renderDecisionColumn("Primary drivers", decision.primary_drivers || []);
    html += renderDecisionColumn("Counter-evidence", decision.counter_evidence || []);
    html += renderDecisionColumn("Uncertainty", decision.uncertainty_factors || []);
    html += renderDecisionColumn("What would help", decision.what_would_help || []);
    return html + '</div></article></div>';
  }

  function renderDecisionColumn(title, items) {
    var html = '<div class="decision-column"><h4>' + escapeHtml(title) + '</h4><ul>';
    items.slice(0, 4).forEach(function (item) {
      html += '<li>' + escapeHtml(item) + '</li>';
    });
    return html + '</ul></div>';
  }

  function renderLayers(layers) {
    var html = '<div class="section-list"><h3>Evidence Layers</h3>';
    layers.forEach(function (layer) {
      html += '<article class="layer"><div><h4>' + escapeHtml(layer.name) + '</h4><span>' + escapeHtml(layer.status) + '</span></div><ul>';
      (layer.findings || []).slice(0, 4).forEach(function (finding) {
        html += "<li>" + escapeHtml(finding) + "</li>";
      });
      html += "</ul></article>";
    });
    return html + "</div>";
  }

  function renderExplainability(explainability) {
    var consensus = explainability.model_consensus || {};
    var strongest = explainability.strongest_evidence || [];
    var trace = explainability.decision_trace || [];
    var html = '<div class="section-list"><h3>Explainability</h3>';
    if (trace.length) {
      html += '<article class="layer"><div><h4>Decision Trace</h4><span>' + escapeHtml(trace.length) + ' steps</span></div><ul>';
      trace.slice(0, 5).forEach(function (item) {
        html += '<li>' + escapeHtml(item) + '</li>';
      });
      html += '</ul></article>';
    }
    html += '<article class="layer"><div><h4>Model Consensus</h4><span>' + escapeHtml(consensus.enabled_models || 0) + ' models</span></div><ul>';
    html += '<li>' + escapeHtml(consensus.ai_votes || 0) + ' model votes for AI-generated.</li>';
    html += '<li>' + escapeHtml(consensus.real_votes || 0) + ' model votes for real or human-origin.</li>';
    html += '<li>Average model AI probability: ' + pct(consensus.average_ai_probability || 0) + '.</li>';
    html += '<li>Disagreement range: ' + pct(consensus.disagreement_range || 0) + '.</li>';
    html += '</ul></article>';
    html += '<article class="layer"><div><h4>Strongest Evidence</h4><span>' + escapeHtml(strongest.length) + ' signals</span></div><ul>';
    strongest.slice(0, 5).forEach(function (item) {
      html += '<li>' + escapeHtml(item.source) + ': ' + escapeHtml(item.label) + '</li>';
    });
    html += '</ul></article></div>';
    return html;
  }

  function renderRegionEvidenceMap(map) {
    if (!map || !map.tiles || !map.tiles.length) return "";
    var cols = map.grid && map.grid.cols ? map.grid.cols : 4;
    var tiles = map.tiles.slice().sort(function (a, b) { return (a.row - b.row) || (a.col - b.col); });
    var html = '<div class="section-list"><h3>Region Evidence Map</h3><article class="region-card"><p>' + escapeHtml(map.interpretation || "") + '</p>';
    html += '<div class="region-grid" style="grid-template-columns:repeat(' + cols + ', minmax(0, 1fr))">';
    tiles.forEach(function (tile) {
      var severity = Math.round((tile.severity || 0) * 100);
      html += '<div class="region-tile ' + escapeAttr(tile.severity_band || "low") + '" title="Row ' + escapeAttr(tile.row) + ', column ' + escapeAttr(tile.col) + ', anomaly ' + severity + '%">' +
        '<span>R' + escapeHtml(tile.row) + ' C' + escapeHtml(tile.col) + '</span><strong>' + severity + '%</strong></div>';
    });
    html += '</div><div class="region-legend"><span><i class="low"></i> Low</span><span><i class="medium"></i> Medium</span><span><i class="high"></i> High</span><strong>' +
      escapeHtml(map.high_severity_tile_count || 0) + ' high-severity tiles</strong></div>';
    html += '<p class="layer-method">Max regional score ' + escapeHtml(map.max_score) + '; mean regional score ' + escapeHtml(map.mean_score) + '. This map is relative to the submitted image.</p></article></div>';
    return html;
  }

  function renderAnalyticalLayers(layers) {
    if (!layers.length) return "";
    var html = '<div class="section-list"><h3>Analytical Layer Ledger</h3>';
    layers.forEach(function (layer) {
      html += '<article class="layer"><div><h4>' + escapeHtml(layer.name) + '</h4><span>' + escapeHtml(layer.conclusion) + '</span></div>';
      html += '<p class="layer-method">' + escapeHtml(layer.method) + '</p>';
      html += '<div class="mini-meters">' + metric("AI signal", layer.ai_signal || 0) + metric("Manipulation signal", layer.manipulation_signal || 0) + '</div><ul>';
      (layer.evidence || []).slice(0, 3).forEach(function (finding) {
        html += '<li>' + escapeHtml(finding) + '</li>';
      });
      html += '</ul></article>';
    });
    return html + '</div>';
  }

  function renderAppendix(appendix) {
    var hashes = appendix.hashes || {};
    var detectors = appendix.detectors || [];
    var html = '<details class="appendix"><summary>Technical Appendix</summary><div class="appendix-grid"><div><h4>Hashes</h4><code>' +
      escapeHtml(hashes.sha256 || "not available") + "</code><code>" + escapeHtml(hashes.average_hash || "not available") +
      "</code></div><div><h4>Detectors</h4>";
    detectors.forEach(function (detector) {
      html += "<p><strong>" + escapeHtml(detector.name) + "</strong>: " + escapeHtml(detector.label) + " (" + escapeHtml(detector.status) + ")</p>";
    });
    return html + "</div></div></details>";
  }

  function bind() {
    var uploadButton = document.getElementById("fallback-upload");
    var urlButton = document.getElementById("fallback-url-mode");
    var form = document.getElementById("fallback-form");
    var consent = document.getElementById("fallback-consent");
    var accessToken = document.getElementById("fallback-access-token");
    var file = document.getElementById("fallback-file");
    var url = document.getElementById("fallback-url");
    var blur = document.getElementById("fallback-blur");
    var refresh = document.getElementById("fallback-refresh");
    var json = document.getElementById("fallback-json");
    var pdf = document.getElementById("fallback-pdf");
    var deleteButton = document.getElementById("fallback-delete");

    if (uploadButton) uploadButton.onclick = function () { state.mode = "upload"; state.error = ""; render(); };
    if (urlButton) urlButton.onclick = function () { state.mode = "url"; state.error = ""; render(); };
    if (consent) consent.onchange = function (event) { state.consent = event.target.checked; };
    if (file) file.onchange = function (event) {
      state.file = event.target.files && event.target.files[0] ? event.target.files[0] : null;
      if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
      state.previewUrl = state.file ? URL.createObjectURL(state.file) : "";
      render();
    };
    if (url) url.oninput = function (event) { state.url = event.target.value; };
    if (accessToken) accessToken.oninput = function (event) {
      state.accessToken = event.target.value;
      if (state.accessToken.trim()) {
        window.localStorage.setItem("aida_access_token", state.accessToken.trim());
      } else {
        window.localStorage.removeItem("aida_access_token");
      }
    };
    if (blur) blur.onclick = function (event) { event.preventDefault(); state.previewBlurred = !state.previewBlurred; render(); };
    if (refresh && state.analysis) refresh.onclick = function () { refreshAnalysis(state.analysis.id, false); };
    if (json && state.analysis) json.onclick = function () { downloadReport("json"); };
    if (pdf && state.analysis) pdf.onclick = function () { downloadReport("pdf"); };
    if (deleteButton && state.analysis) deleteButton.onclick = deleteAnalysis;
    if (form) form.onsubmit = submitAnalysis;
  }

  function submitAnalysis(event) {
    event.preventDefault();
    state.error = "";
    state.submitting = true;
    state.analysis = null;
    render();

    try {
      var form = new FormData();
      form.append("consent_confirmed", state.consent ? "true" : "false");
      if (state.mode === "upload") {
        if (!state.file) throw new Error("Choose an image file.");
        form.append("file", state.file);
      } else {
        if (!state.url.trim()) throw new Error("Enter a public URL.");
        form.append("url", state.url.trim());
      }
      fetch(API_BASE + "/analyses", { method: "POST", body: form, headers: authHeaders() })
        .then(parseResponse)
        .then(function (payload) {
          state.analysis = payload;
          state.submitting = false;
          render();
          refreshAnalysis(payload.id, true);
        })
        .catch(function (error) {
          state.error = error.message;
          state.submitting = false;
          render();
        });
    } catch (error) {
      state.error = error.message;
      state.submitting = false;
      render();
    }
  }

  function refreshAnalysis(id, quiet) {
    fetch(API_BASE + "/analyses/" + id, { headers: authHeaders() })
      .then(parseResponse)
      .then(function (payload) {
        state.analysis = payload;
        render();
        if ((payload.status === "pending" || payload.status === "running") && !state.pollTimer) {
          state.pollTimer = window.setInterval(function () { refreshAnalysis(id, true); }, 1600);
        }
        if (payload.result || payload.status === "failed") {
          window.clearInterval(state.pollTimer);
          state.pollTimer = null;
        }
      })
      .catch(function (error) {
        if (!quiet) state.error = error.message;
        render();
      });
  }

  function downloadReport(format) {
    if (!state.analysis) return;
    fetch(API_BASE + "/analyses/" + state.analysis.id + "/report?format=" + format, { headers: authHeaders() })
      .then(function (response) {
        if (!response.ok) {
          return response.json().catch(function () { return {}; }).then(function (payload) {
            throw new Error(payload.detail || "Download failed with HTTP " + response.status);
          });
        }
        return response.blob();
      })
      .then(function (blob) {
        var url = URL.createObjectURL(blob);
        var anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = "analysis-" + state.analysis.id + "." + format;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        URL.revokeObjectURL(url);
      })
      .catch(function (error) {
        state.error = error.message;
        render();
      });
  }

  function deleteAnalysis() {
    if (!state.analysis) return;
    fetch(API_BASE + "/analyses/" + state.analysis.id, { method: "DELETE", headers: authHeaders() })
      .then(function (response) {
        if (!response.ok) {
          return response.json().catch(function () { return {}; }).then(function (payload) {
            throw new Error(payload.detail || "Delete failed with HTTP " + response.status);
          });
        }
        state.analysis = null;
        state.error = "";
        render();
      })
      .catch(function (error) {
        state.error = error.message;
        render();
      });
  }

  function authHeaders() {
    if (!ACCESS_TOKEN_ENABLED) return {};
    return state.accessToken.trim() ? { "X-AIDA-Access-Token": state.accessToken.trim() } : {};
  }

  function parseResponse(response) {
    return response.json().catch(function () { return {}; }).then(function (payload) {
      if (!response.ok) throw new Error(payload.detail || "Request failed with HTTP " + response.status);
      return payload;
    });
  }

  function verdictLabel(label) {
    return {
      likely_real: "Likely Real",
      likely_ai_generated: "Likely AI Generated",
      likely_manipulated_or_deepfake: "Likely Manipulated",
      inconclusive: "Inconclusive"
    }[label] || label;
  }

  function pct(value) {
    var number = Number(value || 0);
    return Math.round(number * 100) + "%";
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function escapeAttr(value) {
    return escapeHtml(value).replace(/`/g, "&#096;");
  }
})();
