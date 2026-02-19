"""
Enhanced Question Generation Agent with Groq LLM Integration
Generates contextual, adaptive questions based on conversation history and enhanced knowledge base
"""

import json
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

from state_schema import AgentState, GapEntry
from agents.document_processor import EnhancedKnowledgeBase

class QuestionPriority(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class StakeholderType(Enum):
    BUSINESS = "business"
    TECHNICAL = "technical"
    EXECUTIVE = "executive"
    END_USER = "end_user"

@dataclass
class ContextualQuestion:
    id: str
    text: str
    category: str
    priority: QuestionPriority
    stakeholder_type: StakeholderType
    context: str
    linked_gaps: List[str]
    follow_up_questions: List[str]
    expected_answer_type: str  # "text", "choice", "numeric", "boolean"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'text': self.text,
            'category': self.category,
            'priority': self.priority.value,
            'stakeholder_type': self.stakeholder_type.value,
            'context': self.context,
            'linked_gaps': self.linked_gaps,
            'follow_up_questions': self.follow_up_questions,
            'expected_answer_type': self.expected_answer_type
        }

@dataclass
class ConversationHistory:
    messages: List[Dict[str, str]]
    requirements_discovered: List[Dict[str, Any]]
    questions_asked: List[ContextualQuestion]
    answers_received: List[Dict[str, Any]]
    stakeholder_profile: Dict[str, Any]
    
    def get_context_summary(self) -> str:
        """Get a summary of the conversation for LLM context"""
        summary = []
        
        # Add conversation messages
        for msg in self.messages[-5:]:  # Last 5 messages for context
            summary.append(f"{msg.get('role', 'user')}: {msg.get('content', '')}")
        
        # Add discovered requirements
        if self.requirements_discovered:
            summary.append("\nRequirements discovered:")
            for req in self.requirements_discovered[-3:]:  # Last 3 requirements
                summary.append(f"- {req.get('type', 'unknown')}: {req.get('description', '')}")
        
        # Add recent questions and answers
        if self.questions_asked:
            summary.append("\nRecent questions:")
            for q in self.questions_asked[-2:]:  # Last 2 questions
                summary.append(f"Q: {q.text}")
        
        if self.answers_received:
            summary.append("Recent answers:")
            for a in self.answers_received[-2:]:  # Last 2 answers
                summary.append(f"A: {a.get('answer', '')}")
        
        return "\n".join(summary)

