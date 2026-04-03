# EEC Quora Bot

Automated Quora marketing tool for **EEC Global** (Enbee Education Center). Discovers relevant questions on Quora, generates expert-quality answers using AI personas matched to EEC's team, and manages posting with human review.

## Architecture

```
Question Discovery  →  Persona Matching  →  AI Answer Generation  →  Human Review  →  Browser Posting
(Google + Quora)       (topic-based)        (Claude API)             (Dashboard)      (Playwright)
```

### Components

| Component | Description |
|-----------|-------------|
| **Discovery Engine** | Finds relevant Quora questions via Google `site:quora.com` search and direct Quora topic scraping |
| **Persona System** | 8 expert personas mapped to EEC's domains (IELTS/PTE trainer, GRE/SAT specialist, study abroad counselor, visa expert, etc.) |
| **Answer Generator** | Uses Claude API to generate persona-appropriate answers with EEC knowledge base |
| **Review Dashboard** | FastAPI web app for reviewing, approving, or rejecting generated answers |
| **Posting Engine** | Playwright-based browser automation with anti-detection measures |
| **Monitoring** | Account health tracking, failure alerts, activity logging |

## Quick Start

### 1. Install dependencies

```bash
pip install -e .
playwright install chromium
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your Anthropic API key and other settings
```

### 3. Initialize

```bash
python -m src.cli init
```

### 4. Discover questions

```bash
python -m src.cli discover
```

### 5. Generate answers

```bash
python -m src.cli generate              # Generate for top 10 discovered questions
python -m src.cli generate --question-id 5  # Generate for specific question
```

### 6. Start the dashboard

```bash
python -m src.cli dashboard
# Open http://localhost:8000 in your browser
```

### 7. Check status

```bash
python -m src.cli status
```

## Personas

| Persona | Expertise | Answers Questions About |
|---------|-----------|------------------------|
| **Amit Jalan** (Founder) | Study abroad, MBA/MS admissions, career counseling | Study abroad strategy, university selection, career planning |
| **Dr. Priya Sharma** | IELTS, PTE coaching | IELTS/PTE preparation, score improvement, test strategies |
| **Rahul Kapoor** | GRE, SAT, D-SAT | GRE/SAT prep, quantitative reasoning, study plans |
| **Sneha Patel** | Canada, UK, Australia admissions | Country selection, SOP writing, scholarships, MiM programs |
| **Dr. Meera Iyer** | MBBS abroad, Germany | Medical education abroad, NEET counseling, German universities |
| **Vikram Desai** | Visa & immigration | Student/spouse/tourist visas, documentation, interview tips |
| **Ananya Krishnan** | TOEFL, Duolingo, CELPIP, OET | Test comparisons, English proficiency prep |
| **Nikhil Mehta** | Education loans, financial planning | Loan applications, scholarships, cost planning |

## Workflow

1. **Discovery** runs on schedule (or manually) to find new Quora questions
2. Questions are **scored** by relevance (keyword matching, opportunity assessment)
3. Top questions are **matched** to the best expert persona
4. **Claude API** generates answers in the persona's voice with EEC knowledge
5. Answers enter the **review queue** in the dashboard
6. A human **approves, edits, or rejects** each answer
7. Approved answers are **posted** via Playwright with anti-detection measures
8. **Monitoring** tracks account health, posting success, and alerts

## Safety & Rate Limiting

- Maximum 3 posts per account per day (configurable)
- Random delays between posts (30-120 minutes)
- Human-like typing and browsing behavior
- Account rotation and health monitoring
- Automatic pause on CAPTCHA or ban detection
- Human review required before any posting

## Important Notes

- Quora does **not** have an official API for posting. This tool uses browser automation.
- Automated posting **violates** Quora's Terms of Service. Use at your own risk.
- The human-in-the-loop review system helps ensure answer quality and reduces risk.
- Account warm-up is recommended before automated posting (use accounts manually for 2-4 weeks first).
