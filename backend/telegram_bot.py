"""
Telegram Bot Integration für ReeTrade Terminal
===============================================
- Automatische Benachrichtigungen bei Trades
- Befehle für Status, Profit, Balance
- Tägliche Zusammenfassungen
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
import httpx

logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram Bot für ReeTrade Benachrichtigungen"""
    
    def __init__(self, token: str, db=None):
        self.token = token
        self.db = db
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.commands_registered = False
    
    async def send_message(self, chat_id: int, text: str, parse_mode: str = "HTML") -> bool:
        """Sende eine Nachricht an einen Chat"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": parse_mode,
                        "disable_web_page_preview": True
                    }
                )
                
                if response.status_code == 200:
                    return True
                else:
                    logger.error(f"Telegram send error: {response.text}")
                    return False
        except Exception as e:
            logger.error(f"Telegram send exception: {e}")
            return False
    
    async def register_commands(self):
        """Registriere Bot-Befehle bei Telegram"""
        if self.commands_registered:
            return
        
        commands = [
            {"command": "start", "description": "Bot starten"},
            {"command": "status", "description": "Aktuelle offene Positionen"},
            {"command": "profit", "description": "Heutiger Profit"},
            {"command": "profit_week", "description": "Wochenprofit"},
            {"command": "profit_month", "description": "Monatsprofit"},
            {"command": "balance", "description": "Wallet-Stand"},
            {"command": "trades", "description": "Letzte 5 Trades"},
            {"command": "ki", "description": "KI Status & Lernfortschritt"},
            {"command": "stop", "description": "Bot pausieren"},
            {"command": "resume", "description": "Bot fortsetzen"},
            {"command": "help", "description": "Hilfe anzeigen"}
        ]
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"{self.base_url}/setMyCommands",
                    json={"commands": commands}
                )
            self.commands_registered = True
            logger.info("Telegram commands registered")
        except Exception as e:
            logger.error(f"Failed to register commands: {e}")
    
    async def get_updates(self, offset: int = 0) -> List[Dict]:
        """Hole neue Nachrichten (für Polling)"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.base_url}/getUpdates",
                    params={"offset": offset, "timeout": 25}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("result", [])
                return []
        except Exception as e:
            logger.error(f"Telegram getUpdates error: {e}")
            return []
    
    # ============ BENACHRICHTIGUNGEN ============
    
    async def notify_trade_opened(self, chat_id: int, trade: Dict):
        """Benachrichtigung: Trade geöffnet"""
        text = f"""
🟢 <b>TRADE GEÖFFNET</b>

<b>Symbol:</b> {trade.get('symbol', '?')}
<b>Typ:</b> {trade.get('side', 'BUY')}
<b>Menge:</b> {trade.get('quantity', 0):.4f}
<b>Preis:</b> ${trade.get('entry_price', 0):.6f}
<b>Wert:</b> ${trade.get('value', 0):.2f}

<b>Stop-Loss:</b> ${trade.get('stop_loss', 0):.6f}
<b>Take-Profit:</b> ${trade.get('take_profit', 0):.6f}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
        await self.send_message(chat_id, text)
    
    async def notify_trade_closed(self, chat_id: int, trade: Dict):
        """Benachrichtigung: Trade geschlossen"""
        pnl = trade.get('pnl', 0)
        pnl_pct = trade.get('pnl_pct', 0)
        emoji = "🟢" if pnl >= 0 else "🔴"
        
        text = f"""
{emoji} <b>TRADE GESCHLOSSEN</b>

<b>Symbol:</b> {trade.get('symbol', '?')}
<b>Exit-Grund:</b> {trade.get('exit_reason', 'Manual')}

<b>Entry:</b> ${trade.get('entry_price', 0):.6f}
<b>Exit:</b> ${trade.get('exit_price', 0):.6f}

