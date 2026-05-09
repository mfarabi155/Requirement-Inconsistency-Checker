# 🔍 Requirements Inconsistency Checker

An **OWL2 Ontology** and **Rule-based NLP** system for automatically detecting inconsistencies between software requirement statements via the terminal.

---

## 📌 Background

In software development, conflicting requirements are one of the leading causes of project failure. This system helps analysts and developers automatically detect inconsistencies before the implementation phase begins.

**Example of an inconsistency:**
> **#1** "The system must lock the exam feature if student attendance is below 80 percent"
> **#5** "The system may unlock the exam feature if the student receives permission from the lecturer even if attendance is below 80 percent"

Requirements #1 and #5 conflict — one prohibits, the other permits under overlapping conditions.

---

## 🏗️ System Architecture

```
requirement_checker/
├── main.py            # Main CLI (terminal interface)
├── owl_ontology.py    # OWL2 data model & serialization to .owl/XML
├── nlp_extractor.py   # Rule-based NLP (subject, action, object, modality extraction)
└── owl_reasoner.py    # OWL2 Reasoner (inconsistency detection rules)
```

### System Flow

```
Requirement Input
       │
       ▼
[nlp_extractor.py]
  Tokenization → Modality Detection → Condition Detection → Subject/Action/Object Extraction
       │
       ▼
[owl_ontology.py]
  Construct OWL2 Named Individual (RequirementIndividual)
  Store into RequirementsOntology
       │
       ▼
[owl_reasoner.py]
  Compare all requirement pairs O(n²)
  Apply 6 Inconsistency Rules (OWL2 Axioms)
       │
       ▼
  Inconsistency Report + Export .owl (Protégé-compatible)
```

---

## ⚙️ OWL2 Ontology

The system implements OWL2 with the following structure:

### Class Hierarchy
```
Requirement
├── FunctionalRequirement
└── ConstraintRequirement
```

### Object Properties
| Property | Type | Description |
|---|---|---|
| `hasModality` | ObjectProperty | Modality of the requirement |
| `conflictsWith` | SymmetricProperty | Inconsistency relation between requirements |

### Data Properties
| Property | Range | Description |
|---|---|---|
| `requirementText` | xsd:string | Original requirement text |
| `requirementIndex` | xsd:integer | Sequence number |
| `isNegated` | xsd:boolean | Whether the requirement contains negation |
| `hasSubject` | xsd:string | Sentence subject |
| `hasAction` | xsd:string | Action / verb phrase |
| `hasObject` | xsd:string | Object / entity affected by the action |
| `conditionType` | xsd:string | UNCONDITIONAL / CONDITIONAL / EXCEPTION |
| `effectiveModality` | xsd:string | OBLIGATE / PROHIBIT / PERMIT |

### Modality Named Individuals
`MUST` · `MUST_NOT` · `SHOULD` · `CAN` · `CANNOT`

---

## 🧠 Inconsistency Rules (OWL2 Reasoning)

| # | Rule Name | Example | Severity |
|---|---|---|---|
| 1 | **Direct Contradiction** | "must X" vs "must not X" (unconditional) | 🔴 HIGH |
| 2 | **Antonym Action Inconsistency** | "must lock feature" vs "may unlock feature" (overlapping condition) | 🔴 HIGH |
| 3 | **Conditional Contradiction** | "prohibited X" (absolute) vs "allowed X if..." | 🔴 HIGH |
| 4 | **Scope Inconsistency** | Two conditional rules with similar conditions but opposite outcomes | 🟡 MEDIUM |
| 5 | **Semantic Redundancy** | Two requirements stating the same thing differently | 🔵 LOW |
| 6 | **Modal Strength Inconsistency** | "must X" vs "may X" on the same subject | 🟡 MEDIUM |

Topic similarity is detected using **Jaccard Similarity** on normalized tokens with a threshold of **≥ 0.30**.

---

## 🌐 Language Support

The system supports both **Bahasa Indonesia** and **English**, including mixed-language input in the same session.

**Supported English modality keywords (RFC 2119):**

| Keyword | Modality |
|---|---|
| `must`, `shall`, `required` | OBLIGATE |
| `should` | PERMIT (recommended) |
| `may`, `can` | PERMIT |
| `must not`, `shall not` | PROHIBIT |
| `cannot`, `can not` | PROHIBIT |

**Supported English condition keywords:**
`if` · `when` · `unless` · `except` · `provided` · `as long as` · `given that` · `in case`

---

## 🚀 Installation & Usage

### Prerequisites
- Python **3.10+** (uses modern type hints)
- No external libraries required — **pure Python stdlib**