class GroqEnhancedQuestionAgent:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.fallback_questions = self._load_fallback_questions()
    
    def _load_fallback_questions(self) -> Dict[str, List[str]]:
        """Load fallback questions for when LLM is not available"""
        return {
            "missing_detail": [
                "Can you provide more specific details about this requirement?",
                "What are the exact criteria for this feature?",
                "How should this behave in edge cases?"
            ],
            "vague_term": [
                "Can you define what you mean by this term more precisely?",
                "What specific metrics or criteria apply here?",
                "Can you give concrete examples of this requirement?"
            ],
            "conflict": [
                "There seems to be a contradiction here. Can you clarify?",
                "How should the system behave when these requirements conflict?",
                "Which requirement takes priority in this scenario?"
            ],
            "implicit_requirement": [
                "I've inferred this requirement from our conversation. Is this correct?",
                "Should this implied feature be included in the scope?",
                "Can you confirm and elaborate on this requirement?"
            ]
        }
    
    def generate_contextual_questions(self, 
                                    conversation_history: ConversationHistory,
                                    detected_gaps: List[GapEntry],
                                    enhanced_knowledge: EnhancedKnowledgeBase,
                                    max_questions: int = 3) -> List[ContextualQuestion]:
        """
        Generate highly contextual questions using Groq LLM
        """
        
        if not self.llm_client or not hasattr(self.llm_client, 'generate_text'):
            return self._generate_fallback_questions(detected_gaps, max_questions)
        
        try:
            # Prepare context for LLM
            context = self._prepare_llm_context(
                conversation_history, detected_gaps, enhanced_knowledge
            )
            
            # Generate questions using LLM
            llm_questions = self._generate_llm_questions(context, max_questions)
            
            # Parse and structure the questions
            structured_questions = self._parse_llm_response(llm_questions, detected_gaps)
            
            # Enhance with domain knowledge
            enhanced_questions = self._enhance_with_domain_knowledge(
                structured_questions, enhanced_knowledge
            )
            
            return enhanced_questions[:max_questions]
            
        except Exception as e:
            print(f"LLM question generation failed: {e}")
            return self._generate_fallback_questions(detected_gaps, max_questions)
    
    def _prepare_llm_context(self, 
                           conversation_history: ConversationHistory,
                           detected_gaps: List[GapEntry],
                           enhanced_knowledge: EnhancedKnowledgeBase) -> Dict[str, Any]:
        """Prepare comprehensive context for LLM"""
        
        context = {
            "conversation_summary": conversation_history.get_context_summary(),
            "stakeholder_profile": conversation_history.stakeholder_profile,
            "detected_gaps": [
                {
                    "id": gap.id,
                    "category": gap.category,
                    "description": gap.description,
                    "severity": gap.severity,
                    "context": gap.context
                }
                for gap in detected_gaps
            ],
            "domain_patterns": enhanced_knowledge.get_relevant_patterns(),
            "similar_projects": enhanced_knowledge.similar_project_patterns[:2],  # Limit for context
            "company_standards": enhanced_knowledge.company_standards
        }
        
        return context
    
    def _generate_llm_questions(self, context: Dict[str, Any], max_questions: int) -> str:
        """Generate questions using Groq LLM"""
        
        system_prompt = """You are an expert business analyst specializing in requirement elicitation. 
        Your job is to generate highly specific, contextual questions that will:
        1. Fill critical requirement gaps
        2. Clarify ambiguous statements  
        3. Uncover implicit business logic
        4. Ensure completeness based on domain knowledge
        
        Generate questions that are:
        - Specific and actionable
        - Contextually relevant to the conversation
        - Appropriate for the stakeholder type
        - Prioritized by business impact
        - Easy for non-technical clients to answer"""
        
        user_prompt = f"""
        Based on the following context, generate {max_questions} highly specific questions to advance the requirements gathering:

        CONVERSATION CONTEXT:
        {context['conversation_summary']}

        STAKEHOLDER PROFILE:
        {json.dumps(context['stakeholder_profile'], indent=2)}

        DETECTED GAPS:
        {json.dumps(context['detected_gaps'], indent=2)}

        DOMAIN KNOWLEDGE AVAILABLE:
        {json.dumps(context['domain_patterns'], indent=2)}

        SIMILAR PROJECTS:
        {json.dumps(context['similar_projects'], indent=2)}

        For each question, provide:
        1. The question text
        2. Category (functional, non_functional, business_logic, technical, compliance)
        3. Priority (critical, high, medium, low)
        4. Stakeholder type (business, technical, executive, end_user)
        5. Context/reasoning for the question
        6. Expected answer type (text, choice, numeric, boolean)

        Format as JSON array with these fields: text, category, priority, stakeholder_type, context, expected_answer_type
        """
        
        try:
            response = self.llm_client.generate_text(
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            return response
        except Exception as e:
            raise Exception(f"LLM generation failed: {e}")
    
    def _parse_llm_response(self, llm_response: str, detected_gaps: List[GapEntry]) -> List[ContextualQuestion]:
        """Parse LLM response into structured questions"""
        
        questions = []
        
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\[.*\]', llm_response, re.DOTALL)
            if json_match:
                questions_data = json.loads(json_match.group())
            else:
                # Fallback: parse line by line
                questions_data = self._parse_text_response(llm_response)
            
            for i, q_data in enumerate(questions_data):
                question = ContextualQuestion(
                    id=f"llm_q_{i+1}",
                    text=q_data.get('text', ''),
                    category=q_data.get('category', 'general'),
                    priority=QuestionPriority(q_data.get('priority', 'medium')),
                    stakeholder_type=StakeholderType(q_data.get('stakeholder_type', 'business')),
                    context=q_data.get('context', ''),
                    linked_gaps=[gap.id for gap in detected_gaps if gap.category in q_data.get('category', '')],
                    follow_up_questions=[],
                    expected_answer_type=q_data.get('expected_answer_type', 'text')
                )
                questions.append(question)
                
        except Exception as e:
            print(f"Failed to parse LLM response: {e}")
            # Return fallback questions
            return self._generate_fallback_questions(detected_gaps, 3)
        
        return questions
    
    def _parse_text_response(self, text_response: str) -> List[Dict[str, Any]]:
        """Parse text response when JSON parsing fails"""
        questions = []
        
        # Look for question patterns
        question_patterns = [
            r'(?:Question|Q)\s*\d*\s*[:\-]\s*(.+?)(?=\n|$)',
            r'^\d+\.\s*(.+?)(?=\n|$)',
            r'^[\-\*]\s*(.+?)(?=\n|$)'
        ]
        
        for pattern in question_patterns:
            matches = re.findall(pattern, text_response, re.MULTILINE | re.IGNORECASE)
            for match in matches:
                if len(match.strip()) > 10:  # Filter out very short matches
                    questions.append({
                        'text': match.strip(),
                        'category': 'general',
                        'priority': 'medium',
                        'stakeholder_type': 'business',
                        'context': 'Generated from text parsing',
                        'expected_answer_type': 'text'
                    })
        
        return questions[:3]  # Limit to 3 questions
    
    def _enhance_with_domain_knowledge(self, 
                                     questions: List[ContextualQuestion],
                                     enhanced_knowledge: EnhancedKnowledgeBase) -> List[ContextualQuestion]:
        """Enhance questions with domain-specific knowledge"""
        
        enhanced_questions = []
        
        for question in questions:
            # Add follow-up questions based on domain patterns
            follow_ups = self._generate_follow_up_questions(question, enhanced_knowledge)
            question.follow_up_questions = follow_ups
            
            # Adjust priority based on domain importance
            question.priority = self._adjust_priority_by_domain(question, enhanced_knowledge)
            
            enhanced_questions.append(question)
        
        return enhanced_questions
    
    def _generate_follow_up_questions(self, 
                                    question: ContextualQuestion,
                                    enhanced_knowledge: EnhancedKnowledgeBase) -> List[str]:
        """Generate follow-up questions based on domain knowledge"""
        
        follow_ups = []
        
        # Check if question relates to common patterns
        if 'authentication' in question.text.lower() or 'login' in question.text.lower():
            follow_ups.extend([
                "What should happen if a user forgets their password?",
                "Should there be multi-factor authentication?",
                "How long should user sessions last?"
            ])
        
        if 'payment' in question.text.lower() or 'billing' in question.text.lower():
            follow_ups.extend([
                "What payment methods should be supported?",
                "How should failed payments be handled?",
                "Should there be subscription management features?"
            ])
        
        if 'notification' in question.text.lower() or 'email' in question.text.lower():
            follow_ups.extend([
                "Should users be able to opt out of notifications?",
                "What notification channels are needed (email, SMS, push)?",
                "How frequently should notifications be sent?"
            ])
        
        # Add domain-specific follow-ups from enhanced knowledge
        for pattern_key, pattern_data in enhanced_knowledge.domain_specific_patterns.items():
            if isinstance(pattern_data, dict) and 'common_questions' in pattern_data:
                follow_ups.extend(pattern_data['common_questions'][:2])  # Limit to 2 per pattern
        
        return follow_ups[:3]  # Limit total follow-ups
    
    def _adjust_priority_by_domain(self, 
                                 question: ContextualQuestion,
                                 enhanced_knowledge: EnhancedKnowledgeBase) -> QuestionPriority:
        """Adjust question priority based on domain knowledge"""
        
        # Check compliance requirements
        for compliance_rule in enhanced_knowledge.compliance_requirements:
            if any(keyword in question.text.lower() for keyword in ['security', 'privacy', 'data', 'compliance']):
                return QuestionPriority.CRITICAL
        
        # Check company standards
        for standard_name, standard_data in enhanced_knowledge.company_standards.items():
            if 'mandatory_fields' in standard_data:
                for field in standard_data['mandatory_fields']:
                    if field.lower() in question.text.lower():
                        return QuestionPriority.HIGH
        
        return question.priority  # Keep original priority if no domain adjustments
    
    def _generate_fallback_questions(self, detected_gaps: List[GapEntry], max_questions: int) -> List[ContextualQuestion]:
        """Generate fallback questions when LLM is not available"""
        
        questions = []
        
        for i, gap in enumerate(detected_gaps[:max_questions]):
            category_questions = self.fallback_questions.get(gap.category, ["Can you provide more details?"])
            question_text = category_questions[0] if category_questions else "Can you provide more details?"
            
            question = ContextualQuestion(
                id=f"fallback_q_{i+1}",
                text=question_text,
                category=gap.category,
                priority=QuestionPriority(gap.severity),
                stakeholder_type=StakeholderType.BUSINESS,
                context=f"Generated from gap: {gap.description}",
                linked_gaps=[gap.id],
                follow_up_questions=[],
                expected_answer_type='text'
            )
            questions.append(question)
        
        return questions
    
    def prioritize_questions(self, questions: List[ContextualQuestion]) -> List[ContextualQuestion]:
        """Prioritize questions by business impact and urgency"""
        
        priority_order = {
            QuestionPriority.CRITICAL: 0,
            QuestionPriority.HIGH: 1,
            QuestionPriority.MEDIUM: 2,
            QuestionPriority.LOW: 3
        }
        
        return sorted(questions, key=lambda q: priority_order[q.priority])
    
    def tailor_for_stakeholder(self, 
                             questions: List[ContextualQuestion],
                             stakeholder_type: StakeholderType) -> List[ContextualQuestion]:
        """Tailor questions for specific stakeholder type"""
        
        tailored_questions = []
        
        for question in questions:
            # Skip questions not appropriate for stakeholder
            if question.stakeholder_type != stakeholder_type and question.stakeholder_type != StakeholderType.BUSINESS:
                continue
            
            # Adjust language based on stakeholder
            if stakeholder_type == StakeholderType.TECHNICAL:
                question.text = self._make_technical_language(question.text)
            elif stakeholder_type == StakeholderType.EXECUTIVE:
                question.text = self._make_executive_language(question.text)
            elif stakeholder_type == StakeholderType.END_USER:
                question.text = self._make_user_friendly_language(question.text)
            
            tailored_questions.append(question)
        
        return tailored_questions
    
    def _make_technical_language(self, question_text: str) -> str:
        """Adjust question for technical stakeholders"""
        # Add technical context where appropriate
        if 'performance' in question_text.lower():
            return question_text + " (Please specify latency, throughput, and scalability requirements.)"
        if 'security' in question_text.lower():
            return question_text + " (Please include authentication, authorization, and data protection requirements.)"
        return question_text
    
    def _make_executive_language(self, question_text: str) -> str:
        """Adjust question for executive stakeholders"""
        # Focus on business impact
        if 'feature' in question_text.lower():
            return question_text + " (How does this impact business objectives and ROI?)"
        return question_text
    
    def _make_user_friendly_language(self, question_text: str) -> str:
        """Adjust question for end-user stakeholders"""
        # Simplify technical terms
        replacements = {
            'authentication': 'login process',
            'functionality': 'feature',
            'implementation': 'how it works',
            'integration': 'connection with other systems'
        }
        
        for tech_term, simple_term in replacements.items():
            question_text = question_text.replace(tech_term, simple_term)
        
        return question_text