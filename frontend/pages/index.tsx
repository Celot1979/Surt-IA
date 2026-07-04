import { useCallback, useState } from 'react'

type NodeStatus = 'pending' | 'running' | 'completed' | 'failed' | 'rejected'

interface NodeResult {
  node_name: string
  status: NodeStatus
  output: string | null
  error: string | null
  token_usage: Record<string, number>
  duration_ms: number
}

interface AuditResult {
  audit_id: string
  status: NodeStatus
  nodes: NodeResult[]
  summary: string | null
  error: string | null
  created_at: string
}

export default function Home() {
  const [content, setContent] = useState('')
  const [targetPath, setTargetPath] = useState('')
  const [auditId, setAuditId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<AuditResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const pollAudit = useCallback(async (id: string) => {
    try {
      const res = await fetch(`/audit/${id}`)
      if (!res.ok) return
      const data: AuditResult = await res.json()
      setResult(data)
      if (data.status === 'running' || data.status === 'pending') {
        setTimeout(() => pollAudit(id), 2000)
      }
    } catch {
      // retry
      setTimeout(() => pollAudit(id), 3000)
    }
  }, [])

  const handleSubmit = async () => {
    if (!content.trim()) return

    setLoading(true)
    setError(null)
    setResult(null)
    setAuditId(null)

    try {
      const res = await fetch(`/audit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content,
          target_path: targetPath.trim() || undefined,
        }),
      })

      if (!res.ok) {
        const err = await res.text()
        setError(`Error ${res.status}: ${err}`)
        setLoading(false)
        return
      }

      const data: AuditResult = await res.json()
      setAuditId(data.audit_id)
      setResult(data)

      if (data.status === 'running' || data.status === 'pending') {
        setTimeout(() => pollAudit(data.audit_id), 2000)
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Error de conexión')
    } finally {
      setLoading(false)
    }
  }

  const statusClass = (s: NodeStatus) => `status-badge status-${s}`
  const nodeClass = (s: NodeStatus) => `node-item ${s}`

  const nodeLabel = (name: string) => {
    const labels: Record<string, string> = {
      validate_input: 'Validación de seguridad',
      node1_gemini: 'Gemini (Análisis inicial)',
      node2_deepseek: 'DeepSeek (Revisión cruzada)',
      node3_raptor_scan: 'Raptor (Escaneo)',
      node4_raptor_validate: 'Raptor (Validación)',
      finalize: 'Finalización',
    }
    return labels[name] || name
  }

  return (
    <div className="container">
      <header>
        <h1>Surt IA</h1>
        <p>Pipeline multi-agente de auditoría de prompts</p>
      </header>

      <div className="card">
        <div className="form-group">
          <label htmlFor="prompt">Prompt a auditar</label>
          <textarea
            id="prompt"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Ingresa el prompt que deseas analizar..."
          />
        </div>

        <div className="form-group">
          <label htmlFor="target">Ruta del repositorio objetivo (opcional, para Raptor)</label>
          <input
            id="target"
            type="text"
            value={targetPath}
            onChange={(e) => setTargetPath(e.target.value)}
            placeholder="/home/user/proyecto"
          />
        </div>

        <button
          className="btn btn-primary"
          onClick={handleSubmit}
          disabled={loading || !content.trim()}
        >
          {loading ? 'Analizando...' : 'Iniciar auditoría'}
        </button>
      </div>

      {loading && !result && (
        <div className="card loading">
          <div className="spinner" />
          Iniciando pipeline de auditoría...
        </div>
      )}

      {error && (
        <div className="card" style={{ borderColor: '#ef4444' }}>
          <pre style={{ color: '#fca5a5' }}>{error}</pre>
        </div>
      )}

      {result && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 600 }}>Auditoría #{result.audit_id.slice(0, 8)}</h2>
            <span className={statusClass(result.status)}>{result.status}</span>
          </div>

          {result.error && (
            <pre style={{ color: '#fca5a5', marginBottom: 16, padding: 8, background: '#0f172a', borderRadius: 4 }}>
              {result.error}
            </pre>
          )}

          <ul className="node-list">
            {result.nodes.map((node, i) => (
              <li key={i} className={nodeClass(node.status)}>
                <div className="node-header">
                  <span className="node-name">{nodeLabel(node.node_name)}</span>
                  <span className={statusClass(node.status)}>{node.status}</span>
                </div>
                {node.duration_ms > 0 && (
                  <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
                    {(node.duration_ms / 1000).toFixed(1)}s
                    {node.token_usage?.total_tokens > 0 && ` · ${node.token_usage.total_tokens} tokens`}
                  </span>
                )}
                {node.output && (
                  <div className="node-output">{node.output}</div>
                )}
              </li>
            ))}
          </ul>

          {result.summary && (
            <div style={{ marginTop: 16 }}>
              <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: 8 }}>Resumen</h3>
              <div className="node-output">{result.summary}</div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
