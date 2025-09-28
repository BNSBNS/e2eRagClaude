from neo4j import GraphDatabase
from langchain.llms import OpenAI
from typing import List, Dict
import json

class GraphRAGService:
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.llm = OpenAI(temperature=0)
        
        self.entity_extraction_prompt = """
        Extract entities and relationships from this text.
        Return JSON format:
        {
            "entities": [
                {"name": "entity_name", "type": "Person|Organization|Location|Concept", "description": "brief description"}
            ],
            "relationships": [
                {"source": "source_entity", "target": "target_entity", "relationship": "relationship_type"}
            ]
        }
        
        Text: {text}
        """
    
    def extract_entities_and_relationships(self, text: str) -> Dict:
        try:
            prompt = self.entity_extraction_prompt.format(text=text)
            response = self.llm.invoke(prompt)
            return json.loads(response)
        except Exception:
            return {"entities": [], "relationships": []}
    
    def create_knowledge_graph(self, document_id: str, chunks: List[str], metadata: Dict = None):
        all_entities = []
        all_relationships = []
        
        for i, chunk in enumerate(chunks):
            extracted = self.extract_entities_and_relationships(chunk)
            
            for entity in extracted.get("entities", []):
                entity["document_id"] = document_id
                entity["chunk_index"] = i
                all_entities.append(entity)
            
            for rel in extracted.get("relationships", []):
                rel["document_id"] = document_id
                rel["chunk_index"] = i
                all_relationships.append(rel)
        
        self._create_graph_nodes(all_entities, document_id, metadata)
        self._create_graph_relationships(all_relationships)
        
        return {
            "document_id": document_id,
            "entities_created": len(all_entities),
            "relationships_created": len(all_relationships)
        }
    
    def _create_graph_nodes(self, entities: List[Dict], document_id: str, metadata: Dict):
        with self.driver.session() as session:
            session.run(
                """
                MERGE (d:Document {id: $document_id})
                SET d.metadata = $metadata, d.created_at = datetime()
                """,
                document_id=document_id, metadata=metadata or {}
            )
            
            for entity in entities:
                session.run(
                    f"""
                    MERGE (e:{entity['type']} {{name: $name}})
                    SET e.description = $description, e.document_id = $document_id
                    MERGE (d:Document {{id: $document_id}})
                    MERGE (d)-[:CONTAINS]->(e)
                    """,
                    name=entity['name'],
                    description=entity.get('description', ''),
                    document_id=document_id
                )
    
    def _create_graph_relationships(self, relationships: List[Dict]):
        with self.driver.session() as session:
            for rel in relationships:
                session.run(
                    f"""
                    MATCH (source {{name: $source_name}})
                    MATCH (target {{name: $target_name}})
                    MERGE (source)-[:{rel['relationship'].upper().replace(' ', '_')}]->(target)
                    """,
                    source_name=rel['source'],
                    target_name=rel['target']
                )
    
    def query_graph(self, query: str) -> Dict:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (e)
                WHERE toLower(e.name) CONTAINS toLower($query)
                   OR toLower(e.description) CONTAINS toLower($query)
                RETURN e LIMIT 10
                """,
                query=query
            )
            return [record["e"] for record in result]