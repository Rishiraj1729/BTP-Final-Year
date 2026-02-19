"""
Document Processor Agent
Processes user-uploaded documents to enhance the knowledge base beyond master_reference.json
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

class DocumentType(Enum):
    EXISTING_PRD = "existing_prd"
    COMPANY_STANDARD = "company_standard"
    DOMAIN_DOC = "domain_doc"
    TECHNICAL_SPEC = "technical_spec"
    UNKNOWN = "unknown"

@dataclass
class ProcessedDocument:
    doc_type: DocumentType
    title: str
    content: str
    extracted_patterns: Dict[str, Any]
    requirements: List[Dict[str, Any]]
    business_rules: List[str]
    domain_knowledge: Dict[str, Any]

@dataclass
class EnhancedKnowledgeBase:
    master_reference: Dict[str, Any]
    user_documents: List[ProcessedDocument]
    domain_specific_patterns: Dict[str, Any]
    company_standards: Dict[str, Any]
    similar_project_patterns: List[Dict[str, Any]]
    compliance_requirements: List[str]
    
    def get_relevant_patterns(self, domain: str = None) -> Dict[str, Any]:
        """Get patterns relevant to a specific domain"""
        patterns = {}
        
        # Add master reference patterns
        if domain and domain in self.master_reference.get('prd_types', {}):
            patterns['master_patterns'] = self.master_reference['prd_types'][domain]
        
        # Add domain-specific patterns from user docs
        if domain in self.domain_specific_patterns:
            patterns['domain_patterns'] = self.domain_specific_patterns[domain]
        
        # Add company standards
        patterns['company_standards'] = self.company_standards
        
        return patterns
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the enhanced knowledge base"""
        return {
            "total_documents": len(self.user_documents),
            "document_types": [doc.doc_type.value for doc in self.user_documents],
            "domain_patterns": len(self.domain_specific_patterns),
            "company_standards": len(self.company_standards),
            "similar_projects": len(self.similar_project_patterns),
            "compliance_rules": len(self.compliance_requirements)
        }

