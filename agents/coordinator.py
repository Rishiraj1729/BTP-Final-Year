"""
Agent Coordinator - Autonomous Decision Making and Agent Orchestration
Coordinates all agents and makes autonomous decisions about conversation flow
"""

import json
import asyncio
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
import time
import uuid

from state_schema import AgentState
from agents.document_processor import DocumentProcessor, EnhancedKnowledgeBase
from agents.groq_enhanced_questions import GroqEnhancedQuestionAgent, ConversationHistory, ContextualQuestion, StakeholderType
from agents.continuous_gap_detector import ContinuousGapDetector, GapAnalysisResult

class ConversationPhase(Enum):
    INITIALIZATION = "initialization"
    DISCOVERY = "discovery"
    REFINEMENT = "refinement"
    VALIDATION = "validation"
    COMPLETION = "completion"

class DecisionType(Enum):
    CONTINUE_QUESTIONING = "continue_questioning"
    CHANGE_FOCUS = "change_focus"
    ESCALATE_PRIORITY = "escalate_priority"
    GENERATE_PRD = "generate_prd"
    REQUEST_CLARIFICATION = "request_clarification"
    SUGGEST_BREAK = "suggest_break"

@dataclass
class ConversationState:
    session_id: str
    phase: ConversationPhase
    stakeholder_profile: Dict[str, Any]
    requirements_discovered: List[Dict[str, Any]]
    questions_asked: List[ContextualQuestion]
    answers_received: List[Dict[str, Any]]
    gaps_identified: List[Dict[str, Any]]
    completeness_scores: Dict[str, float]
    conversation_duration: float
    last_activity: float
    enhanced_knowledge: Optional[EnhancedKnowledgeBase]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'session_id': self.session_id,
            'phase': self.phase.value,
            'stakeholder_profile': self.stakeholder_profile,
            'requirements_discovered': self.requirements_discovered,
            'questions_asked': [q.to_dict() if hasattr(q, 'to_dict') else q for q in self.questions_asked],
            'answers_received': self.answers_received,
            'gaps_identified': self.gaps_identified,
            'completeness_scores': self.completeness_scores,
            'conversation_duration': self.conversation_duration,
            'last_activity': self.last_activity,
            'has_enhanced_knowledge': self.enhanced_knowledge is not None
        }

@dataclass
class AgentExecutionPlan:
    agents_to_run: List[str]
    execution_order: List[str]
    parallel_groups: List[List[str]]
    expected_duration: float
    priority: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class FlowDecision:
    decision_type: DecisionType
    reasoning: str
    next_actions: List[str]
    priority_level: str
    estimated_time: float
    confidence_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'decision_type': self.decision_type.value,
            'reasoning': self.reasoning,
            'next_actions': self.next_actions,
            'priority_level': self.priority_level,
            'estimated_time': self.estimated_time,
            'confidence_score': self.confidence_score
        }

@dataclass
class ConversationUpdate:
    session_id: str
    timestamp: float
    phase: ConversationPhase
    agent_results: Dict[str, Any]
    next_questions: List[ContextualQuestion]
    completeness_scores: Dict[str, float]
    flow_decision: FlowDecision
    recommendations: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'session_id': self.session_id,
            'timestamp': self.timestamp,
            'phase': self.phase.value,
            'agent_results': self.agent_results,
            'next_questions': [q.to_dict() if hasattr(q, 'to_dict') else q for q in self.next_questions],
            'completeness_scores': self.completeness_scores,
            'flow_decision': self.flow_decision.to_dict() if hasattr(self.flow_decision, 'to_dict') else self.flow_decision,
            'recommendations': self.recommendations
        }