<b>PnL:</b> {'+' if pnl >= 0 else ''}{pnl_pct:.2f}% (${pnl:.2f})
<b>Dauer:</b> {trade.get('duration', '?')}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
        await self.send_message(chat_id, text)
    
    async def notify_smart_exit(self, chat_id: int, decision: Dict):
        """Benachrichtigung: KI Smart Exit Entscheidung"""
        text = f"""
🧠 <b>KI SMART EXIT</b>

<b>Symbol:</b> {decision.get('symbol', '?')}
<b>Exit-Typ:</b> {decision.get('exit_type', '?')}
<b>Confidence:</b> {decision.get('confidence', 0):.0f}%

<b>Gründe:</b>
"""
        for reason in decision.get('reasons', [])[:3]:
            text += f"• {reason}\n"
        
        text += f"\n⏰ {datetime.now().strftime('%H:%M:%S')}"
        await self.send_message(chat_id, text)
    
    async def notify_stop_loss(self, chat_id: int, trade: Dict):
        """Benachrichtigung: Stop-Loss ausgelöst"""
        text = f"""
🛑 <b>STOP-LOSS AUSGELÖST</b>

<b>Symbol:</b> {trade.get('symbol', '?')}
<b>Verlust:</b> {trade.get('pnl_pct', 0):.2f}% (${trade.get('pnl', 0):.2f})

<b>Entry:</b> ${trade.get('entry_price', 0):.6f}
<b>Exit:</b> ${trade.get('exit_price', 0):.6f}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
        await self.send_message(chat_id, text)
    
    async def notify_take_profit(self, chat_id: int, trade: Dict):
        """Benachrichtigung: Take-Profit erreicht"""
        text = f"""
🎯 <b>TAKE-PROFIT ERREICHT!</b>

<b>Symbol:</b> {trade.get('symbol', '?')}
<b>Gewinn:</b> +{trade.get('pnl_pct', 0):.2f}% (${trade.get('pnl', 0):.2f})

<b>Entry:</b> ${trade.get('entry_price', 0):.6f}
<b>Exit:</b> ${trade.get('exit_price', 0):.6f}

🎉 Gut gemacht!
⏰ {datetime.now().strftime('%H:%M:%S')}
"""
        await self.send_message(chat_id, text)
    
    async def send_daily_summary(self, chat_id: int, summary: Dict):
        """Tägliche Zusammenfassung senden"""
        total_pnl = summary.get('total_pnl', 0)
        emoji = "📈" if total_pnl >= 0 else "📉"
        
        text = f"""
{emoji} <b>TÄGLICHE ZUSAMMENFASSUNG</b>
{datetime.now().strftime('%d.%m.%Y')}

<b>Trades heute:</b> {summary.get('trade_count', 0)}
<b>Gewinner:</b> {summary.get('winners', 0)} ✅
<b>Verlierer:</b> {summary.get('losers', 0)} ❌
<b>Win-Rate:</b> {summary.get('win_rate', 0):.1f}%

<b>Tages-PnL:</b> {'+' if total_pnl >= 0 else ''}{summary.get('total_pnl_pct', 0):.2f}%
<b>Absolut:</b> ${total_pnl:.2f}

<b>Bester Trade:</b> {summary.get('best_trade', 'Keiner')}
<b>Schlechtester:</b> {summary.get('worst_trade', 'Keiner')}

<b>Portfolio:</b> ${summary.get('balance', 0):.2f}

🤖 ReeTrade Terminal
"""
        await self.send_message(chat_id, text)
    
    # ============ BEFEHLE HANDLER ============
    
    async def handle_command(self, chat_id: int, command: str, user_id: str) -> str:
        """Verarbeite einen Befehl und gib Antwort zurück"""
        
        if command == "/start" or command == "/help":
            return self._get_help_text()
        
        elif command == "/status":
            return await self._get_status(user_id)
        
        elif command == "/profit":
            return await self._get_profit(user_id, "today")
        
        elif command == "/profit_week":
            return await self._get_profit(user_id, "week")
        
        elif command == "/profit_month":
            return await self._get_profit(user_id, "month")
        
        elif command == "/balance":
            return await self._get_balance(user_id)
        
        elif command == "/trades":
            return await self._get_recent_trades(user_id)
        
        elif command == "/ki":
            return await self._get_ki_status(user_id)
        
        elif command == "/stop":
            return await self._pause_bot(user_id)
        
        elif command == "/resume":
            return await self._resume_bot(user_id)
        
        else:
            return "❓ Unbekannter Befehl. Tippe /help für alle Befehle."
    
    def _get_help_text(self) -> str:
        return """
