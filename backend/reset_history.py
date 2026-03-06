#!/usr/bin/env python3
"""
ReeTrade - History Reset Script
===============================
Löscht alle Trading-History und setzt die RL-KI zurück.

Verwendung auf dem Server:
    cd /opt/reetrade/backend
    python3 reset_history.py
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os

async def clear_history():
    # MongoDB Connection
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    db_name = os.environ.get('DB_NAME', 'reetrade')
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    print('🧹 Lösche Trading History...')
    print()
    
    # 1. Clear trades collection
    result1 = await db.trades.delete_many({})
    print(f'✅ Trades gelöscht: {result1.deleted_count}')
    
    # 2. Clear logs
    result2 = await db.logs.delete_many({})
    print(f'✅ Logs gelöscht: {result2.deleted_count}')
    
    # 3. Reset RL Brain file
    brain_path = '/tmp/reetrade_rl_brain.pkl'
    if os.path.exists(brain_path):
        os.remove(brain_path)
        print(f'✅ RL Brain Reset: {brain_path}')
    else:
        print(f'ℹ️  RL Brain nicht gefunden (wird neu erstellt)')
    
    # 4. Clear symbol pauses
    result4 = await db.symbol_pauses.delete_many({})
    print(f'✅ Symbol Pauses gelöscht: {result4.deleted_count}')
    
    # 5. Clear distributed locks
    result5 = await db.distributed_locks.delete_many({})
    print(f'✅ Distributed Locks gelöscht: {result5.deleted_count}')
    
    print()
    print('═' * 50)
    print('🎉 History erfolgreich gelöscht!')
    print('   Die KI startet komplett frisch.')
    print('   Epsilon: 100% (volle Exploration)')
    print('   Trades: 0')
    print('   Win-Rate: 0%')
    print('═' * 50)
    print()
    print('⚠️  Vergessen Sie nicht, den Service neu zu starten:')
    print('   sudo systemctl restart reetrade-backend')
    
    client.close()

if __name__ == '__main__':
    asyncio.run(clear_history())
