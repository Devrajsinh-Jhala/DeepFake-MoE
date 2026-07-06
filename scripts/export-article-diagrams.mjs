import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { basename, join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = resolve(fileURLToPath(new URL('..', import.meta.url)));
const articlePath = join(root, 'docs', 'deepfake-analyzer-article.md');
const outDir = join(root, 'docs', 'social-diagrams');
const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

function slugify(value) {
  return value
    .toLowerCase()
    .replace(/["'`]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 70);
}

function extractMermaidBlocks(markdown) {
  const lines = markdown.split(/\r?\n/);
  const blocks = [];
  let currentHeading = 'diagram';
  let inBlock = false;
  let buffer = [];

  for (const line of lines) {
    const heading = line.match(/^##\s+(.+)$/);
    if (!inBlock && heading) {
      currentHeading = heading[1].trim();
      continue;
    }

    if (!inBlock && line.trim() === '```mermaid') {
      inBlock = true;
      buffer = [];
      continue;
    }

    if (inBlock && line.trim() === '```') {
      blocks.push({ heading: currentHeading, body: `${buffer.join('\n').trim()}\n` });
      inBlock = false;
      buffer = [];
      continue;
    }

    if (inBlock) buffer.push(line);
  }

  return blocks;
}

function writeSupportFiles() {
  const puppeteerPath = join(outDir, 'puppeteer-config.json');
  const configPath = join(outDir, 'mermaid-config.json');
  const cssPath = join(outDir, 'mermaid-social.css');

  writeFileSync(
    puppeteerPath,
    JSON.stringify(
      {
        executablePath: existsSync(chromePath) ? chromePath : undefined,
        args: ['--no-sandbox', '--disable-setuid-sandbox'],
      },
      null,
      2,
    ),
  );

  writeFileSync(
    configPath,
    JSON.stringify(
      {
        theme: 'base',
        themeVariables: {
          background: '#f8fafc',
          primaryColor: '#ecfdf5',
          primaryTextColor: '#0f172a',
          primaryBorderColor: '#0f766e',
          lineColor: '#0f766e',
          secondaryColor: '#eef2ff',
          secondaryTextColor: '#0f172a',
          secondaryBorderColor: '#475569',
          tertiaryColor: '#fff7ed',
          tertiaryTextColor: '#0f172a',
          tertiaryBorderColor: '#d97706',
          noteBkgColor: '#ffffff',
          noteTextColor: '#0f172a',
          fontFamily: 'Inter, Segoe UI, Arial, sans-serif',
        },
        flowchart: {
          curve: 'basis',
          padding: 18,
          nodeSpacing: 52,
          rankSpacing: 58,
          htmlLabels: true,
        },
        sequence: {
          actorMargin: 78,
          boxMargin: 10,
          messageMargin: 42,
        },
      },
      null,
      2,
    ),
  );

  writeFileSync(
    cssPath,
    [
      'body { margin: 0; background: #f8fafc; }',
      'svg { font-family: Inter, "Segoe UI", Arial, sans-serif !important; }',
      '.node rect, .node polygon, .node circle, .node ellipse { filter: drop-shadow(0 8px 16px rgba(15, 23, 42, 0.08)); }',
      '.edgePath path { stroke-width: 2.4px !important; }',
      '.label, .nodeLabel, .edgeLabel, text { letter-spacing: 0 !important; }',
      '',
    ].join('\n'),
  );

  return { puppeteerPath, configPath, cssPath };
}

function renderDiagram(inputPath, outputPath, format, supportFiles) {
  const command = [
    '--yes',
    '@mermaid-js/mermaid-cli',
    '-i',
    inputPath,
    '-o',
    outputPath,
    '-e',
    format,
    '-b',
    '#f8fafc',
    '-w',
    '1800',
    '-H',
    '1200',
    '-s',
    format === 'png' ? '2' : '1',
    '-c',
    supportFiles.configPath,
    '-C',
    supportFiles.cssPath,
    '-p',
    supportFiles.puppeteerPath,
    '-q',
  ];

  const result = process.platform === 'win32'
    ? spawnSync('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', ['npx', ...command].map(quotePowerShellArg).join(' ')], {
      cwd: root,
      encoding: 'utf8',
    })
    : spawnSync('npx', command, {
      cwd: root,
      encoding: 'utf8',
    });

  if (result.status !== 0) {
    throw new Error(
      `Failed to render ${basename(inputPath)} as ${format}:\n${result.error?.message || result.stderr || result.stdout}`,
    );
  }
}

function quotePowerShellArg(value) {
  if (/^[A-Za-z0-9_./:@=-]+$/.test(value)) return value;
  return `'${String(value).replace(/'/g, "''")}'`;
}

function main() {
  mkdirSync(outDir, { recursive: true });
  const markdown = readFileSync(articlePath, 'utf8');
  const blocks = extractMermaidBlocks(markdown);
  const supportFiles = writeSupportFiles();
  const entries = [];

  blocks.forEach((block, index) => {
    const number = String(index + 1).padStart(2, '0');
    const slug = slugify(block.heading);
    const base = `${number}-${slug}`;
    const mmdPath = join(outDir, `${base}.mmd`);
    const svgPath = join(outDir, `${base}.svg`);
    const pngPath = join(outDir, `${base}.png`);

    writeFileSync(mmdPath, block.body);
    renderDiagram(mmdPath, svgPath, 'svg', supportFiles);
    renderDiagram(mmdPath, pngPath, 'png', supportFiles);

    entries.push({
      heading: block.heading,
      mmd: basename(mmdPath),
      svg: basename(svgPath),
      png: basename(pngPath),
    });
  });

  const readme = [
    '# Social Diagram Exports',
    '',
    'These files are rendered from `docs/deepfake-analyzer-article.md` so the diagrams work on platforms that do not support Mermaid, including X/Twitter.',
    '',
    'Use `.png` for X/Twitter, LinkedIn, and thumbnails. Use `.svg` for websites, docs, and article platforms that preserve vector images.',
    '',
    'Final article file:',
    '',
    '- `docs/deepfake-analyzer-final-article.md` embeds the 5:2 header plus all eight rendered diagram PNGs using GitHub raw URLs.',
    '',
    'Article image order:',
    '',
    '0. `article-header-5x2.png`',
    ...entries.map((entry, index) => `${index + 1}. \`${entry.png}\``),
    '',
    'All exported diagram files:',
    '',
    ...entries.map((entry) => `- ${entry.heading}: \`${entry.png}\`, \`${entry.svg}\`, source \`${entry.mmd}\``),
    '',
    'Regenerate after editing the article:',
    '',
    '```powershell',
    'node scripts/export-article-diagrams.mjs',
    '```',
    '',
  ].join('\n');

  writeFileSync(join(outDir, 'README.md'), readme);
  writeFinalArticle(markdown, entries);
  console.log(`Rendered ${entries.length} Mermaid diagrams into ${outDir}`);
}

function writeFinalArticle(markdown, entries) {
  const rawBase = 'https://raw.githubusercontent.com/Devrajsinh-Jhala/DeepFake-MoE/main/docs/social-diagrams';
  const captions = [
    'A single deepfake score is not enough. The app separates model opinions, metadata, forensic layers, and input-quality checks before the final verdict.',
    'The product flow starts simple for the user, then expands into backend validation, analysis layers, report generation, and privacy-safe runtime storage.',
    'The input boundary is designed for sensitive media: consent, validation, URL safety, ephemeral storage, analysis, reporting, and early deletion.',
    'The evidence bus splits one media packet into independent metadata, provenance, hash, forensic, detector, and quality lanes.',
    'The mixture-of-experts architecture routes evidence through generic detectors, a portrait-gated specialist, forensic/provenance experts, and a safety arbiter.',
    'The report is the actual product: victim summary, evidence ledger, explainable AI trace, technical appendix, PDF export, and JSON export.',
    'The verdict policy allows four outcomes, including inconclusive, so the app can preserve uncertainty instead of forcing a risky binary answer.',
    'The production architecture separates the public web service, durable metadata, queueing, worker inference, encrypted temp storage, model cache, metrics, and audit logs.',
  ];

  let index = 0;
  const body = markdown.replace(/```mermaid[\s\S]*?```/g, () => {
    const entry = entries[index];
    const caption = captions[index] || entry.heading;
    index += 1;
    return [
      `![${entry.heading}](${rawBase}/${entry.png})`,
      '',
      `*Figure ${index}: ${caption}*`,
    ].join('\n');
  });

  const finalArticle = body.replace(
    '# Building an Explainable AI Deepfake Analyzer for Sensitive Media Abuse',
    [
      '# Building an Explainable AI Deepfake Analyzer for Sensitive Media Abuse',
      '',
      '> Publication-ready version with rendered diagrams. Use this file for platforms that do not render Mermaid diagrams.',
      '',
      `![AI Deepfake Analyzer article header](${rawBase}/article-header-5x2.png)`,
      '',
      '*Header image: A privacy-first evidence pipeline for explainable deepfake analysis, with media input, expert signals, safety arbiter, and report output.*',
    ].join('\n'),
  );

  writeFileSync(join(root, 'docs', 'deepfake-analyzer-final-article.md'), finalArticle);
}

main();
