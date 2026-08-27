![](https://capsule-render.vercel.app/api?type=waving&color=0:0B1F3A,100:2DD4BF&height=200&section=header&text=AEOS&fontSize=70&fontColor=ffffff&animation=fadeIn&desc=Engineering%20Decision%20Intelligence&descAlignY=65&descSize=18)

<p align="center">
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&size=20&pause=1500&color=2DD4BF&center=true&vCenter=true&width=650&lines=Reads+your+problem+in+plain+English;Never+lets+the+AI+pick+the+winner;Every+score+is+deterministic+and+traceable" />
</p>

**AEOS** (Automated Engineering decision-support system) turns a plain-English engineering problem into a ranked, evidence-linked technology recommendation — with every score traceable back to the exact arithmetic that produced it.

It is not a chatbot that picks a favorite framework. The AI only reads your problem and states what it implies. A separate, deterministic scoring function — plain code, no AI — computes every number.

> This repository covers the **backend department only**: comparing backend frameworks for a given problem. Frontend, database, cloud, and security departments are planned but not yet built.

---

## Why

Ask an LLM directly "should I use Next.js or Django?" and you get a confident-sounding paragraph with no way to check it. AEOS separates the two things that answer actually requires:

- **Reading** — an LLM interprets your problem and extracts structured requirements and constraints. It never assigns a score.
- **Judging** — a fixed, deterministic formula scores each candidate technology against those requirements, using a hand-curated knowledge base. No AI involved in this step at all.

Every output includes the formula trace behind its score and the evidence behind every claim — so a recommendation is something you can check, not just trust.

---

## How it works

```
Problem statement (plain English)
        ↓
Requirement extraction (LLM)      → structured requirements
        ↓
Constraint extraction (LLM)       → hard vs. soft constraints
        ↓
Knowledge base lookup             → candidate technology profiles
        ↓
Hard-constraint elimination       → plain code, no AI
        ↓
Discipline analysis (LLM)         → what each requirement implies
        ↓
Deterministic weighted scoring    → plain code, no AI
        ↓
Ranked result + formula trace + evidence
```

---

## Tech stack

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Pydantic](https://img.shields.io/badge/Pydantic-E92063?style=for-the-badge&logo=pydantic&logoColor=white)
![Firebase](https://img.shields.io/badge/Firestore-FFCA28?style=for-the-badge&logo=firebase&logoColor=black)
![Ollama](https://img.shields.io/badge/Ollama-000000?style=for-the-badge&logo=ollama&logoColor=white)

| Piece | Choice |
|---|---|
| Orchestrator language | Python |
| Schema enforcement | Pydantic |
| LLM | Local, via [Ollama](https://ollama.com) (`llama3.1`) — no API key, no per-call cost |
| Knowledge base (MVP) | Flat JSON files, one per technology, version-controlled |
| API layer | FastAPI |
| Persistence | Firebase Firestore |
| Deployment (planned) | Railway |

The LLM is accessed through an abstract `LLMProvider` interface (`llm/base.py`), so swapping providers (e.g. back to a hosted API) is a contained change, not a rewrite.

---

## Project structure

```
backend/
├── schemas/              # Pydantic schemas — TechnologyProfile, RequirementAnalysis
├── knowledge_base/       # Curated technology profiles + loader
│   └── backend/          # nextjs.json, express.json, nestjs.json, etc.
├── llm/                  # LLMProvider interface + Claude/Ollama implementations
├── orchestrator/         # Extraction, analysis, and the full pipeline
├── scoring/              # Deterministic scorer — zero LLM calls
├── persistence/          # Firestore client, saves every run
├── api/                  # FastAPI app (/analyze, /health)
├── tests/                # pytest suite, including hand-computed scorer tests
├── secrets/              # Firebase service account key (gitignored, never committed)
└── requirements.txt
```

---

## Setup

**1. Clone and install dependencies**

```bash
git clone https://github.com/AaryamannOberoi/aeos-backend.git
cd aeos-backend
pip install -r requirements.txt
```

**2. Install Ollama and pull the model**

```bash
# Install from https://ollama.com/download, then:
ollama pull llama3.1
```

**3. Set up Firebase**

- Create a Firebase project → enable Firestore (production mode)
- Generate a service account key (Project Settings → Service Accounts) and place the downloaded `.json` file in `secrets/`

**4. Create `.env`**

```
FIREBASE_CREDENTIALS_PATH=secrets/your-firebase-key-filename.json
```

**5. Run the API**

```bash
python api/main.py
```

Server starts at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

---

## Usage

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"problem_statement": "Build a backend for a high-traffic e-commerce platform that needs strong security, rapid development, and horizontal scalability."}'
```

Optionally pass custom weights to reflect your own priorities:

```json
{
  "problem_statement": "...",
  "weights": { "learning_curve": 3.0, "horizontal_scaling": 1.0 }
}
```

Response includes extracted requirements and constraints, any eliminated candidates (and why), any hard constraints that couldn't be verified, and a ranked list of technologies — each with its full scoring arithmetic shown.

---

## Testing

```bash
pytest tests/
```

The scorer's correctness is tested with hand-computed, fixed test cases — independent of any live LLM output — so its arithmetic can be verified on its own.

---

## Current status

- ✅ Full pipeline working end-to-end, tested against multiple problem statements
- ✅ 5 curated backend technology profiles (Next.js, NestJS, Express, Django REST Framework, Spring Boot)
- ✅ Real API, callable over HTTP
- ✅ Every run persisted to Firestore
- 🔜 Deployment, rate limiting, CORS, golden test dataset
- 🔜 Additional engineering disciplines (frontend, database, cloud, security)

## Known limitations

- The system only knows about technologies with a hand-written profile in the knowledge base — it does not draw on the LLM's general knowledge for candidate generation.
- Hard constraints that don't map to a current schema field (e.g. regulatory compliance, database latency) are honestly recorded as unverified rather than guessed at.
- Local LLM inference is slower and slightly less reliable at strict schema-following than a hosted model — a deliberate trade for zero cost and no vendor dependency during development.

---

## License

Not yet decided.

![](https://capsule-render.vercel.app/api?type=waving&color=0:2DD4BF,100:0B1F3A&height=100&section=footer)
