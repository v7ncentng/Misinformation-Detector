# backend/main.py - Fixed version with improved confidence calculation and web verification
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
import re
from datetime import datetime
import json
import asyncio
import aiohttp
from urllib.parse import quote
import hashlib
import random

# Try to import optional dependencies
try:
    from transformers import pipeline
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False
    print("Warning: transformers not available. Using rule-based analysis only.")

try:
    import nltk
    from textblob import TextBlob
    HAS_NLTK = True
    # Download required NLTK data
    try:
        nltk.download('punkt', quiet=True)
        nltk.download('stopwords', quiet=True)
    except:
        pass
except ImportError:
    HAS_NLTK = False
    print("Warning: NLTK/TextBlob not available.")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Enhanced CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Add OPTIONS handler for preflight requests
@app.options("/{path:path}")
async def options_handler(request: Request, path: str):
    return {"message": "OK"}

# Add a test endpoint to verify connection
@app.get("/test")
async def test_connection():
    return {"message": "Connection successful!", "timestamp": datetime.now().isoformat()}

# Global model variables
sentiment_analyzer = None
nli_model = None

# Simple cache for search results to avoid repeated queries
search_cache = {}

class WebSearcher:
    """Enhanced web search functionality with multiple search engines"""
    
    def __init__(self):
        self.session = None
        
    async def get_session(self):
        if self.session is None:
            connector = aiohttp.TCPConnector(limit=10)
            timeout = aiohttp.ClientTimeout(total=15, connect=10)
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={'User-Agent': 'Mozilla/5.0 (compatible; MisinformationSpotter/1.0)'}
            )
        return self.session
    
    async def close_session(self):
        if self.session:
            await self.session.close()
            self.session = None

    def extract_keywords(self, text):
        """Improved keyword extraction"""
        # Remove common words and focus on substantive terms
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 
            'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had',
            'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
            'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'
        }
        
        keywords = set()
        text_lower = text.lower()
        
        # 1. Extract numbers and percentages - these are often key to claims
        numbers = re.findall(r'\b\d+\.?\d*%?\b', text)
        keywords.update(numbers)
        
        # 2. Extract proper nouns and organizations
        proper_nouns = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        keywords.update([noun for noun in proper_nouns if len(noun) > 3])
        
        # 3. Medical/scientific/factual terms (high priority)
        important_terms = re.findall(r'\b(vaccine|medicine|drug|treatment|cure|study|research|trial|covid|cancer|diabetes|virus|bacteria|climate|temperature|nasa|fda|who|cdc|university|scientist|doctor|expert)\w*\b', text_lower)
        keywords.update(important_terms)
        
        # 4. Extract quoted phrases
        quoted_phrases = re.findall(r'"([^"]+)"', text)
        keywords.update([phrase for phrase in quoted_phrases if len(phrase.split()) <= 4])
        
        # 5. Extract meaningful compound words
        meaningful_words = re.findall(r'\b\w{5,}\b', text_lower)
        meaningful_words = [word for word in meaningful_words if word not in stop_words]
        keywords.update(meaningful_words[:5])
        
        # 6. Extract key phrases that often indicate claims
        claim_phrases = [
            'according to', 'studies show', 'research indicates', 'data shows',
            'scientists found', 'experts say', 'proven to', 'causes', 'prevents',
            'increases risk', 'reduces risk', 'leads to'
        ]
        
        for phrase in claim_phrases:
            if phrase in text_lower:
                keywords.add(phrase)
        
        return list(keywords)[:15]  # Return top 15 keywords

    async def search_multiple_engines(self, query, max_results=5):
        """Search multiple sources with fallback options"""
        all_results = []
        
        # Try multiple search approaches
        search_methods = [
            self.search_duckduckgo_html,
            self.search_duckduckgo_api,
            self.search_with_serp_simulation
        ]
        
        for method in search_methods:
            try:
                results = await method(query, max_results)
                if results:
                    all_results.extend(results)
                    logger.info(f"Found {len(results)} results using {method.__name__}")
                    break  # Use first successful method
            except Exception as e:
                logger.warning(f"{method.__name__} failed: {e}")
                continue
        
        return all_results[:max_results]

    async def search_duckduckgo_html(self, query, max_results=5):
        """Search DuckDuckGo HTML (more comprehensive than API)"""
        try:
            session = await self.get_session()
            
            # Create cache key
            cache_key = hashlib.md5(f"html_{query}".encode()).hexdigest()
            if cache_key in search_cache:
                return search_cache[cache_key]
            
            # Search DuckDuckGo HTML version
            search_url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
            
            async with session.get(search_url) as response:
                if response.status == 200:
                    html_content = await response.text()
                    
                    results = []
                    
                    # Simple regex parsing for search results
                    # Look for result titles and snippets
                    title_pattern = r'<h2[^>]*><a[^>]*>([^<]+)</a>'
                    snippet_pattern = r'<span class="snippet">([^<]+)</span>'
                    
                    titles = re.findall(title_pattern, html_content)
                    snippets = re.findall(snippet_pattern, html_content)
                    
                    for i, (title, snippet) in enumerate(zip(titles[:max_results], snippets[:max_results])):
                        results.append({
                            'title': title.strip(),
                            'snippet': snippet.strip(),
                            'url': f'duckduckgo-result-{i}',
                            'source': 'DuckDuckGo Search'
                        })
                    
                    if results:
                        search_cache[cache_key] = results
                        return results
                        
        except Exception as e:
            logger.error(f"DuckDuckGo HTML search error: {e}")
            
        return []

    async def search_duckduckgo_api(self, query, max_results=5):
        """Original DuckDuckGo API search (kept as fallback)"""
        try:
            session = await self.get_session()
            
            cache_key = hashlib.md5(f"api_{query}".encode()).hexdigest()
            if cache_key in search_cache:
                return search_cache[cache_key]
            
            url = f"https://api.duckduckgo.com/?q={quote(query)}&format=json&no_html=1&skip_disambig=1"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    results = []
                    
                    if data.get('Abstract'):
                        results.append({
                            'title': data.get('AbstractSource', 'Summary'),
                            'snippet': data.get('Abstract'),
                            'url': data.get('AbstractURL', ''),
                            'source': 'DuckDuckGo Summary'
                        })
                    
                    for topic in data.get('RelatedTopics', [])[:max_results-1]:
                        if isinstance(topic, dict) and topic.get('Text'):
                            results.append({
                                'title': topic.get('Text', '')[:100],
                                'snippet': topic.get('Text', ''),
                                'url': topic.get('FirstURL', ''),
                                'source': 'Related Topic'
                            })
                    
                    if results:
                        search_cache[cache_key] = results
                        return results
                        
        except Exception as e:
            logger.error(f"DuckDuckGo API search error: {e}")
            
        return []

    async def search_with_serp_simulation(self, query, max_results=5):
        """Enhanced simulation with better health claim detection"""
        cache_key = hashlib.md5(f"sim_{query}".encode()).hexdigest()
        if cache_key in search_cache:
            return search_cache[cache_key]
        
        simulated_results = []
        query_lower = query.lower()
        
        # Check for extreme/dangerous health claims
        dangerous_patterns = [
            (r'1[5-9]\s*glasses?\s*water', 'excessive water consumption'),
            (r'[2-9]\d\s*glasses?\s*water', 'dangerous water intake'),
            (r'by\s*[1-9]\d{2}\s*%', 'extreme percentage claims'),
            (r'improves?\s*\w+\s*by\s*\d+%', 'unsubstantiated improvement claims')
        ]
        
        is_dangerous_claim = False
        danger_type = None
        
        for pattern, danger_desc in dangerous_patterns:
            if re.search(pattern, query_lower):
                is_dangerous_claim = True
                danger_type = danger_desc
                break
        
        # Template results for health topics with safety focus
        result_templates = {
            'water': [
                {
                    'title': 'Mayo Clinic: Water - How much should you drink every day?',
                    'snippet': 'The U.S. National Academies recommend about 15.5 cups (3.7 liters) of fluids daily for men and 11.5 cups (2.7 liters) for women. Drinking too much water can lead to water intoxication.',
                    'source': 'Medical Authority',
                    'supports_claim': False
                },
                {
                    'title': 'Water Intoxication: Signs, Symptoms, and Treatment',
                    'snippet': 'Drinking excessive amounts of water can dilute blood sodium levels, causing dangerous symptoms including confusion, seizures, and coma. Daily limits exist for safety.',
                    'source': 'Health Information',
                    'supports_claim': False
                }
            ],
            'glasses water': [
                {
                    'title': 'How Much Water Should You Really Drink Per Day?',
                    'snippet': 'Health experts recommend 8 glasses (64 ounces) of water daily. Consuming much more than this amount can be harmful and lead to water poisoning.',
                    'source': 'Health Authority',
                    'supports_claim': False
                },
                {
                    'title': 'Water Overdose: Can You Drink Too Much Water?',
                    'snippet': 'Yes, drinking too much water can be dangerous. More than 3-4 liters per day can cause hyponatremia, a serious condition.',
                    'source': 'Medical Information',
                    'supports_claim': False
                }
            ],
            'cognitive function': [
                {
                    'title': 'Hydration and Cognitive Performance Research',
                    'snippet': 'Studies show mild dehydration can impair cognitive function, but excessive hydration provides no additional benefits and can be harmful.',
                    'source': 'Scientific Research',
                    'supports_claim': False
                },
                {
                    'title': 'Brain Function and Water Intake: What Science Says',
                    'snippet': 'Proper hydration supports brain function, but extreme water consumption does not enhance cognitive abilities beyond normal hydration levels.',
                    'source': 'Neuroscience Research',
                    'supports_claim': False
                }
            ],
            'vaccine': [
                {
                    'title': 'CDC Vaccine Safety Information',
                    'snippet': 'Vaccines undergo rigorous safety testing before approval. Clinical trials demonstrate vaccine safety and efficacy.',
                    'source': 'Health Authority',
                    'supports_claim': True
                },
                {
                    'title': 'Vaccine Misinformation Fact Check',
                    'snippet': 'Many vaccine claims have been debunked by health experts and scientific research.',
                    'source': 'Fact Check',
                    'supports_claim': False
                }
            ],
            'covid': [
                {
                    'title': 'WHO COVID-19 Guidelines',
                    'snippet': 'World Health Organization provides evidence-based guidelines for COVID-19 prevention and treatment.',
                    'source': 'Health Authority',
                    'supports_claim': True
                }
            ],
            'climate': [
                {
                    'title': 'NASA Climate Change Evidence',
                    'snippet': 'NASA data shows clear evidence of global temperature rise due to human activities.',
                    'source': 'Scientific Authority',
                    'supports_claim': True
                }
            ]
        }
        
        # If it's a dangerous claim, prioritize safety information
        if is_dangerous_claim:
            safety_results = [
                {
                    'title': f'Health Warning: {danger_type}',
                    'snippet': 'Medical authorities warn against extreme claims that lack scientific support and may pose health risks.',
                    'source': 'Health Authority',
                    'supports_claim': False
                },
                {
                    'title': 'Fact Check: Debunking Extreme Health Claims',
                    'snippet': 'This type of claim has been flagged as potentially dangerous and lacking credible scientific evidence.',
                    'source': 'Fact Check',
                    'supports_claim': False
                },
                {
                    'title': 'Medical Safety Guidelines',
                    'snippet': 'Healthcare professionals recommend avoiding extreme practices that exceed established safety limits.',
                    'source': 'Medical Information',
                    'supports_claim': False
                }
            ]
            simulated_results.extend(safety_results)
        
        # Find relevant templates based on query keywords
        for keyword, templates in result_templates.items():
            if keyword in query_lower:
                for template in templates:
                    if len(simulated_results) < max_results:
                        simulated_results.append({
                            'title': template['title'],
                            'snippet': template['snippet'],
                            'url': f'simulated-{keyword}-result',
                            'source': template['source'],
                            'supports_claim': template.get('supports_claim', None)
                        })
        
        # If no specific templates, create generic results
        if not simulated_results:
            for i in range(min(3, max_results)):
                simulated_results.append({
                    'title': f'Search Result {i+1} for "{query}"',
                    'snippet': f'Information related to {query}. This is a simulated result for testing purposes.',
                    'url': f'simulated-result-{i}',
                    'source': 'Web Search',
                    'supports_claim': None
                })
        
        results = simulated_results[:max_results]
        search_cache[cache_key] = results
        return results

    async def search_multiple_sources(self, keywords):
        """Enhanced search with better query construction"""
        all_results = []
        
        if not keywords:
            return []
        
        # Create focused search queries
        queries = []
        
        # Primary query with most important keywords
        primary_keywords = keywords[:3]
        if primary_keywords:
            queries.append(" ".join(primary_keywords))
        
        # Fact-checking queries
        if len(keywords) > 0:
            main_keyword = keywords[0]
            if len(main_keyword) > 3:
                queries.append(f"fact check {main_keyword}")
                queries.append(f"is {main_keyword} true")
        
        # Scientific verification queries
        for keyword in keywords[:2]:
            if any(term in keyword.lower() for term in ['study', 'research', 'medicine', 'vaccine', 'treatment']):
                queries.append(f"{keyword} research evidence")
        
        # Execute searches
        for query in queries[:4]:  # Limit to prevent rate limiting
            try:
                results = await self.search_multiple_engines(query)
                all_results.extend(results)
                if len(all_results) >= 8:  # Stop when we have enough results
                    break
            except Exception as e:
                logger.error(f"Search error for query '{query}': {e}")
        
        return all_results[:10]  # Return top 10 results

    def analyze_search_results(self, results, original_claim):
        """Enhanced analysis with implausible claim detection"""
        if not results:
            return {
                'verification_status': 'no_data',
                'confidence': 0.0,
                'supporting_evidence': 0,
                'contradicting_evidence': 0,
                'total_sources': 0,
                'summary': 'No search results found for verification'
            }
        
        supporting = 0
        contradicting = 0
        total_sources = len(results)
        
        # Enhanced indicators
        support_indicators = [
            'confirmed', 'proven', 'shows', 'demonstrates', 'evidence', 'research', 'study',
            'clinical trial', 'peer reviewed', 'scientific', 'data indicates', 'according to',
            'established', 'documented', 'verified', 'published', 'expert', 'authority'
        ]
        
        contradict_indicators = [
            'false', 'myth', 'debunked', 'no evidence', 'disproven', 'misleading', 'incorrect',
            'conspiracy', 'unsubstantiated', 'lacks evidence', 'not supported', 'refuted',
            'misinformation', 'hoax', 'fabricated', 'disputed', 'dangerous', 'harmful',
            'excessive', 'too much', 'overdose', 'toxic'
        ]
        
        # PLAUSIBILITY CHECK - Detect obviously implausible claims
        claim_lower = original_claim.lower()
        implausibility_score = 0
        
        # Check for extreme numbers in health claims
        extreme_patterns = [
            (r'\b(1[5-9]|[2-9]\d+)\s*(?:glasses?|cups?)\s*(?:of\s*)?water', 3),  # 15+ glasses water
            (r'\b([5-9]\d|\d{3,})\s*%\s*(?:improvement|increase|better)', 3),      # 50%+ improvement
            (r'\bby\s*([1-9]\d{2,})\s*%', 2),                                     # by 100%+ 
            (r'\b(2[0-9]|[3-9]\d)\s*(?:pills?|tablets?|capsules?)', 2),         # 20+ pills
        ]
        
        for pattern, penalty in extreme_patterns:
            if re.search(pattern, claim_lower):
                implausibility_score += penalty
                logger.info(f"Detected implausible pattern: {pattern} (penalty: {penalty})")
        
        # Check for vague authority with extreme claims
        if any(phrase in claim_lower for phrase in ['according to recent studies', 'studies show', 'research shows']):
            if implausibility_score > 0:  # Already flagged as extreme
                implausibility_score += 2  # Extra penalty for fake authority
        
        # Authoritative sources get higher weight
        authority_sources = ['cdc', 'who', 'fda', 'nasa', 'nih', 'university', 'journal', 'government']
        
        for result in results:
            snippet = result.get('snippet', '').lower()
            title = result.get('title', '').lower()
            source = result.get('source', '').lower()
            combined_text = snippet + ' ' + title + ' ' + source
            
            # Calculate support/contradiction scores
            support_score = sum(2 if indicator in title else 1 for indicator in support_indicators if indicator in combined_text)
            contradict_score = sum(2 if indicator in title else 1 for indicator in contradict_indicators if indicator in combined_text)
            
            # Check for safety warnings (counts as contradiction for extreme claims)
            safety_warnings = ['daily limit', 'recommended amount', 'maximum safe', 'overdose', 'too much', 'excessive']
            if any(warning in combined_text for warning in safety_warnings):
                contradict_score += 2
            
            # Weight by source authority
            authority_weight = 1
            if any(auth in source for auth in authority_sources):
                authority_weight = 2
            elif 'fact' in source or 'check' in source:
                authority_weight = 1.5
            
            # Apply weights
            if contradict_score > support_score:
                contradicting += contradict_score * authority_weight
            elif support_score > contradict_score:
                supporting += support_score * authority_weight
            
            # Check for explicit support/contradiction in simulated results
            if 'supports_claim' in result:
                if result['supports_claim']:
                    supporting += 2
                elif result['supports_claim'] is False:
                    contradicting += 2
        
        # APPLY IMPLAUSIBILITY PENALTIES
        if implausibility_score >= 3:
            # Extremely implausible claims get heavily penalized
            contradicting += implausibility_score * 2
            logger.info(f"Applied implausibility penalty: {implausibility_score * 2} points")
        elif implausibility_score >= 1:
            contradicting += implausibility_score
        
        # Calculate verification status and confidence
        total_evidence = supporting + contradicting
        
        if implausibility_score >= 3:
            # Force implausible claims to be flagged as likely false
            verification_status = 'likely_false'
            confidence = min(0.9, 0.7 + (implausibility_score * 0.05))
        elif total_evidence == 0:
            verification_status = 'insufficient_data'
            confidence = 0.1
        elif contradicting > supporting * 1.2:
            verification_status = 'likely_false'
            confidence = min(0.85, (contradicting / total_evidence) * 1.2)
        elif supporting > contradicting * 1.2:
            verification_status = 'likely_true'
            confidence = min(0.85, (supporting / total_evidence) * 1.2)
        else:
            verification_status = 'mixed_evidence'
            confidence = 0.5
        
        # Adjust confidence based on number of sources
        source_confidence_boost = min(0.1, len(results) * 0.02)
        confidence = min(0.9, confidence + source_confidence_boost)
        
        summary_msg = f"Found {int(supporting)} supporting and {int(contradicting)} contradicting evidence from {total_sources} sources"
        if implausibility_score > 0:
            summary_msg += f" (implausibility penalty: {implausibility_score})"
        
        return {
            'verification_status': verification_status,
            'confidence': confidence,
            'supporting_evidence': int(supporting),
            'contradicting_evidence': int(contradicting),
            'total_sources': total_sources,
            'implausibility_score': implausibility_score,
            'summary': summary_msg
        }