class AutonomousDecisionEngine:
    def __init__(self):
        self.decision_thresholds = {
            'completeness_target': 0.85,
            'clarity_target': 0.80,
            'business_readiness_target': 0.75,
            'technical_readiness_target': 0.70,
            'max_questions_per_session': 15,
            'max_session_duration': 3600,  # 1 hour
            'inactivity_threshold': 300,   # 5 minutes
            'confidence_threshold': 0.7
        }
    
    def create_execution_plan(self, 
                            conversation_state: ConversationState,
                            input_data: Dict[str, Any]) -> AgentExecutionPlan:
        """Create an execution plan for agents based on current state"""
        
        agents_to_run = []
        execution_order = []
        parallel_groups = []
        
        # Always run gap detector to assess current state
        agents_to_run.append('gap_detector')
        execution_order.append('gap_detector')
        
        # Determine what other agents to run based on phase and state
        if conversation_state.phase == ConversationPhase.INITIALIZATION:
            agents_to_run.extend(['transcription', 'analyzer'])
            execution_order.extend(['transcription', 'analyzer'])
            parallel_groups.append(['transcription', 'analyzer'])
            
        elif conversation_state.phase == ConversationPhase.DISCOVERY:
            if input_data.get('new_input'):
                agents_to_run.extend(['transcription', 'analyzer'])
                execution_order.extend(['transcription', 'analyzer'])
            agents_to_run.append('question_generator')
            execution_order.append('question_generator')
            
        elif conversation_state.phase == ConversationPhase.REFINEMENT:
            agents_to_run.extend(['analyzer', 'question_generator'])
            execution_order.extend(['analyzer', 'question_generator'])
            parallel_groups.append(['analyzer', 'question_generator'])
            
        elif conversation_state.phase == ConversationPhase.VALIDATION:
            agents_to_run.extend(['analyzer', 'documentation'])
            execution_order.extend(['analyzer', 'documentation'])
            
        # Estimate execution duration
        estimated_duration = len(agents_to_run) * 2.0  # 2 seconds per agent average
        
        return AgentExecutionPlan(
            agents_to_run=agents_to_run,
            execution_order=execution_order,
            parallel_groups=parallel_groups,
            expected_duration=estimated_duration,
            priority='high' if conversation_state.phase in [ConversationPhase.INITIALIZATION, ConversationPhase.DISCOVERY] else 'medium'
        )
    
    def decide_next_action(self, 
                          agent_results: Dict[str, Any],
                          conversation_state: ConversationState) -> FlowDecision:
        """Make autonomous decision about next action"""
        
        gap_analysis = agent_results.get('gap_analysis')
        if not gap_analysis:
            return self._default_decision(conversation_state)
        
        # Extract scores
        completeness = gap_analysis.get('completeness_score', 0.0)
        clarity = gap_analysis.get('clarity_score', 0.0)
        business_readiness = gap_analysis.get('business_readiness_score', 0.0)
        technical_readiness = gap_analysis.get('technical_readiness_score', 0.0)
        
        # Check session constraints
        if self._should_suggest_break(conversation_state):
            return FlowDecision(
                decision_type=DecisionType.SUGGEST_BREAK,
                reasoning="Session has been running for a long time or user seems fatigued",
                next_actions=['suggest_break', 'save_progress'],
                priority_level='medium',
                estimated_time=0.0,
                confidence_score=0.9
            )
        
        # Check if ready for completion
        if self._ready_for_completion(completeness, clarity, business_readiness, technical_readiness, conversation_state):
            return FlowDecision(
                decision_type=DecisionType.GENERATE_PRD,
                reasoning="All scores meet thresholds and sufficient information gathered",
                next_actions=['generate_prd', 'final_validation'],
                priority_level='high',
                estimated_time=30.0,
                confidence_score=0.95
            )
        
        # Determine focus area and next steps
        focus_area = gap_analysis.get('next_focus_area', 'completeness')
        
        if focus_area == 'completeness':
            return self._decide_completeness_action(gap_analysis, conversation_state)
        elif focus_area == 'clarity':
            return self._decide_clarity_action(gap_analysis, conversation_state)
        elif focus_area == 'business_readiness':
            return self._decide_business_action(gap_analysis, conversation_state)
        elif focus_area == 'technical_readiness':
            return self._decide_technical_action(gap_analysis, conversation_state)
        else:
            return self._default_decision(conversation_state)
    
    def _should_suggest_break(self, conversation_state: ConversationState) -> bool:
        """Check if should suggest a break"""
        current_time = time.time()
        
        # Check session duration
        if conversation_state.conversation_duration > self.decision_thresholds['max_session_duration']:
            return True
        
        # Check inactivity
        if current_time - conversation_state.last_activity > self.decision_thresholds['inactivity_threshold']:
            return True
        
        # Check question fatigue
        if len(conversation_state.questions_asked) > self.decision_thresholds['max_questions_per_session']:
            return True
        
        return False
    
    def _ready_for_completion(self, completeness: float, clarity: float, 
                            business_readiness: float, technical_readiness: float,
                            conversation_state: ConversationState) -> bool:
        """Check if ready for PRD generation"""
        
        scores_meet_threshold = (
            completeness >= self.decision_thresholds['completeness_target'] and
            clarity >= self.decision_thresholds['clarity_target'] and
            business_readiness >= self.decision_thresholds['business_readiness_target'] and
            technical_readiness >= self.decision_thresholds['technical_readiness_target']
        )
        
        sufficient_requirements = len(conversation_state.requirements_discovered) >= 5
        sufficient_interaction = len(conversation_state.answers_received) >= 3
        
        return scores_meet_threshold and sufficient_requirements and sufficient_interaction
    
    def _decide_completeness_action(self, gap_analysis: Dict[str, Any], conversation_state: ConversationState) -> FlowDecision:
        """Decide action when completeness is the focus"""
        
        return FlowDecision(
            decision_type=DecisionType.CONTINUE_QUESTIONING,
            reasoning="Completeness score below threshold, need more requirements",
            next_actions=['generate_discovery_questions', 'focus_on_missing_areas'],
            priority_level='high',
            estimated_time=10.0,
            confidence_score=0.85
        )
    
    def _decide_clarity_action(self, gap_analysis: Dict[str, Any], conversation_state: ConversationState) -> FlowDecision:
        """Decide action when clarity is the focus"""
        
        return FlowDecision(
            decision_type=DecisionType.REQUEST_CLARIFICATION,
            reasoning="Clarity score below threshold, need to clarify vague requirements",
            next_actions=['generate_clarification_questions', 'focus_on_vague_terms'],
            priority_level='high',
            estimated_time=8.0,
            confidence_score=0.80
        )
    
    def _decide_business_action(self, gap_analysis: Dict[str, Any], conversation_state: ConversationState) -> FlowDecision:
        """Decide action when business readiness is the focus"""
        
        return FlowDecision(
            decision_type=DecisionType.CHANGE_FOCUS,
            reasoning="Business readiness low, need to focus on business logic and workflows",
            next_actions=['generate_business_questions', 'focus_on_workflows'],
            priority_level='high',
            estimated_time=12.0,
            confidence_score=0.75
        )
    
    def _decide_technical_action(self, gap_analysis: Dict[str, Any], conversation_state: ConversationState) -> FlowDecision:
        """Decide action when technical readiness is the focus"""
        
        return FlowDecision(
            decision_type=DecisionType.CHANGE_FOCUS,
            reasoning="Technical readiness low, need to focus on technical requirements",
            next_actions=['generate_technical_questions', 'focus_on_nfrs'],
            priority_level='medium',
            estimated_time=10.0,
            confidence_score=0.70
        )
    
    def _default_decision(self, conversation_state: ConversationState) -> FlowDecision:
        """Default decision when unable to determine specific action"""
        
        return FlowDecision(
            decision_type=DecisionType.CONTINUE_QUESTIONING,
            reasoning="Continue with general questioning to gather more information",
            next_actions=['generate_general_questions'],
            priority_level='medium',
            estimated_time=5.0,
            confidence_score=0.60
        )

