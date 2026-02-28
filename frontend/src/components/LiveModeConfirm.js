import React, { useState } from 'react';
import axios from 'axios';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { AlertTriangle } from 'lucide-react';
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

const LiveModeConfirm = ({ open, onClose, onConfirm }) => {
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(1); // 1: request, 2: confirm

  const handleRequest = async () => {
    setLoading(true);
    try {
      await axios.post(`${BACKEND_URL}/api/bot/live/request`, {}, getAuthHeaders());
      setStep(2);
      toast.success('Live Mode angefordert');
    } catch (error) {
      toast.error('Fehler: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async () => {
    if (!password) {
      toast.error('Bitte Passwort eingeben');
      return;
    }

    setLoading(true);
    try {
      await axios.post(
        `${BACKEND_URL}/api/bot/live/confirm`,
        { password },
        getAuthHeaders()
      );
      toast.success('LIVE MODE AKTIVIERT!', {
        duration: 5000,
        className: 'bg-red-500 text-white'
      });
      setPassword('');
      setStep(1);
      onConfirm();
      onClose();
    } catch (error) {
      toast.error('Fehler: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setPassword('');
    setStep(1);
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="bg-zinc-950 border-red-900 border-2" data-testid="live-mode-dialog">
        <DialogHeader>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-12 h-12 bg-red-500/10 rounded-full flex items-center justify-center">
              <AlertTriangle className="w-6 h-6 text-red-500 animate-pulse" />
            </div>
            <DialogTitle className="text-xl text-white">WARNUNG: Live Trading</DialogTitle>
          </div>
          <DialogDescription className="text-zinc-400 leading-relaxed">
            {step === 1 ? (
              <>
                Du bist dabei, den Bot in den <strong className="text-red-500">LIVE MODUS</strong> zu schalten.
                Dies bedeutet, dass echte Orders an MEXC gesendet werden und echtes Geld riskiert wird.
              </>
            ) : (
              <>
                Bestätige den Live Modus mit deinem Admin-Passwort.
                <strong className="text-red-500"> Diese Aktion kann nicht rückgängig gemacht werden!</strong>
              </>
            )}
          </DialogDescription>
        </DialogHeader>

        {step === 1 && (
          <div className="space-y-4 py-4">
            <div className="bg-red-500/10 border border-red-500/20 rounded p-4 space-y-2 text-sm">
              <p className="text-red-500 font-semibold">⚠️ Bitte beachten:</p>
              <ul className="list-disc list-inside space-y-1 text-zinc-300">
                <li>MEXC API Keys müssen konfiguriert sein</li>
                <li>Du handelst mit echtem Geld</li>
                <li>Verluste sind möglich</li>
                <li>Keine Gewinn-Garantie</li>
                <li>Bot stoppt bei max. Daily Loss</li>
              </ul>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="confirm-password" className="text-zinc-400">
                Admin-Passwort zur Bestätigung
              </Label>
              <Input
                id="confirm-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Passwort eingeben"
                className="mt-2 bg-zinc-900 border-zinc-800 text-white"
                data-testid="live-confirm-password"
                autoFocus
              />
            </div>
          </div>
        )}

        <DialogFooter className="gap-2">
          <Button
            onClick={handleClose}
            variant="outline"
            className="bg-zinc-900 border-zinc-800 hover:bg-zinc-800 text-white"
            data-testid="live-cancel-button"
          >
            Abbrechen
          </Button>
          {step === 1 ? (
            <Button
              onClick={handleRequest}
              disabled={loading}
              className="bg-red-900/20 text-red-500 border border-red-900/50 hover:bg-red-900/40"
              data-testid="live-request-button"
            >
              Weiter zur Bestätigung
            </Button>
          ) : (
            <Button
              onClick={handleConfirm}
              disabled={loading || !password}
              className="bg-red-600 text-white hover:bg-red-700 font-bold"
              data-testid="live-final-confirm-button"
            >
              {loading ? 'Bestätige...' : 'LIVE MODUS AKTIVIEREN'}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default LiveModeConfirm;
