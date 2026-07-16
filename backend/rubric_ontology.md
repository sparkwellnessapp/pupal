Vivi Rubric Extraction Ontological North-Star
ARTIFACT B: Full Technical Specification
Final Version — Production Grade

1. Problem Statement
Vivi's rubric system transforms teacher DOCX documents into pedagogically-intelligent grading contracts that preserve teacher intent, distinguish skills from constraints, and guarantee every grading outcome cites explicit student work through atomic EvidenceClaims. The architecture separates universal ontology from configurable policy and implementation.

2. Architecture Layers
Layer
Contains
Changes
Ontology
Classes, relations, invariants
Rarely (versioned)
Policy
Defaults, thresholds, fallbacks
Occasionally
Implementation
Tools, prompts, caching
Frequently

Validation Boundaries:
OWL defines class/relation structure
SHACL validates constraints (sums, coverage, citations)
Code enforces runtime rules (closed-world, numeric tolerance)

3. Invariants and Policies
3.1 Non-Negotiable Invariants
INVARIANT PointSumQuestion:
  |Σ(criterion.points) - question.totalPoints| ≤ tolerance

INVARIANT PointSumCriterion:
  |Σ(rule.maxPoints) - criterion.points| ≤ tolerance

INVARIANT ClosedWorldGrading:
  The GradingRubricContract is exhaustive.
  The grader CANNOT:
    - Invent criteria, rules, or evidence categories
    - Award points for anything not represented in a declared ScoringLevel

INVARIANT EvidenceCitation:
  Every RuleOutcome contains exactly one EvidenceClaim.
  Every EvidenceClaim cites at least one AnswerQuotation.

INVARIANT LevelCoverage:
  Every DiscreteLevelRule has:
    - At least 2 levels
    - A level with points = 0
    - A level with points = maxPoints
    - Levels strictly ordered by points
    - Exactly one level selected per outcome

INVARIANT CriterionAlignment:
  Every Criterion links to at least one SkillTarget OR Requirement.

INVARIANT DoubleCountingPrevention:
  RuleOutcome A and B cannot both reduce points if:
    - They cite the same AnswerQuotation span AND
    - Their claimType is the same
  UNLESS A.dependsOn(B) or B.dependsOn(A) is declared.
3.2 Policies (Configurable Defaults)
Policy
Default
Override Level
Preserve teacher criteria
Always preserve, flag issues
Never
MeasurabilityStatus fallback
not_measurable → ReviewFlag (blocks auto-grade)
Per-school
Requirement promotion
Explicit teacher action; suggest if repeated ≥3 questions + ≥20% weight
Per-teacher
ApproachClass enumeration
Optional; default to allow_multiple_valid_forms: false if uncertain
Per-question
NumericPolicy
Contract-level: precision=0.25, rounding=half_up, tolerance=0.01
Per-contract


4. Core Ontology
4.1 Class Taxonomy
Assessment
├── Test
└── Question {questionType, totalPoints, allowMultipleValidForms}

PedagogicalConcept
├── SkillTarget {priority: primary|trivial}
├── Requirement {promotedToSkill: boolean}
├── CorrectnessModel
│   └── ApproachClass (internal pipeline only, not in grading contract)
└── MisconceptionPattern

GradingConstruct
├── Criterion {points, measurabilityStatus}
├── ReductionRule {maxPoints, scoringType, levelSelectionMode, ruleKind}
│   └── ScoringLevel {levelOrder, points, conditionHint}
└── RuleOutcome {selectedLevelId, evidenceClaim}

Evidence
├── EvidenceClaim {claimType, claimStatement, matchedLevelId, answerQuotations[]}
├── AnswerQuotation {quoteText, spanPointer}
└── PedagogicalSource {sourceType, location}

Annotation {annotationType, severity}
    annotationType: grounding_issue | narrowness_issue | clarity_issue | review_flag | merge_proposal
    severity: error | warning | info

Contract
├── ExtractRubricResponse (editable, includes ApproachClasses for validation)
└── GradingRubricContract (closed-world, minimal, stable)