🤖 <b>ReeTrade Terminal Bot</b>

<b>Verfügbare Befehle:</b>

📊 <b>Status & Info</b>
/status - Offene Positionen
/balance - Wallet-Stand
/ki - KI Status & Lernfortschritt

💰 <b>Profit</b>
/profit - Heutiger Profit
/profit_week - Wochenprofit
/profit_month - Monatsprofit

📜 <b>Historie</b>
/trades - Letzte 5 Trades

⚙️ <b>Steuerung</b>
/stop - Bot pausieren
/resume - Bot fortsetzen

/help - Diese Hilfe
"""
    
    async def _get_status(self, user_id: str) -> str:
        """Hole aktuelle offene Positionen"""
        if not self.db:
            return "❌ Datenbank nicht verfügbar"
        
        try:
            account = await self.db.get_live_account(user_id)
            if not account or not account.positions:
                return "📭 Keine offenen Positionen"
            
            text = f"📊 <b>OFFENE POSITIONEN</b> ({len(account.positions)})\n\n"
            
            for pos in account.positions[:10]:
                pnl_pct = ((pos.current_price - pos.entry_price) / pos.entry_price * 100) if hasattr(pos, 'current_price') else 0
                emoji = "🟢" if pnl_pct >= 0 else "🔴"
                text += f"{emoji} <b>{pos.symbol}</b>\n"
                text += f"   Entry: ${pos.entry_price:.6f}\n"
                text += f"   PnL: {'+' if pnl_pct >= 0 else ''}{pnl_pct:.2f}%\n\n"
            
            return text
        except Exception as e:
            logger.error(f"Status error: {e}")
            return f"❌ Fehler: {str(e)[:50]}"
    
    async def _get_profit(self, user_id: str, period: str) -> str:
        """Hole Profit für einen Zeitraum"""
        if not self.db:
            return "❌ Datenbank nicht verfügbar"
        
        try:
            now = datetime.now(timezone.utc)
            
            if period == "today":
                start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                title = "HEUTE"
            elif period == "week":
                start = now - timedelta(days=7)
                title = "DIESE WOCHE"
            else:
                start = now - timedelta(days=30)
                title = "DIESER MONAT"
            
            trades = await self.db.get_trades(user_id, limit=1000)
            
            # Filter nach Zeitraum
            period_trades = [t for t in trades if t.get('exit_time') and t['exit_time'] >= start]
            
            if not period_trades:
                return f"📊 <b>PROFIT {title}</b>\n\nKeine Trades in diesem Zeitraum"
            
            total_pnl = sum(t.get('pnl', 0) for t in period_trades)
            winners = sum(1 for t in period_trades if t.get('pnl', 0) > 0)
            losers = len(period_trades) - winners
            win_rate = (winners / len(period_trades) * 100) if period_trades else 0
            
            emoji = "📈" if total_pnl >= 0 else "📉"
            
            return f"""
{emoji} <b>PROFIT {title}</b>

<b>Trades:</b> {len(period_trades)}
<b>Gewinner:</b> {winners} ✅
<b>Verlierer:</b> {losers} ❌
<b>Win-Rate:</b> {win_rate:.1f}%

<b>Total PnL:</b> {'+' if total_pnl >= 0 else ''}${total_pnl:.2f}
"""
        except Exception as e:
            logger.error(f"Profit error: {e}")
            return f"❌ Fehler: {str(e)[:50]}"
    
    async def _get_balance(self, user_id: str) -> str:
        """Hole Wallet-Balance"""
        if not self.db:
            return "❌ Datenbank nicht verfügbar"
        
        try:
            account = await self.db.get_live_account(user_id)
            if not account:
                return "❌ Kein Account gefunden"
            
            # Berechne Positions-Wert
            positions_value = sum(p.qty * p.entry_price for p in account.positions) if account.positions else 0
            total = account.balance + positions_value
            
            return f"""
