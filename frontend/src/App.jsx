import React, { useState, useEffect, useRef } from 'react';
import {
  FileUp,
  Settings,
  BarChart3,
  Target,
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
  { id: 'evaluator_router', label: 'Evaluator & Router', icon: '🔍' },
  { id: 'insight_strategy_generator', label: 'Insight & Strategy Generator', icon: '🗺️' },
  { id: 'benchmark', label: 'Benchmark (optional)', icon: '🧭' },
  { id: 'report_generator', label: 'Executive Report', icon: '📄' }
];

const SOURCE_TYPES = [
  {
    id: 'csv',
    label: 'CSV',
    icon: '📄',
    accept: '.csv',
    description: 'Comma-separated values',
    color: 'text-emerald-400',
    badge: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  },
  {
    id: 'excel',
    label: 'Excel',
    icon: '📊',
    accept: '.xlsx,.xls',
    description: 'Microsoft Excel workbook',
    color: 'text-green-400',
    badge: 'bg-green-500/10 text-green-400 border-green-500/20',
  },
  {
    id: 'parquet',
    label: 'Parquet',
    icon: '⚡',
    accept: '.parquet',
    description: 'Apache Parquet columnar format',
    color: 'text-amber-400',
    badge: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  },
  {
    id: 'sqlite',
    label: 'SQLite',
    icon: '🗄️',
    accept: '.db,.sqlite,.sqlite3',
    description: 'SQLite database file',
    color: 'text-sky-400',
    badge: 'bg-sky-500/10 text-sky-400 border-sky-500/20',
  },
];

