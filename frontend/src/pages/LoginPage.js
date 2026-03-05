import React, { useState } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Zap, Lock, ChevronRight } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const LoginPage = ({ onLogin, onSwitchToRegister }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const response = await axios.post(`${BACKEND_URL}/api/auth/login`, {
        email,
        password
      });

      if (response.data.token) {
        localStorage.setItem('auth_token', response.data.token);
        localStorage.setItem('user_email', email);
        toast.success('ZUGANG GEWÄHRT');
        onLogin();
      }
    } catch (error) {
      toast.error('ZUGANG VERWEIGERT');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#050508] cyber-grid relative overflow-hidden">
      {/* Scanlines */}
      <div className="fixed inset-0 pointer-events-none scanlines z-50 opacity-20" />
      
      {/* Decorative Grid Lines */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-px h-full bg-gradient-to-b from-transparent via-cyan-500/20 to-transparent" />
        <div className="absolute top-0 right-1/4 w-px h-full bg-gradient-to-b from-transparent via-cyan-500/20 to-transparent" />
        <div className="absolute top-1/4 left-0 w-full h-px bg-gradient-to-r from-transparent via-cyan-500/20 to-transparent" />
        <div className="absolute bottom-1/4 left-0 w-full h-px bg-gradient-to-r from-transparent via-cyan-500/20 to-transparent" />
      </div>
      
      <div className="relative z-10 w-full max-w-md p-8">
        {/* Header */}
        <div className="flex flex-col items-center mb-10">
          <div className="w-20 h-20 border-2 border-cyan-500/50 flex items-center justify-center mb-6 bg-cyan-500/10 box-glow-cyan">
            <Zap className="w-10 h-10 text-cyan-400" />
          </div>
          <h1 className="font-cyber text-3xl text-white tracking-wider mb-2">
            REE<span className="text-cyan-400 glow-cyan">TRADE</span>
          </h1>
          <p className="text-xs text-zinc-600 font-mono-cyber tracking-widest">
            NEURAL TRADING TERMINAL
          </p>
        </div>

        {/* Login Form */}
        <div className="cyber-panel p-8 box-glow-cyan">
          <div className="flex items-center gap-2 mb-6 pb-4 border-b border-cyan-500/20">
            <Lock className="w-4 h-4 text-cyan-400" />
            <span className="font-cyber text-xs text-cyan-400 tracking-widest uppercase">Secure Access</span>
          </div>
          
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-xs font-mono-cyber text-zinc-500 mb-2 tracking-wider">
                EMAIL ADDRESS
              </label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="operator@reetrade.io"
                className="cyber-input w-full"
                data-testid="login-email-input"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-mono-cyber text-zinc-500 mb-2 tracking-wider">
                ACCESS CODE
              </label>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="cyber-input w-full"
                data-testid="login-password-input"
                required
              />
            </div>

            <Button
              type="submit"
              className="w-full cyber-btn mt-6 py-4"
              disabled={loading}
              data-testid="login-submit-button"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-cyan-400/30 border-t-cyan-400 rounded-full animate-spin" />
                  AUTHENTICATING...
                </span>
              ) : (
                <span className="flex items-center justify-center gap-2">
                  CONNECT
                  <ChevronRight className="w-4 h-4" />
                </span>
              )}
            </Button>
          </form>
        </div>

        {/* Register Link */}
        <div className="mt-8 text-center">
          <button
            onClick={onSwitchToRegister}
            className="text-xs font-mono-cyber text-zinc-600 hover:text-cyan-400 transition-colors tracking-wider"
            data-testid="switch-to-register-button"
          >
            NEW OPERATOR? <span className="text-cyan-400">REGISTER HERE</span>
          </button>
        </div>

        {/* Footer */}
        <div className="mt-8 text-center">
          <p className="text-[10px] text-zinc-700 font-mono-cyber tracking-widest">
            MEXC SPOT · REINFORCEMENT LEARNING · v2.0
          </p>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
