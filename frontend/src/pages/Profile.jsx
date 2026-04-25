import { useState } from 'react'
import axios from 'axios'

function Profile() {
  const [contactId, setContactId] = useState('')
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleSearch = async (e) => {
    e.preventDefault()
    if (!contactId) return

    setLoading(true)
    setError(null)

    try {
      const response = await axios.get(`/api/profile/${contactId}`)
      setProfile(response.data)
    } catch (err) {
      setError(err.response?.data?.detail || '查询失败')
      setProfile(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <h2>画像管理</h2>
      <form onSubmit={handleSearch} className="form">
        <div className="form-group">
          <label>联系人ID</label>
          <input
            type="text"
            value={contactId}
            onChange={(e) => setContactId(e.target.value)}
            placeholder="例如: friend_001"
          />
        </div>
        <button type="submit" disabled={loading}>
          {loading ? '查询中...' : '查询画像'}
        </button>
      </form>

      {error && <div className="error">{error}</div>}
      {profile && (
        <div className="profile-result">
          <div className="profile-section">
            <h3>用户画像</h3>
            <pre>{JSON.stringify(profile.user_profile, null, 2)}</pre>
          </div>
          <div className="profile-section">
            <h3>联系人画像</h3>
            <pre>{JSON.stringify(profile.contact_profile, null, 2)}</pre>
          </div>
          <p className="updated-at">更新时间: {profile.updated_at}</p>
        </div>
      )}
    </div>
  )
}

export default Profile
