"""
Neo4j Graph Database Service
Manages knowledge graph creation and querying
"""

from typing import List, Dict, Optional
from neo4j import AsyncGraphDatabase
from core.config import settings
import structlog

logger = structlog.get_logger()


class Neo4jService:
    """Neo4j graph operations"""
    
    def __init__(self):
        self.driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
    
    async def close(self):
        """Close Neo4j connection"""
        await self.driver.close()
    
    async def create_document_graph(self, document_id: int, entities: List[Dict], relationships: List[Dict]):
        """Create knowledge graph from extracted entities and relationships"""
        async with self.driver.session() as session:
            # Create document node
            await session.run(
                """
                MERGE (d:Document {id: $doc_id})
                SET d.created_at = datetime()
                """,
                doc_id=document_id
            )
            
            # Create entity nodes
            for entity in entities:
                await session.run(
                    """
                    MERGE (e:Entity {name: $name, type: $type})
                    SET e.document_id = $doc_id
                    MERGE (d:Document {id: $doc_id})
                    MERGE (d)-[:CONTAINS]->(e)
                    """,
                    name=entity['name'],
                    type=entity['type'],
                    doc_id=document_id
                )
            
            # Create relationships
            for rel in relationships:
                await session.run(
                    """
                    MATCH (e1:Entity {name: $from_entity})
                    MATCH (e2:Entity {name: $to_entity})
                    WHERE e1.document_id = $doc_id AND e2.document_id = $doc_id
                    MERGE (e1)-[r:RELATES_TO {type: $rel_type}]->(e2)
                    """,
                    from_entity=rel['from'],
                    to_entity=rel['to'],
                    rel_type=rel['type'],
                    doc_id=document_id
                )
            
            logger.info("Graph created", document_id=document_id, 
                       entities=len(entities), relationships=len(relationships))
    
    async def query_graph(self, document_id: int, query: str) -> List[Dict]:
        """Query the knowledge graph"""
        async with self.driver.session() as session:
            # Simple path query - find related entities
            result = await session.run(
                """
                MATCH path = (e1:Entity)-[r*1..2]-(e2:Entity)
                WHERE e1.document_id = $doc_id 
                AND (e1.name CONTAINS $query OR e2.name CONTAINS $query)
                RETURN e1.name as entity1, e2.name as entity2, 
                       type(r[0]) as relationship
                LIMIT 10
                """,
                doc_id=document_id,
                query=query.lower()
            )
            
            paths = []
            async for record in result:
                paths.append({
                    'entity1': record['entity1'],
                    'entity2': record['entity2'],
                    'relationship': record['relationship']
                })
            
            return paths
    
    async def delete_document_graph(self, document_id: int):
        """Delete all nodes and relationships for a document"""
        async with self.driver.session() as session:
            await session.run(
                """
                MATCH (d:Document {id: $doc_id})
                OPTIONAL MATCH (d)-[:CONTAINS]->(e:Entity)
                DETACH DELETE d, e
                """,
                doc_id=document_id
            )
            logger.info("Graph deleted", document_id=document_id)


# Global instance
neo4j_service = Neo4jService()


async def get_neo4j_service():
    """Dependency to get Neo4j service"""
    return neo4j_service