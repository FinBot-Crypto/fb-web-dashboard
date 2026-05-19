import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Operations from './pages/Operations';
import Shadow from './pages/Shadow';
import Status from './pages/Status';

function App() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const toggleSidebar = () => setIsSidebarOpen(!isSidebarOpen);
  const closeSidebar = () => setIsSidebarOpen(false);

  return (
    <Router>
      <div className="flex min-h-screen bg-dark">
        {/* Header Mobile com Hambúrguer */}
        <header className="md:hidden bg-slate-900 border-b border-slate-800 p-4 flex justify-between items-center fixed top-0 left-0 right-0 z-20">
          <div className="text-white font-bold text-xl flex items-center gap-2">
            <span className="text-accentGreen">🤖</span> Crypto Bot
          </div>
          <button 
            onClick={toggleSidebar} 
            className="text-white focus:outline-none p-2 bg-slate-800 rounded-lg"
            aria-label="Alternar Menu"
          >
            {isSidebarOpen ? (
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            )}
          </button>
        </header>

        {/* Sidebar */}
        <nav className={`w-64 bg-slate-900 border-r border-slate-800 p-6 flex flex-col justify-between fixed md:relative h-screen z-10 transition-transform duration-300 ease-in-out ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full'} md:translate-x-0`}>
          <div>
            <div className="text-white font-bold text-xl mb-8 hidden md:flex items-center gap-2">
              <span className="text-accentGreen">🤖</span> Crypto Bot
            </div>
            <ul className="space-y-2 mt-12 md:mt-0">
              <li>
                <Link to="/" onClick={closeSidebar} className="text-slate-300 hover:text-white hover:bg-slate-800 px-4 py-2 rounded-lg block transition-colors">
                  Dashboard
                </Link>
              </li>
              <li>
                <Link to="/operations" onClick={closeSidebar} className="text-slate-300 hover:text-white hover:bg-slate-800 px-4 py-2 rounded-lg block transition-colors">
                  Operações
                </Link>
              </li>
              <li>
                <Link to="/shadow" onClick={closeSidebar} className="text-slate-300 hover:text-white hover:bg-slate-800 px-4 py-2 rounded-lg block transition-colors">
                  Shadow Tests
                </Link>
              </li>
              <li>
                <Link to="/status" onClick={closeSidebar} className="text-slate-300 hover:text-white hover:bg-slate-800 px-4 py-2 rounded-lg block transition-colors">
                  Status
                </Link>
              </li>
            </ul>
          </div>
          
          <div className="text-xs text-slate-600">
            v1.0.0 | Desenvolvido por Antigravity
          </div>
        </nav>

        {/* Overlay para fechar o menu mobile ao clicar fora */}
        {isSidebarOpen && (
          <div 
            className="fixed inset-0 bg-black bg-opacity-50 z-0 md:hidden" 
            onClick={closeSidebar}
          ></div>
        )}

        {/* Main Content */}
        <main className="flex-1 overflow-y-auto mt-16 md:mt-0 p-4 md:p-6">
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
