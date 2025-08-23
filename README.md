# Misinformation-Detector

AI Misinformation Spotter
An intelligent web application that analyzes text for potential misinformation, false claims, and credibility issues using advanced NLP techniques and real-time web verification.

**Key Features**

Factual Claim Detection: Identifies statements that make verifiable factual assertions
Credibility Assessment: Evaluates source reliability and content trustworthiness
Web Verification: Cross-references claims against current web sources in real-time
Risk Level Classification: Categorizes content as low, medium, or high risk for misinformation
Sentiment Analysis: Advanced connotation detection beyond simple word matching

**Specialized Detection**

Health Misinformation: Flags dangerous medical claims and unsubstantiated health advice
Implausibility Detection: Identifies obviously false claims
Fake Authority Recognition: Detects vague citations like "studies show" without specific sources
Red Flag Analysis: Spots conspiracy language, miracle cures, and emotional manipulation

**Technical Features**

Multi-Engine Web Search: Uses DuckDuckGo and fallback search mechanisms
Confidence Scoring: Provides nuanced confidence levels rather than binary true/false
Entity Extraction: Identifies key people, organizations, and concepts
Real-time Processing: Fast analysis suitable for social media content

**Technology Stack**

Backend (Python/FastAPI)
FastAPI: High-performance async web framework
Transformers: Hugging Face models for sentiment analysis and NLI
NLTK/TextBlob: Natural language processing utilities
aiohttp: Asynchronous HTTP client for web searches
Pydantic: Data validation and settings management

**Frontend (React)**

React 18: Modern component-based UI
CSS3: Responsive design with gradient backgrounds
Fetch API: Seamless backend communication

**AI/ML Components**

Zero-shot Classification: Content categorization without training data
Named Entity Recognition: Automatic extraction of key entities
Morphological Analysis: Word structure analysis for sentiment
Semantic Field Mapping: Context-aware word meaning detection

** ⚠️ Disclaimer: This project is currently in the Beta Testing stage!**

# Setup 

**Backend Setup**
Clone repository
```bash
git clone <repository-url>
cd misinformation-spotter/backend
```

Create virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```
Install dependencies
```bash
pip install fastapi uvicorn transformers torch nltk textblob aiohttp
```

Optional ML models (for enhanced analysis)
```bash
pip install sentence-transformers
```

Start backend server
```bash
uvicorn main:app --reload --port 8000
Frontend Setup
bashcd ../frontend
```

Run Frontend
```bash
npm install
npm start
```

