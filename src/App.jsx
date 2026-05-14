import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Operations from './pages/Operations';
import Shadow from './pages/Shadow';
import Status from './pages/Status';

function App() {
  return (
    <Router>
      <div className="flex min-h-screen bg-dark">
        {/* Sidebar */}
        <nav className="w-64 bg-slate-900 border-r border-slate-800 p-6 flex flex-col justify-between">
          <div>
            <div className="text-white font-bold text-xl mb-8 flex items-center gap-2">
              <span className="text-accentGreen">🤖</span> Crypto Bot
            </div>
            <ul className="space-y-2">
              <li>
                <Link to="/" className="text-slate-300 hover:text-white hover:bg-slate-800 px-4 py-2 rounded-lg block transition-colors">
                  Dashboard
                </Link>
              </li>
              <li>
                <Link to="/operations" className="text-slate-300 hover:text-white hover:bg-slate-800 px-4 py-2 rounded-lg block transition-colors">
                  Operações
                </Link>
              </li>
              <li>
                <Link to="/shadow" className="text-slate-300 hover:text-white hover:bg-slate-800 px-4 py-2 rounded-lg block transition-colors">
                  Shadow Tests
                </Link>
              </li>
              <li>
                <Link to="/status" className="text-slate-300 hover:text-white hover:bg-slate-800 px-4 py-2 rounded-lg block transition-colors">
                  Status
                </Link>
              </li>
            </ul>
          </div>
          
          <div className="text-xs text-slate-600">
            v1.0.0 | Desenvolvido por Antigravity
          </div>
        </nav>

        {/* Main Content */}
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/operations" element={<Operations />} />
            <Route path="/shadow" element={<Shadow />} />
            <Route path="/status" element={<Status />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