SubjectModule
├── SkillTaxonomy (SKOS)
├── QuestionTypeSupport
├── CriterionTemplate
├── MisconceptionCatalog
└── ConventionPack
4.2 Key Relations
Relation
Domain → Range
Cardinality
hasQuestion
Test → Question
1..*
hasSkillTarget
Question ∪ Criterion → SkillTarget
0..*
hasRequirement
Question ∪ Criterion → Requirement
0..*
hasCriterion
Question → Criterion
1..*
hasRule
Criterion → ReductionRule
1..*
hasLevel
ReductionRule → ScoringLevel
2..*
hasEvidenceClaim
RuleOutcome → EvidenceClaim
1
citesAnswer
EvidenceClaim → AnswerQuotation
1..*
dependsOn
Rule → Rule
0..*

4.3 RuleKind Enum
The glue between subject modularity and grading reliability.
python
class RuleKind(Enum):
    """
    Describes what the grader is doing. Drives evidence extractor selection.
    Subject templates map QuestionType → likely RuleKinds.
    """
    STRUCTURE_AST = "structure_ast"           # Code structure via AST
    EXECUTION_TESTS = "execution_tests"       # Runtime behavior
    TEXT_ALIGNMENT = "text_alignment"         # Text matches expected
    REFERENCE_CITATION = "reference_citation" # Cites required source
    FORMAT_REQUIREMENT = "format_requirement" # Meets format constraint
    REASONING_QUALITY = "reasoning_quality"   # Explanation/justification quality
    PRESENCE_CHECK = "presence_check"         # Component exists
    NUMERIC_ACCURACY = "numeric_accuracy"     # Math computation correct
Usage: RuleKind ensures the grading agent uses the correct evidence extractor. A STRUCTURE_AST rule cannot be evaluated with TEXT_ALIGNMENT logic.
4.4 Other Key Enums
python
class QuestionType(Enum):
    SHORT_ANSWER = "short_answer"
    CODING_TASK = "coding_task"
    TRACE_TABLE = "trace_table"
    COMPUTATION = "computation"
    PROOF = "proof"
    ESSAY = "essay"
    SOURCE_ANALYSIS = "source_analysis"

class ClaimType(Enum):
    PRESENCE = "presence"
    CORRECTNESS = "correctness"
    COVERAGE = "coverage"
    CONSTRAINT = "constraint"
    QUALITY = "quality"

class MeasurabilityStatus(Enum):
    MEASURABLE = "measurable"
    PARTIALLY_MEASURABLE = "partially_measurable"
    NOT_MEASURABLE = "not_measurable"

class AnnotationSeverity(Enum):
    ERROR = "error"      # Blocks compilation to GradingRubricContract
    WARNING = "warning"  # Allows compilation, requires teacher acknowledgment
    INFO = "info"        # Purely informational

5. EvidenceClaim Specification
python
@dataclass
class EvidenceClaim:
    """
    Atomic, auditable unit. One claim = one idea.
    One EvidenceClaim per RuleOutcome (structural contract).
    """
    claim_id: str
    claim_type: ClaimType              # From finite enum
    claim_statement: str               # Short, atomic, testable (max 200 chars)
    matched_level_id: str              # References exactly one ScoringLevel
    
    # MANDATORY: At least one
    answer_quotations: List[AnswerQuotation]  # len >= 1
    
    # CONDITIONAL: Based on criterion.evidencePolicy
    pedagogical_sources: List[PedagogicalSource]  # may be empty
Design notes:
truth_value removed — derivable from matched_level_id relative to max points
One EvidenceClaim per RuleOutcome by structural contract (not just policy)
This prevents "dump claims until something sticks" behavior

6. Requirement vs SkillTarget
Aspect
SkillTarget
Requirement
Nature
Teachable ability
Constraint/rule
Examples
Loop implementation, proof strategy
"Must use Java", "No libraries"
Default weight
Based on priority
Low (unless promoted)
Promotion
N/A
Teacher can promote to primary skill

Promotion suggestion policy: If requirement appears across ≥3 questions AND teacher consistently weights it ≥20% of question points, system suggests promotion.

