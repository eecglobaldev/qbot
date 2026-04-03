"""EEC-specific knowledge base for answer generation.

Contains factual information about EEC services, exam details, country guides,
and other domain knowledge that personas can reference in their answers.
"""

EEC_COMPANY_FACTS = """
## About EEC (Enbee Education Center)
- Founded in 1997 by Mr. Amit Jalan (Purdue University alumnus)
- 29+ years of experience in overseas education
- 26 centers across 12 cities in Gujarat, India
- Helped 50,000+ students achieve their study abroad dreams
- Recognized by IDP, British Council, TOEFL/ETS, and AIRC
- Publishes 60+ ISBN preparation books annually
- 90,000+ collective classroom hours delivered
- Provides free technology tools worth Rs. 50,000 (mock tests, AI-powered SOP writing, visa interview prep)
"""

EXAM_KNOWLEDGE = {
    "IELTS": {
        "full_name": "International English Language Testing System",
        "types": "Academic (for university admission) and General Training (for migration/work)",
        "sections": "Listening (30 min), Reading (60 min), Writing (60 min), Speaking (11-14 min)",
        "scoring": "Band score 0-9, most universities require 6.5-7.0 for admission",
        "frequency": "Multiple test dates available every month",
        "validity": "2 years",
        "accepted_by": "11,000+ organizations in 140+ countries",
        "tips": [
            "Focus on time management — especially in Reading (20 min per passage)",
            "For Writing Task 2, practice the OREO structure: Opinion, Reason, Example, Opinion restate",
            "Speaking is conversational, not a presentation — be natural",
            "Use the Cambridge IELTS practice books (official material)",
        ],
    },
    "PTE": {
        "full_name": "Pearson Test of English Academic",
        "sections": "Speaking & Writing (54-67 min), Reading (29-30 min), Listening (30-43 min)",
        "scoring": "10-90 score scale, integrated scoring across skills",
        "frequency": "Available throughout the year at Pearson test centers",
        "validity": "2 years",
        "key_advantage": "Computer-based, AI-scored, results in 1-2 business days",
        "tips": [
            "Read Aloud carries heavy weight — practice reading fluently",
            "Repeat Sentence is the highest-scoring item for both Speaking and Listening",
            "Write From Dictation is crucial for Listening and Writing scores",
            "Use PTE practice software to get comfortable with the computer interface",
        ],
    },
    "GRE": {
        "full_name": "Graduate Record Examinations",
        "sections": "Verbal Reasoning (2 sections), Quantitative Reasoning (2 sections), Analytical Writing (1 section)",
        "scoring": "Verbal 130-170, Quant 130-170, AWA 0-6",
        "validity": "5 years",
        "key_fact": "Shorter format since September 2023 (under 2 hours)",
        "tips": [
            "Build vocabulary systematically — learn 10-15 words daily with context",
            "For Quant, focus on number properties and geometry — they appear most often",
            "Practice with official ETS material (PowerPrep tests are the most accurate predictor)",
            "Use the on-screen calculator strategically — don't over-rely on it",
        ],
    },
    "TOEFL": {
        "full_name": "Test of English as a Foreign Language iBT",
        "sections": "Reading (35 min), Listening (36 min), Speaking (16 min), Writing (29 min)",
        "scoring": "0-120 total (30 per section)",
        "validity": "2 years",
        "accepted_by": "12,000+ institutions in 160+ countries",
        "tips": [
            "Note-taking is essential for Listening and Speaking integrated tasks",
            "For Speaking, use the 'TPO' (TOEFL Practice Online) for realistic practice",
            "Writing: aim for 300+ words in the independent task",
            "Reading: practice skimming and scanning — don't read every word",
        ],
    },
    "SAT": {
        "full_name": "Scholastic Assessment Test (now Digital SAT)",
        "sections": "Reading and Writing (64 min), Math (70 min)",
        "scoring": "400-1600 total",
        "key_change": "Fully digital since March 2024, adaptive testing format",
        "tips": [
            "The digital SAT is adaptive — perform well in Module 1 to get harder (higher-scoring) Module 2",
            "Math: master algebra and data analysis — they make up 70% of questions",
            "Reading: focus on evidence-based reasoning and vocabulary in context",
            "Use Khan Academy (free official prep) and Bluebook practice app",
        ],
    },
    "Duolingo": {
        "full_name": "Duolingo English Test",
        "duration": "About 1 hour",
        "scoring": "10-160 scale",
        "key_advantage": "Can take from home, results in 48 hours, accepted by 4,500+ programs",
        "cost": "Around $65 USD — significantly cheaper than IELTS/TOEFL",
        "tips": [
            "Practice typing speed — the test is computer-based with timed responses",
            "The video interview section is reviewed by admissions but not scored",
            "Focus on Read and Complete (fill in the blanks) — it tests overall English ability",
            "You can take the test up to 3 times in 30 days",
        ],
    },
}

