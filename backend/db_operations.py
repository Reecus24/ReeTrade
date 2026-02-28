from motor.motor_asyncio import AsyncIOMotorClient
import os
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import logging
from models import UserSettings, LogEntry, PaperAccount, Trade, DailyMetrics, User
from crypto_utils import crypto_manager

logger = logging.getLogger(__name__)

class Database:
    \"\"\"MongoDB operations with multi-user support\"\"\"
    
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
    
    async def initialize(self):
        \"\"\"Initialize database indexes\"\"\"
        # Create indexes
        await self.users.create_index('email', unique=True)
        await self.settings.create_index('user_id', unique=True)
        await self.user_keys.create_index('user_id', unique=True)
        await self.paper_accounts.create_index('user_id', unique=True)
        await self.logs.create_index([('user_id', 1), ('ts', -1)])
        await self.trades.create_index([('user_id', 1), ('ts', -1)])
        logger.info(\"Database initialized with indexes\")
    
    # ========== USER OPERATIONS ==========
    
    async def create_user(self, email: str, password_hash: str) -> str:
        \"\"\"Create new user and return user_id\"\"\"
        user = User(email=email, password_hash=password_hash)
        doc = user.model_dump()
        result = await self.users.insert_one(doc)
        user_id = str(result.inserted_id)
        
        # Initialize default settings and paper account
        await self.initialize_user_data(user_id)
        
        logger.info(f\"User created: {email} (ID: {user_id})\")
        return user_id
    
    async def get_user_by_email(self, email: str) -> Optional[Dict]:
        \"\"\"Get user by email\"\"\"
        user = await self.users.find_one({'email': email})
        if user:
            user['_id'] = str(user['_id'])
        return user
    
    async def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        \"\"\"Get user by ID\"\"\"
        from bson import ObjectId
        user = await self.users.find_one({'_id': ObjectId(user_id)})
        if user:
            user['_id'] = str(user['_id'])
        return user
    
    async def initialize_user_data(self, user_id: str):
        \"\"\"Initialize default settings and paper account for new user\"\"\"
        # Default settings
        default_settings = UserSettings(user_id=user_id).model_dump()
        await self.settings.insert_one(default_settings)
        
        # Default paper account
        default_account = PaperAccount(user_id=user_id).model_dump()
        await self.paper_accounts.insert_one(default_account)
        
        logger.info(f\"Initialized data for user {user_id}\")
    
    # ========== SETTINGS OPERATIONS ==========
    
    async def get_settings(self, user_id: str) -> UserSettings:
        \"\"\"Get user settings\"\"\"
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
        \"\"\"Update user settings\"\"\"
        await self.settings.update_one(
            {'user_id': user_id},
            {'$set': updates},
            upsert=True
        )
    
    async def get_all_active_users(self) -> List[Dict]:
        \"\"\"Get all users with bot_running=true\"\"\"
        cursor = self.settings.find({'bot_running': True})
        settings_list = await cursor.to_list(length=1000)
        return settings_list
    
    # ========== MEXC KEYS OPERATIONS ==========
    
    async def set_mexc_keys(self, user_id: str, api_key: str, api_secret: str):
        \"\"\"Store encrypted MEXC API keys\"\"\"
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
        logger.info(f\"MEXC keys updated for user {user_id}\")
    
    async def get_mexc_keys(self, user_id: str) -> Optional[Dict[str, str]]:
        \"\"\"Get decrypted MEXC API keys (for backend use only)\"\"\"
        doc = await self.user_keys.find_one({'user_id': user_id})
        if not doc:
            return None
        
        try:
            api_key = crypto_manager.decrypt(doc['api_key_encrypted'])
            api_secret = crypto_manager.decrypt(doc['api_secret_encrypted'])
            return {'api_key': api_key, 'api_secret': api_secret}
        except Exception as e:
            logger.error(f\"Failed to decrypt keys for user {user_id}: {e}\")
            return None
    
    async def has_mexc_keys(self, user_id: str) -> bool:
        \"\"\"Check if user has MEXC keys configured\"\"\"
        doc = await self.user_keys.find_one({'user_id': user_id})
        return doc is not None and 'api_key_encrypted' in doc
    
    async def get_mexc_keys_status(self, user_id: str) -> Dict:
        \"\"\"Get MEXC keys status (connection info only, no keys)\"\"\"
        doc = await self.user_keys.find_one({'user_id': user_id})
        if not doc:
            return {'connected': False, 'last_updated': None}
        return {
            'connected': True,
            'last_updated': doc.get('updated_at')
        }
    
    # ========== LOG OPERATIONS ==========
    
    async def log(self, user_id: str, level: str, msg: str, context: Optional[dict] = None):
        \"\"\"Add log entry for user\"\"\"
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
        log_func(f\"[User {user_id[:8]}] {msg} {context if context else ''}\")
    
    async def get_logs(self, user_id: str, limit: int = 100) -> List[LogEntry]:
        \"\"\"Get recent logs for user\"\"\"
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
        \"\"\"Get paper trading account for user\"\"\"
        doc = await self.paper_accounts.find_one({'user_id': user_id})
        if not doc:
            # Create default if not exists
            default_account = PaperAccount(user_id=user_id)
            await self.paper_accounts.insert_one(default_account.model_dump())
            return default_account
        
        doc.pop('_id', None)
        return PaperAccount(**doc)
    
    async def update_paper_account(self, account: PaperAccount):
        \"\"\"Update paper account for user\"\"\"
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
        \"\"\"Add trade record for user\"\"\"
        doc = trade.model_dump()
        doc['ts'] = doc['ts'].isoformat()
        await self.trades.insert_one(doc)
    
    async def get_trades(self, user_id: str, limit: int = 50) -> List[Trade]:
        \"\"\"Get recent trades for user\"\"\"
        cursor = self.trades.find({'user_id': user_id}).sort('ts', -1).limit(limit)
        trades = await cursor.to_list(length=limit)
        
        for trade in trades:
            if isinstance(trade['ts'], str):
                trade['ts'] = datetime.fromisoformat(trade['ts'])
            trade.pop('_id', None)
        
        return [Trade(**trade) for trade in reversed(trades)]
    
    # ========== METRICS OPERATIONS ==========
    
    async def update_daily_metrics(self, user_id: str, date: str, pnl: float, drawdown: float, trades_count: int):
        \"\"\"Update daily metrics for user\"\"\"
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
        \"\"\"Get daily metrics for user\"\"\"
        cursor = self.daily_metrics.find({'user_id': user_id}).sort('date', -1).limit(days)
        metrics = await cursor.to_list(length=days)
        for m in metrics:
            m.pop('_id', None)
        return [DailyMetrics(**m) for m in reversed(metrics)]
    
    def close(self):
        \"\"\"Close database connection\"\"\"
        self.client.close()