class AgentCoordinator:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.decision_engine = AutonomousDecisionEngine()
        self.active_sessions: Dict[str, ConversationState] = {}
        
        # Initialize agents
        self.agents = {
            'document_processor': DocumentProcessor(llm_client),
            'gap_detector': ContinuousGapDetector(llm_client),
            'question_generator': GroqEnhancedQuestionAgent(llm_client)
        }
    
    async def initialize_conversation(self, 
                                   context: Dict[str, Any],
                                   stakeholders: List[Dict[str, Any]] = None,
                                   domain: str = None,
                                   documents: List[Dict[str, str]] = None) -> ConversationState:
        """Initialize a new conversation session"""
        
        session_id = str(uuid.uuid4())
        current_time = time.time()
        
        # Process documents if provided
        enhanced_knowledge = None
        if documents:
            enhanced_knowledge = self.agents['document_processor'].process_user_documents(documents)
        
        # Determine stakeholder profile
        stakeholder_profile = self._determine_stakeholder_profile(stakeholders, context)
        
        conversation_state = ConversationState(
            session_id=session_id,
            phase=ConversationPhase.INITIALIZATION,
            stakeholder_profile=stakeholder_profile,
            requirements_discovered=[],
            questions_asked=[],
            answers_received=[],
            gaps_identified=[],
            completeness_scores={},
            conversation_duration=0.0,
            last_activity=current_time,
            enhanced_knowledge=enhanced_knowledge
        )
        
        self.active_sessions[session_id] = conversation_state
        
        return conversation_state
    
    async def process_conversation_stream(self, 
                                       session_id: str,
                                       input_stream: Any) -> ConversationUpdate:
        """Process streaming conversation input"""
        
        conversation_state = self.active_sessions.get(session_id)
        if not conversation_state:
            raise ValueError(f"Session {session_id} not found")
        
        current_time = time.time()
        conversation_state.last_activity = current_time
        conversation_state.conversation_duration = current_time - (current_time - conversation_state.conversation_duration)
        
        # Create execution plan
        execution_plan = self.decision_engine.create_execution_plan(
            conversation_state, {'new_input': input_stream}
        )
        
        # Execute agents
        agent_results = await self._execute_agents_parallel(execution_plan, conversation_state, input_stream)
        
        # Make autonomous decision
        flow_decision = self.decision_engine.decide_next_action(agent_results, conversation_state)
        
        # Generate next questions based on decision
        next_questions = await self._generate_next_questions(flow_decision, agent_results, conversation_state)
        
        # Update conversation state
        self._update_conversation_state(conversation_state, agent_results, next_questions, flow_decision)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(flow_decision, agent_results, conversation_state)
        
        return ConversationUpdate(
            session_id=session_id,
            timestamp=current_time,
            phase=conversation_state.phase,
            agent_results=agent_results,
            next_questions=next_questions,
            completeness_scores=conversation_state.completeness_scores,
            flow_decision=flow_decision,
            recommendations=recommendations
        )
    
    async def _execute_agents_parallel(self, 
                                     execution_plan: AgentExecutionPlan,
                                     conversation_state: ConversationState,
                                     input_data: Any) -> Dict[str, Any]:
        """Execute agents in parallel where possible"""
        
        results = {}
        
        # Run gap detector first (always needed)
        if 'gap_detector' in execution_plan.agents_to_run:
            gap_analysis = self._run_gap_detector(conversation_state, input_data)
            results['gap_analysis'] = gap_analysis
        
        # Run other agents based on plan
        tasks = []
        for agent_name in execution_plan.agents_to_run:
            if agent_name != 'gap_detector':  # Already run
                task = self._run_agent_async(agent_name, conversation_state, input_data, results)
                tasks.append((agent_name, task))
        
        # Execute tasks
        if tasks:
            task_results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
            for (agent_name, _), result in zip(tasks, task_results):
                if not isinstance(result, Exception):
                    results[agent_name] = result
                else:
                    print(f"Agent {agent_name} failed: {result}")
                    results[agent_name] = {'error': str(result)}
        
        return results
    
    def _run_gap_detector(self, conversation_state: ConversationState, input_data: Any) -> Dict[str, Any]:
        """Run gap detector synchronously"""
        
        try:
            # Create conversation history
            conv_history = ConversationHistory(
                messages=[],  # Would be populated from input_data in real implementation
                requirements_discovered=conversation_state.requirements_discovered,
                questions_asked=conversation_state.questions_asked,
                answers_received=conversation_state.answers_received,
                stakeholder_profile=conversation_state.stakeholder_profile
            )
            
            # Run gap analysis
            gap_analysis = self.agents['gap_detector'].continuous_gap_analysis(
                current_requirements=conversation_state.requirements_discovered,
                conversation_history=conv_history,
                enhanced_knowledge=conversation_state.enhanced_knowledge or EnhancedKnowledgeBase(
                    master_reference={}, user_documents=[], domain_specific_patterns={},
                    company_standards={}, similar_project_patterns=[], compliance_requirements=[]
                )
            )
            
            return {
                'completeness_score': gap_analysis.completeness_score,
                'clarity_score': gap_analysis.clarity_score,
                'business_readiness_score': gap_analysis.business_readiness_score,
                'technical_readiness_score': gap_analysis.technical_readiness_score,
                'needs_more_questions': gap_analysis.needs_more_questions,
                'next_focus_area': gap_analysis.next_focus_area,
                'gaps': [gap.to_dict() for gap in gap_analysis.all_gaps]
            }
            
        except Exception as e:
            print(f"Gap detector failed: {e}")
            return {
                'completeness_score': 0.5,
                'clarity_score': 0.5,
                'business_readiness_score': 0.5,
                'technical_readiness_score': 0.5,
                'needs_more_questions': True,
                'next_focus_area': 'completeness',
                'gaps': [],
                'error': str(e)
            }
    
    async def _run_agent_async(self, 
                             agent_name: str,
                             conversation_state: ConversationState,
                             input_data: Any,
                             previous_results: Dict[str, Any]) -> Dict[str, Any]:
        """Run an agent asynchronously"""
        
        try:
            if agent_name == 'question_generator':
                return await self._run_question_generator(conversation_state, previous_results)
            else:
                # Placeholder for other agents
                return {'status': 'completed', 'agent': agent_name}
                
        except Exception as e:
            return {'error': str(e), 'agent': agent_name}
    
    async def _run_question_generator(self, 
                                    conversation_state: ConversationState,
                                    previous_results: Dict[str, Any]) -> Dict[str, Any]:
        """Run question generator agent"""
        
        try:
            # Create conversation history
            conv_history = ConversationHistory(
                messages=[],
                requirements_discovered=conversation_state.requirements_discovered,
                questions_asked=conversation_state.questions_asked,
                answers_received=conversation_state.answers_received,
                stakeholder_profile=conversation_state.stakeholder_profile
            )
            
            # Get gaps from previous results
            gap_analysis = previous_results.get('gap_analysis', {})
            gaps = gap_analysis.get('gaps', [])
            
            # Convert gaps to GapEntry objects (simplified)
            from agents.continuous_gap_detector import EnhancedGap, GapCategory, GapSeverity
            gap_objects = []
            for gap_dict in gaps:
                gap_obj = EnhancedGap(
                    id=gap_dict.get('id', ''),
                    category=GapCategory(gap_dict.get('category', 'missing_detail')),
                    severity=GapSeverity(gap_dict.get('severity', 'medium')),
                    description=gap_dict.get('description', ''),
                    context=gap_dict.get('context', ''),
                    affected_requirements=gap_dict.get('affected_requirements', []),
                    suggested_questions=gap_dict.get('suggested_questions', []),
                    resolution_priority=gap_dict.get('resolution_priority', 3),
                    business_impact=gap_dict.get('business_impact', ''),
                    source=gap_dict.get('source', 'unknown')
                )
                gap_objects.append(gap_obj)
            
            # Generate questions
            questions = self.agents['question_generator'].generate_contextual_questions(
                conversation_history=conv_history,
                detected_gaps=gap_objects,
                enhanced_knowledge=conversation_state.enhanced_knowledge or EnhancedKnowledgeBase(
                    master_reference={}, user_documents=[], domain_specific_patterns={},
                    company_standards={}, similar_project_patterns=[], compliance_requirements=[]
                ),
                max_questions=3
            )
            
            return {
                'questions': [q.to_dict() for q in questions],
                'question_count': len(questions)
            }
            
        except Exception as e:
            print(f"Question generator failed: {e}")
            return {'error': str(e), 'questions': []}
    
    async def _generate_next_questions(self, 
                                     flow_decision: FlowDecision,
                                     agent_results: Dict[str, Any],
                                     conversation_state: ConversationState) -> List[ContextualQuestion]:
        """Generate next questions based on flow decision"""
        
        question_results = agent_results.get('question_generator', {})
        questions_data = question_results.get('questions', [])
        
        questions = []
        for q_data in questions_data:
            try:
                question = ContextualQuestion(
                    id=q_data.get('id', ''),
                    text=q_data.get('text', ''),
                    category=q_data.get('category', 'general'),
                    priority=q_data.get('priority', 'medium'),
                    stakeholder_type=q_data.get('stakeholder_type', 'business'),
                    context=q_data.get('context', ''),
                    linked_gaps=q_data.get('linked_gaps', []),
                    follow_up_questions=q_data.get('follow_up_questions', []),
                    expected_answer_type=q_data.get('expected_answer_type', 'text')
                )
                questions.append(question)
            except Exception as e:
                print(f"Failed to create question from data: {e}")
                continue
        
        return questions
    
    def _update_conversation_state(self, 
                                 conversation_state: ConversationState,
                                 agent_results: Dict[str, Any],
                                 next_questions: List[ContextualQuestion],
                                 flow_decision: FlowDecision) -> None:
        """Update conversation state with new results"""
        
        # Update completeness scores
        gap_analysis = agent_results.get('gap_analysis', {})
        conversation_state.completeness_scores = {
            'completeness': gap_analysis.get('completeness_score', 0.0),
            'clarity': gap_analysis.get('clarity_score', 0.0),
            'business_readiness': gap_analysis.get('business_readiness_score', 0.0),
            'technical_readiness': gap_analysis.get('technical_readiness_score', 0.0)
        }
        
        # Update phase based on decision
        if flow_decision.decision_type == DecisionType.GENERATE_PRD:
            conversation_state.phase = ConversationPhase.COMPLETION
        elif flow_decision.decision_type == DecisionType.REQUEST_CLARIFICATION:
            conversation_state.phase = ConversationPhase.REFINEMENT
        elif conversation_state.phase == ConversationPhase.INITIALIZATION:
            conversation_state.phase = ConversationPhase.DISCOVERY
        
        # Add new questions
        conversation_state.questions_asked.extend(next_questions)
        
        # Update gaps
        gaps = gap_analysis.get('gaps', [])
        conversation_state.gaps_identified = gaps
    
    def _generate_recommendations(self, 
                                flow_decision: FlowDecision,
                                agent_results: Dict[str, Any],
                                conversation_state: ConversationState) -> List[str]:
        """Generate recommendations for the user"""
        
        recommendations = []
        
        gap_analysis = agent_results.get('gap_analysis', {})
        completeness = gap_analysis.get('completeness_score', 0.0)
        clarity = gap_analysis.get('clarity_score', 0.0)
        
        if completeness < 0.7:
            recommendations.append("Consider providing more detailed requirements to improve completeness")
        
        if clarity < 0.7:
            recommendations.append("Try to be more specific with technical terms and requirements")
        
        if flow_decision.decision_type == DecisionType.SUGGEST_BREAK:
            recommendations.append("Consider taking a break - you've covered a lot of ground!")
        
        if len(conversation_state.questions_asked) > 10:
            recommendations.append("Great progress! We're gathering comprehensive requirements")
        
        return recommendations
    
    def _determine_stakeholder_profile(self, 
                                     stakeholders: List[Dict[str, Any]] = None,
                                     context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Determine stakeholder profile from provided information"""
        
        if stakeholders:
            return {
                'primary_stakeholder': stakeholders[0] if stakeholders else {},
                'stakeholder_count': len(stakeholders),
                'stakeholder_types': [s.get('type', 'unknown') for s in stakeholders]
            }
        
        # Default profile
        return {
            'primary_stakeholder': {'type': 'business', 'role': 'product_owner'},
            'stakeholder_count': 1,
            'stakeholder_types': ['business']
        }
    
    def get_conversation_status(self, session_id: str) -> Dict[str, Any]:
        """Get current conversation status"""
        
        conversation_state = self.active_sessions.get(session_id)
        if not conversation_state:
            return {'error': 'Session not found'}
        
        return conversation_state.to_dict()
    
    def get_active_ambiguities(self, session_id: str) -> List[Dict[str, Any]]:
        """Get active ambiguities for a session"""
        
        conversation_state = self.active_sessions.get(session_id)
        if not conversation_state:
            return []
        
        return conversation_state.gaps_identified
    
    def get_next_questions(self, session_id: str) -> List[Dict[str, Any]]:
        """Get next recommended questions"""
        
        conversation_state = self.active_sessions.get(session_id)
        if not conversation_state:
            return []
        
        # Return last few questions that haven't been answered yet
        recent_questions = conversation_state.questions_asked[-3:]
        return [q.to_dict() if hasattr(q, 'to_dict') else q for q in recent_questions]