7. ApproachClass (Internal Only)
python
@dataclass
class ApproachClass:
    """
    Used in extraction/validation pipeline. NOT in GradingRubricContract.
    """
    id: str
    name: str
    component_patterns: List[str]
Key simplification:
ApproachClass lives in ExtractRubricResponse and internal pipeline artifacts
GradingRubricContract only has allow_multiple_valid_forms: boolean at question/criterion level
This keeps the grading contract minimal and stable

8. GradingRubricContract Schema
python
GradingRubricContract = {
    "schema_version": "2.0",
    "contract_version": "uuid-v1",  # Increments on edit/recompile
    "rubric_id": "uuid",
    "subject": "computer_science",
    
    # Contract-level constants (inherited downward)
    "numeric_policy": {
        "precision": 0.25,
        "rounding_mode": "half_up",
        "sum_tolerance": 0.01
    },
    
    "questions": [
        {
            "question_id": "q1",
            "question_type": "coding_task",
            "total_points": 20,
            "allow_multiple_valid_forms": True,  # Simplified from ApproachClass[]
            
            "skill_targets": [
                {"id": "cs.loops.for", "priority": "primary"}
            ],
            "requirements": [
                {"id": "req.java", "description": "Must use Java", "promoted": False}
            ],
            
            "criteria": [
                {
                    "criterion_id": "q1.c0",
                    "index": 0,
                    "description": "Loop correctly iterates",
                    "points": 10,
                    "skill_targets": ["cs.loops.for"],
                    "requirements": [],
                    "measurability_status": "measurable",
                    
                    "evidence_policy": {
                        "answer_quotation_required": True,
                        "pedagogical_source": "never"
                    },
                    
                    "rules": [
                        {
                            "rule_id": "q1.c0.r0",
                            "index": 0,
                            "description": "Loop bounds correct",
                            "max_points": 5,
                            "scoring_type": "discrete_levels",
                            "level_selection_mode": "mutually_exclusive",
                            "rule_kind": "structure_ast",
                            
                            "levels": [
                                {"level_id": "none", "level_order": 0, "points": 0, "condition_hint": "Bounds wrong"},
                                {"level_id": "partial", "level_order": 1, "points": 2.5, "condition_hint": "Off-by-one"},
                                {"level_id": "full", "level_order": 2, "points": 5, "condition_hint": "Correct"}
                            ],
                            
                            "depends_on": []
                        }
                    ]
                }
            ]
        }
    ]
}
Simplifications applied:
conflicts_with removed (use depends_on only for v2.0)
approach_classes removed (replaced with allow_multiple_valid_forms boolean)
Level exclusivity removed (single level_selection_mode at rule level)
rubric_version renamed to contract_version

9. Validation Strategy
Concern
Mechanism
Enforcement
Class/relation structure
OWL ontology
Schema definition
Sum constraints, level coverage, evidence citation
SHACL shapes
Pre-save validation
Closed-world, numeric tolerance
Implementation code
Compilation + runtime

Annotation severity enforcement:
Severity
Behavior
error
Blocks compilation to GradingRubricContract
warning
Allows compilation, requires teacher acknowledgment
info
Purely informational, no action required


10. Unified Fallback Behavior
Condition
Fallback
Rationale
QuestionType unclear
short_answer + Annotation(warning)
Safe default
ApproachClass uncertain
allow_multiple_valid_forms: false, skip narrowness
Prevent false positives
measurability_status = not_measurable
ReviewFlag (severity: error), blocks auto-grade
Teacher must approve
Rule decomposition fails
Single rule = criterion itself
Graceful degradation
Code cannot parse (CS)
AST rules → not_measurable → ReviewFlag
Honest about limitations


11. Versioning
Version Type
Purpose
Increment Trigger
schema_version
Contract schema compatibility
Breaking schema change
contract_version
Specific compiled artifact
Teacher edit OR recompile
ontology_version
OWL ontology evolution
Class/relation change

Reproducibility guarantee: Given contract_version, grading is deterministic.

