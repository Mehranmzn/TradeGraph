import React, { useState } from 'react'
import { motion } from 'framer-motion'
import {
  ChartBarIcon,
  BoltIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  CpuChipIcon,
} from '@heroicons/react/24/outline'
import { useQuery } from '@tanstack/react-query'

// Components
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { LoadingSkeleton } from '@/components/ui/LoadingSkeleton'
import { MarketOverview } from '@/components/dashboard/MarketOverview'
import { RecentAnalyses } from '@/components/dashboard/RecentAnalyses'
import { AlertsPanel } from '@/components/dashboard/AlertsPanel'
import { PerformanceChart } from '@/components/charts/PerformanceChart'
import { RecommendationsGrid } from '@/components/dashboard/RecommendationsGrid'

// Services
import { apiClient } from '@/services/api'

const quickStats = [
  {
    name: 'Active Analyses',
    value: '12',
    change: '+2.1%',
    changeType: 'increase' as const,
    icon: CpuChipIcon,
  },
  {
    name: 'Portfolio Value',
    value: '$124,750',
    change: '+5.4%',
    changeType: 'increase' as const,
    icon: ChartBarIcon,
  },
  {
    name: 'Success Rate',
    value: '87.3%',
    change: '+1.2%',
    changeType: 'increase' as const,
    icon: CheckCircleIcon,
  },
  {
    name: 'Active Alerts',
    value: '3',
    change: '-2',
    changeType: 'decrease' as const,
    icon: ExclamationTriangleIcon,
  },
]

const recentRecommendations = [
  {
    symbol: 'AAPL',
    company: 'Apple Inc.',
    recommendation: 'BUY',
    confidence: 0.87,
    targetPrice: 195.50,
    currentPrice: 182.31,
    change: 7.2,
    timestamp: '2 hours ago',
  },
  {
    symbol: 'MSFT',
    company: 'Microsoft Corporation',
    recommendation: 'STRONG_BUY',
    confidence: 0.92,
    targetPrice: 425.00,
    currentPrice: 398.12,
    change: 6.7,
    timestamp: '4 hours ago',
  },
  {
    symbol: 'GOOGL',
    company: 'Alphabet Inc.',
    recommendation: 'HOLD',
    confidence: 0.73,
    targetPrice: 145.00,
    currentPrice: 141.80,
    change: 2.3,
    timestamp: '6 hours ago',
  },
]

