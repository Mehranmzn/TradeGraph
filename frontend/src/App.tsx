import React from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'

// Layout Components
import { Navbar } from '@/components/layout/Navbar'
import { Sidebar } from '@/components/layout/Sidebar'

// Pages
import { Dashboard } from '@/pages/Dashboard'
import { Analysis } from '@/pages/Analysis'
import { Portfolio } from '@/pages/Portfolio'
import { Alerts } from '@/pages/Alerts'
import { Settings } from '@/pages/Settings'
import { Landing } from '@/pages/Landing'

// Providers
import { WebSocketProvider } from '@/services/websocket'
import { AuthProvider } from '@/services/auth'

// Styles
import './styles/globals.css'

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: 2,
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <WebSocketProvider>
          <Router>
            <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
              <Routes>
                {/* Landing page */}
                <Route path="/" element={<Landing />} />

                {/* Main application */}
                <Route path="/app/*" element={<MainApp />} />
              </Routes>

              {/* Global toast notifications */}
              <Toaster
                position="top-right"
                toastOptions={{
                  duration: 4000,
                  className: 'bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 shadow-lg',
                }}
              />
            </div>
          </Router>
        </WebSocketProvider>
      </AuthProvider>
    </QueryClientProvider>
  )
}

function MainApp() {
  const [sidebarOpen, setSidebarOpen] = React.useState(false)

  return (
    <>
      {/* Mobile sidebar */}
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Static sidebar for desktop */}
      <div className="hidden lg:fixed lg:inset-y-0 lg:flex lg:w-64 lg:flex-col">
        <Sidebar open={true} onClose={() => {}} />
      </div>

      {/* Main content */}
      <div className="flex flex-1 flex-col lg:pl-64">
        <Navbar onMenuClick={() => setSidebarOpen(true)} />

        <main className="flex-1">
          <div className="py-6">
            <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
              <Routes>
                <Route index element={<Dashboard />} />
                <Route path="analysis/*" element={<Analysis />} />
                <Route path="portfolio" element={<Portfolio />} />
                <Route path="alerts" element={<Alerts />} />
                <Route path="settings" element={<Settings />} />
              </Routes>
            </div>
          </div>
        </main>
      </div>
    </>
  )
}

export default App