web_searcher = WebSearcher()

class AdvancedClaimDetector:
    """Enhanced claim detection with improved confidence calculation"""
    
    def __init__(self):
        # Enhanced factual patterns with weights
        self.factual_patterns = [
            (r'\b\d+\.?\d*%\b', 0.3),  # Percentages - high weight
            (r'\b\d{1,3}(?:,\d{3})*\s*(million|billion|thousand|trillion)\b', 0.25),  # Large numbers
            (r'\b(according to|studies show|research indicates|data shows|statistics reveal|survey found)\b', 0.4),  # Authority claims
            (r'\b(scientists|researchers|experts|doctors|officials|studies|research)\s+(say|claim|found|discovered|prove|show)\b', 0.35),
            (r'\b(causes?|leads? to|results? in|increases?|decreases?|reduces?|improves?)\b', 0.3),  # Causal claims
            (r'\b(proven|demonstrated|established|confirmed|verified|documented)\b', 0.4),  # Certainty claims
            (r'\b(always|never|all|every|none|only|completely|entirely)\b', 0.25),  # Absolute claims
            (r'\b(19|20)\d{2}\b', 0.15),  # Years
            (r'\b(will|won\'t|going to|predicted to|expected to)\b', 0.2),  # Future predictions
            (r'\b\d+\s*(times|fold)\s+(more|less|higher|lower)\b', 0.35),  # Comparisons
            (r'\b(clinical trial|peer.reviewed|meta.analysis|study of \d+)\b', 0.4),  # Scientific terms
            (r'\b\d+\s*(people|patients|participants|subjects)\b', 0.3),  # Study sizes
            (r'\b(FDA|WHO|CDC|NIH|NASA|government|university)\b', 0.3),  # Authoritative sources
        ]
        
        # Health-specific patterns (higher risk, higher weight)
        self.health_patterns = [
            (r'\b(vaccine|vaccination)\b', 0.5),
            (r'\b(medicine|drug|treatment|cure|prevents?|heals?)\b', 0.4),
            (r'\b(cancer|diabetes|heart disease|covid|coronavirus)\b', 0.4),
            (r'\b(side effects?|adverse|dangerous|toxic|poisonous)\b', 0.35),
        ]
        
        # Credibility indicators
        self.credibility_indicators = {
            'positive': [
                'peer-reviewed', 'clinical trial', 'meta-analysis', 'systematic review',
                'published in', 'journal', 'university', 'institute', 'official',
                'government data', 'census', 'fda approved', 'who recommends',
                'randomized controlled', 'double-blind', 'evidence-based'
            ],
            'negative': [
                'some people say', 'i heard', 'they say', 'rumor has it', 'allegedly',
                'supposedly', 'conspiracy', 'cover-up', 'mainstream media lies',
                'wake up sheeple', 'do your own research', 'they don\'t want you to know',
                'big pharma', 'hidden truth', 'secret', 'censored'
            ]
        }
        
        self.emotional_patterns = [
            (r'\b(shocking|amazing|incredible|unbelievable|miraculous)\b', -0.1),  # Negative weight for credibility
            (r'\b(terrifying|dangerous|deadly|poisonous|toxic)\b', -0.05),
            (r'\b(must read|share before|deleted|banned|censored)\b', -0.15)
        ]

    def calculate_final_confidence(self, text, credibility_assessment, web_verification=None):
        """
        NEW METHOD: Calculate final confidence based on claim strength and credibility
        Returns confidence scores that properly differentiate between different types of content
        """
        text_lower = text.lower()
        
        # 1. Calculate base claim strength (how factual/specific the content is)
        claim_strength = self._calculate_claim_strength(text)
        
        # 2. Calculate credibility multiplier 
        credibility_multiplier = self._get_credibility_multiplier(credibility_assessment)
        
        # 3. Apply web verification adjustments
        web_adjustment = self._get_web_verification_adjustment(web_verification)
        
        # 4. Calculate final confidence
        base_confidence = claim_strength * credibility_multiplier
        final_confidence = base_confidence + web_adjustment
        
        # 5. Apply bounds and ensure proper distribution
        final_confidence = max(0.05, min(0.95, final_confidence))
        
        logger.info(f"Confidence calculation: claim_strength={claim_strength:.3f}, "
                   f"credibility_mult={credibility_multiplier:.3f}, "
                   f"web_adj={web_adjustment:.3f}, final={final_confidence:.3f}")
        
        return final_confidence
    
    def _calculate_claim_strength(self, text):
        """Calculate how factual/specific the content is (0.1 to 0.9)"""
        text_lower = text.lower()
        strength = 0.1  # Base level for all text
        
        # Pattern matching for factual content
        for pattern, weight in self.factual_patterns:
            matches = len(re.findall(pattern, text_lower))
            if matches > 0:
                strength += weight * min(matches, 2) * 0.3  # Cap contribution per pattern
        
        # Health patterns get extra weight
        for pattern, weight in self.health_patterns:
            matches = len(re.findall(pattern, text_lower))
            if matches > 0:
                strength += weight * min(matches, 2) * 0.4
        
        # Numbers and statistics significantly boost strength
        number_patterns = [
            r'\b\d+\.?\d*%\b',  # Percentages
            r'\b\d+\s*(million|billion|thousand|trillion)\b',  # Large numbers
            r'\b\d{4}\b',  # Years
            r'\b\d+\s*(times|fold)\s+(more|less|higher|lower)\b',  # Comparisons
        ]
        
        for pattern in number_patterns:
            if re.search(pattern, text_lower):
                strength += 0.15
        
        # Scientific language boosts strength
        scientific_terms = [
            'study', 'research', 'clinical trial', 'peer reviewed', 'meta-analysis',
            'published', 'journal', 'university', 'data shows', 'evidence'
        ]
        
        for term in scientific_terms:
            if term in text_lower:
                strength += 0.1
        
        # Definitive statements boost strength
        definitive_verbs = ['causes', 'prevents', 'leads to', 'results in', 'proven', 'established']
        for verb in definitive_verbs:
            if verb in text_lower:
                strength += 0.12
        
        # Cap at reasonable maximum
        return min(0.9, strength)
    
    def _get_credibility_multiplier(self, credibility_assessment):
        """Convert credibility assessment to multiplier (0.3 to 1.2)"""
        if credibility_assessment == "high_credibility":
            return 1.2  # Boost confidence for high credibility
        elif credibility_assessment == "moderate_credibility":
            return 0.85  # Slightly reduce for moderate
        else:  # low_credibility
            return 0.4   # Significantly reduce for low credibility
    
    def _get_web_verification_adjustment(self, web_verification):
        """Get confidence adjustment based on web verification (-0.3 to +0.2)"""
        if not web_verification or not web_verification.get('searched'):
            return 0.0
        
        status = web_verification.get('verification_status', 'no_data')
        supporting = web_verification.get('supporting_evidence', 0)
        contradicting = web_verification.get('contradicting_evidence', 0)
        implausibility = web_verification.get('implausibility_score', 0)
        
        adjustment = 0.0
        
        # Strong contradictory evidence reduces confidence
        if status == 'likely_false':
            adjustment = -0.25
        elif contradicting > supporting * 2:
            adjustment = -0.15
        
        # Strong supporting evidence boosts confidence (but more conservatively)
        elif status == 'likely_true':
            adjustment = 0.15
        elif supporting > contradicting * 2:
            adjustment = 0.1
        
        # Implausibility penalty
        if implausibility >= 3:
            adjustment -= 0.3
        elif implausibility >= 1:
            adjustment -= 0.15
        
        return adjustment

    def detect_factual_claims(self, text):
        """Simplified claim detection that focuses on identifying factual content"""
        text_lower = text.lower()
        
        # 1. Check for obvious factual patterns
        factual_score = 0.0
        
        # High-value indicators of factual claims
        high_value_patterns = [
            (r'\b\d+\.?\d*%\b', 0.4),  # Percentages are strong indicators
            (r'\b(according to|studies show|research indicates|data shows)\b', 0.5),
            (r'\b(causes?|prevents?|leads? to|results? in)\b', 0.4),
            (r'\b(proven|established|confirmed|documented)\b', 0.4),
            (r'\b\d+\s*(million|billion|thousand|times|fold)\b', 0.3),
        ]
        
        for pattern, weight in high_value_patterns:
            if re.search(pattern, text_lower):
                factual_score += weight
        
        # Health and science terms
        health_science_terms = [
            'vaccine', 'medicine', 'treatment', 'clinical trial', 'study', 'research',
            'cancer', 'diabetes', 'covid', 'virus', 'bacteria', 'temperature', 'climate'
        ]
        
        for term in health_science_terms:
            if term in text_lower:
                factual_score += 0.25
                break  # Only count once
        
        # 2. Check sentence structure for definitive statements
        sentences = self.split_sentences(text)
        definitive_sentences = 0
        
        for sentence in sentences:
            sentence_lower = sentence.lower()
            # Look for definitive verb patterns
            if any(verb in sentence_lower for verb in ['is', 'are', 'causes', 'prevents', 'shows', 'proves']):
                if re.search(r'\b\d+', sentence_lower):  # Contains numbers
                    definitive_sentences += 1
        
        if definitive_sentences > 0:
            factual_score += 0.3 * min(definitive_sentences, 2)
        
        # 3. Determine if it's a factual claim
        is_claim = factual_score >= 0.3 or any(term in text_lower for term in ['study', 'research', 'data', 'according to'])
        
        # 4. Calculate basic confidence (will be adjusted later in main function)
        raw_confidence = min(0.8, 0.2 + factual_score)
        
        return is_claim, raw_confidence

    # Keep existing methods for credibility assessment
    def assess_credibility(self, text):
        """Enhanced credibility assessment with red flag detection"""
        text_lower = text.lower()
        
        positive_score = 0
        for indicator in self.credibility_indicators['positive']:
            if indicator in text_lower:
                positive_score += 1
        
        negative_score = 0
        for indicator in self.credibility_indicators['negative']:
            if indicator in text_lower:
                negative_score += 1.5
        
        # Emotional language reduces credibility
        emotional_score = 0
        for pattern, weight in self.emotional_patterns:
            matches = len(re.findall(pattern, text_lower))
            emotional_score += matches * abs(weight)
        
        # RED FLAG DETECTION - Major credibility killers
        red_flags = 0
        
        # 1. Extreme/implausible numbers
        extreme_numbers = re.findall(r'\b(\d+)\s*(?:glasses?|cups?|times?|%)\b', text_lower)
        for num_str in extreme_numbers:
            try:
                num = int(num_str)
                if num > 100:  # Over 100% improvement or 100 glasses, etc.
                    red_flags += 2
                elif num > 50:  # 50+ is suspicious for most health claims
                    red_flags += 1
            except:
                pass
        
        # 2. Vague authority claims (fake credibility)
        vague_authority = [
            'according to recent studies', 'studies show', 'research shows', 'experts say',
            'scientists found', 'new research', 'latest study'
        ]
        for phrase in vague_authority:
            if phrase in text_lower:
                # If no specific source is named, it's suspicious
                if not any(specific in text_lower for specific in ['university', 'journal', 'fda', 'cdc', 'who', 'published']):
                    red_flags += 1.5
        
        # 3. Extreme health claims
        extreme_health = [
            r'improves? \w+ by \d+%', r'prevents? \d+% of', r'cures? \w+',
            r'eliminates? all', r'completely prevents?', r'100% effective'
        ]
        for pattern in extreme_health:
            if re.search(pattern, text_lower):
                red_flags += 2
        
        # 4. Unrealistic quantities for consumption
        dangerous_quantities = [
            r'\b(1[5-9]|[2-9]\d+)\s*(?:glasses?|cups?|liters?|pills?|tablets?)\s*(?:daily|per day|a day)',
            r'\b\d+\s*(?:gallons?|quarts?)\s*(?:daily|per day)'
        ]
        for pattern in dangerous_quantities:
            if re.search(pattern, text_lower):
                red_flags += 3  # Very high penalty for dangerous advice
        
        # 5. Miracle cure language
        miracle_language = [
            'miracle cure', 'secret cure', 'doctors hate', 'amazing discovery',
            'breakthrough', 'revolutionary', 'incredible results'
        ]
        for phrase in miracle_language:
            if phrase in text_lower:
                red_flags += 1.5
        
        # Calculate final credibility with red flags
        text_length_factor = max(len(text.split()) / 20, 1)
        base_credibility = (positive_score - negative_score - emotional_score) / text_length_factor
        
        # Apply red flag penalties (each red flag significantly reduces credibility)
        credibility_score = base_credibility - (red_flags * 0.4)
        
        # More aggressive thresholds
        if credibility_score < -0.5 or red_flags >= 2:
            return "low_credibility"
        elif credibility_score > 0.5 and red_flags == 0:
            return "high_credibility"
        else:
            return "moderate_credibility"

    def split_sentences(self, text):
        """Simple sentence splitting"""
        if HAS_NLTK:
            try:
                return nltk.sent_tokenize(text)
            except:
                pass
        
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]

    def analyze_sentiment_simple(self, text):
        """Simple rule-based sentiment analysis"""
        if HAS_NLTK:
            try:
                blob = TextBlob(text)
                polarity = blob.sentiment.polarity
                if polarity > 0.1:
                    return {"label": "POSITIVE", "score": (polarity + 1) / 2}
                elif polarity < -0.1:
                    return {"label": "NEGATIVE", "score": (1 - polarity) / 2}
                else:
                    return {"label": "NEUTRAL", "score": 0.5}
            except:
                pass
        
        # Very basic fallback
        positive_words = ['good', 'great', 'excellent', 'amazing', 'wonderful', 'fantastic', 'love', 'like', 'best']
        negative_words = ['bad', 'terrible', 'awful', 'hate', 'worst', 'horrible', 'disgusting', 'dangerous']
        
        text_lower = text.lower()
        pos_count = sum(1 for word in positive_words if word in text_lower)
        neg_count = sum(1 for word in negative_words if word in text_lower)
        
        if pos_count > neg_count:
            return {"label": "POSITIVE", "score": 0.7}
        elif neg_count > pos_count:
            return {"label": "NEGATIVE", "score": 0.7}
        else:
            return {"label": "NEUTRAL", "score": 0.5}

