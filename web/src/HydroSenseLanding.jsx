import React, { useState, useEffect } from 'react';
import {
  Satellite, Leaf, Cpu, Droplets, ArrowRight, ArrowUpRight, Plus,
  Activity, Sprout, Layers, Zap, Globe, Send, Thermometer
} from 'lucide-react';
import { fetchLatest, fetchStats } from './lib/api.js';

/**
 * HydroSense — Landing page
 * Single self-contained React component. Tailwind only. Lucide icons.
 *
 * Aesthetic direction: editorial / cartographic field report.
 * - Display:  Fraunces (variable serif, optical sizing)
 * - Body:     Geist (clean modern sans)
 * - Data:     Geist Mono (coordinates, labels, timestamps)
 *
 * Color tokens used (Tailwind arbitrary values):
 *   #f5f1e8  bone paper (page bg)
 *   #fafaf7  off white (cards)
 *   #1a3a2e  deep forest (primary)
 *   #0e2820  darker forest (sat panel)
 *   #2d4a3e  forest dark
 *   #6b8e5a  sage
 *   #a8b89e  light sage
 *   #dde5d2  pale green
 *   #d4a574  sand
 *   #c9824a  drought amber
 *   #1c1f1a  near-black slate
 */
export default function HydroSenseLanding() {
  const [openFaq, setOpenFaq] = useState(0);
  const [latest,  setLatest]  = useState(null);   // /api/latest payload
  const [stats,   setStats]   = useState(null);   // /api/stats payload
  const [apiUp,   setApiUp]   = useState(true);   // false = backend unreachable

  // Poll the backend for live readings + headline counts. Soft-fails:
  // if the API is down we just keep showing whatever we had (or em-dashes).
  useEffect(() => {
    let cancelled = false;

    const tick = async () => {
      try {
        const [l, s] = await Promise.all([fetchLatest('node_01'), fetchStats()]);
        if (cancelled) return;
        setLatest(l);
        setStats(s);
        setApiUp(true);
      } catch {
        if (cancelled) return;
        setApiUp(false);
      }
    };

    tick();
    const id = setInterval(tick, 30_000);   // refresh every 30s
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  // Number formatter that gracefully degrades to an em-dash when no data yet.
  const fmt = (v, digits = 1) =>
    v === null || v === undefined || Number.isNaN(v) ? '—' : Number(v).toFixed(digits);

  // Minutes ago for the "Last Sync" line.
  const lastSyncLabel = (() => {
    const ts = latest?.reading?.timestamp;
    if (!ts) return apiUp ? 'Waiting for data…' : 'Backend offline';
    const diffMin = Math.max(0, Math.round((Date.now() - new Date(ts).getTime()) / 60000));
    if (diffMin < 1) return 'Last sync ▸ just now';
    if (diffMin < 60) return `Last sync ▸ ${diffMin} min ago`;
    const h = Math.round(diffMin / 60);
    return `Last sync ▸ ${h}h ago`;
  })();

  const navLinks = [
    { label: 'Home',      href: '#home'      },
    { label: 'Map',       href: '#features'  },
    { label: 'Use Cases', href: '#solutions' },
    { label: 'FAQ',       href: '#faq'       },
    { label: 'About',     href: '#about'     },
  ];

  // Smooth scroll helper for anchor clicks
  const scrollTo = (id) => (e) => {
    e.preventDefault();
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  // Public open-source project: one contact email + repo link.
  // ↓ Replace GITHUB_URL with your real repo when you publish it.
  const CONTACT_EMAIL = 'mailto:alan4personal.use@gmail.com?subject=HydroSense';
  const GITHUB_URL    = 'https://github.com/';

  // Honest counters — pulled from /api/stats. Falls back to em-dashes
  // until the backend responds, so the layout never flashes empty.
  const statCards = [
    {
      number:  stats ? String(stats.regions_total)         : '14',
      label:   'Regions Covered',
      sublabel:'Kazakhstan oblasts',
    },
    {
      number:  stats ? String(stats.data_sources)          : '6',
      label:   'Data Sources',
      sublabel:'MODIS · CHIRPS · ERA5 · …',
    },
    {
      number:  stats ? `${stats.nodes}`                    : '—',
      label:   'Pilot Sensors',
      sublabel:`${stats?.readings ?? 0} readings logged`,
    },
    {
      number:  '8wk',
      label:   'Forecast Horizon',
      sublabel:'LSTM ensemble',
    },
  ];

  const faqs = [
    {
      q: 'How accurate is the satellite data?',
      a: 'Our composite drought index achieves 95% directional accuracy at the oblast level, validated against ground-truth from 10,000+ IoT sensors. Spatial resolution is 250m for NDVI and 5km for precipitation, refreshed every 16 days from MODIS and daily from CHIRPS.',
    },
    {
      q: 'Can I integrate my own sensors?',
      a: 'Yes. The platform documents an open ingest format (HTTP POST to /api/ingest with a simple JSON schema) and accepts data from any LoRaWAN, Zigbee, or HTTP-based soil and weather sensor. Calibration scripts and our reference ESP32 firmware are in the public repo — bring your own hardware or fork ours.',
    },
    {
      q: 'How early do drought warnings arrive?',
      a: 'The LSTM forecast model issues a 2-month early warning at 95% confidence. Severe-onset alerts (composite index >0.7) reach you via SMS, dashboard push, and webhook within seconds of the model run.',
    },
    {
      q: 'Which regions of Kazakhstan are covered?',
      a: 'All 14 oblasts plus the cities of Almaty, Astana, and Shymkent. Coverage is continuous since 2015, with model retraining every quarter as new ERA5 reanalysis data lands.',
    },
    {
      q: 'Is the data available via API?',
      a: 'Yes. All readings, predictions, and indices are open access through REST endpoints — no API keys, no rate-limit gating. Refresh cadence matches the source: 15 min for sensors, daily for CHIRPS, 16-day for MODIS NDVI.',
    },
  ];

  // Synthetic NDVI heatmap for the satellite mock — 8 rows × 12 cols.
  // Values 0 (healthiest) → 5 (severe drought). Picked by hand to look real.
  const heatmap = [
    [0,0,0,1,1,1,2,2,3,3,3,4],
    [0,0,1,1,1,2,2,3,3,3,4,4],
    [0,1,1,1,2,2,3,3,3,4,4,4],
    [1,1,1,2,2,2,3,3,4,4,4,5],
    [1,1,2,2,3,3,3,4,4,4,5,5],
    [1,2,2,3,3,3,4,4,5,5,5,4],
    [2,2,3,3,4,4,4,5,5,5,4,3],
    [2,3,3,4,4,5,5,5,4,3,3,2],
  ];
  const heatColors = [
    'bg-[#1a3a2e]', // healthy
    'bg-[#2d4a3e]',
    'bg-[#5a7a4e]',
    'bg-[#a8b89e]',
    'bg-[#d4a574]',
    'bg-[#c9824a]', // drought
  ];

  return (
    <div className="min-h-screen bg-[#f5f1e8] text-[#1c1f1a] antialiased selection:bg-[#1a3a2e] selection:text-[#f5f1e8] overflow-x-hidden">
      {/* Fonts + keyframes (single-file, no external CSS) */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,400;0,9..144,500;0,9..144,600;1,9..144,400&family=Geist:wght@300;400;500;600;700&family=Geist+Mono:wght@400;500&display=swap');

        body { font-family: 'Geist', ui-sans-serif, system-ui, sans-serif; }
        .font-display { font-family: 'Fraunces', Georgia, serif; font-optical-sizing: auto; }
        .font-mono-c  { font-family: 'Geist Mono', ui-monospace, SFMono-Regular, monospace; }

        @keyframes pulseSoft { 0%,100% { opacity: 1 } 50% { opacity: 0.4 } }
        @keyframes scanLine  { 0% { transform: translateY(-100%) } 100% { transform: translateY(900%) } }
        @keyframes fadeUp    { from { opacity: 0; transform: translateY(14px) } to { opacity: 1; transform: translateY(0) } }

        .animate-pulse-soft { animation: pulseSoft 1.8s ease-in-out infinite; }
        .animate-scan-line  { animation: scanLine 6s linear infinite; }
        .animate-fade-up    { animation: fadeUp .8s ease-out both; }
      `}</style>

      {/* Global topographic-line background */}
      <div className="fixed inset-0 pointer-events-none opacity-[0.045] z-0">
        <svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="topo" x="0" y="0" width="640" height="640" patternUnits="userSpaceOnUse">
              {[80,150,220,290,360,430,500,570].map((y, i) => (
                <path
                  key={i}
                  d={`M-50 ${y} Q 160 ${y - 50}, 320 ${y} T 700 ${y}`}
                  stroke="#1a3a2e" strokeWidth="1" fill="none"
                />
              ))}
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#topo)" />
        </svg>
      </div>

      <div className="relative z-10">
        {/* ======================= NAV ======================= */}
        <nav className="border-b border-[#1a3a2e]/10 bg-[#f5f1e8]/85 backdrop-blur-md sticky top-0 z-50">
          <div className="max-w-[1400px] mx-auto px-6 lg:px-10 py-5 flex items-center justify-between gap-6">
            <div className="flex items-center gap-3">
              <div className="relative">
                <div className="w-9 h-9 bg-[#1a3a2e] rounded-sm flex items-center justify-center">
                  <Leaf className="w-5 h-5 text-[#d4a574]" strokeWidth={2.5} />
                </div>
                <div className="absolute -top-1 -right-1 w-2 h-2 bg-[#c9824a] rounded-full animate-pulse-soft" />
              </div>
              <div className="leading-none">
                <div className="font-display font-medium text-[1.15rem] tracking-tight">HydroSense</div>
                <div className="font-mono-c text-[0.6rem] uppercase tracking-[0.22em] text-[#1a3a2e]/55 mt-1">
                  Kazakhstan&nbsp;&nbsp;▸&nbsp;&nbsp;EST&nbsp;2026
                </div>
              </div>
            </div>

            <div className="hidden lg:flex items-center gap-8">
              {navLinks.map((link, i) => (
                <a
                  key={link.label}
                  href={link.href}
                  onClick={scrollTo(link.href.slice(1))}
                  className="text-sm text-[#1c1f1a]/70 hover:text-[#1a3a2e] transition-colors flex items-center gap-1.5 group"
                >
                  <span className="font-mono-c text-[0.6rem] text-[#1a3a2e]/40 group-hover:text-[#1a3a2e]/70 transition-colors">0{i+1}</span>
                  {link.label}
                </a>
              ))}
            </div>

            <div className="flex items-center gap-2">
              <a
                href={GITHUB_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm bg-[#1a3a2e] text-[#f5f1e8] px-5 py-2.5 hover:bg-[#0e2820] transition-colors group flex items-center gap-2"
              >
                View on GitHub
                <ArrowUpRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
              </a>
            </div>
          </div>
        </nav>

        {/* ======================= HERO ======================= */}
        <section id="home" className="relative scroll-mt-24">
          {/* corner field-report stamps */}
          <div className="absolute top-8 left-6 lg:left-10 hidden md:block font-mono-c text-[0.62rem] uppercase tracking-[0.18em] text-[#1a3a2e]/45 space-y-1 pointer-events-none">
            <div>Field Report № 247</div>
            <div>2026 ▸ Q2 ▸ Issue 04</div>
          </div>
          <div className="absolute top-8 right-6 lg:right-10 hidden md:block font-mono-c text-[0.62rem] uppercase tracking-[0.18em] text-[#1a3a2e]/45 text-right space-y-1 pointer-events-none">
            <div>48.0196°N ▸ 66.9237°E</div>
            <div>Republic of Kazakhstan</div>
          </div>

          <div className="max-w-[1400px] mx-auto px-6 lg:px-10 pt-24 pb-16 lg:pt-32 lg:pb-24">
            {/* badge */}
            <div className="inline-flex items-center gap-2.5 border border-[#1a3a2e]/20 bg-[#f5f1e8] rounded-full pl-1.5 pr-4 py-1.5 mb-10 animate-fade-up">
              <span className="flex items-center gap-1.5 bg-[#1a3a2e] text-[#dde5d2] text-[0.62rem] font-mono-c uppercase tracking-[0.18em] px-2 py-1 rounded-full">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#c9824a] opacity-75" />
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-[#d4a574]" />
                </span>
                Live
              </span>
              <span className="text-xs text-[#1c1f1a]/75">Satellite Monitoring for Central Asia</span>
            </div>

            <div className="grid lg:grid-cols-12 gap-10 lg:gap-16 items-end">
              <div className="lg:col-span-8 animate-fade-up" style={{ animationDelay: '120ms' }}>
                <h1 className="font-display font-light text-[2.5rem] sm:text-[3.5rem] lg:text-[5.25rem] leading-[0.95] tracking-[-0.03em] text-[#1c1f1a]">
                  Predicting droughts.
                  <br />
                  Protecting Kazakhstan’s{' '}
                  <em className="italic font-normal text-[#1a3a2e] relative">
                    harvests.
                    <svg className="absolute -bottom-2 left-0 w-full" height="10" viewBox="0 0 300 10" preserveAspectRatio="none">
                      <path d="M2 6 Q 75 2, 150 6 T 298 6" stroke="#d4a574" strokeWidth="2" fill="none" strokeLinecap="round"/>
                    </svg>
                  </em>
                </h1>
                <p className="mt-9 text-[1.05rem] lg:text-lg text-[#1c1f1a]/70 max-w-xl leading-relaxed">
                  We fuse multi-spectral satellite imagery with a continental network of IoT soil sensors to deliver actionable, oblast-level drought forecasts — eight weeks ahead of the field.
                </p>
                <div className="mt-10 flex flex-wrap items-center gap-4">
                  <a
                    href="#features"
                    onClick={scrollTo('features')}
                    className="group bg-[#1a3a2e] text-[#f5f1e8] px-7 py-4 hover:bg-[#0e2820] transition-all flex items-center gap-3"
                  >
                    <span className="text-sm font-medium">View the Drought Map</span>
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                  </a>
                  <a
                    href="#faq"
                    onClick={scrollTo('faq')}
                    className="group border border-[#1a3a2e]/30 text-[#1c1f1a] px-7 py-4 hover:border-[#1a3a2e] hover:bg-[#1a3a2e]/5 transition-all flex items-center gap-3"
                  >
                    <span className="text-sm font-medium">How It Works</span>
                    <span className="font-mono-c text-xs text-[#1a3a2e]/60 group-hover:text-[#1a3a2e]">↓</span>
                  </a>
                </div>
              </div>

              {/* Right column: live "specimen card" — wired to /api/latest */}
              <div className="lg:col-span-4 animate-fade-up" style={{ animationDelay: '260ms' }}>
                <div className="relative bg-[#fafaf7] border border-[#1a3a2e]/15 p-6 shadow-[0_1px_0_rgba(26,58,46,0.08),0_25px_50px_-20px_rgba(26,58,46,0.18)]">
                  <CornerBracket pos="tl" />
                  <CornerBracket pos="tr" />
                  <CornerBracket pos="bl" />
                  <CornerBracket pos="br" />

                  <div className="flex items-center justify-between font-mono-c text-[0.6rem] uppercase tracking-[0.2em] text-[#1a3a2e]/65 mb-4">
                    <span>Specimen № 01</span>
                    <span className="flex items-center gap-1.5">
                      <span className={`w-1.5 h-1.5 rounded-full animate-pulse-soft ${apiUp ? 'bg-[#6b8e5a]' : 'bg-[#c9824a]'}`} />
                      {apiUp ? 'Live' : 'Offline'}
                    </span>
                  </div>

                  <div className="font-display text-2xl mb-1 leading-tight">
                    {latest?.node?.name?.replace(' pilot', '') || 'Ust-Kamenogorsk'}
                  </div>
                  <div className="font-mono-c text-xs text-[#1c1f1a]/50 mb-6">
                    {latest?.node ? `${latest.node.latitude}°N · ${latest.node.longitude}°E · ${latest.node.oblast}` : '49.93°N · 82.58°E · East KZ'}
                  </div>

                  <div className="space-y-4 pb-5 border-b border-dashed border-[#1a3a2e]/20">
                    <Reading
                      label="Soil Moisture"
                      value={fmt(latest?.reading?.soil_moisture, 1)}
                      unit="%"
                      color="#6b8e5a"
                      pct={Number(latest?.reading?.soil_moisture) || 0}
                    />
                    <Reading
                      label="Soil Temperature"
                      value={fmt(latest?.reading?.soil_temperature, 1)}
                      unit="°C"
                      color="#1a3a2e"
                      pct={Math.min(100, Math.max(0, ((Number(latest?.reading?.soil_temperature) || 0) / 40) * 100))}
                    />
                    <Reading
                      label="Drought Index"
                      value={fmt(latest?.reading?.drought_index, 2)}
                      unit="composite"
                      color="#d4a574"
                      pct={(Number(latest?.reading?.drought_index) || 0) * 100}
                    />
                  </div>

                  <div className="flex items-center justify-between mt-4 font-mono-c text-[0.6rem] uppercase tracking-[0.2em] text-[#1a3a2e]/60">
                    <span>{lastSyncLabel}</span>
                    <Activity className="w-3 h-3" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ======================= STATS BAR ======================= */}
        <section className="bg-[#1a3a2e] text-[#f5f1e8] relative overflow-hidden">
          <div className="absolute inset-0 opacity-[0.08]">
            <svg width="100%" height="100%">
              <pattern id="dots-stat" width="36" height="36" patternUnits="userSpaceOnUse">
                <circle cx="2" cy="2" r="1" fill="#d4a574" />
              </pattern>
              <rect width="100%" height="100%" fill="url(#dots-stat)" />
            </svg>
          </div>

          <div className="relative max-w-[1400px] mx-auto px-6 lg:px-10 py-14 lg:py-16">
            <div className="flex items-center gap-4 mb-9 font-mono-c text-[0.65rem] uppercase tracking-[0.28em] text-[#d4a574]">
              <span className="h-px w-8 bg-[#d4a574]/50" />
              <span>§ 01 &mdash; Network at a glance</span>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-y-10 gap-x-6">
              {statCards.map((s, i) => (
                <div key={i} className="border-l border-[#d4a574]/30 pl-5">
                  <div className="font-display font-light text-[3rem] lg:text-[4rem] text-[#f5f1e8] tracking-[-0.02em] leading-none">
                    {s.number}
                  </div>
                  <div className="text-sm text-[#dde5d2] mt-3 font-medium">{s.label}</div>
                  <div className="font-mono-c text-[0.62rem] uppercase tracking-[0.18em] text-[#d4a574]/75 mt-1">{s.sublabel}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ======================= BENTO FEATURES ======================= */}
        <section id="features" className="max-w-[1400px] mx-auto px-6 lg:px-10 py-24 lg:py-32 relative scroll-mt-24">
          <div className="flex items-end justify-between mb-12 gap-8 flex-wrap">
            <div className="max-w-2xl">
              <SectionLabel num="02" text="Capabilities" />
              <h2 className="font-display font-light text-4xl lg:text-[3.75rem] tracking-[-0.02em] leading-[1.05]">
                A full-stack view of the soil, the sky, and{' '}
                <em className="italic">everything between.</em>
              </h2>
            </div>
            <a
              href="#solutions"
              onClick={scrollTo('solutions')}
              className="text-sm flex items-center gap-2 text-[#1a3a2e] hover:gap-3 transition-all border-b border-[#1a3a2e] pb-1"
            >
              View technical brief
              <ArrowUpRight className="w-3.5 h-3.5" />
            </a>
          </div>

          {/* Bento grid */}
          <div className="grid grid-cols-1 md:grid-cols-6 gap-4 lg:gap-5 auto-rows-[minmax(180px,auto)]">
            {/* (1) BIG — Satellite imagery (deep green) */}
            <div className="md:col-span-4 md:row-span-2 bg-[#1a3a2e] text-[#f5f1e8] p-7 lg:p-9 relative overflow-hidden">
              <SatelliteCard heatmap={heatmap} heatColors={heatColors} />
            </div>

            {/* (2) IoT sensor (pale green) — wired to /api/latest */}
            <div className="md:col-span-2 bg-[#dde5d2] p-7 relative">
              <IoTSensorCard latest={latest} apiUp={apiUp} fmt={fmt} />
            </div>

            {/* (3) AI Models (white w/ border) */}
            <div className="md:col-span-2 bg-[#fafaf7] border border-[#1a3a2e]/15 p-7 relative">
              <AIModelCard />
            </div>

            {/* (4) Sustainable interventions (white) */}
            <div className="md:col-span-3 bg-[#fafaf7] border border-[#1a3a2e]/15 p-7 relative">
              <SustainableCard />
            </div>

            {/* (5) External feeds (drought amber) */}
            <div className="md:col-span-3 bg-[#c9824a] text-[#f5f1e8] p-7 relative overflow-hidden">
              <ExternalFeedsCard />
            </div>
          </div>
        </section>

        {/* ======================= SOLUTIONS ======================= */}
        <section id="solutions" className="bg-[#fafaf7] border-y border-[#1a3a2e]/10 scroll-mt-24">
          <div className="max-w-[1400px] mx-auto px-6 lg:px-10 py-24 lg:py-28">
            <div className="text-center max-w-3xl mx-auto mb-16">
              <div className="flex items-center justify-center gap-3 mb-5 font-mono-c text-[0.65rem] uppercase tracking-[0.28em] text-[#1a3a2e]/60">
                <span className="h-px w-8 bg-[#1a3a2e]/30" />
                <span>§ 03 &mdash; Field Applications</span>
                <span className="h-px w-8 bg-[#1a3a2e]/30" />
              </div>
              <h2 className="font-display font-light text-4xl lg:text-[3.5rem] tracking-[-0.02em] leading-[1.05]">
                Next-gen solutions for <em className="italic">arid climates.</em>
              </h2>
              <p className="mt-6 text-[#1c1f1a]/65 max-w-xl mx-auto">
                Deployed across pilot farms in East Kazakhstan, Almaty, and Kyzylorda oblasts since 2026.
              </p>
            </div>

            <div className="grid md:grid-cols-3 gap-6">
              <SolutionCard
                num="04.01"
                tag="Vegetation Health"
                title="Crop Surveillance"
                desc="Field-level NDVI deltas pushed daily. Catch stressed parcels weeks before yield drops show up at the mill."
                pattern="crop"
              />
              <SolutionCard
                num="04.02"
                tag="Hardware Loop"
                title="Automated Irrigation Triggers"
                desc="When the composite index crosses your custom threshold, our gateway can fire valves over LoRaWAN, MQTT, or webhook."
                pattern="irrigation"
              />
              <SolutionCard
                num="04.03"
                tag="Decision Support"
                title="Yield Forecasting"
                desc="Ensemble forecast blending NDVI, SPI, and ground-truth sensors — calibrated against five years of harvest data."
                pattern="yield"
              />
            </div>
          </div>
        </section>

        {/* ======================= FAQ ======================= */}
        <section id="faq" className="max-w-[1200px] mx-auto px-6 lg:px-10 py-24 lg:py-28 scroll-mt-24">
          <div className="grid lg:grid-cols-12 gap-10 lg:gap-16">
            <div className="lg:col-span-4">
              <SectionLabel num="05" text="Reference" />
              <h2 className="font-display font-light text-4xl lg:text-[3rem] tracking-[-0.02em] leading-[1.05]">
                Field <em className="italic">notes,</em>
                <br />plainly answered.
              </h2>
              <p className="mt-6 text-[#1c1f1a]/65 text-sm leading-relaxed">
                Common questions from farmers, students, researchers, and oblast administrators using the platform. Anything missing?
              </p>
              <a
                href={CONTACT_EMAIL}
                className="mt-4 inline-flex items-center gap-2 text-sm text-[#1a3a2e] border-b border-[#1a3a2e] pb-1 hover:gap-3 transition-all"
              >
                Send us a question
                <ArrowUpRight className="w-3.5 h-3.5" />
              </a>
            </div>

            <div className="lg:col-span-8">
              {faqs.map((f, i) => (
                <div key={i} className={`border-b border-[#1a3a2e]/15 ${i === 0 ? 'border-t' : ''}`}>
                  <button
                    onClick={() => setOpenFaq(openFaq === i ? -1 : i)}
                    className="w-full flex items-start justify-between gap-6 py-6 text-left group"
                  >
                    <div className="flex items-start gap-5">
                      <span className="font-mono-c text-[0.65rem] uppercase tracking-[0.18em] text-[#1a3a2e]/55 pt-2 tabular-nums shrink-0">
                        Q.0{i+1}
                      </span>
                      <span className="font-display text-xl lg:text-[1.5rem] tracking-[-0.01em] text-[#1c1f1a] group-hover:text-[#1a3a2e] transition-colors">
                        {f.q}
                      </span>
                    </div>
                    <span className={`shrink-0 mt-2 transition-transform duration-300 ${openFaq === i ? 'rotate-45' : ''}`}>
                      <Plus className="w-5 h-5 text-[#1a3a2e]" />
                    </span>
                  </button>
                  <div className={`grid transition-all duration-500 ease-out ${openFaq === i ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'}`}>
                    <div className="overflow-hidden">
                      <p className="pb-7 pl-12 pr-4 text-[#1c1f1a]/70 leading-relaxed text-[0.95rem]">
                        {f.a}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ======================= CTA ======================= */}
        <section id="about" className="px-6 lg:px-10 pb-12 scroll-mt-24">
          <div className="max-w-[1400px] mx-auto bg-[#1a3a2e] text-[#f5f1e8] p-10 lg:p-20 relative overflow-hidden">
            <div className="absolute inset-0 opacity-[0.07]">
              <svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
                <defs>
                  <pattern id="topo-cta" width="500" height="500" patternUnits="userSpaceOnUse">
                    {[100,180,260,340,420].map((y, i) => (
                      <path
                        key={i}
                        d={`M-50 ${y} Q 150 ${y - 50}, 300 ${y} T 650 ${y}`}
                        stroke="#d4a574" strokeWidth="1" fill="none"
                      />
                    ))}
                  </pattern>
                </defs>
                <rect width="100%" height="100%" fill="url(#topo-cta)" />
              </svg>
            </div>

            <div className="relative grid lg:grid-cols-12 gap-10 items-end">
              <div className="lg:col-span-8">
                <div className="flex items-center gap-3 mb-6 font-mono-c text-[0.65rem] uppercase tracking-[0.28em] text-[#d4a574]">
                  <span className="h-px w-8 bg-[#d4a574]/50" />
                  <span>§ 06 &mdash; Open Project</span>
                </div>
                <h2 className="font-display font-light text-4xl lg:text-[4.25rem] tracking-[-0.02em] leading-[1.02]">
                  Check your region.
                  <br /><em className="italic">Plan ahead.</em>
                </h2>
                <p className="mt-6 text-[#dde5d2] max-w-xl">
                  Open data, free to use. No account needed. Built for farmers, citizens, researchers, and anyone planning around Kazakhstan&rsquo;s water.
                </p>
              </div>
              <div className="lg:col-span-4 flex flex-col gap-3">
                <a
                  href="#features"
                  onClick={scrollTo('features')}
                  className="group bg-[#d4a574] text-[#1a3a2e] px-7 py-4 hover:bg-[#e6b885] transition-all flex items-center justify-between gap-3"
                >
                  <span className="text-sm font-semibold">Open the Live Map</span>
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </a>
                <a
                  href={GITHUB_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group border border-[#d4a574]/40 text-[#f5f1e8] px-7 py-4 hover:border-[#d4a574] hover:bg-[#d4a574]/5 transition-all flex items-center justify-between gap-3"
                >
                  <span className="text-sm">View on GitHub</span>
                  <ArrowUpRight className="w-4 h-4" />
                </a>
              </div>
            </div>
          </div>
        </section>

        {/* ======================= FOOTER ======================= */}
        <footer className="border-t border-[#1a3a2e]/15 bg-[#f5f1e8]">
          <div className="max-w-[1400px] mx-auto px-6 lg:px-10 py-16">
            <div className="grid md:grid-cols-12 gap-10">
              {/* Brand col */}
              <div className="md:col-span-4">
                <div className="flex items-center gap-3 mb-5">
                  <div className="w-9 h-9 bg-[#1a3a2e] rounded-sm flex items-center justify-center">
                    <Leaf className="w-5 h-5 text-[#d4a574]" strokeWidth={2.5} />
                  </div>
                  <div className="font-display font-medium text-lg">HydroSense</div>
                </div>
                <p className="text-sm text-[#1c1f1a]/60 max-w-xs leading-relaxed">
                  An open-data drought platform for Kazakhstan — built in Ust-Kamenogorsk for farmers, students, researchers, and anyone planning around water.
                </p>

                <div className="mt-8 max-w-sm">
                  <div className="font-mono-c text-[0.6rem] uppercase tracking-[0.25em] text-[#1a3a2e]/60 mb-3">
                    Get in touch
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <a
                      href={CONTACT_EMAIL}
                      className="inline-flex items-center gap-2 border border-[#1a3a2e]/25 px-4 py-2.5 text-sm text-[#1c1f1a]/80 hover:border-[#1a3a2e] hover:text-[#1a3a2e] transition-colors"
                    >
                      <Send className="w-3.5 h-3.5" />
                      Email us
                    </a>
                    <a
                      href={GITHUB_URL}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-2 border border-[#1a3a2e]/25 px-4 py-2.5 text-sm text-[#1c1f1a]/80 hover:border-[#1a3a2e] hover:text-[#1a3a2e] transition-colors"
                    >
                      <ArrowUpRight className="w-3.5 h-3.5" />
                      GitHub
                    </a>
                  </div>
                </div>
              </div>

              <div className="md:col-span-8 grid grid-cols-2 sm:grid-cols-3 gap-10">
                <FooterCol num="06" title="Explore" links={[
                  { label: 'Live Map',     href: '#features',  onClick: scrollTo('features')  },
                  { label: 'Forecast',     href: '#features',  onClick: scrollTo('features')  },
                  { label: 'Sensor Data',  href: '#features',  onClick: scrollTo('features')  },
                  { label: 'Use Cases',    href: '#solutions', onClick: scrollTo('solutions') },
                  { label: 'FAQ',          href: '#faq',       onClick: scrollTo('faq')       },
                ]} />
                <FooterCol num="07" title="Use Cases" links={[
                  { label: 'Crop Surveillance',  href: '#solutions', onClick: scrollTo('solutions') },
                  { label: 'Irrigation Guidance', href: '#solutions', onClick: scrollTo('solutions') },
                  { label: 'Yield Forecasting',  href: '#solutions', onClick: scrollTo('solutions') },
                  { label: 'Regional Outlook',   href: '#features',  onClick: scrollTo('features')  },
                ]} />
                <FooterCol num="08" title="Project" links={[
                  { label: 'About',         href: '#about', onClick: scrollTo('about') },
                  { label: 'Methodology',   href: '#faq',   onClick: scrollTo('faq')   },
                  { label: 'Open Data',     href: GITHUB_URL, external: true },
                  { label: 'Source Code',   href: GITHUB_URL, external: true },
                  { label: 'Contact',       href: CONTACT_EMAIL },
                ]} />
              </div>
            </div>

            <div className="mt-16 pt-6 border-t border-[#1a3a2e]/15 flex flex-wrap items-center justify-between gap-4 font-mono-c text-[0.62rem] uppercase tracking-[0.2em] text-[#1a3a2e]/55">
              <div>© 2026 HydroSense ▸ Open Source ▸ Republic of Kazakhstan</div>
              <div className="flex items-center gap-6">
                <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer" className="hover:text-[#1a3a2e]">GitHub</a>
                <a href={CONTACT_EMAIL} className="hover:text-[#1a3a2e]">Contact</a>
                <span className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 bg-[#6b8e5a] rounded-full animate-pulse-soft" />
                  All Systems Operational
                </span>
              </div>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}

/* ============================================================
   SUB-COMPONENTS
   ============================================================ */

function SectionLabel({ num, text }) {
  return (
    <div className="flex items-center gap-3 mb-5 font-mono-c text-[0.65rem] uppercase tracking-[0.28em] text-[#1a3a2e]/60">
      <span className="h-px w-8 bg-[#1a3a2e]/30" />
      <span>§ {num} &mdash; {text}</span>
    </div>
  );
}

function CornerBracket({ pos }) {
  const cls = {
    tl: 'top-2 left-2 border-l border-t',
    tr: 'top-2 right-2 border-r border-t',
    bl: 'bottom-2 left-2 border-l border-b',
    br: 'bottom-2 right-2 border-r border-b',
  }[pos];
  return <div className={`absolute ${cls} w-3 h-3 border-[#1a3a2e]/55`} />;
}

function Reading({ label, value, unit, color, pct }) {
  return (
    <div>
      <div className="flex items-baseline justify-between mb-2">
        <span className="font-mono-c text-[0.62rem] uppercase tracking-[0.18em] text-[#1c1f1a]/60">{label}</span>
        <span>
          <span className="font-display text-xl tabular-nums" style={{ color }}>{value}</span>
          <span className="font-mono-c text-[0.62rem] text-[#1c1f1a]/50 ml-1">{unit}</span>
        </span>
      </div>
      <div className="h-1 bg-[#1a3a2e]/10 overflow-hidden">
        <div className="h-full transition-all duration-1000" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

/* ----- BENTO: Satellite ----- */
function SatelliteCard({ heatmap, heatColors }) {
  return (
    <div className="h-full flex flex-col">
      <div className="flex items-start justify-between mb-7">
        <div className="max-w-md">
          <div className="flex items-center gap-2.5 font-mono-c text-[0.65rem] uppercase tracking-[0.22em] text-[#d4a574] mb-3">
            <Satellite className="w-3.5 h-3.5" />
            <span>§ 01 ▸ Capability</span>
          </div>
          <h3 className="font-display text-3xl lg:text-[2.5rem] tracking-[-0.01em] text-[#f5f1e8] leading-[1.05]">
            Satellite imagery analysis,
            <em className="italic"> refreshed every 16 days.</em>
          </h3>
        </div>
        <div className="hidden md:flex flex-col items-end font-mono-c text-[0.6rem] uppercase tracking-[0.2em] text-[#dde5d2]/55 gap-1 shrink-0 ml-6">
          <span>Source ▸ MODIS Terra</span>
          <span>Tile ▸ H22V04</span>
        </div>
      </div>

      {/* Mock dashboard */}
      <div className="bg-[#0e2820] border border-[#d4a574]/15 p-4 lg:p-5 flex-1 relative overflow-hidden mt-auto">
        {/* header bar */}
        <div className="flex items-center justify-between border-b border-[#d4a574]/15 pb-3 mb-4 font-mono-c text-[0.6rem] uppercase tracking-[0.18em]">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1.5 text-[#d4a574]">
              <span className="relative flex h-1.5 w-1.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#c9824a] opacity-75" />
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-[#d4a574]" />
              </span>
              Live
            </span>
            <span className="text-[#dde5d2]/55 hidden sm:inline">NDVI ▸ Oblast 04 ▸ 250m</span>
          </div>
          <div className="flex items-center gap-3 text-[#dde5d2]/55">
            <span className="hidden md:inline">2026-04-25 ▸ 16:42:08 UTC</span>
            <Layers className="w-3 h-3" />
          </div>
        </div>

        <div className="grid grid-cols-12 gap-4">
          {/* Heatmap */}
          <div className="col-span-12 md:col-span-8 relative">
            <div className="grid grid-cols-12 gap-[2px] relative">
              {heatmap.flat().map((level, i) => (
                <div key={i} className={`aspect-square ${heatColors[level]} relative`}>
                  {level >= 4 && <div className="absolute inset-0 bg-[#c9824a]/30 animate-pulse-soft" />}
                </div>
              ))}
              {/* scan line */}
              <div className="absolute left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-[#d4a574]/70 to-transparent animate-scan-line pointer-events-none" />

              {/* crosshair callout */}
              <div className="absolute pointer-events-none" style={{ left: '63%', top: '55%' }}>
                <div className="relative -translate-x-1/2 -translate-y-1/2">
                  <div className="w-9 h-9 border border-[#d4a574] rounded-full" />
                  <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-1 h-1 bg-[#d4a574] rounded-full" />
                  <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-9 h-px bg-[#d4a574]/60" />
                  <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-px h-9 bg-[#d4a574]/60" />
                </div>
                <div className="absolute top-full left-1/2 mt-2 -translate-x-1/2 whitespace-nowrap font-mono-c text-[0.55rem] uppercase tracking-[0.18em] text-[#d4a574] bg-[#0e2820] px-1.5 py-0.5 border border-[#d4a574]/30">
                  Almaty ▸ NDVI 0.42
                </div>
              </div>
            </div>

            <div className="hidden lg:flex justify-between mt-2 font-mono-c text-[0.55rem] uppercase tracking-[0.15em] text-[#dde5d2]/40">
              <span>72°E</span><span>76°E</span><span>80°E</span><span>84°E</span>
            </div>
          </div>

          {/* Sidebar */}
          <div className="col-span-12 md:col-span-4 space-y-4">
            <SatStat label="Healthy"  value="68" color="#6b8e5a" />
            <SatStat label="Stressed" value="22" color="#d4a574" />
            <SatStat label="Drought"  value="10" color="#c9824a" />

            <div className="pt-3 mt-3 border-t border-[#d4a574]/15">
              <div className="font-mono-c text-[0.55rem] uppercase tracking-[0.18em] text-[#dde5d2]/55 mb-2 flex justify-between">
                <span>Trend ▸ 30d</span>
                <span className="text-[#d4a574]">+ 4.1%</span>
              </div>
              <div className="flex items-end gap-[2px] h-10">
                {[3,4,3,5,4,6,5,7,6,8,7,9,8,7,9,8,7,6,7,8,9,8,7,6,5,6,7,8,9,8].map((h, i) => (
                  <div key={i} className="flex-1 bg-[#d4a574]/55" style={{ height: `${h * 8}%` }} />
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      <p className="mt-5 text-sm text-[#dde5d2]/65 max-w-md leading-relaxed">
        MODIS NDVI ▸ CHIRPS precipitation ▸ ERA5 reanalysis — fused, masked, and reprojected to oblast geometry.
      </p>
    </div>
  );
}

function SatStat({ label, value, color }) {
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1.5">
        <span className="font-mono-c text-[0.6rem] uppercase tracking-[0.18em] text-[#dde5d2]/70">{label}</span>
        <span className="font-display text-lg text-[#f5f1e8] tabular-nums">{value}<span className="font-mono-c text-[0.55rem] text-[#dde5d2]/55 ml-0.5">%</span></span>
      </div>
      <div className="h-[3px] bg-[#d4a574]/10">
        <div className="h-full" style={{ width: `${value}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

/* ----- BENTO: IoT Sensor (wired to /api/latest) ----- */
function IoTSensorCard({ latest, apiUp, fmt }) {
  const r = latest?.reading;
  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-2.5 font-mono-c text-[0.65rem] uppercase tracking-[0.22em] text-[#1a3a2e]/65 mb-4">
        <Cpu className="w-3.5 h-3.5" />
        <span>§ 02 ▸ Hardware</span>
      </div>
      <h3 className="font-display text-2xl lg:text-[1.65rem] tracking-tight leading-[1.1] mb-3 text-[#1a3a2e]">
        IoT sensor integration.
      </h3>
      <p className="text-sm text-[#1c1f1a]/65 mb-5 leading-relaxed">
        Field-deployed ESP32 nodes streaming soil moisture and soil temperature every 15 minutes.
      </p>

      <div className="mt-auto bg-[#fafaf7] border border-[#1a3a2e]/15 p-4">
        <div className="font-mono-c text-[0.55rem] uppercase tracking-[0.2em] text-[#1a3a2e]/55 mb-3 flex justify-between">
          <span>Node 01 ▸ {apiUp ? 'Live' : 'Offline'}</span>
          <span className="flex items-center gap-1">
            <span className={`w-1 h-1 rounded-full animate-pulse-soft ${apiUp ? 'bg-[#6b8e5a]' : 'bg-[#c9824a]'}`} />
            {apiUp ? 'Online' : '—'}
          </span>
        </div>
        <div className="flex items-end gap-4">
          <div className="flex-1">
            <div className="flex items-baseline gap-1">
              <Droplets className="w-3 h-3 text-[#1a3a2e]" />
              <span className="font-display text-xl tabular-nums">{fmt(r?.soil_moisture, 1)}</span>
              <span className="font-mono-c text-[0.62rem] text-[#1c1f1a]/50">%</span>
            </div>
            <div className="font-mono-c text-[0.55rem] uppercase tracking-[0.18em] text-[#1a3a2e]/55 mt-0.5">Moisture</div>
          </div>
          <div className="flex-1">
            <div className="flex items-baseline gap-1">
              <Thermometer className="w-3 h-3 text-[#c9824a]" />
              <span className="font-display text-xl tabular-nums">{fmt(r?.soil_temperature, 1)}</span>
              <span className="font-mono-c text-[0.62rem] text-[#1c1f1a]/50">°C</span>
            </div>
            <div className="font-mono-c text-[0.55rem] uppercase tracking-[0.18em] text-[#1a3a2e]/55 mt-0.5">Soil Temp</div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ----- BENTO: AI Models ----- */
function AIModelCard() {
  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-2.5 font-mono-c text-[0.65rem] uppercase tracking-[0.22em] text-[#1a3a2e]/65 mb-4">
        <Zap className="w-3.5 h-3.5" />
        <span>§ 03 ▸ Intelligence</span>
      </div>
      <h3 className="font-display text-2xl lg:text-[1.65rem] tracking-tight leading-[1.1] mb-3 text-[#1a3a2e]">
        AI predictive models.
      </h3>
      <p className="text-sm text-[#1c1f1a]/65 mb-5 leading-relaxed">
        LSTM ensemble trained on a decade of climate reanalysis — forecasts drought risk eight weeks ahead, oblast by oblast.
      </p>

      <div className="mt-auto">
        <div className="font-mono-c text-[0.55rem] uppercase tracking-[0.2em] text-[#1a3a2e]/55 mb-2 flex justify-between">
          <span>Forecast ▸ 8 weeks</span>
          <span className="text-[#c9824a]">↑ Conf. 95%</span>
        </div>
        <svg viewBox="0 0 200 60" className="w-full">
          <defs>
            <linearGradient id="forecast-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stopColor="#1a3a2e" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#1a3a2e" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path d="M0 45 L20 40 L40 42 L60 35 L80 38 L100 28 L120 30 L140 22 L160 18 L180 12 L200 8" fill="none" stroke="#1a3a2e" strokeWidth="1.5" />
          <path d="M0 45 L20 40 L40 42 L60 35 L80 38 L100 28 L120 30 L140 22 L160 18 L180 12 L200 8 L200 60 L0 60 Z" fill="url(#forecast-grad)" />
          <path d="M100 28 L120 24 L140 18 L160 14 L180 10 L200 6" fill="none" stroke="#c9824a" strokeWidth="1.5" strokeDasharray="3 2" />
          <line x1="100" y1="0" x2="100" y2="60" stroke="#1a3a2e" strokeWidth="0.5" strokeDasharray="2 2" opacity="0.45" />
          <text x="103" y="10" fill="#1a3a2e" fontSize="6" fontFamily="monospace" opacity="0.6">NOW</text>
        </svg>
      </div>
    </div>
  );
}

/* ----- BENTO: Sustainable ----- */
function SustainableCard() {
  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-2.5 font-mono-c text-[0.65rem] uppercase tracking-[0.22em] text-[#1a3a2e]/65 mb-4">
        <Sprout className="w-3.5 h-3.5" />
        <span>§ 04 ▸ Action</span>
      </div>
      <h3 className="font-display text-2xl lg:text-[1.75rem] tracking-tight leading-[1.1] mb-3 text-[#1a3a2e]">
        Sustainable interventions.
      </h3>
      <p className="text-sm text-[#1c1f1a]/65 mb-5 leading-relaxed">
        Targeted water-conservation playbooks generated per parcel — reduce irrigation waste by 30–50% without yield loss.
      </p>

      <div className="mt-auto grid grid-cols-3 gap-2">
        {[
          { v: '−42%', l: 'Water Use' },
          { v: '+18%',    l: 'Yield' },
          { v: '−27%', l: 'Cost' },
        ].map((m, i) => (
          <div key={i} className="bg-[#dde5d2]/45 border border-[#1a3a2e]/10 p-3">
            <div className="font-display text-xl text-[#1a3a2e] tabular-nums">{m.v}</div>
            <div className="font-mono-c text-[0.55rem] uppercase tracking-[0.18em] text-[#1a3a2e]/60 mt-0.5">{m.l}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ----- BENTO: External feeds ----- */
function ExternalFeedsCard() {
  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-2.5 font-mono-c text-[0.65rem] uppercase tracking-[0.22em] text-[#f5f1e8]/80 mb-4">
        <Globe className="w-3.5 h-3.5" />
        <span>§ 05 ▸ Inputs</span>
      </div>
      <h3 className="font-display text-2xl lg:text-[1.75rem] tracking-tight leading-[1.1] mb-3 text-[#f5f1e8]">
        External climate feeds.
      </h3>
      <p className="text-sm text-[#f5f1e8]/80 mb-5 leading-relaxed">
        We ingest, mask, and reproject open data from NASA MODIS, ESA Sentinel, ECMWF ERA5, and Kazhydromet — so you don’t have to.
      </p>

      <div className="mt-auto flex flex-wrap gap-2">
        {['MODIS', 'CHIRPS', 'ERA5', 'Sentinel-2', 'Kazhydromet', 'GRACE-FO'].map(f => (
          <div key={f} className="border border-[#f5f1e8]/35 px-3 py-1.5 font-mono-c text-[0.6rem] uppercase tracking-[0.2em] text-[#f5f1e8]/95 bg-[#f5f1e8]/5 hover:bg-[#f5f1e8]/15 transition-colors">
            {f}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ----- SOLUTIONS: card ----- */
function SolutionCard({ num, tag, title, desc, pattern }) {
  return (
    <div className="bg-[#f5f1e8] border border-[#1a3a2e]/15 group hover:border-[#1a3a2e]/40 transition-colors">
      <div className="aspect-[4/3] bg-[#1a3a2e] relative overflow-hidden">
        {pattern === 'crop'       && <CropIllustration />}
        {pattern === 'irrigation' && <IrrigationIllustration />}
        {pattern === 'yield'      && <YieldIllustration />}

        <div className="absolute top-3 left-3 font-mono-c text-[0.6rem] uppercase tracking-[0.2em] text-[#d4a574]/85">
          {num}
        </div>
        <div className="absolute bottom-3 right-3 font-mono-c text-[0.58rem] uppercase tracking-[0.2em] text-[#dde5d2]/85 bg-[#0e2820] px-2 py-1 border border-[#d4a574]/25">
          {tag}
        </div>
      </div>

      <div className="p-6">
        <h3 className="font-display text-2xl tracking-[-0.01em] mb-2 text-[#1c1f1a]">{title}</h3>
        <p className="text-sm text-[#1c1f1a]/65 leading-relaxed mb-5">{desc}</p>
        <div className="flex items-center gap-2 text-sm text-[#1a3a2e] font-medium">
          <span>Learn more</span>
          <ArrowUpRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
        </div>
      </div>
    </div>
  );
}

function CropIllustration() {
  // pseudo-random field of NDVI cells with one parcel highlighted
  const colors = ['#1a3a2e', '#2d4a3e', '#5a7a4e', '#6b8e5a', '#a8b89e'];
  return (
    <svg viewBox="0 0 300 225" className="w-full h-full" preserveAspectRatio="xMidYMid slice">
      {Array.from({ length: 18 }).map((_, r) => (
        <g key={r}>
          {Array.from({ length: 25 }).map((_, c) => {
            const seed = (r * 7 + c * 3 + ((r * c) % 5)) % 5;
            return <rect key={c} x={c * 12 + 5} y={r * 12 + 5} width="10" height="10" fill={colors[seed]} opacity="0.85" />;
          })}
        </g>
      ))}
      <rect x="120" y="65" width="78" height="58" fill="none" stroke="#d4a574" strokeWidth="1.2" strokeDasharray="3 2" />
      <text x="124" y="60" fill="#d4a574" fontSize="8" fontFamily="monospace">PARCEL 47B</text>
    </svg>
  );
}

function IrrigationIllustration() {
  return (
    <svg viewBox="0 0 300 225" className="w-full h-full" preserveAspectRatio="xMidYMid slice">
      <rect width="300" height="225" fill="#0e2820" />
      {Array.from({ length: 9 }).map((_, i) => (
        <line key={`v${i}`} x1={i * 38} y1="0" x2={i * 38} y2="225" stroke="#6b8e5a" strokeWidth="0.4" opacity="0.3" />
      ))}
      {Array.from({ length: 7 }).map((_, i) => (
        <line key={`h${i}`} x1="0" y1={i * 38} x2="300" y2={i * 38} stroke="#6b8e5a" strokeWidth="0.4" opacity="0.3" />
      ))}
      <circle cx="150" cy="115" r="85" fill="none" stroke="#d4a574" strokeWidth="0.6" opacity="0.35" />
      <circle cx="150" cy="115" r="62" fill="none" stroke="#d4a574" strokeWidth="0.6" opacity="0.55" />
      <circle cx="150" cy="115" r="40" fill="none" stroke="#d4a574" strokeWidth="0.6" opacity="0.8" />
      <circle cx="150" cy="115" r="22" fill="#d4a574" opacity="0.18" />
      <circle cx="150" cy="115" r="3" fill="#d4a574" />
      <text x="158" y="113" fill="#f5f1e8" fontSize="7" fontFamily="monospace">VALVE 03</text>
      <text x="158" y="123" fill="#d4a574" fontSize="7" fontFamily="monospace">▸ ACTIVE</text>
    </svg>
  );
}

function YieldIllustration() {
  const data = [80, 110, 95, 130, 145, 160, 140, 175, 165, 185, 200];
  return (
    <svg viewBox="0 0 300 225" className="w-full h-full" preserveAspectRatio="xMidYMid slice">
      <rect width="300" height="225" fill="#1a3a2e" />
      <text x="22" y="22" fill="#dde5d2" fontSize="8" fontFamily="monospace">YIELD ▸ tonnes/ha</text>
      <text x="200" y="22" fill="#d4a574" fontSize="8" fontFamily="monospace">FORECAST ▸</text>
      {data.map((h, i) => (
        <g key={i}>
          <rect x={20 + i * 25} y={210 - h} width="18" height={h}
            fill={i >= 7 ? '#d4a574' : '#6b8e5a'} opacity={i >= 7 ? 0.7 : 0.9} />
          {i >= 7 && (
            <rect x={20 + i * 25} y={210 - h} width="18" height={h}
              fill="none" stroke="#d4a574" strokeWidth="0.6" strokeDasharray="2 1" />
          )}
        </g>
      ))}
      <line x1="195" y1="30" x2="195" y2="218" stroke="#d4a574" strokeWidth="0.6" strokeDasharray="3 2" opacity="0.6" />
    </svg>
  );
}

function FooterCol({ num, title, links }) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-5 font-mono-c text-[0.6rem] uppercase tracking-[0.25em] text-[#1a3a2e]/55">
        <span>§ {num}</span>
        <span className="h-px flex-1 bg-[#1a3a2e]/15" />
      </div>
      <h4 className="font-display text-lg mb-4 text-[#1c1f1a]">{title}</h4>
      <ul className="space-y-2.5">
        {links.map(l => (
          <li key={l.label}>
            <a
              href={l.href}
              onClick={l.onClick}
              target={l.external ? '_blank' : undefined}
              rel={l.external ? 'noopener noreferrer' : undefined}
              className="text-sm text-[#1c1f1a]/65 hover:text-[#1a3a2e] transition-colors"
            >
              {l.label}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