export default function App() {
  const [file, setFile] = useState(null);
  const [sourceType, setSourceType] = useState('csv');
  const [tableName, setTableName] = useState('');
  const [metadata, setMetadata] = useState('');
  
  // Rich Ingestion Metadata States
  const [companyDomain, setCompanyDomain] = useState('SaaS / B2B Software');
  const [targetAudience, setTargetAudience] = useState('Mid-Market Enterprise IT Decision Makers');
  const [companyStage, setCompanyStage] = useState('Growth Stage (Series B)');
  const [primaryGoal, setPrimaryGoal] = useState('Maximize Annual Recurring Revenue (ARR) growth and minimize customer churn');
  const [importantKpis, setImportantKpis] = useState('ARR, Churn Rate, Customer Acquisition Cost (CAC), Net Promoter Score (NPS)');
  const [playbookRules, setPlaybookRules] = useState('Analyze Churn correlations with support tickets. Prioritize segment skew analysis on marketing spend ROI.');

  const [useBenchmark, setUseBenchmark] = useState(false);
  const [status, setStatus] = useState('idle'); // idle, uploading, running, done, error
  const [progress, setProgress] = useState({}); // node -> { status, message }
  const [completedSteps, setCompletedSteps] = useState([]);
  const [results, setResults] = useState(null);
  const [activeTab, setActiveTab] = useState('insights');
  const [slideIdx, setSlideIdx] = useState(0);
  const [lightbox, setLightbox] = useState(null); // { url, title, desc }
  const [errorMessage, setErrorMessage] = useState('');
  
  // Chat, Indication, and Sync States
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [expandedInsight, setExpandedInsight] = useState(null);
  const [isSyncing, setIsSyncing] = useState(false);

  const fileInputRef = useRef(null);

  const currentSource = SOURCE_TYPES.find(s => s.id === sourceType);

  const handleFileChange = (e) => {
    const f = e.target.files[0];
    if (f) setFile(f);
  };

  const handleSourceTypeChange = (id) => {
    setSourceType(id);
    setFile(null);
    setTableName('');
    // Reset the file input so a new file can be chosen for the new type
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const renderMarkdown = (mdText) => {
    if (!mdText) return null;
    const lines = mdText.split('\n');
    let inList = false;
    let listItems = [];
    const elements = [];
    
    lines.forEach((line, idx) => {
      const trimmed = line.trim();
      
      // Handle bullet lists
      if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        if (!inList) {
          inList = true;
          listItems = [];
        }
        listItems.push(trimmed.slice(2));
        return;
      } else if (inList) {
        inList = false;
        elements.push(
          <ul key={`list-${idx}`} className="list-disc pl-6 space-y-2 my-4 text-white/70">
            {listItems.map((item, i) => (
              <li key={i} className="text-sm font-light leading-relaxed">{item}</li>
            ))}
          </ul>
        );
      }
      
      // Headings
      if (trimmed.startsWith('# ')) {
        elements.push(<h1 key={idx} className="text-2xl font-heading font-extrabold uppercase tracking-tight text-white border-b border-white/10 pb-4 mt-8 mb-4">{trimmed.slice(2)}</h1>);
      } else if (trimmed.startsWith('## ')) {
        elements.push(<h2 key={idx} className="text-xl font-heading font-bold uppercase tracking-tight text-accent mt-6 mb-3">{trimmed.slice(3)}</h2>);
      } else if (trimmed.startsWith('### ')) {
        elements.push(<h3 key={idx} className="text-lg font-heading font-semibold uppercase tracking-tight text-white/90 mt-4 mb-2">{trimmed.slice(4)}</h3>);
      } else if (trimmed.startsWith('![')) {
        const match = trimmed.match(/!\[(.*?)\]\((.*?)\)/);
        if (match) {
          const caption = match[1];
          const imgUrl = match[2];
          elements.push(
            <div key={idx} className="my-6 rounded-2xl overflow-hidden border border-white/10 bg-white/5 p-4 cursor-pointer" onClick={() => setLightbox({ url: `${API_BASE}${imgUrl}`, title: caption, desc: 'Embedded chart visualization.' })}>
              <img src={`${API_BASE}${imgUrl}`} className="max-h-[300px] mx-auto object-contain" alt={caption} />
              <p className="text-[10px] text-center text-white/40 uppercase tracking-widest mt-2">{caption}</p>
            </div>
          );
        }
      } else if (trimmed.startsWith('|')) {
        elements.push(
          <div key={idx} className="font-mono text-xs text-white/60 bg-white/[0.02] border border-white/5 px-4 py-2 my-1 rounded-lg whitespace-nowrap overflow-x-auto">
            {trimmed}
          </div>
        );
      } else if (trimmed === '') {
        // empty line
      } else {
        elements.push(<p key={idx} className="text-sm text-white/60 leading-relaxed font-light my-3">{trimmed}</p>);
      }
    });
    
    if (inList) {
      elements.push(
        <ul key={`list-end`} className="list-disc pl-6 space-y-2 my-4 text-white/70">
          {listItems.map((item, i) => (
            <li key={i} className="text-sm font-light leading-relaxed">{item}</li>
          ))}
        </ul>
      );
    }
    
    return (
      <div className="space-y-3 max-w-4xl mx-auto bg-black/60 p-10 rounded-[32px] border border-white/5 shadow-2xl text-left">
        {elements}
      </div>
    );
  };

  const startAnalysis = async () => {
    if (!file) return;
    setStatus('uploading');
    setErrorMessage('');
    setCompletedSteps([]);

    // Compile rich metadata into a single string for backward compatibility
    const compiledMetadata = JSON.stringify({
      industry: companyDomain || null,
      company_domain: companyDomain || null,
      target_audience: targetAudience || null,
      company_stage: companyStage || null,
      primary_goal: primaryGoal || null,
      important_kpis: importantKpis ? importantKpis.split(',').map(s => s.trim()).filter(Boolean) : [],
      playbook_rules: playbookRules ? playbookRules.split('\n').map(s => s.trim()).filter(Boolean) : [],
      notes: metadata || null
    });

    const formData = new FormData();
    formData.append('csv_file', file);
    formData.append('metadata', compiledMetadata);
    formData.append('benchmark', useBenchmark);
    formData.append('source_type', sourceType);
    if (sourceType === 'sqlite' && tableName.trim()) {
      formData.append('table_name', tableName.trim());
    }

    try {
      const res = await fetch(`${API_BASE}/analyze`, { method: 'POST', body: formData });
      if (!res.ok) throw new Error(await res.text());
      const { run_id } = await res.json();
      setStatus('running');
      setChatMessages([]);
      connectSSE(run_id);
    } catch (err) {
      setErrorMessage(err.message);
      setStatus('error');
    }
  };

  const handleChatSubmit = async (e) => {
    e.preventDefault();
    if (!chatInput.trim() || !currentRunId || isChatLoading) return;
    
    const userMsg = chatInput.trim();
    setChatInput('');
    setChatMessages(prev => [...prev, { role: 'user', text: userMsg }]);
    setIsChatLoading(true);
    
    try {
      const res = await fetch(`${API_BASE}/api/chat/${currentRunId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      
      setChatMessages(prev => [...prev, { 
        role: 'analyst', 
        text: data.answer, 
        charts: data.charts 
      }]);
    } catch (err) {
      setChatMessages(prev => [...prev, { 
        role: 'analyst', 
        text: `Error executing query: ${err.message}` 
      }]);
    } finally {
      setIsChatLoading(false);
    }
  };

  const handleSyncDatabase = async () => {
    if (!currentRunId || isSyncing) return;
    setIsSyncing(true);
    try {
      const res = await fetch(`${API_BASE}/api/sync/${currentRunId}`, { method: 'POST' });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      alert(`Database sync triggered successfully! Live updates will begin shortly.`);
      setStatus('running');
      setProgress({});
      connectSSE(data.new_run_id);
    } catch (err) {
      alert(`Sync failed: ${err.message}`);
    } finally {
      setIsSyncing(false);
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
      } else if (data.type === 'step_complete') {
        setCompletedSteps(prev => [...prev, data]);
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

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const rid = params.get('run_id');
    if (rid) {
      setStatus('done');
      fetchResults(rid);
    }
  }, []);

  const renderResultSummary = (summary) => {
    if (!summary) return null;
    
    let cleaned = summary.trim();
    
    // Check if it's a numeric float/int value
    if (!isNaN(cleaned) && cleaned !== '') {
      return (
        <div className="inline-flex flex-col p-4 bg-accent/5 border border-accent/20 rounded-2xl text-left mt-2">
          <span className="text-[9px] font-black text-accent uppercase tracking-widest">Calculated Value</span>
          <span className="text-3xl font-heading font-black text-white mt-1">{parseFloat(cleaned).toFixed(4)}</span>
        </div>
      );
    }
    
    let parsedObj = null;
    
    // Attempt standard JSON parsing
    try {
      parsedObj = JSON.parse(cleaned);
    } catch (e) {
      // Fallback: try parsing python representation (single quotes, None/True/False)
      try {
        let jsonStr = cleaned
          .replace(/'/g, '"')
          .replace(/\bNone\b/g, 'null')
          .replace(/\bTrue\b/g, 'true')
          .replace(/\bFalse\b/g, 'false');
        parsedObj = JSON.parse(jsonStr);
      } catch (innerE) {
        parsedObj = null;
      }
    }
    
    if (parsedObj !== null && typeof parsedObj === 'object') {
      if (Array.isArray(parsedObj)) {
        // Check if items are objects (like rows of a DataFrame)
        const isAllObjects = parsedObj.every(item => typeof item === 'object' && item !== null && !Array.isArray(item));
        if (isAllObjects && parsedObj.length > 0) {
          const headers = Object.keys(parsedObj[0]);
          return (
            <div className="overflow-x-auto rounded-xl border border-white/10 bg-white/[0.02] mt-2">
              <table className="min-w-full divide-y divide-white/10 text-left text-xs font-light">
                <thead className="bg-white/5 text-[10px] font-bold text-accent uppercase tracking-wider">
                  <tr>
                    {headers.map(h => (
                      <th key={h} className="px-4 py-2.5 font-semibold">{h.replace(/_/g, ' ')}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5 text-white/80">
                  {parsedObj.map((row, rIdx) => (
                    <tr key={rIdx} className="hover:bg-white/[0.02] transition-colors">
                      {headers.map(h => {
                        const val = row[h];
                        let displayVal = '';
                        if (typeof val === 'number') {
                          displayVal = Number.isInteger(val) ? val.toString() : val.toFixed(4);
                        } else if (typeof val === 'boolean') {
                          displayVal = val ? 'Yes' : 'No';
                        } else if (val === null || val === undefined) {
                          displayVal = '-';
                        } else {
                          displayVal = String(val);
                        }
                        return (
                          <td key={h} className="px-4 py-2 font-mono text-white/70">{displayVal}</td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        } else {
          // Flat list of items
          return (
            <div className="flex flex-wrap gap-2 text-left mt-2">
              {parsedObj.map((item, idx) => (
                <span key={idx} className="px-3 py-1.5 bg-white/[0.03] border border-white/5 rounded-lg text-xs text-white/70">
                  {String(item)}
                </span>
              ))}
            </div>
          );
        }
      } else {
        // Key-Value Object / Series / Dict
        const formatValue = (val) => {
          if (val === null || val === undefined) return '-';
          if (typeof val === 'number') {
            return Number.isInteger(val) ? val.toString() : val.toFixed(4);
          }
          if (typeof val === 'boolean') {
            return val ? 'Yes' : 'No';
          }
          if (Array.isArray(val)) {
            return val.map(v => typeof v === 'object' ? JSON.stringify(v) : String(v)).join(', ');
          }
          if (typeof val === 'object') {
            return Object.entries(val).map(([k, v]) => `${k}: ${v}`).join(' | ');
          }
          return String(val);
        };

        return (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 text-left mt-2">
            {Object.entries(parsedObj).map(([key, val]) => {
              const formatted = formatValue(val);
              const isLong = formatted.length > 25;
              return (
                <div key={key} className="p-3 bg-white/[0.02] border border-white/5 rounded-xl flex flex-col justify-between hover:bg-white/[0.04] transition-colors">
                  <p className="text-[10px] font-bold text-accent uppercase tracking-wider">{key.replace(/_/g, ' ')}</p>
                  <p className={`font-heading text-white mt-1 ${isLong ? 'text-xs font-light text-white/70 leading-relaxed break-all' : 'text-lg font-extrabold'}`}>
                    {formatted}
                  </p>
                </div>
              );
            })}
          </div>
        );
      }
    }
    
    // Multiline or stdout console logs fallback
    const lines = cleaned.split('\n').map(l => l.trim()).filter(Boolean);
    if (lines.length > 1) {
      return (
        <div className="space-y-2 p-4 bg-white/[0.01] border-l-2 border-accent/40 rounded-r-xl text-left mt-2">
          {lines.map((line, lIdx) => {
            // Check if it's a key-value format (e.g. "Metric: Value")
            const colonIdx = line.indexOf(':');
            if (colonIdx > 0 && colonIdx < line.length - 1) {
              const label = line.slice(0, colonIdx).trim();
              const val = line.slice(colonIdx + 1).trim();
              const isValidLabel = label.length < 35 && !label.includes('http') && !label.includes('/') && !label.includes('\\');
              if (isValidLabel) {
                return (
                  <div key={lIdx} className="flex flex-col sm:flex-row sm:items-baseline gap-1 sm:gap-2">
                    <span className="text-[10px] font-bold text-accent uppercase tracking-wider shrink-0">{label}:</span>
                    <span className="text-xs font-mono text-white/80">{val}</span>
                  </div>
                );
              }
            }
            
            if (line.startsWith('- ') || line.startsWith('* ')) {
              return (
                <div key={lIdx} className="flex items-start gap-2 text-xs font-light text-white/70 pl-2">
                  <span className="text-accent text-[10px] mt-0.5">•</span>
                  <span>{line.substring(2)}</span>
                </div>
              );
            }
            
            return (
              <p key={lIdx} className="text-xs font-light leading-relaxed text-white/70">
                {line}
              </p>
            );
          })}
        </div>
      );
    }
    
    return (
      <div className="p-4 bg-white/[0.02] border-l-2 border-accent rounded-r-xl text-xs font-light leading-relaxed text-white/75 italic text-left mt-2">
        "{cleaned.replace(/^["']|["']$/g, '')}"
      </div>
    );
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

                {/* Source Type Selector */}
                <div className="space-y-3">
                  <label className="text-xs font-bold text-white/30 uppercase tracking-widest">Data Source</label>
                  <div className="grid grid-cols-4 gap-2">
                    {SOURCE_TYPES.map(src => (
                      <button
                        key={src.id}
                        onClick={() => handleSourceTypeChange(src.id)}
                        className={`
                          group flex flex-col items-center gap-2 p-4 rounded-2xl border transition-all duration-300
                          ${sourceType === src.id
                            ? 'bg-white/8 border-white/20 shadow-lg'
                            : 'bg-white/[0.02] border-white/5 hover:border-white/10 hover:bg-white/[0.04]'
                          }
                        `}
                      >
                        <span className="text-2xl">{src.icon}</span>
                        <span className={`text-[11px] font-black uppercase tracking-widest ${
                          sourceType === src.id ? src.color : 'text-white/30'
                        }`}>{src.label}</span>
                        <span className="text-[10px] text-white/20 text-center leading-tight hidden lg:block">{src.description}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Drop zone */}
                <div
                  onClick={() => fileInputRef.current.click()}
                  className="group relative h-64 rounded-3xl glass border-2 border-dashed border-white/10 flex flex-col items-center justify-center gap-4 cursor-pointer hover:border-accent/40 hover:bg-white/[0.04] transition-all duration-500"
                >
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileChange}
                    hidden
                    accept={currentSource?.accept}
                  />
                  <div className="w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center group-hover:scale-110 transition-transform duration-500">
                    <FileUp className="w-8 h-8 text-white/40 group-hover:text-white transition-colors" />
                  </div>
                  <div className="text-center">
                    {file ? (
                      <>
                        <p className="text-xl font-medium">{file.name}</p>
                        <div className="flex items-center justify-center gap-2 mt-2">
                          <span className={`px-2 py-0.5 rounded-md text-[9px] font-black uppercase tracking-widest border ${currentSource?.badge}`}>
                            {currentSource?.icon} {currentSource?.label}
                          </span>
                          <span className="text-white/30 text-sm">{(file.size / 1024).toFixed(1)} KB</span>
                        </div>
                      </>
                    ) : (
                      <>
                        <p className="text-xl font-medium">Choose {currentSource?.label} file</p>
                        <p className="text-white/30 text-sm mt-1">{currentSource?.description} · {currentSource?.accept}</p>
                      </>
                    )}
                  </div>
                </div>

                {/* SQLite table name input */}
                {sourceType === 'sqlite' && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="space-y-2"
                  >
                    <label className="text-xs font-bold text-white/30 uppercase tracking-widest flex items-center gap-2">
                      🗄️ Table Name <span className="text-white/20 normal-case font-normal">(optional — leave blank to auto-detect)</span>
                    </label>
                    <input
                      type="text"
                      value={tableName}
                      onChange={e => setTableName(e.target.value)}
                      placeholder="e.g. sales_data"
                      className="w-full bg-white/5 border border-white/10 rounded-2xl px-4 py-3 text-sm focus:outline-none focus:border-sky-500/50 focus:bg-white/[0.08] transition-all font-mono"
                    />
                  </motion.div>
                )}
              </div>

              <div className="glass rounded-3xl p-8 space-y-6 sticky top-8 max-h-[85vh] overflow-y-auto scrollbar-thin">
                <div className="border-b border-white/5 pb-4">
                  <label className="text-xs font-bold text-white/30 uppercase tracking-widest flex items-center gap-2">
                    <Settings className="w-3 h-3 text-accent" /> Company Profile & Parameters
                  </label>
                  <p className="text-[10px] text-white/20 mt-1">Ground the AI Analyst in your business context and playbook constraints.</p>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-white/40 uppercase tracking-wider">Company Domain</label>
                    <input
                      type="text"
                      value={companyDomain}
                      onChange={e => setCompanyDomain(e.target.value)}
                      placeholder="e.g. B2B SaaS"
                      className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-xs focus:outline-none focus:border-accent/40"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-white/40 uppercase tracking-wider">Target Audience</label>
                    <input
                      type="text"
                      value={targetAudience}
                      onChange={e => setTargetAudience(e.target.value)}
                      placeholder="e.g. Enterprise IT"
                      className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-xs focus:outline-none focus:border-accent/40"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-white/40 uppercase tracking-wider">Company Stage</label>
                    <select
                      value={companyStage}
                      onChange={e => setCompanyStage(e.target.value)}
                      className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-xs focus:outline-none focus:border-accent/40 text-white/80"
                    >
                      <option value="" className="bg-black">Select Stage...</option>
                      <option value="Seed" className="bg-black">Seed / Pre-revenue</option>
                      <option value="Series A" className="bg-black">Series A / Growth</option>
                      <option value="Enterprise" className="bg-black">Enterprise Scale</option>
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-white/40 uppercase tracking-wider">Focus KPIs (Comma Sep)</label>
                    <input
                      type="text"
                      value={importantKpis}
                      onChange={e => setImportantKpis(e.target.value)}
                      placeholder="e.g. ARR, Churn, LTV"
                      className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-xs focus:outline-none focus:border-accent/40 font-mono"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-white/40 uppercase tracking-wider">Primary Business Goal</label>
                  <input
                    type="text"
                    value={primaryGoal}
                    onChange={e => setPrimaryGoal(e.target.value)}
                    placeholder="e.g. Increase ARR and reduce churn in Q3"
                    className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-xs focus:outline-none focus:border-accent/40"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-white/40 uppercase tracking-wider">Analyst Playbook Context (One per line)</label>
                  <textarea
                    value={playbookRules}
                    onChange={e => setPlaybookRules(e.target.value)}
                    placeholder="e.g. Ignore test accounts with high duplicates&#10;Fiscal calendar starts in April"
                    className="w-full bg-white/5 border border-white/10 rounded-xl p-3 min-h-[70px] text-xs focus:outline-none focus:border-accent/40 font-light"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-white/40 uppercase tracking-wider">General Ingestion Notes</label>
                  <textarea
                    value={metadata}
                    onChange={(e) => setMetadata(e.target.value)}
                    placeholder="Provide additional background, outliers context, etc..."
                    className="w-full bg-white/5 border border-white/10 rounded-xl p-3 min-h-[70px] text-xs focus:outline-none focus:border-accent/40 font-light"
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
              className="grid lg:grid-cols-[260px,1fr] gap-8 items-start py-8"
            >
              {/* Compact checklist sidebar (15%) */}
              <div className="glass rounded-[32px] border border-white/5 p-6 space-y-6 text-left sticky top-8">
                <div className="border-b border-white/5 pb-3">
                  <h4 className="text-xs font-black text-white/30 uppercase tracking-[0.2em]">Pipeline State</h4>
                </div>
                <div className="space-y-4">
                  {NODES.map((node, i) => {
                    const nodeProgress = progress[node.id];
                    const isActive = nodeProgress?.status === 'active';
                    const isDone = nodeProgress?.status === 'done';

                    return (
                      <div key={node.id} className="flex items-center gap-3">
                        <div className={`
                          w-5 h-5 rounded-full border flex items-center justify-center text-[10px] shrink-0 transition-all duration-300
                          ${isDone ? 'bg-emerald-500 border-emerald-500 text-white font-bold' : isActive ? 'bg-accent border-accent text-white animate-pulse' : 'bg-black border-white/10 text-white/30'}
                        `}>
                          {isDone ? '✓' : i + 1}
                        </div>
                        <span className={`text-xs font-semibold leading-none ${isDone ? 'text-white/60' : isActive ? 'text-accent' : 'text-white/20'}`}>
                          {node.label}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Main Analysis Stream Area (85%) */}
              <div className="space-y-8 bg-black/40 p-8 rounded-[32px] border border-white/5 min-h-[600px]">
                <h3 className="text-xl font-heading font-bold text-left border-b border-white/5 pb-4 uppercase tracking-tight text-white flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full bg-accent animate-pulse" />
                  Live Analysis Stream
                </h3>

                {completedSteps.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-32 text-center space-y-4">
                    <div className="w-12 h-12 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center animate-spin">
                      ⏳
                    </div>
                    <div className="space-y-1">
                      <p className="text-sm font-semibold text-white/80">Initializing Pipeline</p>
                      <p className="text-xs text-white/40 max-w-xs leading-relaxed">Parsing metadata and profiling data schema. Exploration results will stream here shortly.</p>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-8 text-left">
                    {completedSteps.map((step, idx) => (
                      <motion.div
                        key={step.step_id || idx}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="glass rounded-3xl p-8 border border-white/5 hover:border-white/10 transition-all space-y-6"
                      >
                        <div className="flex items-start justify-between border-b border-white/5 pb-4">
                          <div>
                            <span className="text-[10px] font-black text-accent uppercase tracking-widest">Step {step.step_id} Completed</span>
                            <h4 className="text-2xl font-heading font-black uppercase tracking-tight text-white mt-1">{step.title}</h4>
                          </div>
                          <span className="px-2.5 py-1 rounded-md text-[9px] font-black uppercase tracking-widest bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            Success
                          </span>
                        </div>

                        {step.objective && (
                          <div className="space-y-1.5">
                            <p className="text-[9px] font-black text-white/30 uppercase tracking-[0.2em]">Objective</p>
                            <p className="text-xs text-white/60 font-light leading-relaxed">{step.objective}</p>
                          </div>
                        )}

                        {step.charts && step.charts.length > 0 && (
                          <div className="grid sm:grid-cols-1 md:grid-cols-2 gap-6 my-6">
                            {step.charts.map((chart, cIdx) => (
                              <div
                                key={cIdx}
                                className="rounded-2xl border border-white/5 bg-black/40 p-4 cursor-pointer overflow-hidden group relative"
                                onClick={() => setLightbox({ url: `${API_BASE}${chart.url}`, title: chart.title, desc: 'Generated dynamically by the agent.' })}
                              >
                                <div className="aspect-[16/10] overflow-hidden rounded-xl bg-white/5 flex items-center justify-center">
                                  <img
                                    src={`${API_BASE}${chart.url}`}
                                    className="w-full h-full object-contain filter brightness-90 group-hover:brightness-110 transition-all duration-500"
                                    alt={chart.title}
                                  />
                                </div>
                                <p className="text-[9px] font-bold text-center text-white/40 uppercase tracking-widest mt-3">{chart.title}</p>
                              </div>
                            ))}
                          </div>
                        )}

                        {step.result_summary && (
                          <div className="space-y-1.5 pt-4 border-t border-white/5">
                            <p className="text-[9px] font-black text-white/30 uppercase tracking-[0.2em]">Key Findings Summary</p>
                            {renderResultSummary(step.result_summary)}
                          </div>
                        )}
                      </motion.div>
                    ))}

                    {(() => {
                      const activeStepProgress = progress['code_executor'];
                      const isActiveStep = activeStepProgress?.status === 'active';
                      const activeStepMessage = activeStepProgress?.message || '';
                      
                      return isActiveStep && (
                        <motion.div
                          key="active-step-skeleton"
                          initial={{ opacity: 0.5 }}
                          animate={{ opacity: [0.5, 0.8, 0.5] }}
                          transition={{ repeat: Infinity, duration: 2 }}
                          className="glass rounded-3xl p-8 border border-accent/20 bg-accent/5 space-y-6"
                        >
                          <div className="flex items-center justify-between border-b border-white/5 pb-4">
                            <div className="space-y-1">
                              <span className="text-[10px] font-black text-accent uppercase tracking-widest animate-pulse">Running In Sandbox</span>
                              <h4 className="text-xl font-heading font-black uppercase tracking-tight text-white/80">{activeStepMessage || "Processing Analysis Step..."}</h4>
                            </div>
                            <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
                          </div>
                          <div className="space-y-3">
                            <div className="h-3 w-1/3 bg-white/5 rounded-md" />
                            <div className="h-20 w-full bg-white/5 rounded-2xl animate-pulse" />
                          </div>
                        </motion.div>
                      );
                    })()}
                  </div>
                )}
              </div>
            </motion.div>
          ) : status === 'done' && results ? (
            <motion.div
              key="results"
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              className="space-y-12"
            >
              {/* Suite Header with Sync Option */}
              <div className="flex items-center justify-between border-b border-white/5 pb-6">
                <div className="space-y-1">
                  <h2 className="text-3xl font-heading font-black tracking-tight uppercase">Analysis Suite</h2>
                  <p className="text-xs text-white/30 font-light">Interactive reporting dashboard and live analytical sandbox session.</p>
                </div>
                {results.schema_summary?.source_type === 'sqlite' && (
                  <button
                    onClick={handleSyncDatabase}
                    disabled={isSyncing}
                    className="flex items-center gap-2 bg-sky-500/10 border border-sky-500/20 text-sky-400 px-5 py-2.5 rounded-2xl text-xs font-bold uppercase tracking-wider hover:bg-sky-500/20 disabled:opacity-30 active:scale-95 transition-all"
                  >
                    🔄 {isSyncing ? 'Syncing...' : 'Sync Active DB'}
                  </button>
                )}
              </div>

              {/* Top Stats Bar */}
              <div className="grid grid-cols-2 lg:grid-cols-7 gap-4">
                {[
                  { label: 'Analysed Rows', value: results.schema_summary.row_count, icon: <ChevronRight className="w-3 h-3" /> },
                  { label: 'Dimensions', value: results.schema_summary.column_count, icon: <ChevronRight className="w-3 h-3" /> },
                  { label: 'Key Insights', value: results.insights.length, icon: <ChevronRight className="w-3 h-3" /> },
                  { label: 'Visual Cards', value: results.charts.length, icon: <ChevronRight className="w-3 h-3" /> },
                  { label: 'Strategic Ops', value: results.recommendations.length, icon: <ChevronRight className="w-3 h-3" /> },
                  { label: 'Domain', value: results.business_context, icon: <ChevronRight className="w-3 h-3" />, isText: true },
                  {
                    label: 'Source',
                    value: (results.schema_summary?.source_type || sourceType || 'csv').toUpperCase(),
                    icon: <span>{SOURCE_TYPES.find(s => s.id === (results.schema_summary?.source_type || sourceType))?.icon || '📄'}</span>,
                    isText: true,
                    badge: SOURCE_TYPES.find(s => s.id === (results.schema_summary?.source_type || sourceType))?.badge,
                  },
                ].map((stat, i) => (
                  <div key={i} className="glass rounded-2xl p-5 flex flex-col items-center justify-center text-center space-y-2 text-white/90">
                    <p className="text-[10px] font-bold text-white/20 uppercase tracking-[0.2em] flex items-center gap-1">
                      {stat.icon} {stat.label}
                    </p>
                    <p className={`font-heading font-black tracking-tighter ${
                      stat.badge
                        ? `text-[10px] px-2 py-0.5 rounded-md border ${stat.badge}`
                        : stat.isText ? 'text-sm' : 'text-2xl'
                    }`}>
                      {stat.value || '—'}
                    </p>
                  </div>
                ))}
              </div>

              {/* Main Workspace grid with Sidebar Chat */}
              <div className="grid lg:grid-cols-[1fr,360px] gap-8 items-start">
                <div className="space-y-8">
                  {/* Major Tabs */}
                  <div className="flex items-center gap-2 p-1.5 rounded-2xl bg-white/5 border border-white/5 w-fit overflow-x-auto">
                    {[
                      { id: 'insights', label: 'Findings', icon: <Target className="w-4 h-4" /> },
                      { id: 'report', label: 'Executive Report', icon: <CheckCircle2 className="w-4 h-4" /> },
                      { id: 'visuals', label: 'Data Visuals', icon: <BarChart3 className="w-4 h-4" /> },
                      { id: 'strategy', label: 'Strategy', icon: <ArrowRight className="w-4 h-4" /> },
                    ].map(tab => (
                      <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={`
                          px-6 py-2.5 rounded-xl flex items-center gap-2 text-xs font-bold tracking-tight transition-all
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
                            <div className="mt-8 pt-6 border-t border-white/5 flex items-center justify-between text-[10px] font-bold text-white/20 uppercase tracking-widest">
                              <span>Source: {insight.supporting_data}</span>
                              {insight.data_proof && (
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setExpandedInsight(expandedInsight === i ? null : i);
                                  }}
                                  className="text-[9px] font-black text-accent hover:underline flex items-center gap-1 focus:outline-none normal-case tracking-normal"
                                >
                                  {expandedInsight === i ? 'Hide Data Proof' : 'View Data Proof'}
                                </button>
                              )}
                            </div>
                          )}

                          {insight.data_proof && expandedInsight === i && (
                            <motion.div
                              initial={{ opacity: 0, height: 0 }}
                              animate={{ opacity: 1, height: 'auto' }}
                              className="mt-4 space-y-3 font-mono text-[10px] text-white/60 bg-black/60 p-4 rounded-2xl border border-white/5 overflow-x-auto w-full text-left"
                            >
                              <div className="space-y-1">
                                <p className="text-accent uppercase tracking-widest text-[8px] font-bold">Executed Code:</p>
                                <pre className="text-white/80 overflow-x-auto whitespace-pre-wrap font-mono leading-tight">{insight.data_proof.code}</pre>
                              </div>
                              {insight.data_proof.stdout && (
                                <div className="space-y-1 pt-2 border-t border-white/5">
                                  <p className="text-emerald-400 uppercase tracking-widest text-[8px] font-bold">Console Output:</p>
                                  <pre className="text-white/70 overflow-x-auto whitespace-pre-wrap font-mono leading-tight">{insight.data_proof.stdout}</pre>
                                </div>
                              )}
                            </motion.div>
                          )}
                        </motion.div>
                      ))}
                    </div>
                  )}

                  {activeTab === 'report' && (
                    <motion.div
                      initial={{ opacity: 0, y: 15 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="space-y-6"
                    >
                      {results.executive_report ? (
                        renderMarkdown(results.executive_report)
                      ) : (
                        <div className="text-center py-20 glass rounded-[40px] border border-white/5">
                          <p className="text-white/30 font-mono text-sm tracking-widest uppercase">Written report is generating or not available.</p>
                        </div>
                      )}
                    </motion.div>
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


                </div>
              </div>

              {/* Right Column: Persistent Obsidian Copilot Chat Sidebar */}
                <div className="glass rounded-[32px] border border-white/5 p-6 flex flex-col h-[650px] justify-between sticky top-8">
                  <div className="space-y-2 border-b border-white/5 pb-4 text-left">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full bg-accent animate-pulse" />
                      <h3 className="text-sm font-heading font-black uppercase tracking-wider text-white">Obsidian Copilot</h3>
                    </div>
                    <p className="text-[10px] text-white/30 font-light">Ask questions, segment categories, or request new charts dynamically.</p>
                  </div>
                  
                  {/* Messages Area */}
                  <div className="flex-1 overflow-y-auto my-4 space-y-4 pr-2 scrollbar-thin flex flex-col">
                    {chatMessages.length === 0 ? (
                      <div className="my-auto flex flex-col items-center justify-center text-center p-6 space-y-3">
                        <span className="text-3xl">🤖</span>
                        <p className="text-xs text-white/40 leading-relaxed font-light">"How can I help you explore this data? Ask me to segment tier groups, check correlations, or plot new visuals."</p>
                      </div>
                    ) : (
                      chatMessages.map((msg, i) => (
                        <div key={i} className={`flex flex-col gap-1.5 text-left ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                          <div className={`px-4 py-3 rounded-2xl text-xs leading-relaxed max-w-[90%] font-light ${
                            msg.role === 'user' 
                              ? 'bg-accent text-white rounded-tr-none' 
                              : 'bg-white/5 border border-white/5 text-white/80 rounded-tl-none'
                          }`}>
                            <p className="whitespace-pre-wrap">{msg.text}</p>
                            
                            {msg.charts && msg.charts.map((c, j) => (
                              <div 
                                key={j} 
                                className="mt-3 rounded-xl overflow-hidden border border-white/10 bg-black/40 p-2 cursor-pointer" 
                                onClick={() => setLightbox({ url: `${API_BASE}${c.url}`, title: c.title, desc: 'Generated via Interactive Chat Q&A.' })}
                              >
                                <img src={`${API_BASE}${c.url}`} className="w-full object-contain max-h-[140px] rounded-lg" alt="Chat Chart" />
                                <p className="text-[8px] font-bold text-center text-white/45 uppercase tracking-widest mt-1.5">{c.title}</p>
                              </div>
                            ))}
                          </div>
                          <span className="text-[8px] font-mono text-white/20 uppercase tracking-widest px-1">
                            {msg.role === 'user' ? 'User' : 'Obsidian Analyst'}
                          </span>
                        </div>
                      ))
                    )}
                    {isChatLoading && (
                      <div className="flex items-center gap-2 text-white/30 text-[10px] font-mono uppercase tracking-widest animate-pulse mt-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-accent animate-ping" />
                        Analyst is querying...
                      </div>
                    )}
                  </div>
                  
                  {/* Chat Input form */}
                  <form onSubmit={handleChatSubmit} className="flex gap-2 pt-4 border-t border-white/5">
                    <input
                      type="text"
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      disabled={isChatLoading}
                      placeholder="Ask about plan tiers, ROI, segments..."
                      className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-xs focus:outline-none focus:border-accent/40 focus:bg-white/[0.08] transition-all font-light text-white/80"
                    />
                    <button
                      type="submit"
                      disabled={!chatInput.trim() || isChatLoading}
                      className="px-4 rounded-xl bg-white text-black font-bold text-xs hover:scale-105 active:scale-95 transition-all disabled:opacity-30 disabled:hover:scale-100 flex items-center justify-center shrink-0"
                    >
                      Send
                    </button>
                  </form>
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
