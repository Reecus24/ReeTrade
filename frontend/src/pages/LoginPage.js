import React, { useState } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Lock } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const LoginPage = ({ onLogin }) => {
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const response = await axios.post(`${BACKEND_URL}/api/auth/login`, {
        password
      });

      if (response.data.token) {
        localStorage.setItem('auth_token', response.data.token);
        toast.success('Login erfolgreich');
        onLogin();
      }
    } catch (error) {
      toast.error('Falsches Passwort');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-black">
      <div className="w-full max-w-md p-8 bg-zinc-950 border border-zinc-800 rounded-lg">
        <div className="flex flex-col items-center mb-8">
          <div className="w-16 h-16 bg-white/5 rounded-full flex items-center justify-center mb-4">
            <Lock className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white mb-2">AlgoTrade Terminal</h1>
          <p className="text-zinc-500 text-sm">Zugang nur für autorisierte Nutzer</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-zinc-400 mb-2">
              Passwort
            </label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Passwort eingeben"
              className="w-full bg-zinc-900 border-zinc-800 text-white placeholder:text-zinc-600"
              data-testid="login-password-input"
              required
            />
          </div>

          <Button
            type="submit"
            className="w-full bg-white text-black hover:bg-gray-200 font-medium"
            disabled={loading}
            data-testid="login-submit-button"
          >
            {loading ? 'Anmeldung...' : 'Anmelden'}
          </Button>
        </form>

        <div className="mt-6 text-center text-xs text-zinc-600">
          MEXC SPOT Trading Bot · Paper & Live Mode
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