💰 <b>WALLET BALANCE</b>

<b>Verfügbar:</b> ${account.balance:.2f}
<b>In Positionen:</b> ${positions_value:.2f}
<b>Gesamt:</b> ${total:.2f}

<b>Offene Positionen:</b> {len(account.positions) if account.positions else 0}
"""
        except Exception as e:
            logger.error(f"Balance error: {e}")
            return f"❌ Fehler: {str(e)[:50]}"
    
    async def _get_recent_trades(self, user_id: str) -> str:
        """Hole letzte Trades"""
        if not self.db:
            return "❌ Datenbank nicht verfügbar"
        
        try:
            trades = await self.db.get_trades(user_id, limit=5)
            
            if not trades:
                return "📜 Noch keine Trades"
            
            text = "📜 <b>LETZTE 5 TRADES</b>\n\n"
            
            for t in trades[:5]:
                pnl = t.get('pnl', 0)
                emoji = "🟢" if pnl >= 0 else "🔴"
                text += f"{emoji} <b>{t.get('symbol', '?')}</b>\n"
                text += f"   PnL: {'+' if pnl >= 0 else ''}${pnl:.2f}\n"
                text += f"   {t.get('exit_reason', '?')}\n\n"
            
            return text
        except Exception as e:
            logger.error(f"Trades error: {e}")
            return f"❌ Fehler: {str(e)[:50]}"
    
    async def _get_ki_status(self, user_id: str) -> str:
        """Hole KI Status"""
        if not self.db:
            return "❌ Datenbank nicht verfügbar"
        
        try:
            # Hole KI State aus DB
            ki_data = await self.db.ki_states.find_one({"user_id": user_id})
            
            if not ki_data:
                return """
🧠 <b>KI STATUS</b>

<b>Phase:</b> Datensammlung
<b>Trades:</b> 0/10
<b>Status:</b> KI beobachtet noch

Die KI übernimmt nach 10 Trades.
"""
            
            trade_count = ki_data.get('total_trades', 0)
            phase = "KI AKTIV" if trade_count >= 10 else "Datensammlung"
            confidence = ki_data.get('ki_confidence', 0.5) * 100
            
            return f"""
🧠 <b>KI STATUS</b>

<b>Phase:</b> {phase}
<b>Trades:</b> {trade_count}/10
<b>Confidence:</b> {confidence:.0f}%

<b>Gelernte Parameter:</b>
• RSI angepasst: {ki_data.get('adjusted_rsi', 'Nein')}
• Stop-Loss optimiert: {ki_data.get('adjusted_sl', 'Nein')}
"""
        except Exception as e:
            logger.error(f"KI status error: {e}")
            return f"❌ Fehler: {str(e)[:50]}"
    
    async def _pause_bot(self, user_id: str) -> str:
        """Pausiere den Bot"""
        if not self.db:
            return "❌ Datenbank nicht verfügbar"
        
        try:
            await self.db.users.update_one(
                {"_id": user_id},
                {"$set": {"settings.bot_paused": True}}
            )
            return "⏸️ Bot wurde pausiert. Keine neuen Trades werden eröffnet."
        except Exception as e:
            return f"❌ Fehler: {str(e)[:50]}"
    
    async def _resume_bot(self, user_id: str) -> str:
        """Setze Bot fort"""
        if not self.db:
            return "❌ Datenbank nicht verfügbar"
        
        try:
            await self.db.users.update_one(
                {"_id": user_id},
                {"$set": {"settings.bot_paused": False}}
            )
            return "▶️ Bot wurde fortgesetzt. Trading ist wieder aktiv."
        except Exception as e:
            return f"❌ Fehler: {str(e)[:50]}"


# Singleton instance
_telegram_bot: Optional[TelegramBot] = None


def get_telegram_bot(token: str = None, db=None) -> TelegramBot:
    """Get or create Telegram bot instance"""
    global _telegram_bot
    if _telegram_bot is None and token:
        _telegram_bot = TelegramBot(token, db)
    return _telegram_bot
