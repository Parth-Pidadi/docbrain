import { useState, useRef, useEffect } from 'react';
import { askQuestion } from '../api/client';
import toast from 'react-hot-toast';
import Layout from '../components/Layout';
import './QA.css';

const SUGGESTIONS = [
  'What was my total spending last month?',
  'List all vendors I have invoices from',
  'What are the payment terms in my contracts?',
  'Summarize my recent bank transactions',
];

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
                <span className="mono source-id">{s.doc_id?.slice(0,8)}…</span>
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
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const send = async (question) => {
    const q = question || input.trim();
    if (!q) return;
    setInput('');
    setMessages((m) => [...m, { role: 'user', content: q }]);
    setLoading(true);
    try {
      const { data } = await askQuestion(q);
      setMessages((m) => [...m, { role: 'ai', content: data.answer, sources: data.sources }]);
    } catch (err) {
      toast.error('Failed to get answer');
      setMessages((m) => [...m, { role: 'ai', content: 'Something went wrong. Please try again.' }]);
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
          <h1>Ask Anything</h1>
          <p>Query across all your documents in plain English</p>
        </div>

        <div className="qa-chat">
          {messages.length === 0 ? (
            <div className="qa-welcome">
              <div className="qa-welcome-icon">◈</div>
              <h2>What would you like to know?</h2>
              <p>Ask questions about your uploaded invoices, receipts, contracts, or bank statements.</p>
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
            placeholder="Ask about your documents…"
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
