import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom'
import Upload from './pages/Upload'
import Profile from './pages/Profile'
import Reply from './pages/Reply'
import './App.css'

function App() {
  return (
    <Router>
      <div className="app">
        <nav className="nav">
          <h1>ChatHelper</h1>
          <div className="nav-links">
            <Link to="/">上传记录</Link>
            <Link to="/profile">画像管理</Link>
            <Link to="/reply">推荐回复</Link>
          </div>
        </nav>
        <main className="main">
          <Routes>
            <Route path="/" element={<Upload />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/reply" element={<Reply />} />
          </Routes>
        </main>
      </div>
    </Router>
  )
}

export default App
