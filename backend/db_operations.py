from motor.motor_asyncio import AsyncIOMotorClient
import os
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import logging
from models import BotSettings, LogEntry, PaperAccount, Trade, DailyMetrics

logger = logging.getLogger(__name__)

class Database:
    """MongoDB operations"""
    
    def __init__(self):
        mongo_url = os.environ['MONGO_URL']
        self.client = AsyncIOMotorClient(mongo_url)
        self.db = self.client[os.environ['DB_NAME']]
        
        # Collections
        self.settings = self.db.settings
        self.logs = self.db.logs
        self.paper_accounts = self.db.paper_accounts
        self.trades = self.db.trades
        self.daily_metrics = self.db.daily_metrics
    
    async def initialize(self):
        """Initialize database with default settings"""
        existing = await self.settings.find_one({'_id': 'settings'})
        if not existing:
            default_settings = BotSettings().model_dump()
            default_settings['_id'] = 'settings'
            await self.settings.insert_one(default_settings)
            logger.info("Initialized default settings")
        
        # Initialize paper account if not exists
        existing_account = await self.paper_accounts.find_one({'_id': 'default'})
        if not existing_account:
            default_account = PaperAccount().model_dump()
            default_account['_id'] = 'default'
            await self.paper_accounts.insert_one(default_account)
            logger.info("Initialized paper account with $10,000")
    
    async def get_settings(self) -> BotSettings:
        """Get bot settings"""
        doc = await self.settings.find_one({'_id': 'settings'}, {'_id': 0})
        if not doc:
            return BotSettings()
        return BotSettings(**doc)
    
    async def update_settings(self, updates: Dict[str, Any]):
        """Update bot settings"""
        await self.settings.update_one(
            {'_id': 'settings'},
            {'$set': updates}
        )
    
    async def log(self, level: str, msg: str, context: Optional[dict] = None):
        """Add log entry"""
        log_entry = LogEntry(
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
        log_func(f"{msg} {context if context else ''}")
    
    async def get_logs(self, limit: int = 100) -> List[LogEntry]:
        """Get recent logs"""
        cursor = self.logs.find({}, {'_id': 0}).sort('ts', -1).limit(limit)
        logs = await cursor.to_list(length=limit)
        
        # Convert ISO strings back to datetime
        for log in logs:
            if isinstance(log['ts'], str):
                log['ts'] = datetime.fromisoformat(log['ts'])
        
        # Return in chronological order
        return [LogEntry(**log) for log in reversed(logs)]
    
    async def get_paper_account(self) -> PaperAccount:
        """Get paper trading account"""
        doc = await self.paper_accounts.find_one({'_id': 'default'}, {'_id': 0})
        if not doc:
            return PaperAccount()
        return PaperAccount(**doc)
    
    async def update_paper_account(self, account: PaperAccount):
        """Update paper account"""
        doc = account.model_dump()
        # Convert datetime objects to ISO strings
        for pos in doc.get('open_positions', []):
            if 'entry_time' in pos and isinstance(pos['entry_time'], datetime):
                pos['entry_time'] = pos['entry_time'].isoformat()
        
        await self.paper_accounts.update_one(
            {'_id': 'default'},
            {'$set': doc},
            upsert=True
        )
    
    async def add_trade(self, trade: Trade):
        """Add trade record"""
        doc = trade.model_dump()
        doc['ts'] = doc['ts'].isoformat()
        await self.trades.insert_one(doc)
    
    async def get_trades(self, limit: int = 50) -> List[Trade]:
        """Get recent trades"""
        cursor = self.trades.find({}, {'_id': 0}).sort('ts', -1).limit(limit)
        trades = await cursor.to_list(length=limit)
        
        for trade in trades:
            if isinstance(trade['ts'], str):
                trade['ts'] = datetime.fromisoformat(trade['ts'])
        
        return [Trade(**trade) for trade in reversed(trades)]
    
    async def update_daily_metrics(self, date: str, pnl: float, drawdown: float, trades_count: int):
        """Update daily metrics"""
        await self.daily_metrics.update_one(
            {'date': date},
            {'$set': {
                'pnl': pnl,
                'drawdown': drawdown,
                'trades_count': trades_count
            }},
            upsert=True
        )
    
    async def get_daily_metrics(self, days: int = 30) -> List[DailyMetrics]:
        """Get daily metrics"""
        cursor = self.daily_metrics.find({}, {'_id': 0}).sort('date', -1).limit(days)
        metrics = await cursor.to_list(length=days)
        return [DailyMetrics(**m) for m in reversed(metrics)]
    
    def close(self):
        """Close database connection"""
        self.client.close()
