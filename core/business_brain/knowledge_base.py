"""
Business Brain - Knowledge Base Module

Handles retrieval of business-specific information using RAG (Retrieval-Augmented Generation).
Keeps business knowledge separate from the conversation engine.
"""
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class BusinessKnowledge:
    """Business information structure"""
    business_id: str
    business_name: str
    industry: str
    description: str
    services: List[Dict[str, Any]]
    policies: Dict[str, Any]
    contact_info: Dict[str, Any]
    faqs: List[Dict[str, str]]
    operating_hours: Dict[str, str]
    locations: List[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]] = None


class KnowledgeBase:
    """
    Manages business knowledge for AI workers.
    
    In production, this would connect to:
    - Vector database (Pinecone, Weaviate, etc.) for semantic search
    - Business CRM for real-time data
    - Document store for policies/procedures
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.knowledge_cache: Dict[str, BusinessKnowledge] = {}
    
    async def load_business_knowledge(self, business_id: str) -> BusinessKnowledge:
        """
        Load complete business knowledge.
        """
        # Check cache first
        if business_id in self.knowledge_cache:
            return self.knowledge_cache[business_id]
        
        # In production: Load from database
        # For now: Load from JSON file
        knowledge_file = f"config/businesses/{business_id}.json"
        
        try:
            with open(knowledge_file, 'r') as f:
                data = json.load(f)
            
            knowledge = BusinessKnowledge(
                business_id=business_id,
                business_name=data['business_name'],
                industry=data['industry'],
                description=data['description'],
                services=data.get('services', []),
                policies=data.get('policies', {}),
                contact_info=data['contact_info'],
                faqs=data.get('faqs', []),
                operating_hours=data.get('operating_hours', {}),
                locations=data.get('locations', []),
                metadata=data.get('metadata')
            )
            
            self.knowledge_cache[business_id] = knowledge
            return knowledge
            
        except FileNotFoundError:
            logger.error(f"Knowledge file not found for business: {business_id}")
            raise
    
    async def query(
        self, 
        business_id: str, 
        query: str, 
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Semantic search over business knowledge.
        
        In production: Use vector database for similarity search
        For now: Simple keyword matching
        """
        knowledge = await self.load_business_knowledge(business_id)
        
        results = []
        query_lower = query.lower()
        
        # Search FAQs
        for faq in knowledge.faqs:
            question = faq['question'].lower()
            if any(word in question for word in query_lower.split()):
                results.append({
                    'type': 'faq',
                    'question': faq['question'],
                    'answer': faq['answer'],
                    'relevance': 0.9
                })
        
        # Search services
        for service in knowledge.services:
            if query_lower in service['name'].lower() or query_lower in service.get('description', '').lower():
                results.append({
                    'type': 'service',
                    'name': service['name'],
                    'description': service.get('description', ''),
                    'price': service.get('price'),
                    'relevance': 0.8
                })
        
        # Sort by relevance and return top_k
        results.sort(key=lambda x: x['relevance'], reverse=True)
        return results[:top_k]
    
    def get_summary(self, business_id: str) -> str:
        """
        Get concise business summary for system prompt.
        """
        if business_id not in self.knowledge_cache:
            # Synchronous load for quick access
            import asyncio
            asyncio.run(self.load_business_knowledge(business_id))
        
        knowledge = self.knowledge_cache[business_id]
        
        summary = f"""
{knowledge.business_name} - {knowledge.industry}

{knowledge.description}

Key Services:
{chr(10).join(f"- {s['name']}: {s.get('description', '')}" for s in knowledge.services[:5])}

Contact: {knowledge.contact_info.get('phone', 'N/A')}
Hours: {', '.join(f"{day}: {hours}" for day, hours in list(knowledge.operating_hours.items())[:3])}

Top FAQs:
{chr(10).join(f"- {faq['question']}" for faq in knowledge.faqs[:3])}
        """.strip()
        
        return summary
    
    async def get_operating_status(self, business_id: str) -> Dict[str, Any]:
        """
        Check if business is currently open.
        """
        from datetime import datetime
        
        knowledge = await self.load_business_knowledge(business_id)
        now = datetime.now()
        day = now.strftime('%A')
        current_time = now.strftime('%H:%M')
        
        day_hours = knowledge.operating_hours.get(day, 'Closed')
        
        if day_hours == 'Closed':
            return {
                'open': False,
                'message': f"We're closed on {day}s"
            }
        
        # Parse hours (assuming format like "09:00-17:00")
        try:
            open_time, close_time = day_hours.split('-')
            if open_time <= current_time <= close_time:
                return {
                    'open': True,
                    'closes_at': close_time,
                    'message': f"We're open until {close_time}"
                }
            else:
                return {
                    'open': False,
                    'opens_at': open_time,
                    'message': f"We're closed. We open at {open_time}"
                }
        except:
            return {'open': True, 'message': 'Hours vary'}
    
    async def get_service_details(
        self, 
        business_id: str, 
        service_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific service.
        """
        knowledge = await self.load_business_knowledge(business_id)
        
        for service in knowledge.services:
            if service_name.lower() in service['name'].lower():
                return service
        
        return None
