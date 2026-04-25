import { useState } from 'react'
import axios from 'axios'

function Upload() {
  const [file, setFile] = useState(null)
  const [contactId, setContactId] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!file || !contactId) {
      setError('请选择文件并输入联系人ID')
      return
    }

    setLoading(true)
    setError(null)
    setResult(null)

    const formData = new FormData()
    formData.append('file', file)
    formData.append('contact_id', contactId)

    try {
      const response = await axios.post('/api/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      setResult(response.data)
    } catch (err) {
      setError(err.response?.data?.detail || '上传失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <h2>上传聊天记录</h2>
      <form onSubmit={handleSubmit} className="form">
        <div className="form-group">
          <label>联系人ID</label>
          <input
            type="text"
            value={contactId}
            onChange={(e) => setContactId(e.target.value)}
            placeholder="例如: friend_001"
          />
        </div>
        <div className="form-group">
          <label>聊天记录文件</label>
          <input
            type="file"
            onChange={(e) => setFile(e.target.files[0])}
            accept=".txt,.csv,.json"
          />
        </div>
        <button type="submit" disabled={loading}>
          {loading ? '处理中...' : '上传并分析'}
        </button>
      </form>

      {error && <div className="error">{error}</div>}
      {result && (
        <div className="success">
          <p>✓ {result.message}</p>
          <p>解析了 {result.records_count} 条记录</p>
        </div>
      )}
    </div>
  )
}

export default Upload
