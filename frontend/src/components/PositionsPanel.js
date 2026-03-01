import React, { useState } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { toast } from 'sonner';
import { TrendingUp, TrendingDown, X, Loader2, AlertTriangle, RefreshCw } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

const PositionsPanel = ({ positions = [], mode = 'paper', onSellComplete }) => {
  const [sellDialog, setSellDialog] = useState({ open: false, position: null, loading: false });
  const [confirmData, setConfirmData] = useState(null);
  const [syncing, setSyncing] = useState(false);

  const getAuthHeaders = () => {
    const token = localStorage.getItem('auth_token');
    return { headers: { Authorization: `Bearer ${token}` } };
  };

  const handleSyncWithMexc = async () => {
    setSyncing(true);
    try {
      const response = await axios.post(
        `${BACKEND_URL}/api/positions/sync`,
        {},
        getAuthHeaders()
      );
      toast.success(response.data.message + ` (${response.data.open_positions} Positionen)`);
      if (onSellComplete) onSellComplete();
    } catch (error) {
      toast.error('Sync fehlgeschlagen: ' + (error.response?.data?.detail || error.message));
    } finally {
      setSyncing(false);
    }
  };

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('de-DE', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 6
    }).format(value || 0);
  };

  const handleSellClick = async (position) => {
    setSellDialog({ open: true, position, loading: true });
    
    try {
      // First call without confirm to get current price and PnL
      const response = await axios.post(
        `${BACKEND_URL}/api/positions/sell`,
        { symbol: position.symbol, position_id: position.id, confirm: false },
        getAuthHeaders()
      );
      
      setConfirmData(response.data);
      setSellDialog(prev => ({ ...prev, loading: false }));
    } catch (error) {
      toast.error('Fehler beim Laden der Position: ' + (error.response?.data?.detail || error.message));
      setSellDialog({ open: false, position: null, loading: false });
    }
  };

  const handleConfirmSell = async () => {
    if (!sellDialog.position) return;
    
    setSellDialog(prev => ({ ...prev, loading: true }));
    
    try {
      const response = await axios.post(
        `${BACKEND_URL}/api/positions/sell`,
        { symbol: sellDialog.position.symbol, position_id: sellDialog.position.id, confirm: true },
        getAuthHeaders()
      );
      
      toast.success(
        `${response.data.message} PnL: ${response.data.pnl >= 0 ? '+' : ''}${response.data.pnl.toFixed(2)} USDT (${response.data.pnl_pct >= 0 ? '+' : ''}${response.data.pnl_pct.toFixed(1)}%)`
      );
      
      setSellDialog({ open: false, position: null, loading: false });
      setConfirmData(null);
      
      // Trigger refresh
      if (onSellComplete) onSellComplete();
      
    } catch (error) {
      toast.error('Verkauf fehlgeschlagen: ' + (error.response?.data?.detail || error.message));
      setSellDialog(prev => ({ ...prev, loading: false }));
    }
  };

  if (!positions || positions.length === 0) {
    return (
      <div className="p-4 bg-zinc-900/50 rounded-lg text-center text-zinc-500">
        Keine offenen Positionen
      </div>
    );
  }

  return (
    <div className="space-y-2" data-testid="positions-panel">
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm font-medium text-zinc-400">
          Offene Positionen ({positions.length})
        </div>
        <Button 
          variant="ghost" 
          size="sm" 
          onClick={handleSyncWithMexc}
          disabled={syncing}
          className="text-xs text-zinc-500 hover:text-white"
          title="Mit MEXC synchronisieren (erkennt externe Verkäufe)"
        >
          <RefreshCw className={`w-3 h-3 mr-1 ${syncing ? 'animate-spin' : ''}`} />
          {syncing ? 'Sync...' : 'MEXC Sync'}
        </Button>
      </div>
      
      {positions.map((pos, idx) => {
        const hasCurrentPrice = pos.current_price && pos.current_price > 0;
        const pnlAmount = hasCurrentPrice 
          ? (pos.current_price - pos.entry_price) * pos.qty 
          : null;
        const pnlPct = hasCurrentPrice 
          ? ((pos.current_price - pos.entry_price) / pos.entry_price) * 100 
          : null;
        const isProfit = pnlAmount !== null && pnlAmount >= 0;
        
        return (
          <div 
            key={pos.id || idx} 
            className="p-3 bg-zinc-900 border border-zinc-800 rounded-lg"
            data-testid={`position-${pos.symbol}`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div>
                  <div className="font-bold text-white">{pos.symbol}</div>
                  <div className="text-xs text-zinc-500">
                    {pos.qty?.toLocaleString()} @ {formatCurrency(pos.entry_price)}
                  </div>
                </div>
                <Badge className={pos.side === 'LONG' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}>
                  {pos.side}
                </Badge>
              </div>
              
              <div className="flex items-center gap-4">
                {/* Live PnL Display */}
                {pnlAmount !== null && (
                  <div className="text-right min-w-[100px]">
                    <div className={`text-sm font-bold ${isProfit ? 'text-green-400' : 'text-red-400'}`}>
                      {isProfit ? '+' : ''}{pnlAmount.toFixed(4)} $
                    </div>
                    <div className={`text-xs ${isProfit ? 'text-green-500' : 'text-red-500'}`}>
                      {isProfit ? '+' : ''}{pnlPct.toFixed(2)}%
                    </div>
                  </div>
                )}
                
                <div className="text-right">
                  <div className="text-xs text-zinc-500">Stop / TP</div>
                  <div className="text-xs font-mono">
                    <span className="text-red-400">{pos.stop_loss?.toFixed(4)}</span>
                    {' / '}
                    <span className="text-green-400">{pos.take_profit?.toFixed(4)}</span>
                  </div>
                </div>
                
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => handleSellClick(pos)}
                  className="bg-red-600 hover:bg-red-700"
                  data-testid={`sell-btn-${pos.symbol}`}
                >
                  <X className="w-4 h-4 mr-1" />
                  Verkaufen
                </Button>
              </div>
            </div>
          </div>
        );
      })}

      {/* Sell Confirmation Dialog */}
      <AlertDialog open={sellDialog.open} onOpenChange={(open) => !open && setSellDialog({ open: false, position: null, loading: false })}>
        <AlertDialogContent className="bg-zinc-900 border-zinc-700">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-white flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-yellow-500" />
              Position verkaufen?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-zinc-400">
              {sellDialog.loading ? (
                <div className="flex items-center gap-2 py-4">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Lade aktuelle Daten...
                </div>
              ) : confirmData?.position ? (
                <div className="space-y-3 py-2">
                  <div className="p-3 bg-zinc-800 rounded-lg space-y-2">
                    <div className="flex justify-between">
                      <span>Symbol:</span>
                      <span className="font-bold text-white">{confirmData.position.symbol}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Menge:</span>
                      <span className="font-mono text-white">{confirmData.position.qty}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Einkaufspreis:</span>
                      <span className="font-mono text-white">{formatCurrency(confirmData.position.entry_price)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Aktueller Preis:</span>
                      <span className="font-mono text-white">{formatCurrency(confirmData.position.current_price)}</span>
                    </div>
                    <hr className="border-zinc-700" />
                    <div className="flex justify-between text-lg">
                      <span>Gewinn/Verlust:</span>
                      <span className={`font-bold ${confirmData.position.pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                        {confirmData.position.pnl >= 0 ? '+' : ''}{confirmData.position.pnl.toFixed(4)} USDT
                        <span className="text-sm ml-1">
                          ({confirmData.position.pnl_pct >= 0 ? '+' : ''}{confirmData.position.pnl_pct.toFixed(2)}%)
                        </span>
                      </span>
                    </div>
                  </div>
                  
                  <div className="p-3 bg-yellow-900/30 border border-yellow-700/50 rounded-lg text-yellow-400 text-sm">
                    {confirmData.warning}
                  </div>
                  
                  {mode === 'live' && (
                    <div className="p-3 bg-red-900/30 border border-red-700/50 rounded-lg text-red-400 text-sm font-medium">
                      ⚠️ LIVE MODE: Dies ist ein echter Verkauf auf MEXC!
                    </div>
                  )}
                </div>
              ) : null}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="bg-zinc-800 border-zinc-700 text-white hover:bg-zinc-700">
              Abbrechen
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmSell}
              disabled={sellDialog.loading}
              className="bg-red-600 hover:bg-red-700 text-white"
            >
              {sellDialog.loading ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : null}
              Ja, jetzt verkaufen
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default PositionsPanel;
