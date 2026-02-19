"""
Continuous Gap Detection Agent with LLM Enhancement
Continuously analyzes requirements for gaps using both rule-based and LLM approaches
"""

import json
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from state_schema import AgentState, GapEntry
from agents.document_processor import EnhancedKnowledgeBase
from agents.groq_enhanced_questions import ConversationHistory

class GapSeverity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class GapCategory(Enum):
    MISSING_DETAIL = "missing_detail"
    VAGUE_TERM = "vague_term"
    CONFLICT = "conflict"
    IMPLICIT_REQUIREMENT = "implicit_requirement"
    BUSINESS_LOGIC_GAP = "business_logic_gap"
    COMPLIANCE_GAP = "compliance_gap"
    TECHNICAL_GAP = "technical_gap"
    STAKEHOLDER_MISALIGNMENT = "stakeholder_misalignment"

@dataclass
class EnhancedGap:
    id: str
    category: GapCategory
    severity: GapSeverity
    description: str
    context: str
    affected_requirements: List[str]
    suggested_questions: List[str]
    resolution_priority: int
    business_impact: str
    source: str  # "rule_based", "llm_detected", "domain_knowledge"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'category': self.category.value,
            'severity': self.severity.value,
            'description': self.description,
            'context': self.context,
            'affected_requirements': self.affected_requirements,
            'suggested_questions': self.suggested_questions,
            'resolution_priority': self.resolution_priority,
            'business_impact': self.business_impact,
            'source': self.source
        }

@dataclass
class GapAnalysisResult:
    rule_based_gaps: List[EnhancedGap]
    llm_detected_gaps: List[EnhancedGap]
    domain_gaps: List[EnhancedGap]
    completeness_score: float
    clarity_score: float
    business_readiness_score: float
    technical_readiness_score: float
    needs_more_questions: bool
    next_focus_area: str
    
    @property
    def all_gaps(self) -> List[EnhancedGap]:
        """Get all gaps combined and deduplicated"""
        all_gaps = self.rule_based_gaps + self.llm_detected_gaps + self.domain_gaps
        
        # Simple deduplication by description similarity
        unique_gaps = []
        for gap in all_gaps:
            is_duplicate = False
            for existing in unique_gaps:
                if self._gaps_similar(gap, existing):
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_gaps.append(gap)
        
        return sorted(unique_gaps, key=lambda g: g.resolution_priority)
    
    def _gaps_similar(self, gap1: EnhancedGap, gap2: EnhancedGap) -> bool:
        """Check if two gaps are similar (for deduplication)"""
        # Simple similarity check based on description overlap
        words1 = set(gap1.description.lower().split())
        words2 = set(gap2.description.lower().split())
        overlap = len(words1.intersection(words2))
        return overlap > max(len(words1), len(words2)) * 0.6

