import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import OverviewTab from '@/components/OverviewTab';
import StrategieTab from '@/components/StrategieTab';
import BacktestTab from '@/components/BacktestTab';
import LogsTab from '@/components/LogsTab';
import SettingsTab from '@/components/SettingsTab';
import { Activity, TrendingUp, FileText, Settings2, Settings } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return {
    headers: {
      Authorization: `Bearer ${token}`
    }
  };
};

const DashboardPage = ({ onLogout }) => {
  const [status, setStatus] = useState(null);
  const [logs, setLogs] = useState([]);
  const [activeTab, setActiveTab] = useState('overview');
  const userEmail = localStorage.getItem('user_email') || 'User';

  const fetchStatus = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/status`, getAuthHeaders());
      setStatus(response.data);
    } catch (error) {
      if (error.response?.status === 401) {
        toast.error('Session abgelaufen');
        onLogout();
      }
    }
  };

  const fetchLogs = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/logs?limit=100`, getAuthHeaders());
      setLogs(response.data.logs || []);
    } catch (error) {
      console.error('Logs fetch error:', error);
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchLogs();

    const interval = setInterval(() => {
      fetchStatus();
      fetchLogs();
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-black text-white">
      <header className="border-b border-zinc-900 bg-black/50 backdrop-blur-md sticky top-0 z-50">
        <div className="container mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-white/5 rounded-full flex items-center justify-center">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold">ReeTrade Terminal</h1>
              <p className="text-xs text-zinc-500">Multi-User MEXC Bot</p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <span className="text-sm text-zinc-400">{userEmail}</span>
            <button
              onClick={onLogout}
              className="text-sm text-zinc-400 hover:text-white transition-colors"
              data-testid="logout-button"
            >
              Abmelden
            </button>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-6 py-8">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-5 bg-zinc-950 border border-zinc-800" data-testid="dashboard-tabs">
            <TabsTrigger value="overview" className="data-[state=active]:bg-zinc-800 data-[state=active]:text-white" data-testid="tab-overview">
              <Activity className="w-4 h-4 mr-2" />
              Overview
            </TabsTrigger>
            <TabsTrigger value="strategie" className="data-[state=active]:bg-zinc-800 data-[state=active]:text-white" data-testid="tab-strategie">
              <Settings2 className="w-4 h-4 mr-2" />
              Strategie
            </TabsTrigger>
            <TabsTrigger value="settings" className="data-[state=active]:bg-zinc-800 data-[state=active]:text-white" data-testid="tab-settings">
              <Settings className="w-4 h-4 mr-2" />
              Settings
            </TabsTrigger>
            <TabsTrigger value="backtest" className="data-[state=active]:bg-zinc-800 data-[state=active]:text-white" data-testid="tab-backtest">
              <TrendingUp className="w-4 h-4 mr-2" />
              Backtest
            </TabsTrigger>
            <TabsTrigger value="logs" className="data-[state=active]:bg-zinc-800 data-[state=active]:text-white" data-testid="tab-logs">
              <FileText className="w-4 h-4 mr-2" />
              Logs
            </TabsTrigger>
          </TabsList>

          <div className="mt-6">
            <TabsContent value="overview" className="mt-0">
              <OverviewTab status={status} onRefresh={fetchStatus} />
            </TabsContent>

            <TabsContent value="strategie" className="mt-0">
              <StrategieTab status={status} />
            </TabsContent>

            <TabsContent value="settings" className="mt-0">
              <SettingsTab />
            </TabsContent>

            <TabsContent value="backtest" className="mt-0">
              <BacktestTab />
            </TabsContent>

            <TabsContent value="logs" className="mt-0">
              <LogsTab logs={logs} />
            </TabsContent>
          </div>
        </Tabs>
      </div>
    </div>
  );
};

export default DashboardPage;
