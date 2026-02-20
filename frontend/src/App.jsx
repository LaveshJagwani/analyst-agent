import React, { useState, useEffect, useRef } from 'react';
import {
  FileUp,
  Settings,
  BarChart3,
  Target,
  Presentation,
  CheckCircle2,
  AlertCircle,
  ChevronRight,
  Download,
  Maximize2,
  X,
  Plus,
  ArrowRight
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? ''
  : 'https://analyst-agent-b0qp.onrender.com';

const NODES = [
  { id: 'metadata_parser', label: 'Metadata Parser', icon: '📄' },
  { id: 'schema_analyzer', label: 'Schema Analyzer', icon: '💎' },
  { id: 'context_classifier', label: 'Context Classifier', icon: '🌐' },
  { id: 'analysis_planner', label: 'Analysis Planner', icon: '📝' },
  { id: 'code_executor', label: 'Code Executor', icon: '⚡' },
  { id: 'insight_validator', label: 'Insight Validator', icon: '🛡️' },
  { id: 'strategy_generator', label: 'Strategy Generator', icon: '🗺️' },
  { id: 'benchmark', label: 'Benchmark (optional)', icon: '🧭' },
  { id: 'presentation_generator', label: 'Presentation Generator', icon: '🎭' },
];

export default function App() {
  const [file, setFile] = useState(null);
  const [metadata, setMetadata] = useState('');
  const [useBenchmark, setUseBenchmark] = useState(false);
  const [status, setStatus] = useState('idle'); // idle, uploading, running, done, error
  const [progress, setProgress] = useState({}); // node -> { status, message }
  const [results, setResults] = useState(null);
  const [activeTab, setActiveTab] = useState('insights');
  const [slideIdx, setSlideIdx] = useState(0);
  const [lightbox, setLightbox] = useState(null); // { url, title, desc }
  const [errorMessage, setErrorMessage] = useState('');

  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    const f = e.target.files[0];
    if (f && f.name.endsWith('.csv')) setFile(f);
  };

  const startAnalysis = async () => {
    if (!file) return;
    setStatus('uploading');
    setErrorMessage('');

    const formData = new FormData();
    formData.append('csv_file', file);
    formData.append('metadata', metadata);
    formData.append('benchmark', useBenchmark);

    try {
      const res = await fetch(`${API_BASE}/analyze`, { method: 'POST', body: formData });
      if (!res.ok) throw new Error(await res.text());
      const { run_id } = await res.json();
      setStatus('running');
      connectSSE(run_id);
    } catch (err) {
      setErrorMessage(err.message);
      setStatus('error');
    }
  };

  const connectSSE = (runId) => {
    const evs = new EventSource(`${API_BASE}/stream/${runId}`);

    evs.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type === 'node_complete') {
        setProgress(prev => ({ ...prev, [data.node]: { status: 'done', message: 'Complete' } }));
      } else if (data.type === 'node_progress') {
        setProgress(prev => ({ ...prev, [data.node]: { status: 'active', message: data.message } }));
      } else if (data.type === 'done') {
        evs.close();
        setStatus('done');
        fetchResults(runId);
      } else if (data.type === 'error') {
        evs.close();
        setErrorMessage(data.message);
        setStatus('error');
      }
    };

    evs.onerror = () => evs.close();
  };

  const [currentRunId, setCurrentRunId] = useState(null);

  const fetchResults = async (runId) => {
    const res = await fetch(`${API_BASE}/results/${runId}`);
    const data = await res.json();
    if (data.status === 'done') {
      setResults(data.result);
      setCurrentRunId(runId);
    }
  };

  const downloadPptx = (runId) => {
    window.location.href = `${API_BASE}/export/pptx/${runId}`;
  };

  return (
    <div className="min-h-screen font-body selection:bg-accent/30 selection:text-white">
      {/* Background Decor */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-accent/5 rounded-full blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-accent-secondary/5 rounded-full blur-[120px]" />
      </div>

      <header className="sticky top-0 z-50 glass border-b border-white/5 py-4 px-6">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-white flex items-center justify-center text-black font-black text-xl">
              A
            </div>
            <h1 className="text-lg font-heading font-bold tracking-tight">
              OBSIDIAN <span className="text-white/40">ANALYST</span>
            </h1>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-[10px] font-mono tracking-widest text-white/30 uppercase">Enterprise v1.2</span>
            <div className="h-4 w-[1px] bg-white/10" />
            <div className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-[11px] font-medium text-white/50 uppercase tracking-tighter">System Ready</span>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-12 relative z-10">
        <AnimatePresence mode="wait">
          {status === 'idle' || status === 'uploading' ? (
            <motion.div
              key="setup"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="grid lg:grid-cols-[1fr,400px] gap-12 items-start"
            >
              <div className="space-y-8">
                <div className="space-y-4">
                  <h2 className="text-5xl font-heading font-extrabold tracking-tight leading-[1.1]">
                    Extract intelligence <br /> from raw data.
                  </h2>
                  <p className="text-white/40 text-lg max-w-xl">
                    Upload your dataset and let the Obsidian engine perform deep structural analysis,
                    market benchmarking, and strategic synthesis.
                  </p>
                </div>

                <div
                  onClick={() => fileInputRef.current.click()}
                  className="group relative h-80 rounded-3xl glass border-2 border-dashed border-white/10 flex flex-col items-center justify-center gap-4 cursor-pointer hover:border-accent/40 hover:bg-white/[0.04] transition-all duration-500"
                >
                  <input type="file" ref={fileInputRef} onChange={handleFileChange} hidden accept=".csv" />
                  <div className="w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center group-hover:scale-110 transition-transform duration-500">
                    <FileUp className="w-8 h-8 text-white/40 group-hover:text-white transition-colors" />
                  </div>
                  <div className="text-center">
                    <p className="text-xl font-medium">{file ? file.name : 'Choose dataset source'}</p>
                    <p className="text-white/30 text-sm mt-1">{file ? `${(file.size / 1024).toFixed(1)} KB` : 'Drag and drop .csv file here'}</p>
                  </div>
                </div>
              </div>

              <div className="glass rounded-3xl p-8 space-y-8 sticky top-32">
                <div className="space-y-4">
                  <label className="text-xs font-bold text-white/30 uppercase tracking-widest flex items-center gap-2">
                    <Settings className="w-3 h-3" /> Analysis Parameters
                  </label>
                  <textarea
                    value={metadata}
                    onChange={(e) => setMetadata(e.target.value)}
                    placeholder="Describe business model, key goals, or specific KPIs to track..."
                    className="w-100% w-full bg-white/5 border border-white/10 rounded-2xl p-4 min-h-[160px] text-sm focus:outline-none focus:border-accent/50 focus:bg-white/[0.08] transition-all"
                  />
                </div>

                <div className="flex items-center justify-between p-4 rounded-2xl bg-white/5 border border-white/5">
                  <div className="space-y-0.5">
                    <p className="text-sm font-semibold">Live Benchmarking</p>
                    <p className="text-[11px] text-white/30">Fetch market data via Tavily</p>
                  </div>
                  <button
                    onClick={() => setUseBenchmark(!useBenchmark)}
                    className={`w-12 h-6 rounded-full relative transition-colors duration-300 ${useBenchmark ? 'bg-accent' : 'bg-white/10'}`}
                  >
                    <div className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full transition-transform duration-300 ${useBenchmark ? 'translate-x-6' : ''}`} />
                  </button>
                </div>

                <button
                  disabled={!file || status === 'uploading'}
                  onClick={startAnalysis}
                  className="w-full py-5 rounded-2xl bg-white text-black font-heading font-black text-lg hover:scale-[1.02] active:scale-[0.98] disabled:opacity-30 disabled:hover:scale-100 transition-all duration-300 shadow-xl shadow-white/5 flex items-center justify-center gap-3"
                >
                  {status === 'uploading' ? (
                    <div className="w-6 h-6 border-4 border-black/20 border-t-black rounded-full animate-spin" />
                  ) : (
                    <>
                      INITIATE SEQUENCE <ArrowRight className="w-5 h-5" />
                    </>
                  )}
                </button>
              </div>
            </motion.div>
          ) : (status === 'running' || (status === 'done' && !results)) ? (
            <motion.div
              key="running"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="max-w-2xl mx-auto space-y-12 py-20"
            >
              <div className="text-center space-y-4">
                <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass border-white/10 text-xs font-bold text-accent uppercase tracking-widest">
                  <div className="w-2 h-2 rounded-full bg-accent animate-pulse" />
                  Processing Pipeline
                </div>
                <h2 className="text-4xl font-heading font-black uppercase tracking-tighter">Analyzing Dataset</h2>
              </div>

              <div className="space-y-0">
                {NODES.map((node, i) => {
                  const nodeProgress = progress[node.id];
                  const isActive = nodeProgress?.status === 'active';
                  const isDone = nodeProgress?.status === 'done';

                  return (
                    <div key={node.id} className="relative group flex gap-6 pb-10">
                      {i < NODES.length - 1 && (
                        <div className={`absolute left-[17px] top-8 bottom-0 w-[2px] transition-colors duration-500 ${isDone ? 'bg-accent' : 'bg-white/5'}`} />
                      )}
                      <div className={`
                        w-9 h-9 rounded-full border-2 flex items-center justify-center z-10 transition-all duration-500
                        ${isDone ? 'bg-accent border-accent text-white' : isActive ? 'bg-black border-accent text-accent shadow-[0_0_20px_rgba(99,102,241,0.4)]' : 'bg-black border-white/10 text-white/20'}
                      `}>
                        {isDone ? <CheckCircle2 className="w-4 h-4" /> : <span className="text-xs font-bold">{i + 1}</span>}
                      </div>
                      <div className="space-y-1">
                        <p className={`font-semibold tracking-tight ${isDone ? 'text-white' : isActive ? 'text-accent' : 'text-white/20'}`}>
                          {node.label}
                        </p>
                        <p className="text-[11px] font-mono text-white/30 uppercase tracking-widest">
                          {isActive ? nodeProgress.message : isDone ? 'Task finalized' : 'Queueing...'}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </motion.div>
          ) : status === 'done' && results ? (
            <motion.div
              key="results"
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              className="space-y-12"
            >
              {/* Top Stats Bar */}
              <div className="grid grid-cols-2 lg:grid-cols-6 gap-4">
                {[
                  { label: 'Analysed Rows', value: results.schema_summary.row_count, icon: <ChevronRight className="w-3 h-3" /> },
                  { label: 'Dimensions', value: results.schema_summary.column_count, icon: <ChevronRight className="w-3 h-3" /> },
                  { label: 'Key Insights', value: results.insights.length, icon: <ChevronRight className="w-3 h-3" /> },
                  { label: 'Visual Cards', value: results.charts.length, icon: <ChevronRight className="w-3 h-3" /> },
                  { label: 'Strategic Ops', value: results.recommendations.length, icon: <ChevronRight className="w-3 h-3" /> },
                  { label: 'Domain', value: results.business_context, icon: <ChevronRight className="w-3 h-3" />, isText: true },
                ].map((stat, i) => (
                  <div key={i} className="glass rounded-2xl p-5 flex flex-col items-center justify-center text-center space-y-2">
                    <p className="text-[10px] font-bold text-white/20 uppercase tracking-[0.2em] flex items-center gap-1">
                      {stat.icon} {stat.label}
                    </p>
                    <p className={`font-heading font-black tracking-tighter ${stat.isText ? 'text-sm' : 'text-2xl'}`}>
                      {stat.value || '—'}
                    </p>
                  </div>
                ))}
              </div>

              {/* Major Tabs */}
              <div className="space-y-8">
                <div className="flex items-center gap-2 p-1.5 rounded-2xl bg-white/5 border border-white/5 w-fit mx-auto overflow-x-auto">
                  {[
                    { id: 'insights', label: 'Findings', icon: <Target className="w-4 h-4" /> },
                    { id: 'visuals', label: 'Data Visuals', icon: <BarChart3 className="w-4 h-4" /> },
                    { id: 'strategy', label: 'Strategy', icon: <ArrowRight className="w-4 h-4" /> },
                    { id: 'deck', label: 'Presentation', icon: <Presentation className="w-4 h-4" /> },
                  ].map(tab => (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={`
                        px-8 py-3 rounded-xl flex items-center gap-3 text-sm font-bold tracking-tight transition-all
                        ${activeTab === tab.id ? 'bg-white text-black shadow-lg shadow-white/5' : 'text-white/40 hover:text-white hover:bg-white/5'}
                      `}
                    >
                      {tab.icon} {tab.label}
                    </button>
                  ))}
                </div>

                <div className="mt-8">
                  {activeTab === 'insights' && (
                    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                      {results.insights.map((insight, i) => (
                        <motion.div
                          key={i}
                          initial={{ opacity: 0, y: 20 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: i * 0.1 }}
                          className="glass rounded-3xl p-8 flex flex-col justify-between group hover:border-white/20"
                        >
                          <div className="space-y-4">
                            <div className="flex items-start justify-between">
                              <h3 className="text-xl font-heading font-bold leading-tight group-hover:text-accent transition-colors">{insight.title}</h3>
                              <span className={`px-2 py-1 rounded-md text-[9px] font-black uppercase tracking-widest border
                                ${insight.confidence === 'high' ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' :
                                  insight.confidence === 'low' ? 'bg-rose-500/10 text-rose-500 border-rose-500/20' :
                                    'bg-amber-500/10 text-amber-500 border-amber-500/20'}
                              `}>
                                {insight.confidence}
                              </span>
                            </div>
                            {insight.metric_value && (
                              <div className="py-2 px-3 rounded-lg bg-black/40 text-accent font-mono text-sm inline-block">
                                {insight.metric_value}
                              </div>
                            )}
                            <p className="text-sm text-white/50 leading-relaxed font-light">{insight.description}</p>
                          </div>
                          {insight.supporting_data && (
                            <div className="mt-8 pt-6 border-t border-white/5 text-[10px] font-bold text-white/20 uppercase tracking-widest">
                              Source: {insight.supporting_data}
                            </div>
                          )}
                        </motion.div>
                      ))}
                    </div>
                  )}

                  {activeTab === 'visuals' && (
                    <div className="grid md:grid-cols-2 gap-8">
                      {results.charts.map((chart, i) => (
                        <div
                          key={i}
                          onClick={() => setLightbox({ url: `${API_BASE}${chart.url}`, title: chart.step_title, desc: chart.step_objective })}
                          className="glass rounded-3xl overflow-hidden group cursor-pointer"
                        >
                          <div className="aspect-[16/9] overflow-hidden bg-white/5 relative">
                            <img src={`${API_BASE}${chart.url}`} className="w-full h-full object-contain filter brightness-90 group-hover:brightness-110 transition-all duration-700" loading="lazy" />
                            <div className="absolute inset-0 bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                              <Maximize2 className="w-8 h-8 text-white" />
                            </div>
                          </div>
                          <div className="p-6 space-y-2">
                            <h4 className="font-heading font-bold text-lg">{chart.step_title}</h4>
                            <p className="text-xs text-white/40 font-light">{chart.step_objective}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {activeTab === 'strategy' && (
                    <div className="space-y-6">
                      {results.recommendations.map((rec, i) => (
                        <div key={i} className="glass rounded-3xl p-10 flex flex-col md:flex-row gap-12 border-l-4 border-l-accent group hover:bg-white/[0.03] transition-colors">
                          <div className="md:w-1/3 space-y-4">
                            <div className="text-[10px] font-black text-accent uppercase tracking-widest">Strategic Vector {i + 1}</div>
                            <h4 className="text-3xl font-heading font-bold tracking-tighter leading-none">{rec.action}</h4>
                          </div>
                          <div className="flex-1 grid sm:grid-cols-2 gap-8">
                            {[
                              { label: 'Operational Rationale', value: rec.rationale },
                              { label: 'Projected Impact', value: rec.expected_impact },
                              { label: 'Risk Mitigation', value: rec.risk },
                              { label: 'Primary Next Step', value: rec.suggested_next_step },
                            ].map((field, j) => (
                              <div key={j} className="space-y-1">
                                <p className="text-[9px] font-black text-white/20 uppercase tracking-[0.2em]">{field.label}</p>
                                <p className="text-sm text-white/60 leading-relaxed font-light">{field.value || 'N/A'}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {activeTab === 'deck' && (
                    <div className="max-w-4xl mx-auto space-y-8">
                      <div className="flex items-center justify-between">
                        <h3 className="text-2xl font-heading font-bold tracking-tight">EXECUTIVE BRIEF</h3>
                        <button
                          onClick={() => downloadPptx(currentRunId)}
                          className="bg-accent text-white px-6 py-3 rounded-2xl text-xs font-bold uppercase tracking-widest hover:scale-105 active:scale-95 transition-all flex items-center gap-2"
                        >
                          <Download className="w-4 h-4" /> Export Slide Deck
                        </button>
                      </div>

                      {results.presentation?.slides?.length > 0 ? (
                        <div className="aspect-[16/10] bg-[#020202] rounded-[40px] border border-white/10 p-16 relative overflow-hidden flex flex-col justify-between shadow-2xl shadow-accent/5">
                          <div className="space-y-8">
                            <h4 className="text-4xl font-heading font-black uppercase tracking-tight border-b border-white/5 pb-8">
                              {results.presentation.slides[slideIdx]?.title}
                            </h4>
                            <div className="grid md:grid-cols-[1fr,1fr] gap-12">
                              <div className="space-y-6">
                                {results.presentation.slides[slideIdx]?.content?.map((bullet, idx) => (
                                  <div key={idx} className="flex gap-4">
                                    <div className="w-1.5 h-1.5 rounded-full bg-accent mt-2.5 shrink-0" />
                                    <p className="text-xl font-light text-white/70 leading-relaxed font-body">{bullet}</p>
                                  </div>
                                ))}
                              </div>
                              {results.presentation.slides[slideIdx]?.chart_reference && (
                                <div className="rounded-3xl glass border border-white/5 overflow-hidden flex items-center justify-center p-4">
                                  <img
                                    src={`${API_BASE}/charts/${results.presentation.slides[slideIdx].chart_reference.split(/[\\/]/).pop()}`}
                                    className="w-full h-full object-contain"
                                    alt="Slide Visual"
                                  />
                                </div>
                              )}
                            </div>
                          </div>

                          <div className="flex items-center justify-between pt-12 border-t border-white/5">
                            <div className="flex gap-2">
                              <button
                                onClick={() => setSlideIdx(Math.max(0, slideIdx - 1))}
                                disabled={slideIdx === 0}
                                className="w-12 h-12 rounded-full glass border-white/10 flex items-center justify-center hover:bg-white/10 disabled:opacity-20"
                              >
                                ←
                              </button>
                              <button
                                onClick={() => setSlideIdx(Math.min(results.presentation.slides.length - 1, slideIdx + 1))}
                                disabled={slideIdx === results.presentation.slides.length - 1}
                                className="w-12 h-12 rounded-full glass border-white/10 flex items-center justify-center hover:bg-white/10 disabled:opacity-20"
                              >
                                →
                              </button>
                            </div>
                            <p className="text-[10px] font-mono font-bold text-white/20 uppercase tracking-[0.4em]">
                              Slide {slideIdx + 1} // {results.presentation.slides.length}
                            </p>
                          </div>
                        </div>
                      ) : (
                        <div className="text-center py-20 glass rounded-[40px] border border-white/5">
                          <p className="text-white/30 font-mono text-sm tracking-widest uppercase">Performance results generated. No slides available.</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          ) : status === 'error' && (
            <motion.div
              key="error"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="max-w-md mx-auto py-20 text-center space-y-8"
            >
              <div className="w-20 h-20 rounded-full bg-rose-500/10 border border-rose-500/20 flex items-center justify-center mx-auto">
                <AlertCircle className="w-10 h-10 text-rose-500" />
              </div>
              <div className="space-y-2">
                <h2 className="text-3xl font-heading font-black italic uppercase italic tracking-tighter">Analysis Terminated</h2>
                <p className="text-white/40 text-sm leading-relaxed">{errorMessage}</p>
              </div>
              <button
                onClick={() => setStatus('idle')}
                className="px-8 py-4 rounded-2xl glass border-white/10 text-xs font-black uppercase tracking-widest hover:bg-white/5"
              >
                Reset Environment
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* Lightbox */}
      <AnimatePresence>
        {lightbox && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[1000] flex items-center justify-center p-8 backdrop-blur-2xl bg-black/80"
          >
            <button onClick={() => setLightbox(null)} className="absolute top-8 right-8 w-12 h-12 rounded-full glass flex items-center justify-center text-white hover:bg-white/10">
              <X className="w-6 h-6" />
            </button>
            <div className="max-w-6xl w-full grid md:grid-cols-[1fr,300px] gap-12 bg-black rounded-[40px] border border-white/10 overflow-hidden">
              <div className="p-8 flex items-center justify-center bg-[#050505]">
                <img src={lightbox.url} className="w-full max-h-[70vh] object-contain" />
              </div>
              <div className="p-12 space-y-6 flex flex-col justify-center">
                <h4 className="text-3xl font-heading font-black italic uppercase italic tracking-tighter border-b border-white/5 pb-6">{lightbox.title}</h4>
                <p className="text-white/40 leading-relaxed font-light">{lightbox.desc}</p>
                <button className="flex items-center gap-2 text-xs font-black text-accent uppercase tracking-widest pt-4">
                  <Download className="w-4 h-4" /> Save Visual Asset
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
