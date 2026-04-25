import { useState } from 'react'
import axios from 'axios'

function Reply() {
  const [contactId, setContactId] = useState('')
  const [context, setContext] = useState('')
  const [replies, setReplies] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleGenerate = async (e) => {
    e.preventDefault()
    if (!contactId || !context) {
      setError('请输入联系人ID和当前对话')
      return
    }

    setLoading(true)
    setError(null)
    setReplies([])

    try {
      const response = await axios.post('/api/reply', {
        contact_id: contactId,
        current_context: context
      })
      setReplies(response.data.replies || [])
    } catch (err) {
      setError(err.response?.data?.detail || '生成失败')
    } finally {
      setLoading(false)
    }
  }

  const handleFeedback = async (reply) => {
    const feedback = prompt('请输入反馈（说明为什么这条回复不合适）：')
    if (!feedback) return

    try {
      await axios.post('/api/reply/feedback', {
        contact_id: contactId,
        reply: reply,
        feedback: feedback
      })
      alert('反馈已提交，系统将学习改进')
    } catch (err) {
      alert('提交失败：' + (err.response?.data?.detail || err.message))
    }
  }

  return (
    <div className="page">
      <h2>推荐回复</h2>
      <form onSubmit={handleGenerate} className="form">
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
          <label>当前对话</label>
          <textarea
            value={context}
            onChange={(e) => setContext(e.target.value)}
            placeholder="输入对方最新的消息..."
            rows={4}
          />
        </div>
        <button type="submit" disabled={loading}>
          {loading ? '生成中...' : '生成推荐回复'}
        </button>
      </form>

      {error && <div className="error">{error}</div>}
      {replies.length > 0 && (
        <div className="replies">
          <h3>推荐回复</h3>
          {replies.map((item, index) => (
            <div key={index} className="reply-item">
              <div className="reply-content">
                <span className="reply-number">{index + 1}</span>
                <div className="reply-text">
                  <p>{item.reply}</p>
                  {item.evaluation && (
                    <div className={`evaluation ${item.evaluation.is_appropriate ? 'good' : 'warning'}`}>
                      <span>评分: {(item.evaluation.score * 100).toFixed(0)}%</span>
                      {!item.evaluation.is_appropriate && (
                        <div className="issues">
                          <strong>问题:</strong> {item.evaluation.issues.join(', ')}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
              <button
                className="feedback-btn"
                onClick={() => handleFeedback(item.reply)}
              >
                反馈
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default Reply
