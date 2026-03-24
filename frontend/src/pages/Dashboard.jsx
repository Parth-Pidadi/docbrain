import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { uploadDocument, extractDocument, getInsightsSummary, getDocuments, renameDocument, deleteDocument } from '../api/client';
import toast from 'react-hot-toast';
import Layout from '../components/Layout';
import './Dashboard.css';

const ACCEPT = '.pdf,.png,.jpg,.jpeg,.tiff,.webp';

function DocTypeIcon({ type }) {
  const icons = { invoice: '🧾', receipt: '🏷️', bank_statement: '🏦', contract: '📋', unknown: '📄' };
  return <span>{icons[type] || '📄'}</span>;
}

function DocCard({ doc, onExtract, onRename, onDelete }) {
  const isExtracted = !!doc.doc_type;
  const [editing, setEditing] = useState(false);
  const [nameVal, setNameVal] = useState(doc.filename);
  const inputRef = useRef(null);

  useEffect(() => { setNameVal(doc.filename); }, [doc.filename]);
  useEffect(() => { if (editing) inputRef.current?.focus(); }, [editing]);

  const commitRename = () => {
    const trimmed = nameVal.trim();
    if (trimmed && trimmed !== doc.filename) {
      onRename(doc, trimmed);
    } else {
      setNameVal(doc.filename); // revert if empty or unchanged
    }
    setEditing(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') commitRename();
    if (e.key === 'Escape') { setNameVal(doc.filename); setEditing(false); }
  };

  return (
    <div className={`doc-card ${isExtracted ? 'extracted' : ''}`}>
      <div className="doc-card-top">
        <div className="doc-icon">
          <DocTypeIcon type={doc.doc_type} />
        </div>
        <span className={`badge badge-${doc.doc_type || 'unknown'}`}>
          {doc.doc_type ? doc.doc_type.replace('_', ' ') : 'pending'}
        </span>
        {/* Actions */}
        <div className="doc-actions">
          {isExtracted && (
            <button
              className="doc-action-btn"
              title="Re-extract (refreshes embeddings)"
              onClick={() => onExtract(doc)}
            >↺</button>
          )}
          <button
            className="doc-action-btn"
            title="Rename"
            onClick={() => setEditing(true)}
          >✎</button>
          <button
            className="doc-action-btn doc-action-delete"
            title="Delete"
            onClick={() => onDelete(doc)}
          >✕</button>
        </div>
      </div>
      <div className="doc-card-body">
        {editing ? (
          <input
            ref={inputRef}
            className="doc-rename-input"
            value={nameVal}
            onChange={(e) => setNameVal(e.target.value)}
            onBlur={commitRename}
            onKeyDown={handleKeyDown}
          />
        ) : (
          <p
            className="doc-filename"
            title={doc.filename}
            onDoubleClick={() => setEditing(true)}
          >
            {doc.filename}
          </p>
        )}
        <p className="doc-id mono">{doc.doc_id?.slice(0, 8) || doc.id?.slice(0,8)}…</p>
      </div>
      {!isExtracted && (
        <button
          className="btn btn-primary btn-sm doc-extract-btn"
          onClick={() => onExtract(doc)}
        >
          Extract →
        </button>
      )}
      {isExtracted && doc.extracted_fields?._embedding_warning && (
        <p className="embedding-warn">⚠ Colab was offline — hover &amp; click ↺ to re-extract with embeddings</p>
      )}
      {isExtracted && (
        <div className="doc-fields-preview">
          {Object.entries(doc.extracted_fields || {}).slice(0, 3).map(([k, v]) => (
            <div key={k} className="doc-field-row">
              <span className="df-key">{k.replace(/_/g, ' ')}</span>
              <span className="df-val">{typeof v === 'object' ? '…' : String(v).slice(0, 24)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Dashboard() {
  const [docs, setDocs] = useState([]);
  const [summary, setSummary] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [extractingId, setExtractingId] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    // Load existing documents from the database
    getDocuments()
      .then((r) => setDocs(r.data))
      .catch(() => {});
    getInsightsSummary()
      .then((r) => setSummary(r.data))
      .catch(() => {});
  }, []);

  const handleFiles = async (files) => {
    const file = files[0];
    if (!file) return;
    setUploading(true);
    try {
      const { data } = await uploadDocument(file);
      toast.success(`${file.name} uploaded!`);
      const newDoc = { ...data, filename: file.name };
      setDocs((d) => [newDoc, ...d]);
      // Auto-extract
      handleExtract(newDoc);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleExtract = async (doc) => {
    const docId = doc.doc_id || doc.id;
    setExtractingId(docId);
    try {
      const { data } = await extractDocument(docId);
      toast.success(`Extracted as ${data.doc_type.replace('_', ' ')}`);
      setDocs((prev) =>
        prev.map((d) => {
          const id = d.doc_id || d.id;
          return id === docId ? { ...d, ...data } : d;
        })
      );
      if (summary) {
        setSummary((s) => ({
          ...s,
          total_documents: (s.total_documents || 0) + (s.by_type?.[data.doc_type] ? 0 : 1),
          by_type: { ...s.by_type, [data.doc_type]: (s.by_type?.[data.doc_type] || 0) + 1 },
        }));
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Extraction failed');
    } finally {
      setExtractingId(null);
    }
  };

  const handleRename = async (doc, newName) => {
    const docId = doc.doc_id || doc.id;
    try {
      await renameDocument(docId, newName);
      setDocs((prev) =>
        prev.map((d) => (d.doc_id === docId || d.id === docId) ? { ...d, filename: newName } : d)
      );
      toast.success('Renamed successfully');
    } catch {
      toast.error('Rename failed');
    }
  };

  const handleDelete = async (doc) => {
    const docId = doc.doc_id || doc.id;
    if (!window.confirm(`Delete "${doc.filename}"? This cannot be undone.`)) return;
    try {
      await deleteDocument(docId);
      setDocs((prev) => prev.filter((d) => (d.doc_id || d.id) !== docId));
      toast.success('Document deleted');
      // Refresh summary
      getInsightsSummary().then((r) => setSummary(r.data)).catch(() => {});
    } catch {
      toast.error('Delete failed');
    }
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  const TYPE_COLORS = {
    invoice: 'var(--accent)',
    receipt: 'var(--success)',
    bank_statement: 'var(--info)',
    contract: 'var(--warning)',
  };

  return (
    <Layout>
      <div className="dashboard fade-up">
        {/* Header */}
        <div className="dash-header">
          <div>
            <h1 className="dash-title">Documents</h1>
            <p className="dash-subtitle">Upload, extract, and query your documents</p>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={() => navigate('/qa')}>
            ◎ Ask a Question
          </button>
        </div>

        {/* Stats row */}
        {summary && (
          <div className="stats-row">
            <div className="stat-card">
              <span className="stat-value">{summary.total_documents}</span>
              <span className="stat-label">Documents</span>
            </div>
            {Object.entries(summary.by_type || {}).map(([type, count]) => (
              <div key={type} className="stat-card">
                <span className="stat-value" style={{ color: TYPE_COLORS[type] || 'var(--text)' }}>
                  {count}
                </span>
                <span className="stat-label">{type.replace('_', ' ')}</span>
              </div>
            ))}
          </div>
        )}

        {/* Upload zone */}
        <div
          className={`upload-zone ${dragging ? 'dragging' : ''} ${uploading ? 'loading' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => document.getElementById('file-input').click()}
        >
          <input
            id="file-input"
            type="file"
            accept={ACCEPT}
            style={{ display: 'none' }}
            onChange={(e) => handleFiles(e.target.files)}
          />
          {uploading ? (
            <><div className="spinner spinner-lg" /><p>Uploading…</p></>
          ) : extractingId ? (
            <><div className="spinner spinner-lg" /><p>Extracting…</p></>
          ) : (
            <>
              <div className="uz-icon">⬆</div>
              <p className="uz-label">Drop a document here or <span className="uz-link">browse files</span></p>
              <p className="uz-hint">PDF, PNG, JPG, JPEG, TIFF, WEBP · Max 20 MB</p>
            </>
          )}
        </div>

        {/* Doc grid */}
        {docs.length === 0 ? (
          <div className="empty-state">
            <div className="es-icon">📄</div>
            <h3>No documents yet</h3>
            <p>Upload your first invoice, receipt, or contract above</p>
          </div>
        ) : (
          <div className="doc-grid">
            {docs.map((doc) => {
              const id = doc.doc_id || doc.id;
              return (
                <div key={id} className={extractingId === id ? 'extracting-overlay' : ''}>
                  <DocCard
                    doc={doc}
                    onExtract={handleExtract}
                    onRename={handleRename}
                    onDelete={handleDelete}
                  />
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Layout>
  );
}
