"""
owl_ontology.py
Implementasi OWL2 Ontology untuk domain kebutuhan sistem (requirements).
Menggunakan struktur OWL2 dengan Manchester Syntax logic.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import xml.etree.ElementTree as ET
from datetime import datetime


# ── OWL2 Namespaces ───────────────────────────────────────────────────────────
OWL_NS  = "http://www.w3.org/2002/07/owl#"
RDF_NS  = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"
XSD_NS  = "http://www.w3.org/2001/XMLSchema#"
BASE_IRI = "http://requirements-ontology.org/owl#"


class Modality(Enum):
    """OWL2 Named Individual untuk modalitas kebutuhan."""
    MUST     = "MUST"        # Wajib / harus
    MUST_NOT = "MUST_NOT"    # Harus tidak
    SHOULD   = "SHOULD"      # Sebaiknya
    CAN      = "CAN"         # Bisa / dapat
    CANNOT   = "CANNOT"      # Tidak bisa


class ConditionType(Enum):
    """Tipe kondisi dalam kebutuhan."""
    UNCONDITIONAL = "UNCONDITIONAL"   # Tanpa syarat
    CONDITIONAL   = "CONDITIONAL"     # Dengan syarat (if/jika/apabila)
    EXCEPTION     = "EXCEPTION"       # Pengecualian (kecuali/unless)


@dataclass
class OWLIndividual:
    """Representasi OWL2 Named Individual."""
    iri: str
    class_type: str
    properties: dict = field(default_factory=dict)
    annotations: dict = field(default_factory=dict)


@dataclass
class RequirementIndividual:
    """
    OWL2 Individual untuk satu kalimat kebutuhan.
    
    Class hierarchy:
      Requirement
        ├── FunctionalRequirement
        └── ConstraintRequirement
    
    Object Properties:
      - hasSubject      → SubjectEntity
      - hasAction       → ActionEntity
      - hasObject       → ObjectEntity
      - hasModality     → ModalityIndividual
      - hasCondition    → ConditionEntity
      - conflictsWith   → Requirement  (diisi saat reasoning)
    
    Data Properties:
      - requirementText : xsd:string
      - requirementIndex: xsd:integer
      - isNegated       : xsd:boolean
    """
    index: int
    text: str
    subject: str            # hasSubject
    action: str             # hasAction  (verb phrase)
    obj: str                # hasObject  (feature/resource)
    modality: Modality      # hasModality
    is_negated: bool        # isNegated
    condition_type: ConditionType
    condition_text: str     # teks kondisi jika ada
    raw_tokens: list = field(default_factory=list)

    @property
    def iri(self) -> str:
        return f"{BASE_IRI}Requirement_{self.index}"

    @property
    def effective_modality(self) -> str:
        """Combine modality + negation → semantic label."""
        if self.is_negated:
            if self.modality in (Modality.MUST, Modality.SHOULD):
                return "PROHIBIT"
            if self.modality == Modality.CAN:
                return "PROHIBIT"
        else:
            if self.modality == Modality.MUST:
                return "OBLIGATE"
            if self.modality == Modality.MUST_NOT:
                return "PROHIBIT"
            if self.modality in (Modality.CAN, Modality.SHOULD):
                return "PERMIT"
        return "UNKNOWN"

    def to_owl_xml(self) -> str:
        """Serialize ke OWL2/XML snippet."""
        lines = [
            f'  <!-- Requirement #{self.index} -->',
            f'  <owl:NamedIndividual rdf:about="{self.iri}">',
            f'    <rdf:type rdf:resource="{BASE_IRI}Requirement"/>',
            f'    <req:requirementIndex rdf:datatype="{XSD_NS}integer">{self.index}</req:requirementIndex>',
            f'    <req:requirementText rdf:datatype="{XSD_NS}string">{self.text}</req:requirementText>',
            f'    <req:hasSubject rdf:datatype="{XSD_NS}string">{self.subject}</req:hasSubject>',
            f'    <req:hasAction rdf:datatype="{XSD_NS}string">{self.action}</req:hasAction>',
            f'    <req:hasObject rdf:datatype="{XSD_NS}string">{self.obj}</req:hasObject>',
            f'    <req:hasModality rdf:resource="{BASE_IRI}{self.modality.value}"/>',
            f'    <req:isNegated rdf:datatype="{XSD_NS}boolean">{str(self.is_negated).lower()}</req:isNegated>',
            f'    <req:conditionType rdf:datatype="{XSD_NS}string">{self.condition_type.value}</req:conditionType>',
            f'    <req:conditionText rdf:datatype="{XSD_NS}string">{self.condition_text}</req:conditionText>',
            f'    <req:effectiveModality rdf:datatype="{XSD_NS}string">{self.effective_modality}</req:effectiveModality>',
            f'  </owl:NamedIndividual>',
        ]
        return "\n".join(lines)


@dataclass
class InconsistencyAxiom:
    """
    OWL2 Axiom: conflictsWith(R_i, R_j)
    Merupakan Symmetric ObjectProperty.
    """
    req_a: RequirementIndividual
    req_b: RequirementIndividual
    conflict_type: str
    explanation: str
    severity: str  # HIGH / MEDIUM / LOW
    similarity_score: float

    def to_owl_xml(self) -> str:
        return (
            f'  <!-- Inconsistency: R{self.req_a.index} conflictsWith R{self.req_b.index} -->\n'
            f'  <owl:NegativeObjectPropertyAssertion>\n'
            f'    <owl:ObjectProperty rdf:about="{BASE_IRI}conflictsWith"/>\n'
            f'    <owl:sourceIndividual rdf:resource="{self.req_a.iri}"/>\n'
            f'    <owl:targetIndividual rdf:resource="{self.req_b.iri}"/>\n'
            f'    <rdfs:comment>{self.conflict_type}: {self.explanation}</rdfs:comment>\n'
            f'  </owl:NegativeObjectPropertyAssertion>'
        )


class RequirementsOntology:
    """
    OWL2 Ontology untuk menyimpan dan mengelola kebutuhan sistem.
    Mendukung serialisasi ke OWL/XML format.
    """

    ONTOLOGY_HEADER = f"""<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="{RDF_NS}"
         xmlns:rdfs="{RDFS_NS}"
         xmlns:owl="{OWL_NS}"
         xmlns:xsd="{XSD_NS}"
         xmlns:req="{BASE_IRI}">

  <owl:Ontology rdf:about="{BASE_IRI}">
    <rdfs:label>Requirements Inconsistency Ontology</rdfs:label>
    <rdfs:comment>OWL2 ontology untuk pendeteksian inkonsistensi kebutuhan sistem</rdfs:comment>
    <owl:versionInfo>1.0</owl:versionInfo>
  </owl:Ontology>

  <!-- ═══ OWL2 Class Hierarchy ═══ -->
  <owl:Class rdf:about="{BASE_IRI}Requirement"/>
  <owl:Class rdf:about="{BASE_IRI}FunctionalRequirement">
    <rdfs:subClassOf rdf:resource="{BASE_IRI}Requirement"/>
  </owl:Class>
  <owl:Class rdf:about="{BASE_IRI}ConstraintRequirement">
    <rdfs:subClassOf rdf:resource="{BASE_IRI}Requirement"/>
  </owl:Class>

  <!-- ═══ Object Properties ═══ -->
  <owl:ObjectProperty rdf:about="{BASE_IRI}hasModality"/>
  <owl:ObjectProperty rdf:about="{BASE_IRI}conflictsWith">
    <rdf:type rdf:resource="{OWL_NS}SymmetricProperty"/>
    <rdfs:comment>Menandai dua kebutuhan yang saling berkonflik</rdfs:comment>
  </owl:ObjectProperty>

  <!-- ═══ Data Properties ═══ -->
  <owl:DatatypeProperty rdf:about="{BASE_IRI}requirementText">
    <rdfs:range rdf:resource="{XSD_NS}string"/>
  </owl:DatatypeProperty>
  <owl:DatatypeProperty rdf:about="{BASE_IRI}requirementIndex">
    <rdfs:range rdf:resource="{XSD_NS}integer"/>
  </owl:DatatypeProperty>
  <owl:DatatypeProperty rdf:about="{BASE_IRI}isNegated">
    <rdfs:range rdf:resource="{XSD_NS}boolean"/>
  </owl:DatatypeProperty>
  <owl:DatatypeProperty rdf:about="{BASE_IRI}hasSubject"/>
  <owl:DatatypeProperty rdf:about="{BASE_IRI}hasAction"/>
  <owl:DatatypeProperty rdf:about="{BASE_IRI}hasObject"/>
  <owl:DatatypeProperty rdf:about="{BASE_IRI}conditionType"/>
  <owl:DatatypeProperty rdf:about="{BASE_IRI}conditionText"/>
  <owl:DatatypeProperty rdf:about="{BASE_IRI}effectiveModality"/>

  <!-- ═══ Modality Named Individuals ═══ -->
  <owl:NamedIndividual rdf:about="{BASE_IRI}MUST"/>
  <owl:NamedIndividual rdf:about="{BASE_IRI}MUST_NOT"/>
  <owl:NamedIndividual rdf:about="{BASE_IRI}SHOULD"/>
  <owl:NamedIndividual rdf:about="{BASE_IRI}CAN"/>
  <owl:NamedIndividual rdf:about="{BASE_IRI}CANNOT"/>

"""

    def __init__(self):
        self.individuals: list[RequirementIndividual] = []
        self.inconsistencies: list[InconsistencyAxiom] = []

    def add_individual(self, req: RequirementIndividual):
        self.individuals.append(req)

    def add_inconsistency(self, axiom: InconsistencyAxiom):
        self.inconsistencies.append(axiom)

    def export_owl_xml(self, path: str):
        """Export ontologi ke file OWL/XML."""
        parts = [self.ONTOLOGY_HEADER]
        parts.append("  <!-- ═══ Requirement Individuals ═══ -->")
        for ind in self.individuals:
            parts.append(ind.to_owl_xml())
        parts.append("\n  <!-- ═══ Inconsistency Axioms ═══ -->")
        for axiom in self.inconsistencies:
            parts.append(axiom.to_owl_xml())
        parts.append("\n</rdf:RDF>")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(parts))
        return path
