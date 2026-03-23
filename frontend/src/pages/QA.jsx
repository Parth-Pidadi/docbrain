import { useState, useRef, useEffect } from 'react';
import { askQuestion, getDocuments } from '../api/client';
import toast from 'react-hot-toast';
import Layout from '../components/Layout';
import './QA.css';

const SUGGESTIONS = [
  'What was my total spending last month?',
  'List all vendors I have invoices from',
  'What are the red flags in my contracts?',
  'Summarize my recent bank transactions',
  'What items did I purchase?',
  'Analyze my contract for risky clauses',
  'Are there any auto-renewal clauses I should know about?',
  'What are my obligations under this contract?',
];

const DOC_ICONS = {
  invoice: '🧾', receipt: '🏷️', bank_statement: '🏦',
  contract: '📋', unknown: '📄',
};

function Message({ msg }) {
  const isUser = msg.role === 'user';
  return (
    <div className={`msg ${isUser ? 'msg-user' : 'msg-ai'}`}>
      <div className="msg-avatar">{isUser ? '◉' : '◈'}</div>
      <div className="msg-body">
        <p className="msg-text">{msg.content}</p>
        {msg.sources?.length > 0 && (
          <div className="msg-sources">
            <p className="sources-label">Sources</p>
            {msg.sources.map((s, i) => (
              <div key={i} className="source-chip">
                <span className="mono source-id">{s.doc_id?.slice(0, 8)}…</span>
                <span className="source-score">{(s.score * 100).toFixed(0)}%</span>
                <span className="source-chunk">{s.chunk?.slice(0, 80)}…</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function QA() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [docs, setDocs] = useState([]);
  const [selectedDocs, setSelectedDocs] = useState([]); // empty = global
  const [scopeOpen, setScopeOpen] = useState(false);
  const bottomRef = useRef(null);

  // Detect duplicate filenames (same file uploaded more than once)
  const filenameCounts = docs.reduce((acc, d) => {
    acc[d.filename] = (acc[d.filename] || 0) + 1;
    return acc;
  }, {});
  const hasDuplicates = Object.values(filenameCounts).some((c) => c > 1);

  useEffect(() => {
    getDocuments()
      .then(({ data }) => setDocs(data))
      .catch(() => {});
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const toggleDoc = (docId) => {
    setSelectedDocs((prev) =>
      prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId]
    );
  };

  const selectAll = () => setSelectedDocs([]);
  const isGlobal = selectedDocs.length === 0;

  const scopeLabel = isGlobal
    ? 'All Documents'
    : selectedDocs.length === 1
    ? docs.find((d) => d.doc_id === selectedDocs[0])?.filename || '1 doc'
    : `${selectedDocs.length} documents`;

  const send = async (question) => {
    const q = question || input.trim();
    if (!q) return;
    setInput('');
    const updatedMessages = [...messages, { role: 'user', content: q }];
    setMessages(updatedMessages);
    setLoading(true);
    try {
      const doc_ids = selectedDocs.length > 0 ? selectedDocs : null;
      // Send last 6 messages as history (excluding the one we just added)
      const history = messages.slice(-6).map((m) => ({
        role: m.role === 'ai' ? 'assistant' : 'user',
        content: m.content,
      }));
      const { data } = await askQuestion(q, doc_ids, history);
      setMessages((m) => [...m, { role: 'ai', content: data.answer, sources: data.sources }]);
    } catch (err) {
      const detail = err.response?.data?.detail || 'Failed to get answer. Please try again.';
      toast.error(detail, { duration: 5000 });
      setMessages((m) => [...m, { role: 'ai', content: `⚠️ ${detail}` }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  };

  return (
    <Layout>
      <div className="qa-page fade-up">
        <div className="qa-header">
          <div className="qa-header-top">
            <div>
              <h1>Ask Anything</h1>
              <p>Query your documents in plain English</p>
            </div>

            {/* Scope Selector */}
            <div className="scope-wrapper">
              <button
                className={`scope-btn ${!isGlobal ? 'scope-btn--active' : ''}`}
                onClick={() => setScopeOpen((o) => !o)}
              >
                <span className="scope-icon">{isGlobal ? '◎' : '◉'}</span>
                <span className="scope-label">{scopeLabel}</span>
                <span className="scope-arrow">{scopeOpen ? '▴' : '▾'}</span>
              </button>

              {scopeOpen && (
                <div className="scope-dropdown">
                  <div className="scope-dropdown-header">
                    <span>Select documents to query</span>
                    <button className="scope-clear" onClick={selectAll}>
                      {isGlobal ? 'All selected' : 'Clear selection'}
                    </button>
                  </div>

                  {/* Global option */}
                  <div
                    className={`scope-item ${isGlobal ? 'scope-item--active' : ''}`}
                    onClick={selectAll}
                  >
                    <div className="scope-item-icon">◎</div>
                    <div className="scope-item-info">
                      <p className="scope-item-name">All Documents</p>
                      <p className="scope-item-meta">Query across everything</p>
                    </div>
                    {isGlobal && <span className="scope-check">✓</span>}
                  </div>

                  {/* Divider */}
                  {docs.length > 0 && <div className="scope-divider" />}

                  {/* Duplicate file warning */}
                  {hasDuplicates && (
                    <div className="scope-duplicate-warning">
                      ⚠️ You have duplicate filenames — selecting both will count data twice.
                    </div>
                  )}

                  {/* Individual docs */}
                  {docs.map((doc) => {
                    const selected = selectedDocs.includes(doc.doc_id);
                    const isDuplicate = filenameCounts[doc.filename] > 1;
                    return (
                      <div
                        key={doc.doc_id}
                        className={`scope-item ${selected ? 'scope-item--active' : ''} ${!doc.is_extracted ? 'scope-item--disabled' : ''}`}
                        onClick={() => doc.is_extracted && toggleDoc(doc.doc_id)}
                        title={!doc.is_extracted ? 'Extract this document first' : isDuplicate ? 'Duplicate filename — may cause double-counting' : ''}
                      >
                        <div className="scope-item-icon">
                          {DOC_ICONS[doc.doc_type] || '📄'}
                        </div>
                        <div className="scope-item-info">
                          <p className="scope-item-name">
                            {doc.filename}
                            {isDuplicate && <span className="scope-dupe-badge"> ×2</span>}
                          </p>
                          <p className="scope-item-meta">
                            {doc.doc_type
                              ? doc.doc_type.replace('_', ' ')
                              : 'not extracted yet'}
                          </p>
                        </div>
                        {selected && <span className="scope-check">✓</span>}
                        {!doc.is_extracted && <span className="scope-pending">pending</span>}
                      </div>
                    );
                  })}

                  {docs.length === 0 && (
                    <p className="scope-empty">No documents uploaded yet</p>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Active scope pill */}
          {!isGlobal && (
            <div className="scope-active-pills">
              {selectedDocs.map((id) => {
                const doc = docs.find((d) => d.doc_id === id);
                return (
                  <span key={id} className="scope-pill">
                    {DOC_ICONS[doc?.doc_type] || '📄'} {doc?.filename}
                    <button onClick={() => toggleDoc(id)}>×</button>
                  </span>
                );
              })}
            </div>
          )}
        </div>

        <div className="qa-chat">
          {messages.length === 0 ? (
            <div className="qa-welcome">
              <div className="qa-welcome-icon">◈</div>
              <h2>What would you like to know?</h2>
              <p>
                {isGlobal
                  ? 'Querying across all your documents.'
                  : `Querying ${selectedDocs.length} selected document${selectedDocs.length > 1 ? 's' : ''}.`}
              </p>
              <div className="suggestions">
                {SUGGESTIONS.map((s) => (
                  <button key={s} className="suggestion-chip" onClick={() => send(s)}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="messages">
              {messages.map((msg, i) => (
                <Message key={i} msg={msg} />
              ))}
              {loading && (
                <div className="msg msg-ai">
                  <div className="msg-avatar">◈</div>
                  <div className="msg-body">
                    <div className="typing-indicator">
                      <span /><span /><span />
                    </div>
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        <div className="qa-input-row">
          <textarea
            className="qa-input"
            placeholder={
              isGlobal
                ? 'Ask about all your documents…'
                : `Ask about ${scopeLabel}…`
            }
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKey}
            rows={1}
            disabled={loading}
          />
          <button
            className="btn btn-primary qa-send-btn"
            onClick={() => send()}
            disabled={loading || !input.trim()}
          >
            {loading ? <div className="spinner" /> : '↑'}
          </button>
        </div>
        <p className="qa-hint">Enter to send · Shift+Enter for new line</p>
      </div>
    </Layout>
  );
}
