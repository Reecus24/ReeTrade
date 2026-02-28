from motor.motor_asyncio import AsyncIOMotorClient
import os
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import logging
from models import UserSettings, LogEntry, PaperAccount, Trade, DailyMetrics, User
from crypto_utils import crypto_manager

logger = logging.getLogger(__name__)

class Database:
    # MongoDB operations with multi-user support
    
    def __init__(self):
        mongo_url = os.environ['MONGO_URL']
        self.client = AsyncIOMotorClient(mongo_url)
        self.db = self.client[os.environ['DB_NAME']]
        
        # Collections
        self.users = self.db.users
        self.settings = self.db.settings
        self.user_keys = self.db.user_keys
        self.logs = self.db.logs
        self.paper_accounts = self.db.paper_accounts
        self.trades = self.db.trades
        self.daily_metrics = self.db.daily_metrics
        self.audit_logs = self.db.audit_logs
        self.symbol_pauses = self.db.symbol_pauses
    
    async def initialize(self):
        # Initialize database indexes
        # Create indexes
        await self.users.create_index('email', unique=True)
        await self.settings.create_index('user_id', unique=True)
        await self.user_keys.create_index('user_id', unique=True)
        await self.paper_accounts.create_index('user_id', unique=True)
        await self.logs.create_index([('user_id', 1), ('ts', -1)])
        await self.trades.create_index([('user_id', 1), ('ts', -1)])
        await self.audit_logs.create_index([('user_id', 1), ('ts', -1)])
        await self.audit_logs.create_index('action')
        await self.symbol_pauses.create_index([('user_id', 1), ('symbol', 1)])
        await self.symbol_pauses.create_index('pause_until')
        logger.info("Database initialized with indexes")
    
    # ========== USER OPERATIONS ==========
    
    async def create_user(self, email: str, password_hash: str) -> str:
        user = User(email=email, password_hash=password_hash)
        doc = user.model_dump()
        result = await self.users.insert_one(doc)
        user_id = str(result.inserted_id)
        
        # Initialize default settings and paper account
        await self.initialize_user_data(user_id)
        
        logger.info(f"User created: {email} (ID: {user_id})")
        return user_id
    
    async def get_user_by_email(self, email: str) -> Optional[Dict]:
        user = await self.users.find_one({'email': email})
        if user:
            user['_id'] = str(user['_id'])
        return user
    
    async def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        from bson import ObjectId
        user = await self.users.find_one({'_id': ObjectId(user_id)})
        if user:
            user['_id'] = str(user['_id'])
        return user
    
    async def initialize_user_data(self, user_id: str):
        # Default settings
        default_settings = UserSettings(user_id=user_id).model_dump()
        await self.settings.insert_one(default_settings)
        
        # Default paper account
        default_account = PaperAccount(user_id=user_id).model_dump()
        await self.paper_accounts.insert_one(default_account)
        
        logger.info(f"Initialized data for user {user_id}")
    
    # ========== SETTINGS OPERATIONS ==========
    
    async def get_settings(self, user_id: str) -> UserSettings:
        doc = await self.settings.find_one({'user_id': user_id})
        if not doc:
            # Create default if not exists
            default_settings = UserSettings(user_id=user_id)
            await self.settings.insert_one(default_settings.model_dump())
            return default_settings
        
        # Remove MongoDB _id
        doc.pop('_id', None)
        return UserSettings(**doc)
    
    async def update_settings(self, user_id: str, updates: Dict[str, Any]):
        await self.settings.update_one(
            {'user_id': user_id},
            {'$set': updates},
            upsert=True
        )
    
    async def get_all_active_users(self) -> List[Dict]:
        # Find users with either paper_running or live_running active
        cursor = self.settings.find({
            '$or': [
                {'paper_running': True},
                {'live_running': True},
                {'bot_running': True}  # Legacy support
            ]
        })
        settings_list = await cursor.to_list(length=1000)
        return settings_list
    
    # ========== MEXC KEYS OPERATIONS ==========
    
    async def set_mexc_keys(self, user_id: str, api_key: str, api_secret: str):
        encrypted_key = crypto_manager.encrypt(api_key)
        encrypted_secret = crypto_manager.encrypt(api_secret)
        
        await self.user_keys.update_one(
            {'user_id': user_id},
            {'$set': {
                'api_key_encrypted': encrypted_key,
                'api_secret_encrypted': encrypted_secret,
                'updated_at': datetime.now(timezone.utc)
            }},
            upsert=True
        )
        logger.info(f"MEXC keys updated for user {user_id}")
    
    async def get_mexc_keys(self, user_id: str) -> Optional[Dict[str, str]]:
        doc = await self.user_keys.find_one({'user_id': user_id})
        if not doc:
            return None
        
        try:
            api_key = crypto_manager.decrypt(doc['api_key_encrypted'])
            api_secret = crypto_manager.decrypt(doc['api_secret_encrypted'])
            return {'api_key': api_key, 'api_secret': api_secret}
        except Exception as e:
            logger.error(f"Failed to decrypt keys for user {user_id}: {e}")
            return None
    
    async def has_mexc_keys(self, user_id: str) -> bool:
        doc = await self.user_keys.find_one({'user_id': user_id})
        return doc is not None and 'api_key_encrypted' in doc
    
    async def get_mexc_keys_status(self, user_id: str) -> Dict:
        doc = await self.user_keys.find_one({'user_id': user_id})
        if not doc:
            return {'connected': False, 'last_updated': None}
        return {
            'connected': True,
            'last_updated': doc.get('updated_at')
        }
    
    # ========== LOG OPERATIONS ==========
    
    async def log(self, user_id: str, level: str, msg: str, context: Optional[dict] = None):
        log_entry = LogEntry(
            user_id=user_id,
            ts=datetime.now(timezone.utc),
            level=level,
            msg=msg,
            context=context
        )
        doc = log_entry.model_dump()
        doc['ts'] = doc['ts'].isoformat()
        await self.logs.insert_one(doc)
        
        # Also log to console
        log_func = getattr(logger, level.lower(), logger.info)
        log_func(f"[User {user_id[:8]}] {msg} {context if context else ''}")
    
    async def get_logs(self, user_id: str, limit: int = 100) -> List[LogEntry]:
        cursor = self.logs.find({'user_id': user_id}).sort('ts', -1).limit(limit)
        logs = await cursor.to_list(length=limit)
        
        # Convert ISO strings back to datetime
        for log in logs:
            if isinstance(log['ts'], str):
                log['ts'] = datetime.fromisoformat(log['ts'])
            log.pop('_id', None)
        
        # Return in chronological order
        return [LogEntry(**log) for log in reversed(logs)]
    
    # ========== PAPER ACCOUNT OPERATIONS ==========
    
    async def get_paper_account(self, user_id: str) -> PaperAccount:
        doc = await self.paper_accounts.find_one({'user_id': user_id})
        if not doc:
            # Create default if not exists
            default_account = PaperAccount(user_id=user_id)
            await self.paper_accounts.insert_one(default_account.model_dump())
            return default_account
        
        doc.pop('_id', None)
        return PaperAccount(**doc)
    
    async def update_paper_account(self, account: PaperAccount):
        doc = account.model_dump()
        # Convert datetime objects to ISO strings
        for pos in doc.get('open_positions', []):
            if 'entry_time' in pos and isinstance(pos['entry_time'], datetime):
                pos['entry_time'] = pos['entry_time'].isoformat()
        
        await self.paper_accounts.update_one(
            {'user_id': account.user_id},
            {'$set': doc},
            upsert=True
        )
    
    # ========== TRADE OPERATIONS ==========
    
    async def add_trade(self, trade: Trade):
        doc = trade.model_dump()
        doc['ts'] = doc['ts'].isoformat()
        await self.trades.insert_one(doc)
    
    async def get_today_exposure(self, user_id: str, mode: str) -> float:
        """Get total notional traded today (UTC) for daily cap tracking"""
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Query for trades opened today (BUY trades = new positions)
        cursor = self.trades.find({
            'user_id': user_id,
            'mode': mode,
            'side': 'BUY'  # Only count position opens
        })
        trades = await cursor.to_list(length=10000)
        
        today_exposure = 0.0
        for trade in trades:
            ts = trade.get('ts')
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            
            # Check if trade was opened today
            if ts >= today_start:
                notional = trade.get('notional') or (trade.get('qty', 0) * trade.get('entry', 0))
                today_exposure += notional
        
        return today_exposure
    
    async def get_trades(self, user_id: str, limit: int = 50) -> List[Trade]:
        cursor = self.trades.find({'user_id': user_id}).sort('ts', -1).limit(limit)
        trades = await cursor.to_list(length=limit)
        
        for trade in trades:
            if isinstance(trade['ts'], str):
                trade['ts'] = datetime.fromisoformat(trade['ts'])
            trade.pop('_id', None)
        
        return [Trade(**trade) for trade in reversed(trades)]
    
    async def get_trades_paginated(
        self, 
        user_id: str, 
        mode: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 200, 
        offset: int = 0
    ) -> tuple[List[dict], int]:
        """Get trades with pagination and filters. Returns (trades, total_count)"""
        query = {'user_id': user_id}
        
        if mode:
            query['mode'] = mode
        if symbol:
            query['symbol'] = symbol
        
        # Get total count
        total = await self.trades.count_documents(query)
        
        # Get paginated results
        cursor = self.trades.find(query).sort('ts', -1).skip(offset).limit(limit)
        trades = await cursor.to_list(length=limit)
        
        result = []
        for trade in trades:
            trade.pop('_id', None)
            if isinstance(trade['ts'], str):
                trade['ts'] = datetime.fromisoformat(trade['ts']).isoformat()
            result.append(trade)
        
        return result, total
    
    async def get_daily_pnl(
        self, 
        user_id: str, 
        mode: Optional[str] = None,
        days: int = 30
    ) -> List[dict]:
        """Aggregate PnL by day for the last N days"""
        # Calculate date range
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=days - 1)
        
        # Build query
        query = {
            'user_id': user_id,
            'exit': {'$exists': True, '$ne': None}  # Only closed trades
        }
        if mode:
            query['mode'] = mode
        
        # Get all relevant trades
        cursor = self.trades.find(query)
        trades = await cursor.to_list(length=10000)
        
        # Aggregate by date
        daily_pnl = {}
        for trade in trades:
            ts = trade.get('ts')
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts)
            
            trade_date = ts.date()
            
            # Only include trades in the date range
            if start_date <= trade_date <= end_date:
                date_str = trade_date.isoformat()
                pnl = trade.get('pnl', 0) or 0
                
                if date_str not in daily_pnl:
                    daily_pnl[date_str] = {
                        'date': date_str,
                        'pnl': 0,
                        'trades_count': 0,
                        'wins': 0,
                        'losses': 0
                    }
                
                daily_pnl[date_str]['pnl'] += pnl
                daily_pnl[date_str]['trades_count'] += 1
                if pnl > 0:
                    daily_pnl[date_str]['wins'] += 1
                elif pnl < 0:
                    daily_pnl[date_str]['losses'] += 1
        
        # Fill in missing dates with 0
        result = []
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.isoformat()
            if date_str in daily_pnl:
                result.append(daily_pnl[date_str])
            else:
                result.append({
                    'date': date_str,
                    'pnl': 0,
                    'trades_count': 0,
                    'wins': 0,
                    'losses': 0
                })
            current_date += timedelta(days=1)
        
        return result
    
    # ========== METRICS OPERATIONS ==========
    
    async def update_daily_metrics(self, user_id: str, date: str, pnl: float, drawdown: float, trades_count: int):
        await self.daily_metrics.update_one(
            {'user_id': user_id, 'date': date},
            {'$set': {
                'pnl': pnl,
                'drawdown': drawdown,
                'trades_count': trades_count
            }},
            upsert=True
        )
    
    async def get_daily_metrics(self, user_id: str, days: int = 30) -> List[DailyMetrics]:
        cursor = self.daily_metrics.find({'user_id': user_id}).sort('date', -1).limit(days)
        metrics = await cursor.to_list(length=days)
        for m in metrics:
            m.pop('_id', None)
        return [DailyMetrics(**m) for m in reversed(metrics)]
    
    def close(self):
        self.client.close()
    
    # ========== AUDIT LOG OPERATIONS ==========
    
    async def audit_log(self, user_id: str, action: str, details: Optional[dict] = None, ip_address: Optional[str] = None):
        from models import AuditLogEntry
        entry = AuditLogEntry(
            user_id=user_id,
            ts=datetime.now(timezone.utc),
            action=action,
            details=details,
            ip_address=ip_address
        )
        doc = entry.model_dump()
        doc['ts'] = doc['ts'].isoformat()
        await self.audit_logs.insert_one(doc)
        logger.info(f"[Audit] User {user_id[:8]} - {action}")
    
    async def get_audit_logs(self, user_id: Optional[str] = None, action: Optional[str] = None, limit: int = 100) -> List[dict]:
        query = {}
        if user_id:
            query['user_id'] = user_id
        if action:
            query['action'] = action
        
        cursor = self.audit_logs.find(query).sort('ts', -1).limit(limit)
        logs = await cursor.to_list(length=limit)
        
        for log in logs:
            if isinstance(log['ts'], str):
                log['ts'] = datetime.fromisoformat(log['ts'])
            log.pop('_id', None)
        
        return logs
    
    # ========== SYMBOL TRADING PAUSE OPERATIONS ==========
    
    async def set_symbol_pause(self, user_id: str, symbol: str, pause_hours: int, reason: str, consecutive_losses: int):
        from models import SymbolTradingPause
        pause_until = datetime.now(timezone.utc) + timedelta(hours=pause_hours)
        
        pause = SymbolTradingPause(
            user_id=user_id,
            symbol=symbol,
            pause_until=pause_until,
            reason=reason,
            consecutive_losses=consecutive_losses
        )
        
        await self.symbol_pauses.update_one(
            {'user_id': user_id, 'symbol': symbol},
            {'$set': pause.model_dump()},
            upsert=True
        )
        
        logger.info(f"[User {user_id[:8]}] Symbol {symbol} paused for {pause_hours}h - {reason}")
    
    async def is_symbol_paused(self, user_id: str, symbol: str) -> bool:
        pause = await self.symbol_pauses.find_one({
            'user_id': user_id,
            'symbol': symbol,
            'pause_until': {'$gt': datetime.now(timezone.utc)}
        })
        return pause is not None
    
    async def get_recent_symbol_losses(self, user_id: str, symbol: str, hours: int = 12) -> int:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        # Count losing trades
        count = await self.trades.count_documents({
            'user_id': user_id,
            'symbol': symbol,
            'ts': {'$gte': since.isoformat()},
            'pnl': {'$lt': 0}
        })
        
        return count
