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
import { TrendingUp, TrendingDown, X, Loader2, AlertTriangle, RefreshCw, Layers, Trash2 } from 'lucide-react';

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
      toast.error('SYNC ERROR: ' + (error.response?.data?.detail || error.message));
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

  const formatQty = (qty) => {
    if (!qty) return '0';
    if (qty >= 1000) {
      return new Intl.NumberFormat('de-DE', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
      }).format(Math.round(qty));
    } else if (qty >= 1) {
      return new Intl.NumberFormat('de-DE', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      }).format(qty);
    } else {
      return new Intl.NumberFormat('de-DE', {
        minimumFractionDigits: 4,
        maximumFractionDigits: 6
      }).format(qty);
    }
  };

  const formatTradeDuration = (entryTime) => {
    if (!entryTime) return null;
    const entry = new Date(entryTime);
    const now = new Date();
    const diffMs = now - entry;
    const minutes = Math.floor(diffMs / 60000);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
    
    if (days > 0) return `${days}d ${hours % 24}h`;
    else if (hours > 0) return `${hours}h ${minutes % 60}m`;
    else return `${minutes}m`;
  };

  const formatEntryDate = (entryTime) => {
    if (!entryTime) return null;
    const entry = new Date(entryTime);
    return entry.toLocaleDateString('de-DE', { 
      day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'
    });
  };

  const handleSellClick = async (position) => {
    setSellDialog({ open: true, position, loading: true });
    
    try {
      const response = await axios.post(
        `${BACKEND_URL}/api/positions/sell`,
        { symbol: position.symbol, position_id: position.id, confirm: false },
        getAuthHeaders()
      );
      setConfirmData(response.data);
      setSellDialog(prev => ({ ...prev, loading: false }));
    } catch (error) {
      toast.error('FEHLER: ' + (error.response?.data?.detail || error.message));
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
      toast.success(`${response.data.message} PnL: ${response.data.pnl >= 0 ? '+' : ''}${response.data.pnl.toFixed(2)} USDT`);
      setSellDialog({ open: false, position: null, loading: false });
      setConfirmData(null);
      if (onSellComplete) onSellComplete();
    } catch (error) {
      toast.error('SELL FAILED: ' + (error.response?.data?.detail || error.message));
      setSellDialog(prev => ({ ...prev, loading: false }));
    }
  };

  if (!positions || positions.length === 0) {
    return (
      <div className="cyber-panel p-8 text-center mb-6">
        <Layers className="w-12 h-12 mx-auto text-zinc-700 mb-3" />
        <p className="text-zinc-600 font-mono-cyber">NO OPEN POSITIONS</p>
      </div>
    );
  }

  // Separate active positions from dust positions
  const activePositions = positions.filter(pos => !pos.is_dust);
  const dustPositions = positions.filter(pos => pos.is_dust);

  const totalCurrentValue = activePositions.reduce((sum, pos) => {
    return sum + (pos.current_price && pos.current_price > 0 ? pos.current_price * pos.qty : pos.entry_price * pos.qty);
  }, 0);
  const totalEntryValue = activePositions.reduce((sum, pos) => sum + (pos.entry_price * pos.qty), 0);
  const totalPnl = totalCurrentValue - totalEntryValue;
  const totalPnlPct = totalEntryValue > 0 ? (totalPnl / totalEntryValue) * 100 : 0;

  // Dust total value
  const dustTotalValue = dustPositions.reduce((sum, pos) => {
    return sum + (pos.current_price && pos.current_price > 0 ? pos.current_price * pos.qty : pos.entry_price * pos.qty);
  }, 0);

  return (
    <div className="space-y-4 mb-6" data-testid="positions-panel">
      {/* Header - Only count active positions */}
      <div className="cyber-panel p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 flex items-center justify-center bg-green-500/20 border border-green-500/50">
              <Layers className="w-6 h-6 text-green-400" />
            </div>
            <div>
              <h3 className="font-cyber text-lg text-green-400 tracking-widest uppercase">
                POSITIONS <span className="text-zinc-400">({activePositions.length})</span>
                {dustPositions.length > 0 && (
                  <span className="text-zinc-600 text-sm ml-2">+{dustPositions.length} Dust</span>
                )}
              </h3>
              <p className="text-base text-zinc-300 font-mono-cyber">
                Total: <span className="text-white text-lg">{totalCurrentValue.toFixed(2)} $</span>
                <span className={`ml-3 text-lg ${totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {totalPnl >= 0 ? '+' : ''}{totalPnl.toFixed(2)} $ ({totalPnl >= 0 ? '+' : ''}{totalPnlPct.toFixed(2)}%)
                </span>
              </p>
            </div>
          </div>
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={handleSyncWithMexc}
            disabled={syncing}
            className="text-zinc-400 hover:text-cyan-400 font-mono-cyber text-base"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${syncing ? 'animate-spin' : ''}`} />
            {syncing ? 'SYNC...' : 'MEXC SYNC'}
          </Button>
        </div>
      </div>
      
      {/* Active Position Cards */}
      {activePositions.map((pos, idx) => {
        const hasCurrentPrice = pos.current_price && pos.current_price > 0;
        const grossPnlAmount = hasCurrentPrice ? (pos.current_price - pos.entry_price) * pos.qty : null;
        const grossPnlPct = hasCurrentPrice ? ((pos.current_price - pos.entry_price) / pos.entry_price) * 100 : null;
        const buyFee = pos.entry_price * pos.qty * 0.001;
        const sellFee = hasCurrentPrice ? pos.current_price * pos.qty * 0.001 : 0;
        const totalFees = buyFee + sellFee;
        const netPnlAmount = hasCurrentPrice ? grossPnlAmount - totalFees : null;
        const netPnlPct = hasCurrentPrice ? ((netPnlAmount) / (pos.entry_price * pos.qty)) * 100 : null;
        const breakEvenPrice = pos.entry_price * 1.002;
        const aboveBreakEven = hasCurrentPrice && pos.current_price >= breakEvenPrice;
        const isNetProfit = netPnlAmount !== null && netPnlAmount >= 0;
        const currentValue = hasCurrentPrice ? pos.current_price * pos.qty : null;
        const entryValue = pos.entry_price * pos.qty;
        
        return (
          <div 
            key={pos.id || idx} 
            className={`cyber-panel p-5 ${isNetProfit ? 'border-green-500/30' : 'border-red-500/30'}`}
            data-testid={`position-${pos.symbol}`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                {/* Symbol & Side */}
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="font-cyber text-2xl text-white">{pos.symbol.replace('USDT', '')}</span>
                    <Badge className={`cyber-badge text-sm ${pos.side === 'LONG' ? 'bg-green-500/20 text-green-400 border border-green-500/50' : 'bg-red-500/20 text-red-400 border border-red-500/50'}`}>
                      {pos.side}
                    </Badge>
                    {pos.entry_time && (
                      <Badge className="cyber-badge text-sm bg-zinc-800 text-zinc-400 border border-zinc-700">
                        {formatTradeDuration(pos.entry_time)}
                      </Badge>
                    )}
                  </div>
                  <div className="text-base text-zinc-300 font-mono-cyber">
                    <span className="text-zinc-500">Qty:</span> {formatQty(pos.qty)} 
                    <span className="text-zinc-500 ml-3">Entry:</span> {formatCurrency(pos.entry_price)}
                    <span className="text-cyan-400 ml-3 font-cyber">= {entryValue.toFixed(2)} $</span>
                  </div>
                  {hasCurrentPrice && (
                    <div className="text-base font-mono-cyber mt-2">
                      <span className="text-zinc-500">Now: </span>
                      <span className={`text-lg ${pos.current_price >= pos.entry_price ? 'text-green-400' : 'text-red-400'}`}>
                        {formatCurrency(pos.current_price)}
                      </span>
                      <span className="text-zinc-500 ml-4">Value: </span>
                      <span className="text-lg text-white">{currentValue.toFixed(2)} $</span>
                    </div>
                  )}
                </div>
              </div>
              
              <div className="flex items-center gap-8">
                {/* PnL Display */}
                {netPnlAmount !== null && (
                  <div className="text-right">
                    <div className={`text-2xl font-cyber ${isNetProfit ? 'text-green-400 glow-green' : 'text-red-400'}`}>
                      {isNetProfit ? '+' : ''}{netPnlAmount.toFixed(2)} $
                    </div>
                    <div className={`text-base font-mono-cyber ${isNetProfit ? 'text-green-400' : 'text-red-400'}`}>
                      {isNetProfit ? '+' : ''}{netPnlPct.toFixed(2)}%
                      <span className="text-zinc-500 ml-2">(Fee: {totalFees.toFixed(3)}$)</span>
                    </div>
                  </div>
                )}
                
                {/* KI Exit - Kein festes TP mehr */}
                <div className="text-right">
                  <div className="text-sm text-zinc-400 font-mono-cyber mb-1">EXIT</div>
                  <div className="text-base font-mono-cyber">
                    <span className="text-cyan-400">🧠 KI</span>
                  </div>
                  <div className="text-xs text-zinc-600 font-mono-cyber">
                    Notfall: {pos.stop_loss?.toFixed(4)}
                  </div>
                </div>
                
                {/* Sell Button */}
                <Button
                  onClick={() => handleSellClick(pos)}
                  className="cyber-btn bg-red-500/20 border-red-500 text-red-400 hover:bg-red-500/30 px-6 py-3 text-base"
                  data-testid={`sell-btn-${pos.symbol}`}
                >
                  <X className="w-5 h-5 mr-2" />
                  SELL
                </Button>
              </div>
            </div>
          </div>
        );
      })}

      {/* DUST POSITIONS SECTION */}
      {dustPositions.length > 0 && (
        <div className="cyber-panel p-4 border-zinc-700/50 bg-zinc-900/30" data-testid="dust-positions">
          <div className="flex items-center gap-2 mb-3">
            <Trash2 className="w-4 h-4 text-zinc-500" />
            <h4 className="font-cyber text-sm text-zinc-500 tracking-widest uppercase">
              DUST / RESTBESTÄNDE ({dustPositions.length})
            </h4>
            <span className="text-xs text-zinc-600 font-mono-cyber ml-auto">
              ~{dustTotalValue.toFixed(4)} $
            </span>
          </div>
          
          <div className="space-y-2">
            {dustPositions.map((pos, idx) => {
              const value = pos.current_price > 0 ? pos.current_price * pos.qty : pos.entry_price * pos.qty;
              return (
                <div 
                  key={pos.id || `dust-${idx}`}
                  className="flex items-center justify-between py-2 px-3 bg-black/30 border border-zinc-800"
                  data-testid={`dust-${pos.symbol}`}
                >
                  <div className="flex items-center gap-3">
                    <span className="font-cyber text-zinc-400">{pos.symbol.replace('USDT', '')}</span>
                    <span className="text-xs text-zinc-600 font-mono-cyber">
                      {pos.qty?.toFixed(6)} Stk
                    </span>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-xs text-zinc-500 font-mono-cyber">
                      ~{value.toFixed(4)} $
                    </span>
                    <Badge className="cyber-badge text-xs bg-zinc-800 text-zinc-500 border border-zinc-700">
                      DUST
                    </Badge>
                  </div>
                </div>
              );
            })}
          </div>
          
          <p className="text-xs text-zinc-600 font-mono-cyber mt-3 italic">
            Diese Bestände sind zu klein zum Verkaufen (unter Min. Notional). Sie werden ignoriert.
          </p>
        </div>
      )}

      {/* Sell Confirmation Dialog */}
      <AlertDialog open={sellDialog.open} onOpenChange={(open) => !open && setSellDialog({ open: false, position: null, loading: false })}>
        <AlertDialogContent className="bg-[#0a0a0f] border border-cyan-500/30">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-cyber text-cyan-400 flex items-center gap-2 tracking-widest">
              <AlertTriangle className="w-5 h-5 text-yellow-400" />
              SELL POSITION?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-zinc-400 font-mono-cyber">
              {sellDialog.loading ? (
                <div className="flex items-center gap-2 py-4">
                  <Loader2 className="w-4 h-4 animate-spin text-cyan-400" />
                  LOADING DATA...
                </div>
              ) : confirmData?.position ? (
                <div className="space-y-3 py-2">
                  <div className="p-4 bg-black/50 border border-cyan-500/20 space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-zinc-500">SYMBOL</span>
                      <span className="font-cyber text-white">{confirmData.position.symbol}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-zinc-500">QTY</span>
                      <span className="font-mono-cyber text-white">{confirmData.position.qty}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-zinc-500">ENTRY</span>
                      <span className="font-mono-cyber text-white">{formatCurrency(confirmData.position.entry_price)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-zinc-500">CURRENT</span>
                      <span className="font-mono-cyber text-white">{formatCurrency(confirmData.position.current_price)}</span>
                    </div>
                    <hr className="border-cyan-500/20" />
                    <div className="flex justify-between text-lg">
                      <span className="text-zinc-400">P/L</span>
                      <span className={`font-cyber ${confirmData.position.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {confirmData.position.pnl >= 0 ? '+' : ''}{confirmData.position.pnl.toFixed(4)} USDT
                        <span className="text-sm ml-1">
                          ({confirmData.position.pnl_pct >= 0 ? '+' : ''}{confirmData.position.pnl_pct.toFixed(2)}%)
                        </span>
                      </span>
                    </div>
                  </div>
                  
                  <div className="p-3 bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 text-sm font-mono-cyber">
                    {confirmData.warning}
                  </div>
                  
                  {mode === 'live' && (
                    <div className="p-3 bg-red-500/10 border border-red-500/30 text-red-400 text-sm font-mono-cyber">
                      <AlertTriangle className="w-4 h-4 inline mr-2" />
                      LIVE MODE: REAL TRADE ON MEXC!
                    </div>
                  )}
                </div>
              ) : null}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="cyber-btn bg-zinc-900 border-zinc-700 text-zinc-400 hover:bg-zinc-800 hover:text-white">
              CANCEL
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmSell}
              disabled={sellDialog.loading}
              className="cyber-btn bg-red-500/20 border-red-500 text-red-400 hover:bg-red-500/30"
            >
              {sellDialog.loading && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
              CONFIRM SELL
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default PositionsPanel;
