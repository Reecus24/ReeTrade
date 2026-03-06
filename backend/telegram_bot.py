"""
ReeTrade Telegram Bot - Saubere Implementierung
================================================
- Pro-User Telegram Integration
- Code-basiertes Linking (Code von Telegram → Web-App)
- Trade-Benachrichtigungen pro User
"""

import os
import logging
import aiohttp
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict
import secrets

logger = logging.getLogger(__name__)

class TelegramBot:
    """Telegram Bot für ReeTrade - Pro User"""
    
    def __init__(self, token: str, db):
        self.token = token
        self.db = db
        self.base_url = f"https://api.telegram.org/bot{token}"
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close session"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CORE API METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def send_message(self, chat_id: int, text: str, parse_mode: str = "HTML") -> bool:
        """Send message to a specific chat"""
        try:
            session = await self._get_session()
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode
            }
            
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    return True
                else:
                    error = await resp.text()
                    logger.warning(f"[TELEGRAM] Send failed: {error}")
                    return False
        except Exception as e:
            logger.error(f"[TELEGRAM] Send error: {e}")
            return False
    
    async def get_updates(self, offset: int = 0) -> list:
        """Get updates from Telegram (polling)"""
        try:
            session = await self._get_session()
            url = f"{self.base_url}/getUpdates"
            params = {"offset": offset, "timeout": 30}
            
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("result", [])
                else:
                    return []
        except Exception as e:
            logger.error(f"[TELEGRAM] Get updates error: {e}")
            return []
    
    # ═══════════════════════════════════════════════════════════════════════════
    # LINK CODE GENERATION (User tippt /link in Telegram)
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def generate_link_code(self, chat_id: int) -> str:
        """
        Generiert einen 6-stelligen Code für das Telegram-Linking
        User gibt diesen Code dann in der Web-App ein
        """
        # 6-stelliger alphanumerischer Code
        code = secrets.token_hex(3).upper()  # z.B. "A1B2C3"
        
        # Speichere in DB mit Expiration (10 Minuten)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        
        await self.db.db.telegram_link_codes.update_one(
            {"chat_id": str(chat_id)},
            {"$set": {
                "code": code,
                "chat_id": str(chat_id),
                "created_at": datetime.now(timezone.utc),
                "expires_at": expires_at,
                "used": False
            }},
            upsert=True
        )
        
        logger.info(f"[TELEGRAM] Link code {code} generated for chat {chat_id}")
        return code
    
    # ═══════════════════════════════════════════════════════════════════════════
    # COMMAND HANDLERS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def handle_command(self, chat_id: int, command: str, user_id: Optional[str] = None) -> str:
        """Handle Telegram commands"""
        
        cmd = command.lower().split()[0]
        
        if cmd == "/start":
            return self._get_start_message()
        
        elif cmd == "/help":
            return self._get_help_message()
        
        elif cmd == "/link":
            code = await self.generate_link_code(chat_id)
            return f"""🔗 <b>Dein Linking-Code:</b>

<code>{code}</code>

Gib diesen Code in der ReeTrade Web-App unter <b>Settings → Telegram</b> ein.

⏱️ Code gültig für 10 Minuten."""
        
        # Befehle die einen verknüpften User brauchen
        if not user_id:
            return "❌ Telegram nicht verknüpft.\n\nTippe /link und gib den Code in der Web-App ein."
        
        if cmd == "/status":
            return await self._get_status(user_id)
        
        elif cmd == "/balance":
            return await self._get_balance(user_id)
        
        elif cmd == "/profit":
            return await self._get_profit(user_id)
        
        elif cmd == "/ki" or cmd == "/ai":
            return await self._get_ki_status(user_id)
        
        elif cmd == "/trades":
            return await self._get_recent_trades(user_id)
        
        else:
            return "❓ Unbekannter Befehl. Tippe /help für alle Befehle."
    
    def _get_start_message(self) -> str:
        return """🤖 <b>ReeTrade Bot</b>

Willkommen! Dieser Bot sendet dir Trading-Benachrichtigungen.

<b>Verknüpfung:</b>
1. Tippe /link
2. Gib den Code in der Web-App ein

<b>Befehle:</b>
/status - Offene Positionen
/balance - Wallet-Stand
/profit - Heutiger Profit
/trades - Letzte Trades
/ki - KI Status"""
    
    def _get_help_message(self) -> str:
        return """📚 <b>Befehle</b>

/link - Verknüpfungscode generieren
/status - Offene Positionen
/balance - Wallet-Stand
/profit - Heutiger Profit
/trades - Letzte 5 Trades
/ki - RL-KI Status

<b>Benachrichtigungen:</b>
• 🟢 Trade geöffnet
• 🔴 Trade geschlossen
• 📊 Tägliche Zusammenfassung (21:00)"""
    
    async def _get_status(self, user_id: str) -> str:
        """Get open positions status"""
        try:
            account = await self.db.get_live_account(user_id)
            
            if not account or not account.open_positions:
                return "📭 Keine offenen Positionen."
            
            lines = ["📊 <b>Offene Positionen</b>\n"]
            
            for pos in account.open_positions:
                lines.append(
                    f"• <b>{pos.symbol}</b>\n"
                    f"  Entry: ${pos.entry_price:.4f} | Qty: {pos.qty:.4f}"
                )
            
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Fehler: {str(e)}"
    
    async def _get_balance(self, user_id: str) -> str:
        """Get wallet balance"""
        try:
            keys = await self.db.get_mexc_keys(user_id)
            if not keys:
                return "❌ MEXC Keys nicht konfiguriert."
            
            from mexc_client import MexcClient
            mexc = MexcClient(api_key=keys['api_key'], api_secret=keys['api_secret'])
            account = await mexc.get_account()
            
            usdt_balance = 0
            for balance in account.get('balances', []):
                if balance.get('asset') == 'USDT':
                    usdt_balance = float(balance.get('free', 0))
                    break
            
            return f"""💰 <b>Wallet Balance</b>

USDT: <code>${usdt_balance:.2f}</code>"""
        except Exception as e:
            return f"❌ Fehler: {str(e)}"
    
    async def _get_profit(self, user_id: str) -> str:
        """Get today's profit"""
        try:
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            
            trades = await self.db.get_trades(user_id, limit=100)
            
            today_trades = []
            for t in trades:
                ts = t.get('ts')
                if ts:
                    if isinstance(ts, str):
                        ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    if ts >= today_start and t.get('pnl') is not None:
                        today_trades.append(t)
            
            if not today_trades:
                return "📊 Heute noch keine abgeschlossenen Trades."
            
            total_pnl = sum(t.get('pnl', 0) for t in today_trades)
            winners = len([t for t in today_trades if t.get('pnl', 0) > 0])
            losers = len(today_trades) - winners
            
            emoji = "🟢" if total_pnl >= 0 else "🔴"
            
            return f"""📈 <b>Heutiger Profit</b>

{emoji} PnL: <code>${total_pnl:+.2f}</code>
🎯 Trades: {len(today_trades)} ({winners}W / {losers}L)
📊 Win Rate: {(winners/len(today_trades)*100):.0f}%"""
        except Exception as e:
            return f"❌ Fehler: {str(e)}"
    
    async def _get_ki_status(self, user_id: str) -> str:
        """Get RL-AI status"""
        try:
            from rl_trading_ai import get_rl_trading_ai
            rl_ai = get_rl_trading_ai()
            status = rl_ai.get_status()
            
            exploration_pct = status.get('exploration_pct', 100)
            learning_pct = 100 - exploration_pct
            
            phase = "🎲 Exploration" if exploration_pct > 50 else "🎯 Exploitation"
            
            return f"""🧠 <b>RL-KI Status</b>

{phase}
📊 Trades: {status.get('total_trades', 0)}
🎯 Exploitation: {learning_pct:.0f}%
🎲 Exploration: {exploration_pct:.0f}%
ε: {status.get('epsilon', 1.0):.3f}"""
        except Exception as e:
            return f"❌ Fehler: {str(e)}"
    
    async def _get_recent_trades(self, user_id: str) -> str:
        """Get recent trades"""
        try:
            trades = await self.db.get_trades(user_id, limit=5)
            
            if not trades:
                return "📭 Keine Trades gefunden."
            
            lines = ["📜 <b>Letzte 5 Trades</b>\n"]
            
            for t in trades[:5]:
                pnl = t.get('pnl', 0)
                emoji = "🟢" if pnl >= 0 else "🔴"
                symbol = t.get('symbol', '?')
                lines.append(f"{emoji} {symbol}: ${pnl:+.2f}")
            
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Fehler: {str(e)}"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TRADE NOTIFICATIONS (Pro User)
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def notify_trade_opened(self, user_id: str, trade_data: dict):
        """Benachrichtigung: Trade geöffnet"""
        chat_id = await self._get_user_chat_id(user_id)
        if not chat_id:
            return
        
        symbol = trade_data.get('symbol', '?')
        entry = trade_data.get('entry', 0)
        qty = trade_data.get('qty', 0)
        notional = entry * qty
        
        message = f"""🟢 <b>TRADE GEÖFFNET</b>

📈 {symbol}
💰 Entry: ${entry:.4f}
📦 Qty: {qty:.6f}
💵 Wert: ${notional:.2f}"""
        
        await self.send_message(int(chat_id), message)
    
    async def notify_trade_closed(self, user_id: str, trade_data: dict):
        """Benachrichtigung: Trade geschlossen"""
        chat_id = await self._get_user_chat_id(user_id)
        if not chat_id:
            return
        
        symbol = trade_data.get('symbol', '?')
        entry = trade_data.get('entry', 0)
        exit_price = trade_data.get('exit', 0)
        pnl = trade_data.get('pnl', 0)
        pnl_pct = trade_data.get('pnl_pct', 0)
        reason = trade_data.get('reason', 'Unknown')
        
        emoji = "🟢" if pnl >= 0 else "🔴"
        
        message = f"""{emoji} <b>TRADE GESCHLOSSEN</b>

📊 {symbol}
📥 Entry: ${entry:.4f}
📤 Exit: ${exit_price:.4f}
💰 PnL: <code>${pnl:+.2f}</code> ({pnl_pct:+.2f}%)
📝 Grund: {reason}"""
        
        await self.send_message(int(chat_id), message)
    
    async def notify_daily_summary(self, user_id: str, summary: dict):
        """Tägliche Zusammenfassung"""
        chat_id = await self._get_user_chat_id(user_id)
        if not chat_id:
            return
        
        trade_count = summary.get('trade_count', 0)
        total_pnl = summary.get('total_pnl', 0)
        winners = summary.get('winners', 0)
        losers = summary.get('losers', 0)
        win_rate = summary.get('win_rate', 0)
        
        emoji = "🟢" if total_pnl >= 0 else "🔴"
        
        message = f"""📊 <b>TAGES-ZUSAMMENFASSUNG</b>

{emoji} PnL: <code>${total_pnl:+.2f}</code>
🎯 Trades: {trade_count} ({winners}W / {losers}L)
📈 Win Rate: {win_rate:.0f}%

Gute Nacht! 🌙"""
        
        await self.send_message(int(chat_id), message)
    
    async def _get_user_chat_id(self, user_id: str) -> Optional[str]:
        """Get Telegram chat_id for a user"""
        try:
            from bson import ObjectId
            user = await self.db.users.find_one({"_id": ObjectId(user_id)})
            return user.get('telegram_chat_id') if user else None
        except Exception:
            return None


# Singleton
_telegram_bot: Optional[TelegramBot] = None

def get_telegram_bot(token: str = None, db = None) -> Optional[TelegramBot]:
    """Get or create Telegram bot instance"""
    global _telegram_bot
    
    if _telegram_bot is None and token and db:
        _telegram_bot = TelegramBot(token, db)
    
    return _telegram_bot