export function Dashboard() {
  const [timeRange, setTimeRange] = useState('7d')

  const { data: metrics, isLoading: metricsLoading } = useQuery({
    queryKey: ['metrics'],
    queryFn: () => apiClient.get('/analysis/metrics'),
    refetchInterval: 30000, // Refetch every 30 seconds
  })

  const { data: healthData, isLoading: healthLoading } = useQuery({
    queryKey: ['health'],
    queryFn: () => apiClient.get('/health/detailed'),
    refetchInterval: 10000, // Refetch every 10 seconds
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Dashboard
          </h1>
          <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
            Welcome back! Here's an overview of your financial analysis.
          </p>
        </div>

        <div className="mt-4 sm:mt-0 flex space-x-3">
          <Button
            variant="outline"
            onClick={() => window.location.reload()}
            className="flex items-center space-x-2"
          >
            <BoltIcon className="w-4 h-4" />
            <span>Refresh</span>
          </Button>
          <Button className="flex items-center space-x-2">
            <CpuChipIcon className="w-4 h-4" />
            <span>New Analysis</span>
          </Button>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {quickStats.map((stat, index) => (
          <motion.div
            key={stat.name}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: index * 0.1 }}
          >
            <Card className="p-6 hover:shadow-md transition-shadow">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
                    <stat.icon className="w-5 h-5 text-white" />
                  </div>
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 dark:text-gray-400 truncate">
                      {stat.name}
                    </dt>
                    <dd className="flex items-baseline">
                      <div className="text-2xl font-semibold text-gray-900 dark:text-white">
                        {stat.value}
                      </div>
                      <div className={`ml-2 flex items-baseline text-sm font-semibold ${
                        stat.changeType === 'increase'
                          ? 'text-green-600 dark:text-green-400'
                          : 'text-red-600 dark:text-red-400'
                      }`}>
                        {stat.changeType === 'increase' ? (
                          <ArrowTrendingUpIcon className="self-center flex-shrink-0 h-4 w-4 text-green-500" />
                        ) : (
                          <ArrowTrendingDownIcon className="self-center flex-shrink-0 h-4 w-4 text-red-500" />
                        )}
                        <span className="sr-only">
                          {stat.changeType === 'increase' ? 'Increased' : 'Decreased'} by
                        </span>
                        {stat.change}
                      </div>
                    </dd>
                  </dl>
                </div>
              </div>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left Column - Charts and Analysis */}
        <div className="lg:col-span-2 space-y-6">
          {/* Performance Chart */}
          <Card className="p-6">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-medium text-gray-900 dark:text-white">
                Portfolio Performance
              </h3>
              <div className="flex space-x-2">
                {['24h', '7d', '30d', '1y'].map((range) => (
                  <button
                    key={range}
                    onClick={() => setTimeRange(range)}
                    className={`px-3 py-1 text-sm rounded-md transition-colors ${
                      timeRange === range
                        ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
                        : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
                    }`}
                  >
                    {range}
                  </button>
                ))}
              </div>
            </div>
            <PerformanceChart timeRange={timeRange} />
          </Card>

          {/* Recent Recommendations */}
          <Card className="p-6">
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-6">
              Recent Recommendations
            </h3>
            <div className="space-y-4">
              {recentRecommendations.map((rec, index) => (
                <motion.div
                  key={rec.symbol}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.4, delay: index * 0.1 }}
                  className="flex items-center justify-between p-4 rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                >
                  <div className="flex items-center space-x-4">
                    <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center text-white font-semibold text-sm">
                      {rec.symbol.slice(0, 2)}
                    </div>
                    <div>
                      <div className="font-medium text-gray-900 dark:text-white">
                        {rec.symbol}
                      </div>
                      <div className="text-sm text-gray-500 dark:text-gray-400">
                        {rec.company}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-4">
                    <Badge
                      variant={
                        rec.recommendation === 'STRONG_BUY' ? 'success' :
                        rec.recommendation === 'BUY' ? 'success' :
                        rec.recommendation === 'HOLD' ? 'warning' : 'danger'
                      }
                    >
                      {rec.recommendation}
                    </Badge>

                    <div className="text-right">
                      <div className="font-medium text-gray-900 dark:text-white">
                        ${rec.currentPrice.toFixed(2)}
                      </div>
                      <div className="text-sm text-green-600 dark:text-green-400">
                        +{rec.change}%
                      </div>
                    </div>

                    <div className="text-right">
                      <div className="text-sm text-gray-500 dark:text-gray-400">
                        Confidence
                      </div>
                      <div className="font-medium text-gray-900 dark:text-white">
                        {(rec.confidence * 100).toFixed(0)}%
                      </div>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </Card>
        </div>

        {/* Right Column - Sidebar */}
        <div className="space-y-6">
          {/* Market Overview */}
          <MarketOverview />

          {/* Active Alerts */}
          <AlertsPanel />

          {/* Recent Analyses */}
          <RecentAnalyses />

          {/* System Health */}
          <Card className="p-6">
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4">
              System Health
            </h3>
            {healthLoading ? (
              <LoadingSkeleton className="h-20" />
            ) : (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    API Status
                  </span>
                  <div className="flex items-center space-x-2">
                    <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                    <span className="text-sm font-medium text-green-600 dark:text-green-400">
                      Operational
                    </span>
                  </div>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    Data Sources
                  </span>
                  <div className="flex items-center space-x-2">
                    <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                    <span className="text-sm font-medium text-green-600 dark:text-green-400">
                      Connected
                    </span>
                  </div>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    AI Agents
                  </span>
                  <div className="flex items-center space-x-2">
                    <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                    <span className="text-sm font-medium text-green-600 dark:text-green-400">
                      Active
                    </span>
                  </div>
                </div>

                {healthData?.data?.system_info && (
                  <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                    <div className="text-xs text-gray-500 dark:text-gray-400 space-y-1">
                      <div>CPU: {healthData.data.system_info.cpu_usage_percent}%</div>
                      <div>Memory: {healthData.data.system_info.memory.used_percent}%</div>
                      <div>Uptime: {Math.floor(healthData.data.uptime / 3600)}h</div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}