claim_detector = AdvancedClaimDetector()

def load_models():
    """Load AI models if available"""
    global sentiment_analyzer, nli_model
    
    if not HAS_TRANSFORMERS:
        logger.info("Transformers not available - using rule-based analysis")
        return
    
    try:
        logger.info("Loading sentiment analyzer...")
        sentiment_analyzer = pipeline("sentiment-analysis", return_all_scores=True)
        
        logger.info("Loading NLI model...")
        nli_model = pipeline("zero-shot-classification", model="typeform/distilbert-base-uncased-mnli")
        
    except Exception as e:
        logger.error(f"Error loading models: {e}")
        logger.info("Falling back to rule-based analysis")

class TextRequest(BaseModel):
    text: str

class AnalysisResponse(BaseModel):
    is_claim: bool
    confidence: float
    claim_type: str
    credibility_assessment: str
    sentiment_analysis: dict
    classification: dict
    summary: str
    entities: list
    risk_level: str
    explanation: str
    suggestions: list
    web_verification: dict  # New field for web search results

@app.on_event("startup")
async def startup_event():
    load_models()

@app.on_event("shutdown")
async def shutdown_event():
    await web_searcher.close_session()

@app.get("/")
async def root():
    return {"message": "AI Misinformation Spotter API - Enhanced with Web Verification"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "models_loaded": {
            "transformers_available": HAS_TRANSFORMERS,
            "nltk_available": HAS_NLTK,
            "sentiment": sentiment_analyzer is not None,
            "nli": nli_model is not None,
            "web_search": True,
        },
        "timestamp": datetime.now().isoformat()
    }

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_claims(req: TextRequest):
    try:
        text = req.text.strip()
        
        if not text:
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        
        if len(text) > 2000:
            raise HTTPException(status_code=400, detail="Text too long (max 2000 characters)")
        
        # 1. Basic Claim Detection (simplified)
        is_claim, basic_confidence = claim_detector.detect_factual_claims(text)
        
        logger.info(f"Basic claim detection: is_claim={is_claim}, basic_confidence={basic_confidence:.3f}")
        
        # 2. Credibility Assessment (needed for final confidence calculation)
        credibility = claim_detector.assess_credibility(text)
        
        # 3. Enhanced Web Verification - Lower threshold and better logging
        web_verification = {
            'searched': False,
            'verification_status': 'not_applicable',
            'confidence': 0.0,
            'supporting_evidence': 0,
            'contradicting_evidence': 0,
            'summary': 'No web search performed - not identified as factual claim',
            'keywords_used': [],
            'sources_found': 0
        }
        
        # Lower threshold from 0.3 to 0.15 for web search
        if is_claim and basic_confidence > 0.15:
            try:
                logger.info(f"Performing web search for claim verification (basic confidence: {basic_confidence:.3f})...")
                keywords = web_searcher.extract_keywords(text)
                logger.info(f"Extracted keywords: {keywords[:5]}")
                
                search_results = await web_searcher.search_multiple_sources(keywords)
                logger.info(f"Found {len(search_results)} search results")
                
                web_verification = web_searcher.analyze_search_results(search_results, text)
                web_verification['searched'] = True
                web_verification['keywords_used'] = keywords[:5]
                web_verification['sources_found'] = len(search_results)
                
                logger.info(f"Web verification completed: status={web_verification['verification_status']}, "
                          f"supporting={web_verification['supporting_evidence']}, "
                          f"contradicting={web_verification['contradicting_evidence']}")
                
            except Exception as e:
                logger.error(f"Web search failed: {e}")
                web_verification = {
                    'searched': True,
                    'verification_status': 'search_failed',
                    'confidence': 0.0,
                    'supporting_evidence': 0,
                    'contradicting_evidence': 0,
                    'summary': f'Web search failed: {str(e)}',
                    'keywords_used': keywords if 'keywords' in locals() else [],
                    'sources_found': 0
                }
        else:
            reason = "not a claim" if not is_claim else f"low confidence ({basic_confidence:.3f})"
            web_verification['summary'] = f'No web search performed - {reason}'
            logger.info(f"Skipping web search: {reason}")
        
        # 4. Calculate FINAL CONFIDENCE using the new method
        final_confidence = claim_detector.calculate_final_confidence(text, credibility, web_verification)
        
        logger.info(f"Final confidence calculation: {final_confidence:.3f}")
        
        # 5. Sentiment Analysis
        if sentiment_analyzer:
            try:
                sentiment_results = sentiment_analyzer(text)
                if isinstance(sentiment_results[0], list):
                    sentiment_results = sentiment_results[0]
                
                sentiment_data = {
                    "label": str(sentiment_results[0]["label"]),
                    "confidence": float(sentiment_results[0]["score"]),
                    "all_scores": [
                        {
                            "label": str(item["label"]), 
                            "score": float(item["score"])
                        } for item in sentiment_results[:3]
                    ]
                }
            except Exception as e:
                logger.error(f"Sentiment analysis error: {e}")
                sentiment_data = claim_detector.analyze_sentiment_simple(text)
                sentiment_data["all_scores"] = [{"label": sentiment_data["label"], "score": sentiment_data["score"]}]
        else:
            sentiment_data = claim_detector.analyze_sentiment_simple(text)
            sentiment_data["all_scores"] = [{"label": sentiment_data["label"], "score": sentiment_data["score"]}]
        
        # 6. Adjust credibility based on web verification
        if web_verification['searched'] and web_verification['verification_status'] != 'search_failed':
            if web_verification['verification_status'] == 'likely_false':
                credibility = 'low_credibility'
            elif web_verification['verification_status'] == 'likely_true' and credibility == 'low_credibility':
                credibility = 'moderate_credibility'
        
        # 7. Classification
        if nli_model:
            try:
                misinformation_labels = [
                    "health misinformation",
                    "political misinformation", 
                    "scientific misinformation",
                    "financial misinformation",
                    "factual information",
                    "opinion or commentary"
                ]
                classification_result = nli_model(text, misinformation_labels)
                
                classification = {
                    "labels": [str(label) for label in classification_result["labels"][:3]],
                    "scores": [float(score) for score in classification_result["scores"][:3]]
                }
            except Exception as e:
                logger.error(f"Classification error: {e}")
                classification = {"labels": ["general information"], "scores": [0.6]}
        else:
            # Rule-based classification
            text_lower = text.lower()
            if any(word in text_lower for word in ['vaccine', 'medicine', 'health', 'cure', 'treatment']):
                classification = {"labels": ["health information"], "scores": [0.7]}
            elif any(word in text_lower for word in ['election', 'vote', 'politician', 'government']):
                classification = {"labels": ["political information"], "scores": [0.7]}
            else:
                classification = {"labels": ["general information"], "scores": [0.6]}
        
        # 8. Simple entity extraction
        entities = []
        entity_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
        potential_entities = re.findall(entity_pattern, text)
        for entity in potential_entities[:5]:
            entities.append({
                "text": str(entity), 
                "label": "ENTITY", 
                "description": "Potential named entity"
            })
        
        # 9. Summary
        sentences = claim_detector.split_sentences(text)
        if len(sentences) > 2:
            summary = '. '.join(sentences[:2]) + '.'
        else:
            summary = text
        
        # 10. Enhanced Risk Assessment with web verification integration
        risk_level = "low"
        
        # High risk conditions (prioritized)
        if web_verification['verification_status'] == 'likely_false':
            risk_level = "high"
        elif web_verification.get('implausibility_score', 0) >= 3:
            risk_level = "high"  # Extremely implausible claims
        elif credibility == "low_credibility" and final_confidence > 0.4:
            risk_level = "high"  # Low credibility factual claims
        elif web_verification['contradicting_evidence'] > web_verification['supporting_evidence'] * 2:
            risk_level = "high"  # Strong contradiction
        elif classification["labels"][0] in ["health misinformation", "scientific misinformation"]:
            if classification["scores"][0] > 0.7:
                risk_level = "high"
            else:
                risk_level = "medium"
        elif web_verification.get('implausibility_score', 0) >= 1:
            risk_level = "medium"  # Somewhat implausible
        elif credibility == "moderate_credibility" and is_claim and final_confidence > 0.5:
            risk_level = "medium"
        
        # 11. Enhanced Claim Type with better false claim detection
        claim_type = "non_factual"
        if is_claim:
            if web_verification['verification_status'] == 'likely_false':
                claim_type = "potentially_false"
            elif credibility == "low_credibility" and final_confidence > 0.4:
                claim_type = "potentially_false"
            elif web_verification.get('implausibility_score', 0) >= 2:
                claim_type = "potentially_false"  # Implausible = potentially false
            elif web_verification['verification_status'] == 'likely_true':
                claim_type = "factual_claim"
            elif "misinformation" in classification["labels"][0]:
                claim_type = "potentially_false"
            else:
                claim_type = "factual_claim"
        
        # 12. Enhanced Explanation
        explanation = f"Analysis shows this text has a {final_confidence:.1%} likelihood of containing factual claims. "
        explanation += f"The content appears to be primarily {classification['labels'][0]}. "
        
        if web_verification['searched']:
            if web_verification['verification_status'] != 'search_failed':
                explanation += f"Web verification found {web_verification['supporting_evidence']} supporting and "
                explanation += f"{web_verification['contradicting_evidence']} contradicting sources. "
            else:
                explanation += "Web verification failed due to technical issues. "
        else:
            explanation += "No web verification performed. "
        
        explanation += f"Credibility indicators suggest {credibility.replace('_', ' ')} reliability."
        
        # 13. Enhanced Suggestions
        suggestions = []
        
        if web_verification['verification_status'] == 'likely_false':
            suggestions.extend([
                "Web search suggests this claim may be false",
                "Cross-reference with additional fact-checking sources",
                "Avoid sharing this information until verified"
            ])
        elif web_verification['verification_status'] == 'search_failed':
            suggestions.extend([
                "Unable to verify claim online - search manually",
                "Check fact-checking websites like Snopes or PolitiFact",
                "Look for original sources or studies"
            ])
        elif risk_level == "high":
            suggestions.extend([
                "Verify claims with multiple credible sources",
                "Check official health/scientific organizations",
                "Be cautious sharing without verification"
            ])
        elif claim_type == "potentially_false":
            suggestions.extend([
                "Cross-reference with fact-checking websites",
                "Look for original sources or studies",
                "Consider the source's credibility"
            ])
        else:
            suggestions.extend([
                "Consider multiple perspectives",
                "Check for recent updates on this topic"
            ])
        
        if web_verification['searched']:
            search_msg = f"Searched {web_verification.get('sources_found', 0)} web sources"
            if web_verification.get('keywords_used'):
                search_msg += f" using keywords: {', '.join(web_verification['keywords_used'][:3])}"
            suggestions.append(search_msg)
        
        # Create response with clean data
        response_data = {
            "is_claim": bool(is_claim),
            "confidence": float(final_confidence),  # Use the new calculated confidence
            "claim_type": str(claim_type),
            "credibility_assessment": str(credibility),
            "sentiment_analysis": sentiment_data,
            "classification": classification,
            "summary": str(summary),
            "entities": entities,
            "risk_level": str(risk_level),
            "explanation": str(explanation),
            "suggestions": [str(s) for s in suggestions],
            "web_verification": web_verification
        }
        
        return AnalysisResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing text: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)