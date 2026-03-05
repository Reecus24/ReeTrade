import React, { useState } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Zap, UserPlus, ChevronRight } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const RegisterPage = ({ onRegister, onSwitchToLogin }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const response = await axios.post(`${BACKEND_URL}/api/auth/register`, {
        email,
        password
      });

      if (response.data.token) {
        localStorage.setItem('auth_token', response.data.token);
        localStorage.setItem('user_email', email);
        localStorage.setItem('user_name', name || email.split('@')[0]);
        toast.success('OPERATOR REGISTRIERT');
        onRegister();
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'REGISTRIERUNG FEHLGESCHLAGEN');
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
        <div className="absolute top-0 left-1/4 w-px h-full bg-gradient-to-b from-transparent via-magenta-500/20 to-transparent" style={{background: 'linear-gradient(to bottom, transparent, rgba(255,0,255,0.2), transparent)'}} />
        <div className="absolute top-0 right-1/4 w-px h-full bg-gradient-to-b from-transparent via-magenta-500/20 to-transparent" style={{background: 'linear-gradient(to bottom, transparent, rgba(255,0,255,0.2), transparent)'}} />
        <div className="absolute top-1/4 left-0 w-full h-px bg-gradient-to-r from-transparent via-magenta-500/20 to-transparent" style={{background: 'linear-gradient(to right, transparent, rgba(255,0,255,0.2), transparent)'}} />
        <div className="absolute bottom-1/4 left-0 w-full h-px bg-gradient-to-r from-transparent via-magenta-500/20 to-transparent" style={{background: 'linear-gradient(to right, transparent, rgba(255,0,255,0.2), transparent)'}} />
      </div>
      
      <div className="relative z-10 w-full max-w-md p-8">
        {/* Header */}
        <div className="flex flex-col items-center mb-10">
          <div className="w-20 h-20 border-2 border-[#ff00ff]/50 flex items-center justify-center mb-6 bg-[#ff00ff]/10" style={{boxShadow: '0 0 20px rgba(255,0,255,0.3)'}}>
            <Zap className="w-10 h-10 text-[#ff00ff]" />
          </div>
          <h1 className="font-cyber text-3xl text-white tracking-wider mb-2">
            REE<span className="text-[#ff00ff]" style={{textShadow: '0 0 10px #ff00ff'}}>TRADE</span>
          </h1>
          <p className="text-xs text-zinc-600 font-mono-cyber tracking-widest">
            NEW OPERATOR REGISTRATION
          </p>
        </div>

        {/* Register Form */}
        <div className="cyber-panel p-8" style={{boxShadow: '0 0 20px rgba(255,0,255,0.2)', borderColor: 'rgba(255,0,255,0.3)'}}>
          <div className="flex items-center gap-2 mb-6 pb-4 border-b border-[#ff00ff]/20">
            <UserPlus className="w-4 h-4 text-[#ff00ff]" />
            <span className="font-cyber text-xs text-[#ff00ff] tracking-widest uppercase">Create Account</span>
          </div>
          
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-xs font-mono-cyber text-zinc-500 mb-2 tracking-wider">
                OPERATOR NAME
              </label>
              <Input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Ghost_Runner"
                className="cyber-input w-full"
                data-testid="register-name-input"
              />
            </div>

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
                data-testid="register-email-input"
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
                data-testid="register-password-input"
                required
              />
              <p className="text-[10px] text-zinc-600 mt-1 font-mono-cyber">MIN 6 CHARACTERS</p>
            </div>

            <Button
              type="submit"
              className="w-full py-4 font-cyber text-sm tracking-widest uppercase border border-[#ff00ff] bg-transparent text-[#ff00ff] hover:bg-[#ff00ff]/10 transition-all"
              disabled={loading}
              data-testid="register-submit-button"
              style={{boxShadow: '0 0 15px rgba(255,0,255,0.2)'}}
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-[#ff00ff]/30 border-t-[#ff00ff] rounded-full animate-spin" />
                  PROCESSING...
                </span>
              ) : (
                <span className="flex items-center justify-center gap-2">
                  INITIALIZE ACCOUNT
                  <ChevronRight className="w-4 h-4" />
                </span>
              )}
            </Button>
          </form>
        </div>

        {/* Login Link */}
        <div className="mt-8 text-center">
          <button
            onClick={onSwitchToLogin}
            className="text-xs font-mono-cyber text-zinc-600 hover:text-[#ff00ff] transition-colors tracking-wider"
            data-testid="switch-to-login-button"
          >
            EXISTING OPERATOR? <span className="text-[#ff00ff]">LOGIN HERE</span>
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

export default RegisterPage;