12. Subject Module Interface
python
class SubjectModule(ABC):
    
    @property
    @abstractmethod
    def skill_taxonomy(self) -> SKOSConceptScheme:
        """SKOS concept scheme with stable IRIs."""
        pass
    
    @property
    @abstractmethod
    def supported_question_types(self) -> List[QuestionType]:
        pass
    
    @property
    @abstractmethod
    def supported_rule_kinds(self) -> Dict[QuestionType, List[RuleKind]]:
        """Maps question types to likely rule kinds for template selection."""
        pass
    
    @abstractmethod
    def get_criterion_templates(self, question_type: QuestionType) -> List[CriterionTemplate]:
        pass
    
    @abstractmethod
    def get_misconceptions(self, topic: str) -> List[MisconceptionPattern]:
        pass
    
    @abstractmethod
    def get_conventions(self) -> ConventionPack:
        """Implicit requirements for this subject."""
        pass
    
    @abstractmethod
    def evaluate_rule(
        self, 
        answer: StudentAnswer, 
        rule: ReductionRule
    ) -> RuleOutcome:
        """
        Returns exactly ONE RuleOutcome containing ONE EvidenceClaim.
        This is a structural contract, not just a preference.
        """
        pass
Key constraint: evaluate_rule returns one RuleOutcome, not a list. This prevents non-deterministic "claim dumping."

13. RuleOutcome Structure
python
@dataclass
class RuleOutcome:
    """
    Result of evaluating one ReductionRule against one StudentAnswer.
    Contains exactly one EvidenceClaim (structural contract).
    """
    rule_id: str
    selected_level_id: str
    points_awarded: float
    evidence_claim: EvidenceClaim  # Exactly one, not a list
    
    def validate(self) -> bool:
        return (
            self.evidence_claim is not None and
            len(self.evidence_claim.answer_quotations) >= 1 and
            0 <= self.points_awarded <= self.rule.max_points
        )

APPENDICES
Appendix A: Pipeline → Competency Mapping
Phase
Step
Competency Groups
1. Ingest
Parse DOCX, extract teacher criteria
Extraction Fidelity
2. Classify
QuestionType + Skills + Requirements
Pedagogy, Subject
3. Model
Correctness + ApproachClasses
Correctness Model
4. Validate
Flag, enhance, add missing
Criterion Quality
5. Weight
Assign points
Point Allocation
6. Compile
Rules → Contract
Rules, Evidence


Appendix B: MVP Phasing
Phase 1: Core Infrastructure (4-6 weeks)
EvidenceClaim with one-per-outcome contract
Requirement class + promotion suggestion
QuestionType → template routing
RuleKind enum + subject module integration
SHACL shapes for 7 invariants
NumericPolicy at contract level
contract_version tracking
Annotation severity enforcement
Exit: All SHACL shapes pass, evidence citation rate = 100%
Phase 2: Pedagogical Intelligence (4-6 weeks)
CS skill taxonomy (SKOS, hardcoded from Bagrut)
ApproachClass in pipeline (not contract)
allow_multiple_valid_forms boolean
MeasurabilityStatus + unified fallback
Merge detection
Exit: Teacher edit rate < 5 per rubric
Phase 3: Contract + Grading (3-4 weeks)
GradingRubricContract v2.0 compiler
Closed-world enforcement
depends_on for double-counting prevention
Backward compatibility layer
Exit: Grading uses new contract
Phase 4: Quality Assurance (3-4 weeks)
Golden rubric suite (20+ CS)
Golden grading suite (50+ outcomes)
Adversarial tests
CI/CD regression blocking
Exit: 95% golden suite pass
Phase 5: Subject Expansion (6-8 weeks)
Subject module interface finalized
Math module
Math golden suite
Exit: Second subject operational

Appendix C: Open Questions
Narrowness calibration: What confidence threshold for ApproachClass enumeration?
Promotion learning: Exact weighting for "repeated + high-weighted" detection?
Cross-subject validation: Will universal/specific split hold for humanities?
Partial measurability: When does partially_measurable trigger ReviewFlag?

Appendix D: Assumptions
Teachers upload complete rubrics
Single DOCX per rubric
Bagrut syllabus hardcoded as CS taxonomy
Teachers review before grading
Discrete levels sufficient (no continuous scoring)
Teacher edit rate is valid quality proxy


