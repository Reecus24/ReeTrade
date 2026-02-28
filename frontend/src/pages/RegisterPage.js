import React, { useState } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Lock } from 'lucide-react';
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
        toast.success('Registrierung erfolgreich!');
        onRegister();
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Registrierung fehlgeschlagen');
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
          <h1 className="text-2xl font-bold text-white mb-2">ReeTrade Terminal</h1>
          <p className="text-zinc-500 text-sm">Neues Konto erstellen</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-zinc-400 mb-2">
              Name
            </label>
            <Input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Dein Name"
              className="w-full bg-zinc-900 border-zinc-800 text-white placeholder:text-zinc-600"
              data-testid="register-name-input"
            />
          </div>

          <div>
            <label htmlFor="email" className="block text-sm font-medium text-zinc-400 mb-2">
              Email
            </label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="deine@email.com"
              className="w-full bg-zinc-900 border-zinc-800 text-white placeholder:text-zinc-600"
              data-testid="register-email-input"
              required
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-zinc-400 mb-2">
              Passwort
            </label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Mindestens 6 Zeichen"
              className="w-full bg-zinc-900 border-zinc-800 text-white placeholder:text-zinc-600"
              data-testid="register-password-input"
              required
            />
          </div>

          <Button
            type="submit"
            className="w-full bg-white text-black hover:bg-gray-200 font-medium"
            disabled={loading}
            data-testid="register-submit-button"
          >
            {loading ? 'Registrierung...' : 'Konto erstellen'}
          </Button>
        </form>

        <div className="mt-6 text-center">
          <button
            onClick={onSwitchToLogin}
            className="text-sm text-zinc-400 hover:text-white transition-colors"
            data-testid="switch-to-login-button"
          >
            Bereits registriert? Zum Login
          </button>
        </div>

        <div className="mt-6 text-center text-xs text-zinc-600">
          MEXC SPOT Trading Bot · Multi-User
        </div>
      </div>
    </div>
  );
};

export default RegisterPage;