COUNTRY_GUIDES = {
    "USA": {
        "popular_for": "MS, MBA, PhD, Undergraduate",
        "visa_type": "F-1 Student Visa",
        "avg_tuition": "$20,000-$55,000/year",
        "living_cost": "$10,000-$20,000/year",
        "work_rights": "20 hrs/week on-campus during semester, OPT after graduation",
        "key_exams": "GRE/GMAT + TOEFL/IELTS",
        "intake": "Fall (main), Spring, Summer",
    },
    "Canada": {
        "popular_for": "MS, MBA, Diploma, Undergraduate",
        "visa_type": "Study Permit",
        "avg_tuition": "CAD 15,000-35,000/year",
        "living_cost": "CAD 10,000-15,000/year",
        "work_rights": "20 hrs/week during semester, PGWP after graduation (up to 3 years)",
        "key_exams": "IELTS/PTE/CELPIP",
        "intake": "Fall (Sep), Winter (Jan), Summer (May)",
        "pr_pathway": "Express Entry, PNP programs — study in Canada can lead to PR",
    },
    "UK": {
        "popular_for": "MS, MBA, Undergraduate",
        "visa_type": "Student Route Visa (Tier 4)",
        "avg_tuition": "£12,000-38,000/year",
        "living_cost": "£9,000-15,000/year",
        "work_rights": "20 hrs/week, Graduate Route visa (2 years post-study work)",
        "key_exams": "IELTS/PTE",
        "intake": "September (main), January",
    },
    "Australia": {
        "popular_for": "MS, MBA, Nursing, Engineering",
        "visa_type": "Student Visa (Subclass 500)",
        "avg_tuition": "AUD 20,000-45,000/year",
        "living_cost": "AUD 21,041/year (govt. requirement)",
        "work_rights": "Unlimited during term (changed 2024), PSWV after graduation",
        "key_exams": "IELTS/PTE/TOEFL",
        "intake": "February, July",
    },
    "Germany": {
        "popular_for": "MS, Engineering, MBBS, MiM",
        "visa_type": "National Visa (D-type)",
        "avg_tuition": "€0-1,500/semester at public universities",
        "living_cost": "€11,208/year (blocked account requirement)",
        "work_rights": "120 full days or 240 half days per year",
        "key_exams": "IELTS/TOEFL + APS Certificate for Indian students",
        "intake": "Winter (October), Summer (April)",
        "special_note": "Many tuition-free programs at public universities",
    },
}

# Soft-sell templates for naturally mentioning EEC
EEC_MENTION_TEMPLATES = [
    "In my experience coaching students at EEC over the past {years} years, I've found that...",
    "I've seen many students go through this exact situation. At our center, we typically advise...",
    "Based on helping thousands of students prepare for {exam}, my top recommendation is...",
    "One approach that has worked really well for our students is...",
    "From my {years}+ years of experience in {field}, I'd suggest...",
    "Having guided over {count} students through this process, here's what I've learned...",
]