### Installation
```bash
git clone https://github.com/mfarabi155/Requirement-Inconsistency-Checker
cd requirement-inconsistency-checker
```

### Run
```bash
python main.py
```

---

## 🖥️ Usage Demo

```
╔══════════════════════════════════════════════════════════════╗
║     🔍 REQUIREMENTS INCONSISTENCY CHECKER                    ║
║     Powered by OWL2 Ontology + Rule-based NLP                ║
╚══════════════════════════════════════════════════════════════╝

[Requirement #1] > The system must lock the exam feature if student attendance is below 80 percent
  ✔ Added as OBLIGATE | Condition: CONDITIONAL

[Requirement #2] > The system may unlock the exam feature if the student receives permission from the lecturer
  ✔ Added as PERMIT | Condition: CONDITIONAL

[Requirement #3] > done

  ⚠️  Inconsistency #1  [HIGH]
  ─────────────────────────────────────────────────────────────
  Type        : Conditional Contradiction
  Pair        : Requirement #1 ↔ Requirement #2
  Similarity  : 61%

  Requirement #1: "The system must lock the exam feature if student attendance..."
  Requirement #2: "The system may unlock the exam feature if the student receives..."

  📌 Explanation:
     Requirement #1 mandates the action 'lock' under the condition that
     attendance is below 80%, but requirement #2 permits the opposing
     action 'unlock' under an overlapping condition...
```

---

## 📝 Terminal Commands

| Command | Function |
|---|---|
| *(type a requirement sentence)* | Add a new requirement |
| `done` / `selesai` | Run inconsistency analysis |
| `list` / `lihat` | Display the list of entered requirements |
| `hapus <N>` | Delete requirement number N |
| `debug on` / `debug off` | Show/hide NLP extraction details |
| `reset` | Clear all requirements and start over |
| `exit` / `keluar` | Exit the program |

---

## 📤 OWL/XML Output

After analysis, the system automatically exports the ontology to:
```
requirements_ontology_YYYYMMDD_HHMMSS.owl
```

This file is compatible with **[Protégé OWL Editor](https://protege.stanford.edu/)** and standard OWL2 reasoners such as HermiT and Pellet.

Example OWL/XML snippet:
```xml
<owl:NamedIndividual rdf:about="...#Requirement_1">
  <rdf:type rdf:resource="...#Requirement"/>
  <req:requirementText>The system must lock the exam feature...</req:requirementText>
  <req:hasModality rdf:resource="...#MUST"/>
  <req:effectiveModality>OBLIGATE</req:effectiveModality>
  <req:conditionType>CONDITIONAL</req:conditionType>
  <req:isNegated rdf:datatype="...#boolean">false</req:isNegated>
</owl:NamedIndividual>

<owl:NegativeObjectPropertyAssertion>
  <owl:ObjectProperty rdf:about="...#conflictsWith"/>
  <owl:sourceIndividual rdf:resource="...#Requirement_1"/>
  <owl:targetIndividual rdf:resource="...#Requirement_5"/>
</owl:NegativeObjectPropertyAssertion>
```

---

## 📚 Sample Requirements for Testing

Copy and input one by one into the terminal:

```
The system must lock the exam feature if student attendance is below 80 percent
The system must save activity logs every time a user performs a login
The user must not access the admin panel without two-factor authentication
The user can access the admin panel if they have logged in using a Google account
The system may unlock the exam feature if the student receives permission from the lecturer even if attendance is below 80 percent
The system must save activity logs every time a user enters the system
The lecturer must be able to download grade reports for all students at any time
The system shall not display student grades to anyone other than the assigned lecturer
Students can view the exam grades of other students for comparison purposes
The system must block exam access if cheating is detected during the exam
```

**Expected inconsistencies detected:**

| Pair | Type | Severity |
|---|---|---|
| #1 ↔ #5 | Conditional Contradiction (lock vs unlock, overlapping condition) | 🔴 HIGH |
| #3 ↔ #4 | Conditional Contradiction (block admin vs allow with Google login) | 🔴 HIGH |
| #8 ↔ #9 | Direct Contradiction (hide grades vs allow viewing) | 🔴 HIGH |
| #2 ↔ #6 | Semantic Redundancy | 🔵 LOW |

---

## 🔧 Future Development

Possible improvements:

- [ ] Integrate **spaCy** for more accurate NLP (dependency parsing)
- [ ] Integrate **owlready2** for full OWL2 reasoning (HermiT/Pellet)
- [ ] Support input from `.txt` or `.csv` files
- [ ] Web interface using Flask/FastAPI
- [ ] Inconsistency graph visualization

---

## 📄 License

MIT License — free to use and modify.
