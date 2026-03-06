"""
Distributed Lock / Leader Election für ReeTrade
================================================
Verwendet MongoDB TTL-basiertes Locking um sicherzustellen,
dass nur eine Instanz gleichzeitig Telegram Polling ausführt.

Dies verhindert den 409 Conflict Error bei mehreren laufenden Instanzen.
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class DistributedLock:
    """
    MongoDB-basiertes Distributed Lock mit TTL
    
    Verwendet eine Collection mit TTL Index um automatisch
    abgelaufene Locks zu entfernen.
    """
    
    def __init__(self, db, lock_name: str = "telegram_polling", ttl_seconds: int = 30):
        self.db = db
        self.lock_name = lock_name
        self.ttl_seconds = ttl_seconds
        self.instance_id = f"{os.getpid()}_{uuid.uuid4().hex[:8]}"
        self.is_leader = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._initialized = False
    
    async def initialize(self):
        """Erstelle TTL Index für automatische Lock-Expiration"""
        if self._initialized:
            return
        
        try:
            # Erstelle Collection falls nicht vorhanden
            if 'distributed_locks' not in await self.db.db.list_collection_names():
                await self.db.db.create_collection('distributed_locks')
            
            # Erstelle TTL Index (Locks expiren automatisch)
            await self.db.db.distributed_locks.create_index(
                "expires_at",
                expireAfterSeconds=0  # Dokumente werden gelöscht wenn expires_at < now
            )
            
            # Unique Index auf lock_name
            await self.db.db.distributed_locks.create_index(
                "lock_name",
                unique=True
            )
            
            self._initialized = True
            logger.info(f"[Lock] Initialized distributed lock system (instance: {self.instance_id})")
            
        except Exception as e:
            # Index existiert möglicherweise bereits
            logger.debug(f"[Lock] Index setup: {e}")
            self._initialized = True
    
    async def try_acquire(self) -> bool:
        """
        Versuche das Lock zu erwerben
        
        Returns:
            True wenn Lock erworben, False sonst
        """
        await self.initialize()
        
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=self.ttl_seconds)
        
        try:
            # Versuche Lock zu erstellen oder zu aktualisieren
            result = await self.db.db.distributed_locks.find_one_and_update(
                {
                    "lock_name": self.lock_name,
                    "$or": [
                        {"holder": self.instance_id},  # Wir halten es bereits
                        {"expires_at": {"$lt": now}}   # Abgelaufen
                    ]
                },
                {
                    "$set": {
                        "holder": self.instance_id,
                        "expires_at": expires_at,
                        "acquired_at": now,
                        "last_heartbeat": now
                    }
                },
                upsert=False,
                return_document=True
            )
            
            if result and result.get('holder') == self.instance_id:
                if not self.is_leader:
                    logger.info(f"[Lock] ✅ Acquired lock '{self.lock_name}' (instance: {self.instance_id})")
                self.is_leader = True
                return True
            
            # Lock existiert nicht - versuche zu erstellen
            try:
                await self.db.db.distributed_locks.insert_one({
                    "lock_name": self.lock_name,
                    "holder": self.instance_id,
                    "expires_at": expires_at,
                    "acquired_at": now,
                    "last_heartbeat": now
                })
                logger.info(f"[Lock] ✅ Created and acquired lock '{self.lock_name}' (instance: {self.instance_id})")
                self.is_leader = True
                return True
            except Exception:
                # Jemand anderes hat es gerade erstellt
                pass
            
            # Prüfe wer das Lock hält
            current_lock = await self.db.db.distributed_locks.find_one({"lock_name": self.lock_name})
            if current_lock:
                holder = current_lock.get('holder', 'unknown')
                expires = current_lock.get('expires_at')
                if holder != self.instance_id:
                    logger.debug(f"[Lock] Lock held by {holder}, expires at {expires}")
            
            self.is_leader = False
            return False
            
        except Exception as e:
            logger.error(f"[Lock] Error acquiring lock: {e}")
            self.is_leader = False
            return False
    
    async def release(self):
        """Gib das Lock frei"""
        if not self.is_leader:
            return
        
        try:
            result = await self.db.db.distributed_locks.delete_one({
                "lock_name": self.lock_name,
                "holder": self.instance_id
            })
            
            if result.deleted_count > 0:
                logger.info(f"[Lock] Released lock '{self.lock_name}'")
            
            self.is_leader = False
            
        except Exception as e:
            logger.error(f"[Lock] Error releasing lock: {e}")
    
    async def heartbeat(self):
        """Update Lock TTL (verlängert Lease)"""
        if not self.is_leader:
            return False
        
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=self.ttl_seconds)
        
        try:
            result = await self.db.db.distributed_locks.update_one(
                {
                    "lock_name": self.lock_name,
                    "holder": self.instance_id
                },
                {
                    "$set": {
                        "expires_at": expires_at,
                        "last_heartbeat": now
                    }
                }
            )
            
            if result.modified_count > 0:
                return True
            else:
                # Lock wurde von jemand anderem übernommen
                logger.warning(f"[Lock] Lost lock '{self.lock_name}' - someone else took it")
                self.is_leader = False
                return False
                
        except Exception as e:
            logger.error(f"[Lock] Heartbeat error: {e}")
            return False
    
    async def start_heartbeat_loop(self, interval: float = 10.0):
        """Starte Heartbeat-Loop um Lock am Leben zu halten"""
        async def _loop():
            while True:
                await asyncio.sleep(interval)
                if self.is_leader:
                    success = await self.heartbeat()
                    if not success:
                        logger.warning("[Lock] Heartbeat failed, no longer leader")
                        break
        
        self._heartbeat_task = asyncio.create_task(_loop())
        logger.info(f"[Lock] Started heartbeat loop (interval: {interval}s)")
    
    async def stop_heartbeat_loop(self):
        """Stoppe Heartbeat-Loop"""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None
    
    async def get_lock_status(self) -> dict:
        """Hole aktuellen Lock-Status"""
        try:
            lock = await self.db.db.distributed_locks.find_one({"lock_name": self.lock_name})
            if lock:
                return {
                    "lock_name": self.lock_name,
                    "holder": lock.get("holder"),
                    "is_me": lock.get("holder") == self.instance_id,
                    "expires_at": lock.get("expires_at"),
                    "last_heartbeat": lock.get("last_heartbeat")
                }
            return {"lock_name": self.lock_name, "holder": None}
        except Exception as e:
            return {"error": str(e)}


# Global instance für Telegram Lock
telegram_lock: Optional[DistributedLock] = None


def get_telegram_lock(db) -> DistributedLock:
    """Hole oder erstelle Telegram Lock"""
    global telegram_lock
    if telegram_lock is None:
        telegram_lock = DistributedLock(db, "telegram_polling", ttl_seconds=30)
    return telegram_lock