class ContinuousGapDetector:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.completeness_threshold = 0.85
        self.clarity_threshold = 0.80
        self.business_readiness_threshold = 0.75
        self.technical_readiness_threshold = 0.70
        
        # Rule-based gap detection patterns
        self.gap_patterns = self._initialize_gap_patterns()
    
    def _initialize_gap_patterns(self) -> Dict[str, List[Dict[str, Any]]]:
        """Initialize rule-based gap detection patterns"""
        return {
            "vague_terms": [
                {"pattern": r"\b(fast|slow|good|bad|easy|hard|simple|complex)\b", "severity": "medium"},
                {"pattern": r"\b(performance|scalable|secure|reliable)\b", "severity": "high"},
                {"pattern": r"\b(user-friendly|intuitive|responsive)\b", "severity": "medium"},
                {"pattern": r"\b(many|few|some|several|lots)\b", "severity": "low"}
            ],
            "missing_details": [
                {"pattern": r"\b(login|authentication)\b", "missing": ["password reset", "session management", "multi-factor auth"], "severity": "high"},
                {"pattern": r"\b(payment|billing)\b", "missing": ["payment methods", "refunds", "failed payments"], "severity": "high"},
                {"pattern": r"\b(notification|email)\b", "missing": ["frequency", "opt-out", "templates"], "severity": "medium"},
                {"pattern": r"\b(search|filter)\b", "missing": ["search criteria", "sorting", "pagination"], "severity": "medium"},
                {"pattern": r"\b(report|analytics)\b", "missing": ["data sources", "export formats", "scheduling"], "severity": "medium"}
            ],
            "business_logic_gaps": [
                {"pattern": r"\b(user role|permission|access)\b", "missing": ["role hierarchy", "permission inheritance", "access control"], "severity": "high"},
                {"pattern": r"\b(workflow|process|approval)\b", "missing": ["approval chain", "escalation", "rollback"], "severity": "high"},
                {"pattern": r"\b(data|information)\b", "missing": ["data validation", "data retention", "data privacy"], "severity": "high"}
            ]
        }
    
    def continuous_gap_analysis(self, 
                               current_requirements: List[Dict[str, Any]],
                               conversation_history: ConversationHistory,
                               enhanced_knowledge: EnhancedKnowledgeBase) -> GapAnalysisResult:
        """
        Perform comprehensive gap analysis using multiple approaches
        """
        
        # Rule-based gap detection
        rule_based_gaps = self._detect_rule_based_gaps(current_requirements, conversation_history)
        
        # LLM-enhanced gap detection
        llm_gaps = self._detect_llm_gaps(current_requirements, conversation_history, enhanced_knowledge)
        
        # Domain-specific gap detection
        domain_gaps = self._detect_domain_gaps(current_requirements, enhanced_knowledge)
        
        # Calculate various scores
        completeness_score = self._calculate_completeness_score(current_requirements, enhanced_knowledge)
        clarity_score = self._calculate_clarity_score(current_requirements, conversation_history)
        business_readiness_score = self._calculate_business_readiness_score(current_requirements, enhanced_knowledge)
        technical_readiness_score = self._calculate_technical_readiness_score(current_requirements, enhanced_knowledge)
        
        # Determine if more questions are needed
        needs_more_questions = self._should_continue_questioning(
            completeness_score, clarity_score, business_readiness_score, technical_readiness_score
        )
        
        # Determine next focus area
        next_focus_area = self._determine_next_focus_area(
            completeness_score, clarity_score, business_readiness_score, technical_readiness_score
        )
        
        return GapAnalysisResult(
            rule_based_gaps=rule_based_gaps,
            llm_detected_gaps=llm_gaps,
            domain_gaps=domain_gaps,
            completeness_score=completeness_score,
            clarity_score=clarity_score,
            business_readiness_score=business_readiness_score,
            technical_readiness_score=technical_readiness_score,
            needs_more_questions=needs_more_questions,
            next_focus_area=next_focus_area
        )
    
    def _detect_rule_based_gaps(self, 
                               current_requirements: List[Dict[str, Any]],
                               conversation_history: ConversationHistory) -> List[EnhancedGap]:
        """Detect gaps using rule-based patterns"""
        
        gaps = []
        req_text = " ".join([req.get('description', '') for req in current_requirements])
        conversation_text = conversation_history.get_context_summary()
        full_text = f"{req_text} {conversation_text}"
        
        gap_id = 1
        
        # Detect vague terms
        for pattern_info in self.gap_patterns["vague_terms"]:
            matches = re.findall(pattern_info["pattern"], full_text, re.IGNORECASE)
            for match in matches:
                gap = EnhancedGap(
                    id=f"rule_gap_{gap_id}",
                    category=GapCategory.VAGUE_TERM,
                    severity=GapSeverity(pattern_info["severity"]),
                    description=f"Vague term '{match}' needs clarification",
                    context=f"Found in: {self._find_context(match, full_text)}",
                    affected_requirements=[req['id'] for req in current_requirements if match.lower() in req.get('description', '').lower()],
                    suggested_questions=[f"What specific criteria define '{match}' in this context?"],
                    resolution_priority=self._calculate_priority(GapSeverity(pattern_info["severity"])),
                    business_impact="May lead to unclear requirements and implementation issues",
                    source="rule_based"
                )
                gaps.append(gap)
                gap_id += 1
        
        # Detect missing details
        for pattern_info in self.gap_patterns["missing_details"]:
            if re.search(pattern_info["pattern"], full_text, re.IGNORECASE):
                for missing_detail in pattern_info["missing"]:
                    if missing_detail.lower() not in full_text.lower():
                        gap = EnhancedGap(
                            id=f"rule_gap_{gap_id}",
                            category=GapCategory.MISSING_DETAIL,
                            severity=GapSeverity(pattern_info["severity"]),
                            description=f"Missing detail: {missing_detail}",
                            context=f"Related to: {pattern_info['pattern']}",
                            affected_requirements=[],
                            suggested_questions=[f"How should {missing_detail} be handled?"],
                            resolution_priority=self._calculate_priority(GapSeverity(pattern_info["severity"])),
                            business_impact="Missing implementation details may cause delays",
                            source="rule_based"
                        )
                        gaps.append(gap)
                        gap_id += 1
        
        # Detect business logic gaps
        for pattern_info in self.gap_patterns["business_logic_gaps"]:
            if re.search(pattern_info["pattern"], full_text, re.IGNORECASE):
                for missing_logic in pattern_info["missing"]:
                    if missing_logic.lower() not in full_text.lower():
                        gap = EnhancedGap(
                            id=f"rule_gap_{gap_id}",
                            category=GapCategory.BUSINESS_LOGIC_GAP,
                            severity=GapSeverity(pattern_info["severity"]),
                            description=f"Business logic gap: {missing_logic}",
                            context=f"Related to: {pattern_info['pattern']}",
                            affected_requirements=[],
                            suggested_questions=[f"What are the rules for {missing_logic}?"],
                            resolution_priority=self._calculate_priority(GapSeverity(pattern_info["severity"])),
                            business_impact="Missing business rules may cause incorrect system behavior",
                            source="rule_based"
                        )
                        gaps.append(gap)
                        gap_id += 1
        
        return gaps
    
    def _detect_llm_gaps(self, 
                        current_requirements: List[Dict[str, Any]],
                        conversation_history: ConversationHistory,
                        enhanced_knowledge: EnhancedKnowledgeBase) -> List[EnhancedGap]:
        """Use LLM to detect sophisticated gaps"""
        
        if not self.llm_client or not hasattr(self.llm_client, 'generate_text'):
            return []
        
        try:
            # Prepare context for LLM
            context = self._prepare_llm_gap_context(current_requirements, conversation_history, enhanced_knowledge)
            
            # Generate gap analysis using LLM
            llm_response = self._generate_llm_gap_analysis(context)
            
            # Parse LLM response into structured gaps
            llm_gaps = self._parse_llm_gaps(llm_response)
            
            return llm_gaps
            
        except Exception as e:
            print(f"LLM gap detection failed: {e}")
            return []
    
    def _prepare_llm_gap_context(self, 
                                current_requirements: List[Dict[str, Any]],
                                conversation_history: ConversationHistory,
                                enhanced_knowledge: EnhancedKnowledgeBase) -> Dict[str, Any]:
        """Prepare context for LLM gap analysis"""
        
        return {
            "requirements": current_requirements,
            "conversation": conversation_history.get_context_summary(),
            "stakeholder_profile": conversation_history.stakeholder_profile,
            "domain_patterns": enhanced_knowledge.get_relevant_patterns(),
            "compliance_requirements": enhanced_knowledge.compliance_requirements,
            "similar_projects": enhanced_knowledge.similar_project_patterns[:2]
        }
    
    def _generate_llm_gap_analysis(self, context: Dict[str, Any]) -> str:
        """Generate gap analysis using LLM"""
        
        system_prompt = """You are an expert requirements analyst with deep domain knowledge. 
        Your job is to identify gaps, inconsistencies, and missing information in requirements that might not be obvious.
        
        Focus on:
        1. COMPLETENESS GAPS: Missing functional/non-functional requirements, edge cases, error scenarios
        2. CLARITY GAPS: Ambiguous terminology, unclear business rules, vague acceptance criteria
        3. CONSISTENCY GAPS: Contradictions between requirements, conflicting business rules
        4. BUSINESS LOGIC GAPS: Missing workflows, approval processes, data validation rules
        5. COMPLIANCE GAPS: Missing regulatory requirements, security standards, privacy rules
        6. TECHNICAL GAPS: Missing architecture decisions, integration points, performance criteria
        7. STAKEHOLDER ALIGNMENT: Different expectations between stakeholders
        
        Be specific and actionable in your analysis."""
        
        user_prompt = f"""
        Analyze the following requirements and conversation for gaps:

        CURRENT REQUIREMENTS:
        {json.dumps(context['requirements'], indent=2)}

        CONVERSATION CONTEXT:
        {context['conversation']}

        STAKEHOLDER PROFILE:
        {json.dumps(context['stakeholder_profile'], indent=2)}

        DOMAIN KNOWLEDGE:
        {json.dumps(context['domain_patterns'], indent=2)}

        COMPLIANCE REQUIREMENTS:
        {json.dumps(context['compliance_requirements'], indent=2)}

        SIMILAR PROJECTS (for reference):
        {json.dumps(context['similar_projects'], indent=2)}

        For each gap you identify, provide:
        1. Category (completeness, clarity, consistency, business_logic, compliance, technical, stakeholder_alignment)
        2. Severity (critical, high, medium, low)
        3. Description of the gap
        4. Business impact
        5. Suggested questions to resolve the gap

        Format as JSON array with fields: category, severity, description, business_impact, suggested_questions
        """
        
        try:
            response = self.llm_client.generate_text(
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            return response
        except Exception as e:
            raise Exception(f"LLM gap analysis failed: {e}")
    
    def _parse_llm_gaps(self, llm_response: str) -> List[EnhancedGap]:
        """Parse LLM response into structured gaps"""
        
        gaps = []
        
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\[.*\]', llm_response, re.DOTALL)
            if json_match:
                gaps_data = json.loads(json_match.group())
            else:
                # Fallback: parse text response
                gaps_data = self._parse_text_gaps(llm_response)
            
            for i, gap_data in enumerate(gaps_data):
                category_map = {
                    'completeness': GapCategory.MISSING_DETAIL,
                    'clarity': GapCategory.VAGUE_TERM,
                    'consistency': GapCategory.CONFLICT,
                    'business_logic': GapCategory.BUSINESS_LOGIC_GAP,
                    'compliance': GapCategory.COMPLIANCE_GAP,
                    'technical': GapCategory.TECHNICAL_GAP,
                    'stakeholder_alignment': GapCategory.STAKEHOLDER_MISALIGNMENT
                }
                
                category = category_map.get(gap_data.get('category', 'completeness'), GapCategory.MISSING_DETAIL)
                severity = GapSeverity(gap_data.get('severity', 'medium'))
                
                gap = EnhancedGap(
                    id=f"llm_gap_{i+1}",
                    category=category,
                    severity=severity,
                    description=gap_data.get('description', ''),
                    context="Identified by LLM analysis",
                    affected_requirements=[],
                    suggested_questions=gap_data.get('suggested_questions', []),
                    resolution_priority=self._calculate_priority(severity),
                    business_impact=gap_data.get('business_impact', ''),
                    source="llm_detected"
                )
                gaps.append(gap)
                
        except Exception as e:
            print(f"Failed to parse LLM gaps: {e}")
        
        return gaps
    
    def _parse_text_gaps(self, text_response: str) -> List[Dict[str, Any]]:
        """Parse text response when JSON parsing fails"""
        gaps = []
        
        # Look for gap patterns in text
        gap_sections = re.split(r'\n(?=\d+\.|\*|\-)', text_response)
        
        for section in gap_sections:
            if len(section.strip()) > 20:  # Filter out very short sections
                gaps.append({
                    'category': 'completeness',
                    'severity': 'medium',
                    'description': section.strip()[:200],  # Limit description length
                    'business_impact': 'Potential impact on project success',
                    'suggested_questions': ['Can you provide more details about this area?']
                })
        
        return gaps[:5]  # Limit to 5 gaps from text parsing
    
    def _detect_domain_gaps(self, 
                           current_requirements: List[Dict[str, Any]],
                           enhanced_knowledge: EnhancedKnowledgeBase) -> List[EnhancedGap]:
        """Detect gaps based on domain-specific knowledge"""
        
        gaps = []
        gap_id = 1
        
        # Check compliance requirements
        req_text = " ".join([req.get('description', '') for req in current_requirements])
        
        for compliance_rule in enhanced_knowledge.compliance_requirements:
            # Check if compliance rule is addressed
            rule_keywords = compliance_rule.lower().split()[:3]  # First 3 words as keywords
            if not any(keyword in req_text.lower() for keyword in rule_keywords):
                gap = EnhancedGap(
                    id=f"domain_gap_{gap_id}",
                    category=GapCategory.COMPLIANCE_GAP,
                    severity=GapSeverity.HIGH,
                    description=f"Compliance requirement not addressed: {compliance_rule}",
                    context="Based on domain-specific compliance requirements",
                    affected_requirements=[],
                    suggested_questions=[f"How will the system comply with: {compliance_rule}?"],
                    resolution_priority=self._calculate_priority(GapSeverity.HIGH),
                    business_impact="Non-compliance may result in legal or regulatory issues",
                    source="domain_knowledge"
                )
                gaps.append(gap)
                gap_id += 1
        
        # Check company standards
        for standard_name, standard_data in enhanced_knowledge.company_standards.items():
            if 'mandatory_fields' in standard_data:
                for field in standard_data['mandatory_fields']:
                    if field.lower() not in req_text.lower():
                        gap = EnhancedGap(
                            id=f"domain_gap_{gap_id}",
                            category=GapCategory.MISSING_DETAIL,
                            severity=GapSeverity.HIGH,
                            description=f"Company standard requires: {field}",
                            context=f"Based on company standard: {standard_name}",
                            affected_requirements=[],
                            suggested_questions=[f"How should {field} be implemented according to company standards?"],
                            resolution_priority=self._calculate_priority(GapSeverity.HIGH),
                            business_impact="Non-compliance with company standards may cause project rejection",
                            source="domain_knowledge"
                        )
                        gaps.append(gap)
                        gap_id += 1
        
        return gaps
    
    def _calculate_completeness_score(self, 
                                    current_requirements: List[Dict[str, Any]],
                                    enhanced_knowledge: EnhancedKnowledgeBase) -> float:
        """Calculate requirement completeness score"""
        
        if not current_requirements:
            return 0.0
        
        # Base score from requirement count and detail level
        base_score = min(len(current_requirements) / 10.0, 0.6)  # Max 0.6 from count
        
        # Detail level score
        total_detail_score = 0
        for req in current_requirements:
            description = req.get('description', '')
            detail_score = min(len(description.split()) / 20.0, 0.1)  # Max 0.1 per requirement
            total_detail_score += detail_score
        
        detail_score = min(total_detail_score, 0.3)  # Max 0.3 from detail
        
        # Coverage score based on domain patterns
        coverage_score = self._calculate_coverage_score(current_requirements, enhanced_knowledge)
        
        return min(base_score + detail_score + coverage_score, 1.0)
    
    def _calculate_clarity_score(self, 
                               current_requirements: List[Dict[str, Any]],
                               conversation_history: ConversationHistory) -> float:
        """Calculate requirement clarity score"""
        
        if not current_requirements:
            return 0.0
        
        total_clarity = 0
        vague_terms = ['fast', 'slow', 'good', 'bad', 'easy', 'hard', 'simple', 'complex', 'user-friendly', 'intuitive']
        
        for req in current_requirements:
            description = req.get('description', '').lower()
            word_count = len(description.split())
            
            if word_count == 0:
                continue
            
            # Penalize vague terms
            vague_count = sum(1 for term in vague_terms if term in description)
            vague_penalty = vague_count / word_count
            
            # Reward specific terms
            specific_terms = ['must', 'shall', 'will', 'exactly', 'precisely', 'specifically']
            specific_count = sum(1 for term in specific_terms if term in description)
            specific_bonus = specific_count / word_count
            
            clarity = max(0.0, 1.0 - vague_penalty + specific_bonus)
            total_clarity += clarity
        
        return min(total_clarity / len(current_requirements), 1.0)
    
    def _calculate_business_readiness_score(self, 
                                          current_requirements: List[Dict[str, Any]],
                                          enhanced_knowledge: EnhancedKnowledgeBase) -> float:
        """Calculate business readiness score"""
        
        business_areas = ['user roles', 'permissions', 'workflow', 'approval', 'business rules', 'validation']
        covered_areas = 0
        
        req_text = " ".join([req.get('description', '') for req in current_requirements]).lower()
        
        for area in business_areas:
            if area in req_text:
                covered_areas += 1
        
        return covered_areas / len(business_areas)
    
    def _calculate_technical_readiness_score(self, 
                                           current_requirements: List[Dict[str, Any]],
                                           enhanced_knowledge: EnhancedKnowledgeBase) -> float:
        """Calculate technical readiness score"""
        
        technical_areas = ['performance', 'security', 'scalability', 'integration', 'api', 'database']
        covered_areas = 0
        
        req_text = " ".join([req.get('description', '') for req in current_requirements]).lower()
        
        for area in technical_areas:
            if area in req_text:
                covered_areas += 1
        
        return covered_areas / len(technical_areas)
    
    def _calculate_coverage_score(self, 
                                current_requirements: List[Dict[str, Any]],
                                enhanced_knowledge: EnhancedKnowledgeBase) -> float:
        """Calculate how well requirements cover expected domain areas"""
        
        # Get expected patterns from domain knowledge
        expected_patterns = enhanced_knowledge.get_relevant_patterns()
        
        if not expected_patterns:
            return 0.1  # Default score if no domain patterns
        
        coverage = 0
        total_patterns = 0
        
        req_text = " ".join([req.get('description', '') for req in current_requirements]).lower()
        
        for pattern_type, patterns in expected_patterns.items():
            if isinstance(patterns, dict):
                for pattern_key, pattern_value in patterns.items():
                    total_patterns += 1
                    if isinstance(pattern_value, str) and pattern_value.lower() in req_text:
                        coverage += 1
                    elif isinstance(pattern_value, list):
                        for item in pattern_value:
                            if isinstance(item, str) and item.lower() in req_text:
                                coverage += 1
                                break
        
        return coverage / max(total_patterns, 1) * 0.1  # Max 0.1 contribution
    
    def _should_continue_questioning(self, 
                                   completeness_score: float,
                                   clarity_score: float,
                                   business_readiness_score: float,
                                   technical_readiness_score: float) -> bool:
        """Determine if more questions are needed"""
        
        return (completeness_score < self.completeness_threshold or
                clarity_score < self.clarity_threshold or
                business_readiness_score < self.business_readiness_threshold or
                technical_readiness_score < self.technical_readiness_threshold)
    
    def _determine_next_focus_area(self, 
                                 completeness_score: float,
                                 clarity_score: float,
                                 business_readiness_score: float,
                                 technical_readiness_score: float) -> str:
        """Determine what area to focus on next"""
        
        scores = {
            'completeness': completeness_score,
            'clarity': clarity_score,
            'business_readiness': business_readiness_score,
            'technical_readiness': technical_readiness_score
        }
        
        # Return the area with the lowest score
        return min(scores.items(), key=lambda x: x[1])[0]
    
    def _calculate_priority(self, severity: GapSeverity) -> int:
        """Calculate numeric priority from severity"""
        priority_map = {
            GapSeverity.CRITICAL: 1,
            GapSeverity.HIGH: 2,
            GapSeverity.MEDIUM: 3,
            GapSeverity.LOW: 4
        }
        return priority_map[severity]
    
    def _find_context(self, term: str, text: str, context_length: int = 50) -> str:
        """Find context around a term in text"""
        term_index = text.lower().find(term.lower())
        if term_index == -1:
            return ""
        
        start = max(0, term_index - context_length)
        end = min(len(text), term_index + len(term) + context_length)
        
        return text[start:end].strip()