class DocumentProcessor:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.master_reference = self._load_master_reference()
    
    def _load_master_reference(self) -> Dict[str, Any]:
        """Load the master reference JSON"""
        try:
            with open(Path(__file__).resolve().parent.parent / "master_reference.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load master_reference.json: {e}")
            return {}
    
    def process_user_documents(self, documents: List[Dict[str, str]]) -> EnhancedKnowledgeBase:
        """
        Process user-uploaded documents and create enhanced knowledge base
        
        Args:
            documents: List of dicts with 'filename', 'content' keys
        """
        processed_docs = []
        
        for doc in documents:
            try:
                processed_doc = self._process_single_document(doc)
                processed_docs.append(processed_doc)
            except Exception as e:
                print(f"Error processing document {doc.get('filename', 'unknown')}: {e}")
                continue
        
        # Create enhanced knowledge base
        enhanced_kb = self._create_enhanced_knowledge_base(processed_docs)
        
        return enhanced_kb
    
    def _process_single_document(self, doc: Dict[str, str]) -> ProcessedDocument:
        """Process a single document"""
        content = doc['content']
        filename = doc.get('filename', 'unknown')
        
        # Classify document type
        doc_type = self._classify_document(content, filename)
        
        # Extract different types of information based on document type
        if doc_type == DocumentType.EXISTING_PRD:
            extracted_info = self._extract_prd_patterns(content)
        elif doc_type == DocumentType.COMPANY_STANDARD:
            extracted_info = self._extract_standard_patterns(content)
        elif doc_type == DocumentType.DOMAIN_DOC:
            extracted_info = self._extract_domain_patterns(content)
        elif doc_type == DocumentType.TECHNICAL_SPEC:
            extracted_info = self._extract_technical_patterns(content)
        else:
            extracted_info = self._extract_generic_patterns(content)
        
        return ProcessedDocument(
            doc_type=doc_type,
            title=filename,
            content=content,
            extracted_patterns=extracted_info.get('patterns', {}),
            requirements=extracted_info.get('requirements', []),
            business_rules=extracted_info.get('business_rules', []),
            domain_knowledge=extracted_info.get('domain_knowledge', {})
        )
    
    def _classify_document(self, content: str, filename: str) -> DocumentType:
        """Classify document type using rules and optionally LLM"""
        content_lower = content.lower()
        filename_lower = filename.lower()
        
        # Rule-based classification first
        if any(keyword in content_lower for keyword in ['product requirements', 'prd', 'functional requirements', 'user stories']):
            return DocumentType.EXISTING_PRD
        
        if any(keyword in content_lower for keyword in ['standard', 'template', 'guideline', 'policy']):
            return DocumentType.COMPANY_STANDARD
        
        if any(keyword in content_lower for keyword in ['compliance', 'regulation', 'hipaa', 'gdpr', 'sox']):
            return DocumentType.DOMAIN_DOC
        
        if any(keyword in content_lower for keyword in ['api', 'architecture', 'technical specification', 'system design']):
            return DocumentType.TECHNICAL_SPEC
        
        # Use LLM for more sophisticated classification if available
        if self.llm_client and hasattr(self.llm_client, 'generate_text'):
            return self._classify_with_llm(content)
        
        return DocumentType.UNKNOWN
    
    def _classify_with_llm(self, content: str) -> DocumentType:
        """Use LLM to classify document type"""
        try:
            classification_prompt = f"""
            Analyze this document and classify it as one of:
            1. EXISTING_PRD: Previous project requirements document
            2. COMPANY_STANDARD: Company-specific requirement templates/standards  
            3. DOMAIN_DOC: Domain-specific documentation (compliance, regulations)
            4. TECHNICAL_SPEC: Technical specifications or architecture docs
            5. UNKNOWN: Cannot determine type
            
            Document content (first 1000 chars):
            {content[:1000]}...
            
            Respond with just the classification: EXISTING_PRD, COMPANY_STANDARD, DOMAIN_DOC, TECHNICAL_SPEC, or UNKNOWN
            """
            
            result = self.llm_client.generate_text(
                system_prompt="You are a document classifier for requirements engineering.",
                user_prompt=classification_prompt
            )
            
            result_clean = result.strip().upper()
            if 'EXISTING_PRD' in result_clean:
                return DocumentType.EXISTING_PRD
            elif 'COMPANY_STANDARD' in result_clean:
                return DocumentType.COMPANY_STANDARD
            elif 'DOMAIN_DOC' in result_clean:
                return DocumentType.DOMAIN_DOC
            elif 'TECHNICAL_SPEC' in result_clean:
                return DocumentType.TECHNICAL_SPEC
            else:
                return DocumentType.UNKNOWN
                
        except Exception as e:
            print(f"LLM classification failed: {e}")
            return DocumentType.UNKNOWN
    
    def _extract_prd_patterns(self, content: str) -> Dict[str, Any]:
        """Extract patterns from existing PRD documents"""
        patterns = {}
        requirements = []
        business_rules = []
        
        # Extract functional requirements
        fr_matches = re.findall(r'(?:FR-?\d+|Functional Requirement|User Story)[\s:]*([^\n]+)', content, re.IGNORECASE)
        for match in fr_matches:
            requirements.append({
                'type': 'functional',
                'description': match.strip(),
                'source': 'existing_prd'
            })
        
        # Extract non-functional requirements
        nfr_matches = re.findall(r'(?:NFR-?\d+|Non-Functional|Performance|Security)[\s:]*([^\n]+)', content, re.IGNORECASE)
        for match in nfr_matches:
            requirements.append({
                'type': 'non_functional',
                'description': match.strip(),
                'source': 'existing_prd'
            })
        
        # Extract business rules
        rule_patterns = [
            r'(?:Business Rule|Rule|Policy)[\s:]*([^\n]+)',
            r'(?:Must|Should|Shall)[\s]+([^\n]+)',
            r'(?:When|If)[\s]+([^,\n]+)(?:,|\sthen)[\s]*([^\n]+)'
        ]
        
        for pattern in rule_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    rule = ' '.join(match)
                else:
                    rule = match
                business_rules.append(rule.strip())
        
        # Extract common patterns
        patterns['requirement_structure'] = self._analyze_requirement_structure(content)
        patterns['acceptance_criteria_style'] = self._analyze_acceptance_criteria(content)
        patterns['priority_scheme'] = self._analyze_priority_scheme(content)
        
        return {
            'patterns': patterns,
            'requirements': requirements,
            'business_rules': business_rules,
            'domain_knowledge': {'type': 'prd_example'}
        }
    
    def _extract_standard_patterns(self, content: str) -> Dict[str, Any]:
        """Extract patterns from company standards/templates"""
        patterns = {}
        
        # Extract template sections
        section_matches = re.findall(r'(?:^|\n)#+\s*([^\n]+)', content, re.MULTILINE)
        patterns['standard_sections'] = [section.strip() for section in section_matches]
        
        # Extract mandatory fields
        mandatory_matches = re.findall(r'(?:required|mandatory|must include)[\s:]*([^\n]+)', content, re.IGNORECASE)
        patterns['mandatory_fields'] = [field.strip() for field in mandatory_matches]
        
        # Extract validation rules
        validation_matches = re.findall(r'(?:validate|check|ensure)[\s:]*([^\n]+)', content, re.IGNORECASE)
        patterns['validation_rules'] = [rule.strip() for rule in validation_matches]
        
        return {
            'patterns': patterns,
            'requirements': [],
            'business_rules': patterns.get('validation_rules', []),
            'domain_knowledge': {'type': 'company_standard'}
        }
    
    def _extract_domain_patterns(self, content: str) -> Dict[str, Any]:
        """Extract patterns from domain-specific documents"""
        patterns = {}
        compliance_rules = []
        
        # Extract compliance requirements
        compliance_patterns = [
            r'(?:must comply|required by|mandated)[\s]+([^\n]+)',
            r'(?:regulation|standard|compliance)[\s:]*([^\n]+)',
            r'(?:audit|review|verification)[\s:]*([^\n]+)'
        ]
        
        for pattern in compliance_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            compliance_rules.extend([match.strip() for match in matches])
        
        # Extract domain-specific terminology
        domain_terms = re.findall(r'(?:define|definition)[\s:]*([^\n]+)', content, re.IGNORECASE)
        patterns['domain_terminology'] = [term.strip() for term in domain_terms]
        
        return {
            'patterns': patterns,
            'requirements': [],
            'business_rules': compliance_rules,
            'domain_knowledge': {
                'type': 'domain_specific',
                'compliance_rules': compliance_rules,
                'terminology': patterns.get('domain_terminology', [])
            }
        }
    
    def _extract_technical_patterns(self, content: str) -> Dict[str, Any]:
        """Extract patterns from technical specifications"""
        patterns = {}
        
        # Extract API endpoints
        api_matches = re.findall(r'(?:GET|POST|PUT|DELETE)\s+([^\s\n]+)', content)
        patterns['api_endpoints'] = api_matches
        
        # Extract technology stack mentions
        tech_patterns = [
            r'(?:using|built with|technology)[\s:]*([^\n]+)',
            r'(?:database|db)[\s:]*([^\n]+)',
            r'(?:framework|library)[\s:]*([^\n]+)'
        ]
        
        tech_stack = []
        for pattern in tech_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            tech_stack.extend([match.strip() for match in matches])
        
        patterns['technology_stack'] = tech_stack
        
        return {
            'patterns': patterns,
            'requirements': [],
            'business_rules': [],
            'domain_knowledge': {
                'type': 'technical_spec',
                'apis': patterns.get('api_endpoints', []),
                'technologies': tech_stack
            }
        }
    
    def _extract_generic_patterns(self, content: str) -> Dict[str, Any]:
        """Extract generic patterns from unknown document types"""
        patterns = {}
        
        # Extract any requirement-like statements
        requirement_patterns = [
            r'(?:system|application|user)[\s]+(?:must|should|shall)[\s]+([^\n]+)',
            r'(?:requirement|need|feature)[\s:]*([^\n]+)'
        ]
        
        requirements = []
        for pattern in requirement_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                requirements.append({
                    'type': 'generic',
                    'description': match.strip(),
                    'source': 'generic_doc'
                })
        
        return {
            'patterns': patterns,
            'requirements': requirements,
            'business_rules': [],
            'domain_knowledge': {'type': 'generic'}
        }
    
    def _analyze_requirement_structure(self, content: str) -> Dict[str, Any]:
        """Analyze how requirements are structured in the document"""
        structure = {}
        
        # Check for numbering schemes
        if re.search(r'FR-\d+', content):
            structure['functional_numbering'] = 'FR-XXX'
        if re.search(r'NFR-\d+', content):
            structure['nfr_numbering'] = 'NFR-XXX'
        if re.search(r'US-\d+', content):
            structure['user_story_numbering'] = 'US-XXX'
        
        # Check for priority schemes
        if re.search(r'(?:high|medium|low)\s+priority', content, re.IGNORECASE):
            structure['priority_scheme'] = 'high_medium_low'
        elif re.search(r'P[0-3]', content):
            structure['priority_scheme'] = 'P0_P1_P2_P3'
        
        return structure
    
    def _analyze_acceptance_criteria(self, content: str) -> Dict[str, Any]:
        """Analyze acceptance criteria patterns"""
        criteria_style = {}
        
        if re.search(r'given[\s]+.*when[\s]+.*then', content, re.IGNORECASE):
            criteria_style['format'] = 'gherkin'
        elif re.search(r'acceptance criteria', content, re.IGNORECASE):
            criteria_style['format'] = 'bullet_points'
        
        return criteria_style
    
    def _analyze_priority_scheme(self, content: str) -> str:
        """Analyze priority scheme used"""
        if re.search(r'P[0-3]', content):
            return 'P0_P1_P2_P3'
        elif re.search(r'(?:high|medium|low)', content, re.IGNORECASE):
            return 'high_medium_low'
        elif re.search(r'(?:critical|important|nice)', content, re.IGNORECASE):
            return 'critical_important_nice'
        return 'unknown'
    
    def _create_enhanced_knowledge_base(self, processed_docs: List[ProcessedDocument]) -> EnhancedKnowledgeBase:
        """Create enhanced knowledge base from processed documents"""
        
        # Organize documents by type
        domain_patterns = {}
        company_standards = {}
        similar_projects = []
        compliance_requirements = []
        
        for doc in processed_docs:
            if doc.doc_type == DocumentType.EXISTING_PRD:
                similar_projects.append({
                    'title': doc.title,
                    'patterns': doc.extracted_patterns,
                    'requirements': doc.requirements
                })
            
            elif doc.doc_type == DocumentType.COMPANY_STANDARD:
                company_standards[doc.title] = {
                    'patterns': doc.extracted_patterns,
                    'rules': doc.business_rules
                }
            
            elif doc.doc_type == DocumentType.DOMAIN_DOC:
                domain_key = doc.title.replace(' ', '_').lower()
                domain_patterns[domain_key] = doc.domain_knowledge
                compliance_requirements.extend(doc.business_rules)
            
            elif doc.doc_type == DocumentType.TECHNICAL_SPEC:
                tech_key = f"tech_{doc.title.replace(' ', '_').lower()}"
                domain_patterns[tech_key] = doc.domain_knowledge
        
        return EnhancedKnowledgeBase(
            master_reference=self.master_reference,
            user_documents=processed_docs,
            domain_specific_patterns=domain_patterns,
            company_standards=company_standards,
            similar_project_patterns=similar_projects,
            compliance_requirements=compliance_requirements
        )