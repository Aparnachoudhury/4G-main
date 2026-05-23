

"""
MongoDB database configuration and connection management
"""

import certifi
import motor.motor_asyncio
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class MongoDB:
    """MongoDB connection and collection management"""

    def __init__(self, connection_string: str,
                 database_name: str = "iwown_health"):

        self.connection_string = connection_string
        self.database_name = database_name

        self.client: Optional[
            motor.motor_asyncio.AsyncIOMotorClient
        ] = None

        self.database: Optional[
            motor.motor_asyncio.AsyncIOMotorDatabase
        ] = None

        self.collections = {
            'health_data': 'health_data',
            'alarms': 'alarms',
            'sos_calls': 'sos_calls',
            'device_info': 'device_info',
            'status': 'status',
            'sleep_data': 'sleep_data'
        }

    async def connect(self):
        """Connect to MongoDB"""

        try:

            self.client = motor.motor_asyncio.AsyncIOMotorClient(
                self.connection_string,
                tlsCAFile=certifi.where(),
                serverSelectionTimeoutMS=30000,
                connectTimeoutMS=30000,
                socketTimeoutMS=30000,
                maxPoolSize=10,
                minPoolSize=1,
                maxIdleTimeMS=30000
            )

            self.database = self.client[
                self.database_name
            ]

            # Test connection
            await self.client.admin.command('ping')

            logger.info(
                f"Connected to MongoDB database: {self.database_name}"
            )

            # Create indexes
            await self._create_indexes()

        except Exception as e:

            logger.error(
                f"Failed to connect to MongoDB: {e}"
            )

            logger.info(
                "Trying alternative connection..."
            )

            await self._try_alternative_connection()

    async def _try_alternative_connection(self):
        """Fallback connection"""

        try:

            self.client = motor.motor_asyncio.AsyncIOMotorClient(
                self.connection_string,
                tlsCAFile=certifi.where()
            )

            self.database = self.client[
                self.database_name
            ]

            await self.client.admin.command('ping')

            logger.info(
                f"Alternative connection successful: {self.database_name}"
            )

            await self._create_indexes()

        except Exception as e:

            logger.error(
                f"Alternative connection failed: {e}"
            )

            raise

    async def disconnect(self):
        """Close MongoDB connection"""

        if self.client:
            self.client.close()

            logger.info(
                "Disconnected from MongoDB"
            )

    async def _create_indexes(self):
        """Create indexes"""

        try:

            await self.database[
                self.collections['health_data']
            ].create_index([
                ("device_id", 1),
                ("timestamp", -1)
            ])

            await self.database[
                self.collections['alarms']
            ].create_index([
                ("device_id", 1),
                ("timestamp", -1)
            ])

            await self.database[
                self.collections['sos_calls']
            ].create_index([
                ("device_id", 1),
                ("timestamp", -1)
            ])

            await self.database[
                self.collections['device_info']
            ].create_index(
                [("device_id",1)],
                unique=True
            )

            await self.database[
                self.collections['status']
            ].create_index(
                [("device_id",1)],
                unique=True
            )

            await self.database[
                self.collections['sleep_data']
            ].create_index([
                ("device_id",1),
                ("sleep_date",-1)
            ])

            logger.info(
                "Database indexes created"
            )

        except Exception as e:

            logger.error(
                f"Failed creating indexes: {e}"
            )

    def get_collection(self, collection_name: str):

        if self.database is None:
            raise RuntimeError(
                "Database not connected"
            )

        if collection_name not in self.collections:
            raise ValueError(
                f"Unknown collection: {collection_name}"
            )

        return self.database[
            self.collections[collection_name]
        ]
# Global database instance
mongodb: Optional[MongoDB] = None

async def get_database() -> MongoDB:
    """Get the global database instance"""
    if not mongodb:
        raise RuntimeError("Database not initialized")
    return mongodb

async def init_database(connection_string: str, database_name: str = "iwown_health"):
    """Initialize the global database instance"""
    global mongodb
    mongodb = MongoDB(connection_string, database_name)
    await mongodb.connect()
    return mongodb