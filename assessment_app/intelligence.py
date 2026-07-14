import os
import json
import random
import re
from tavily import TavilyClient
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv('GROQ_API_KEY'))
tavily = TavilyClient(
    api_key=os.getenv("TAVILY_API_KEY")
)
# ── Topic banks per field ─────────────────────────────────────────────────
FIELD_TOPICS = {
    'AI Engineer': [
        'neural network architectures', 'deep learning fundamentals', 'model training and optimization',
        'loss functions and backpropagation', 'convolutional neural networks', 'recurrent neural networks',
        'transformers and attention mechanisms', 'AI model deployment', 'MLOps pipelines',
        'data preprocessing for AI', 'transfer learning', 'reinforcement learning basics',
        'AI ethics and bias', 'LLM prompting and fine-tuning'
    ],
    'Full Stack Developer': [
        'HTML5 and CSS3', 'JavaScript ES6+', 'React or Vue.js frontend frameworks',
        'Node.js and Express', 'RESTful API design', 'database design with SQL and NoSQL',
        'authentication and JWT', 'version control with Git', 'responsive web design',
        'web performance optimization', 'Docker basics', 'CI/CD for web apps',
        'TypeScript fundamentals', 'state management patterns'
    ],
    'Cybersecurity Analyst': [
        'network security fundamentals', 'cryptography and encryption', 'ethical hacking concepts',
        'penetration testing methodology', 'firewalls and intrusion detection systems',
        'social engineering attacks', 'malware analysis', 'web application security',
        'OWASP Top 10 vulnerabilities', 'identity and access management',
        'security information and event management (SIEM)', 'incident response procedures',
        'vulnerability scanning', 'digital forensics basics'
    ],
    'Cloud Engineer': [
        'cloud computing models (IaaS, PaaS, SaaS)', 'AWS core services', 'Azure fundamentals',
        'Google Cloud Platform basics', 'virtual machines and containers',
        'cloud networking and VPCs', 'cloud storage solutions', 'serverless architecture',
        'cloud security best practices', 'Kubernetes and orchestration',
        'infrastructure as code with Terraform', 'cloud cost optimization',
        'auto-scaling and load balancing', 'cloud monitoring and logging'
    ],
    'DevOps Engineer': [
        'CI/CD pipeline design', 'Docker and containerization', 'Kubernetes orchestration',
        'infrastructure as code', 'Git branching strategies', 'automated testing in pipelines',
        'monitoring and observability', 'Linux system administration',
        'shell scripting and automation', 'configuration management with Ansible',
        'site reliability engineering principles', 'microservices deployment',
        'log management', 'DevSecOps practices'
    ],
    'Data Scientist': [
        'statistical analysis fundamentals', 'Python for data science', 'pandas and NumPy',
        'data visualization with matplotlib or seaborn', 'machine learning algorithms',
        'supervised vs unsupervised learning', 'model evaluation and cross-validation',
        'feature engineering', 'natural language processing basics',
        'SQL for data extraction', 'hypothesis testing', 'regression and classification',
        'dimensionality reduction', 'data storytelling and communication'
    ],
    'Backend Developer': [
        'RESTful API design principles', 'database design and normalization',
        'SQL queries and joins', 'NoSQL databases', 'authentication and authorization',
        'caching strategies', 'message queues and async processing',
        'API security best practices', 'server-side programming concepts',
        'microservices architecture', 'database indexing and optimization',
        'error handling and logging', 'unit and integration testing',
        'web server configuration'
    ],
    'Machine Learning Engineer': [
        'supervised learning algorithms', 'unsupervised learning techniques',
        'model training pipelines', 'feature selection and engineering',
        'model evaluation metrics', 'overfitting and regularization',
        'ensemble methods', 'neural network basics', 'scikit-learn library',
        'data preprocessing and normalization', 'hyperparameter tuning',
        'ML model deployment', 'A/B testing for models', 'model versioning and monitoring'
    ],
    'Mobile Developer': [
        'mobile UI/UX principles', 'React Native fundamentals', 'Flutter basics',
        'iOS development concepts', 'Android development concepts',
        'mobile app state management', 'REST API integration in mobile apps',
        'mobile app authentication', 'push notifications',
        'app performance optimization', 'mobile app testing',
        'app store deployment process', 'offline-first design', 'device sensors and APIs'
    ],
    'UI/UX Designer': [
        'user-centered design principles', 'wireframing and prototyping',
        'design thinking methodology', 'usability testing',
        'information architecture', 'interaction design',
        'accessibility and inclusive design', 'color theory and typography',
        'Figma or design tool proficiency', 'user research methods',
        'responsive design principles', 'design systems',
        'A/B testing for UI', 'cognitive psychology in design'
    ],
    'Front End Developer': [
        'HTML5 semantic markup', 'CSS3 and Flexbox/Grid', 'JavaScript DOM manipulation',
        'React or Vue.js component architecture', 'TypeScript fundamentals',
        'web accessibility (WCAG)', 'responsive and mobile-first design',
        'browser developer tools', 'web performance optimization',
        'CSS animations and transitions', 'state management with Redux or Pinia',
        'testing React components', 'build tools like Vite or Webpack',
        'progressive web app concepts'
    ],
    'Data Analyst': [
        'descriptive statistics', 'SQL for data analysis', 'Excel advanced functions',
        'Python pandas for data manipulation', 'data visualization best practices',
        'Power BI or Tableau', 'data cleaning and validation',
        'exploratory data analysis', 'pivot tables and reporting',
        'business intelligence concepts', 'KPI definition and tracking',
        'cohort analysis', 'data storytelling', 'ETL processes'
    ],
}

SOFT_SKILL_TOPICS = [
    'leadership in team projects', 'conflict resolution in the workplace',
    'written and verbal communication', 'time management under deadlines',
    'critical thinking and decision making', 'emotional intelligence',
    'adaptability to change', 'giving and receiving feedback',
    'problem-solving under pressure', 'collaboration across teams',
]

BLOOM_LEVELS_BY_THETA = {
    'low':    ['Remembering', 'Understanding'],
    'mid':    ['Understanding', 'Applying'],
    'high':   ['Applying', 'Analyzing'],
    'expert': ['Analyzing', 'Evaluating', 'Creating']
}

def get_bloom_level(theta: float) -> str:
    if theta < -0.5:
        return random.choice(BLOOM_LEVELS_BY_THETA['low'])
    elif theta < 0.5:
        return random.choice(BLOOM_LEVELS_BY_THETA['mid'])
    elif theta < 1.5:
        return random.choice(BLOOM_LEVELS_BY_THETA['high'])
    return random.choice(BLOOM_LEVELS_BY_THETA['expert'])

def clean_ai_response(response_text: str):
    if not response_text:
        return None
    cleaned = response_text.strip()
    # Strip markdown fences if present
    if '```' in cleaned:
        lines = cleaned.split('\n')
        lines = [l for l in lines if not l.strip().startswith('```')]
        cleaned = '\n'.join(lines).strip()
    # Find the JSON array — look for [ ... ] even if surrounded by text
    start = cleaned.find('[')
    end = cleaned.rfind(']')
    if start != -1 and end != -1 and end > start:
        array_str = cleaned[start:end+1]
        try:
            parsed = json.loads(array_str)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
    # Try parsing the whole thing
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            return parsed
        # Handle {"questions": [...]} wrapper
        if isinstance(parsed, dict):
            for key in ['questions', 'items', 'data', 'results']:
                if key in parsed and isinstance(parsed[key], list):
                    return parsed[key]
            # If it looks like a single question, wrap it
            if 'question_text' in parsed:
                return [parsed]
        return None
    except json.JSONDecodeError:
        return None


def fallback_question(expertise_field: str, theta: float, topic: str) -> dict:
    """Improved fallback with randomized correct answer."""
    bloom = get_bloom_level(theta)
    
    options_list = [
        f"A core principle or best practice in {topic}",
        f"A common misconception or beginner mistake in {topic}",
        f"An advanced technique or application of {topic}",
        f"A related but less central concept to {topic}"
    ]
    
    random.shuffle(options_list)
    correct_idx = random.randint(0, 3)
    correct_letter = chr(97 + correct_idx)  # a, b, c, or d
    
    return {
        'question_text': f"Which of the following best describes {topic} in the context of {expertise_field}?",
        'options': {
            'a': options_list[0],
            'b': options_list[1],
            'c': options_list[2],
            'd': options_list[3],
        },
        'correct_answer': correct_letter,
        'difficulty_level': round(theta, 2),
        'bloom_level': bloom,
        'topic': topic
    }



def generate_question_batch(
    start_step: int,
    current_theta: float,
    skill_type: str,
    expertise_field: str,
    batch_size: int = 10,
    previously_asked: list = None
) -> list:
    previously_asked = previously_asked or []
    expertise_field = expertise_field.strip()

    field_topics = FIELD_TOPICS.get(expertise_field, FIELD_TOPICS['Full Stack Developer'])
    selected_topics = random.sample(field_topics, min(batch_size, len(field_topics)))
    while len(selected_topics) < batch_size:
        selected_topics.append(random.choice(field_topics))

    bloom_level = get_bloom_level(current_theta)
    difficulty_label = (
        'beginner (recall and understanding)' if current_theta < 0 else
        'intermediate (application and analysis)' if current_theta < 1.5 else
        'advanced (evaluation and creation)'
    )

    if skill_type == 'technical':
        topics_list = '\n'.join([f'{i+1}. {t}' for i, t in enumerate(selected_topics)])
        avoid_section = f'\nAvoid these topics: {", ".join(previously_asked[:12])}' if previously_asked else ''

        prompt = f"""You are an expert examiner creating a technical assessment.

Field: {expertise_field}
Difficulty: {difficulty_label}
Bloom Level: {bloom_level}
{avoid_section}

Create exactly {batch_size} multiple-choice questions (one per topic below).

Topics:
{topics_list}

Return **ONLY** a valid JSON array like this. No extra text, no explanation, no markdown:

[
  {{
    "question_text": "Full question text here?",
    "options": {{"a": "Option A", "b": "Option B", "c": "Option C", "d": "Option D"}},
    "correct_answer": "b",
    "difficulty_level": {round(current_theta, 2)},
    "bloom_level": "{bloom_level}",
    "topic": "exact topic name"
  }}
]

Make sure:
- "correct_answer" is one of "a", "b", "c", or "d"
- Questions are high quality and educational
- Correct answers are randomized"""

    else:
        # Soft skills (simplified for now)
        prompt = f"Generate {batch_size} soft skill scenario questions. Return only JSON array."

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=3000,
            response_format={"type": "text"}
        )

        content = response.choices[0].message.content.strip()
        print("Raw Groq response preview:", content[:300] + "...")  # For debugging

        parsed = clean_ai_response(content)

        if isinstance(parsed, list) and len(parsed) >= 4:
            valid = []
            for q in parsed:
                if all(k in q for k in ['question_text', 'options', 'correct_answer']):
                    if isinstance(q['options'], dict) and q['correct_answer'] in ['a','b','c','d']:
                        valid.append(q)
            if len(valid) >= 4:
                print(f"✅ Successfully generated {len(valid)} high-quality questions!")
                return valid[:batch_size]

        print("⚠️ JSON parsing failed → Using fallback")
        return [fallback_question(expertise_field, current_theta, t) for t in selected_topics]

    except Exception as e:
        print(f'Groq Error: {e}')
        return [fallback_question(expertise_field, current_theta, t) for t in selected_topics]

def calculate_next_difficulty(current_theta: float, was_correct: bool) -> float:
    k = 0.25
    if was_correct:
        return min(round(current_theta + k, 2), 3.0)
    return max(round(current_theta - k, 2), -3.0)

def get_level_context(theta: float) -> dict:
    """Returns rich context about the user's level for the LLM prompt."""
    if theta < -0.5:
        return {
            'bucket': 'beginner',
            'bloom': get_bloom_level(theta),
            'description': 'Foundational level. Needs core concepts, basic syntax, and introductory materials.',
            'resource_types': 'introductory courses, beginner tutorials, documentation basics, video walkthroughs'
        }
    elif theta < 0.5:
        return {
            'bucket': 'intermediate',
            'bloom': get_bloom_level(theta),
            'description': 'Building practical skills. Needs hands-on projects, pattern recognition, and applied learning.',
            'resource_types': 'project-based courses, intermediate tutorials, coding challenges, design patterns'
        }
    elif theta < 1.5:
        return {
            'bucket': 'advanced',
            'bloom': get_bloom_level(theta),
            'description': 'Deep specialization. Needs architecture, optimization, and advanced patterns.',
            'resource_types': 'advanced courses, system design resources, performance optimization guides, technical books'
        }
    return {
        'bucket': 'expert',
        'bloom': get_bloom_level(theta),
        'description': 'Mastery and innovation. Needs cutting-edge research, leadership, and novel problem-solving.',
        'resource_types': 'research papers, conference talks, expert-level courses, architecture case studies, technical leadership resources'
    }


def get_tier_constraints(tier: str) -> str:
    """Returns strict constraints for the LLM based on tier."""
    if tier == 'paid':
        return """
TIER CONSTRAINTS (PAID - STRICT):
- ONLY recommend paid resources: Udemy courses, Coursera specializations, Pluralsight, Frontend Masters, Educative, LinkedIn Learning, O'Reilly, Manning books, A Cloud Guru, DataCamp paid, etc.
- NEVER recommend free resources like YouTube, freeCodeCamp, MDN, official docs, or blog posts.
- Include realistic pricing context if known ($20-$200 range).
- Focus on premium, certificate-bearing, or instructor-led content.
"""
    return """
TIER CONSTRAINTS (FREE - STRICT):
- ONLY recommend free resources: official documentation, freeCodeCamp, YouTube tutorials, MDN, W3Schools, Kaggle Learn, Fast.ai, The Odin Project, GitHub Skills, Coursera audit mode, edX audit, Khan Academy, etc.
- NEVER recommend paid courses, books for purchase, or certification exams.
- Include "free" or "no cost" in descriptions.
"""


def validate_recommendation_urls(result: dict) -> dict:
    """
    Post-processes LLM output to ensure URLs are well-formed.
    Does NOT replace with hardcoded URLs — just validates format.
    """
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    for section in ['skill_development', 'improvement_resources']:
        for item in result.get(section, []):
            url = item.get('url', '')
            # If URL is missing or malformed, flag it (don't hardcode replacement)
            if not url or not url_pattern.match(url):
                item['url'] = ''  # Clear invalid URLs — frontend can hide or show "search manually"
                item['description'] += ' [Note: Search for this resource manually]'
            # Ensure URLs use https
            elif url.startswith('http://'):
                item['url'] = url.replace('http://', 'https://', 1)
    return result

def _clean_llm_json(raw: str) -> str:
    """Strips markdown fences and extracts clean JSON from LLM response."""
    if not raw:
        return ""
    
    raw = raw.strip()
    
    # Remove opening ``` or ```json
    if raw.startswith('```'):
        first_newline = raw.find('\n')
        if first_newline != -1:
            raw = raw[first_newline:].strip()
        elif raw.startswith('```json'):
            raw = raw[7:].strip()
        elif raw.startswith('```'):
            raw = raw[3:].strip()
    
    # Remove closing ```
    if raw.endswith('```'):
        raw = raw[:-3].strip()
    
    # Remove "json" prefix if present
    if raw.startswith('json'):
        raw = raw[4:].strip()
    
    return raw.strip()

def search_learning_resources(query: str, max_results: int = 3):
    """
    Searches the web using Tavily and returns cleaned learning resources.
    """

    try:

        response = tavily.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_answer=False,
            include_images=False,
        )

        resources = []

        for result in response.get("results", []):

            resources.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "description": result.get("content", "")[:250]
            })

        return resources

    except Exception as e:

        print("Tavily Search Error:", e)

        return []
    
def build_search_queries(skill_category, level_bucket, tier):
    """
    Builds several search queries so Tavily can find diverse resources.
    """
    
    if tier == "paid":

        return [

        f"best paid {level_bucket} {skill_category} course",

        f"Udemy {level_bucket} {skill_category}",

        f"Coursera {level_bucket} {skill_category}",

        f"Pluralsight {level_bucket} {skill_category}",

        f"{level_bucket} {skill_category} certification"

    ]

    else:

            return [

        f"free {level_bucket} {skill_category} tutorial",

        f" {level_bucket} {skill_category} official documentation",

        f"freeCodeCamp {level_bucket} {skill_category}",

        f"YouTube {level_bucket} {skill_category}",

        f" {level_bucket} {skill_category} roadmap"

    ]
            


   
def collect_real_resources(skill_category, level_bucket, tier):

    queries = build_search_queries(
        skill_category,
        level_bucket,
        tier
    )


    resources = []

    seen = set()

    for query in queries:

        results = search_learning_resources(query)

        for r in results:

            url = r["url"]

            if url not in seen:

                seen.add(url)

                resources.append(r)

    return resources


def get_recommendations(skill_category: str, final_score: float, tier: str = "free") -> dict:
    """
    Uses Groq to identify learning topics, then Tavily to retrieve real learning resources.
    """

    level_ctx = get_level_context(final_score)

    try:

        prompt = f"""
You are an expert career mentor.

A student completed an adaptive assessment.

Field:
{skill_category}

Skill Level:
{level_ctx["bucket"]}

Bloom Level:
{level_ctx["bloom"]}

Recommend exactly THREE learning milestones.

For each milestone return:

- title
- topic
- short description
- priority

Return ONLY valid JSON.

Example:

[
    {{
        "title":"Master REST APIs",
        "topic":"REST API Design",
        "description":"Learn API architecture and HTTP best practices.",
        "priority":"High"
    }}
]
"""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            temperature=0.4,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        content = response.choices[0].message.content

        milestones = json.loads(_clean_llm_json(content))

    except Exception as e:

        print("Groq Recommendation Error:", e)

        milestones = [
            {
                "title": f"Improve {skill_category}",
                "topic": skill_category,
                "description": "Continue improving your skills.",
                "priority": "High"
            }
        ]

    skill_development = []

    improvement_resources = []

    seen_urls = set()

    for milestone in milestones:

     
        resources = collect_real_resources(
            milestone["topic"],
            level_ctx["bucket"],
            tier
        )

        skill_development.append({

            "title": milestone["title"],

            "description": milestone["description"],

            "priority": milestone["priority"],

            "buttonText": "Start Learning",

            "url": resources[0]["url"] if resources else ""

        })

        for resource in resources:

            if resource["url"] in seen_urls:
                continue

            seen_urls.add(resource["url"])

            improvement_resources.append({

                "title": resource["title"],

                "type": "Learning Resource",

                "priority": milestone["priority"],

                "url": resource["url"],

                "description": resource["description"]

            })

    return {

        "skill_development": skill_development,

        "improvement_resources": improvement_resources

    }

def _get_field_context(skill_category: str) -> str:
    """Returns specific context about a field to prevent generic recommendations."""
    contexts = {
        'AI Engineer': 'Focus on: neural networks, deep learning, MLOps, LLMs, PyTorch/TensorFlow, model deployment. NOT: web dev, CSS, React, mobile apps.',
        'Data Scientist': 'Focus on: statistics, Python, pandas, scikit-learn, data visualization, SQL, hypothesis testing, ML algorithms. NOT: frontend, backend APIs, DevOps.',
        'Data Analyst': 'Focus on: SQL, Excel, Tableau/PowerBI, business intelligence, reporting, KPIs, data storytelling. NOT: neural networks, system design, Kubernetes.',
        'Full Stack Developer': 'Focus on: frontend (React/Vue), backend (Node/Python), databases, REST APIs, deployment. NOT: data science, AI model training, cybersecurity forensics.',
        'Front End Developer': 'Focus on: HTML/CSS, JavaScript, React/Vue, accessibility, performance, responsive design. NOT: backend architecture, databases, ML.',
        'Backend Developer': 'Focus on: APIs, databases, caching, message queues, authentication, microservices. NOT: UI design, CSS, mobile UI.',
        'DevOps Engineer': 'Focus on: CI/CD, Docker, Kubernetes, Terraform, monitoring, cloud platforms, scripting. NOT: frontend frameworks, data analysis, AI research.',
        'Cloud Engineer': 'Focus on: AWS/Azure/GCP, networking, serverless, IaC, security, cost optimization. NOT: mobile development, UI/UX, data science pipelines.',
        'Cybersecurity Analyst': 'Focus on: network security, penetration testing, SIEM, incident response, compliance, forensics. NOT: frontend development, database design, ML.',
        'Machine Learning Engineer': 'Focus on: ML pipelines, model serving, feature engineering, MLflow, Kubeflow, A/B testing. NOT: web design, mobile apps, general backend.',
        'Mobile Developer': 'Focus on: iOS/Android, React Native, Flutter, mobile UI, state management, push notifications. NOT: web backend, data science, cloud architecture.',
        'UI/UX Designer': 'Focus on: Figma, user research, wireframing, prototyping, usability testing, design systems. NOT: programming, databases, DevOps.',
    }
    return contexts.get(skill_category, f'Focus on: core competencies for {skill_category}. Avoid generic programming resources.')


def _enforce_tier_constraints(result: dict, tier: str, field: str, level: str) -> dict:
    """
    Hard post-validation: removes recommendations that violate tier/field/level.
    This is the safety net when the LLM ignores prompt instructions.
    """
    # Define forbidden keywords per tier
    if tier == 'paid':
        forbidden_keywords = ['freecodecamp', 'youtube.com', 'mdn', 'w3schools', 'khan academy', 
                             'the odin project', 'github skills', 'fast.ai', 'kaggle learn', 
                             'free', 'no cost', 'open source', 'documentation', 'tutorial (free)']
    else:
        forbidden_keywords = ['udemy', 'coursera certificate', 'pluralsight', 'frontend masters',
                             'educative.io', 'linkedin learning', 'o\'reilly', 'manning', 
                             'a cloud guru', 'datacamp paid', 'paid', '$', 'subscription', 'certification exam']

    # Field mismatch keywords (generic resources that appear for any field)
    field_mismatch = {
        'Data Scientist': ['react', 'vue', 'css', 'html', 'frontend', 'web design', 'mobile app'],
        'AI Engineer': ['css', 'html', 'web design', 'excel advanced', 'tableau', 'powerbi'],
        'Data Analyst': ['neural network', 'deep learning', 'pytorch', 'tensorflow', 'kubernetes'],
        'UI/UX Designer': ['python', 'javascript', 'database', 'api', 'backend', 'devops'],
        'Cybersecurity Analyst': ['react', 'vue', 'frontend', 'data visualization', 'pandas'],
    }
    
    forbidden_for_field = field_mismatch.get(field, [])

    def is_valid(item: dict) -> bool:
        text = f"{item.get('title', '')} {item.get('description', '')} {item.get('type', '')}".lower()
        
        # Check tier violation
        for keyword in forbidden_keywords:
            if keyword in text:
                return False
        
        # Check field mismatch
        for keyword in forbidden_for_field:
            if keyword in text:
                return False
        
        # Check URL validity
        url = item.get('url', '')
        if not url or not url.startswith('https://'):
            return False
            
        return True

    # Filter out invalid recommendations
    for section in ['skill_development', 'improvement_resources']:
        if section in result:
            result[section] = [item for item in result[section] if is_valid(item)]
            
            # If we filtered out too many, add fallback search links
            if len(result[section]) < 2:
                result[section].append({
                    "title": f"Search {tier} {field} {level} resources",
                    "description": f"Find verified {tier} resources for {level}-level {field} professionals.",
                    "url": f"https://www.google.com/search?q={tier}+{field.replace(' ', '+')}+{level}+courses",
                    "priority": "High",
                    "buttonText": "Search Resources" if section == 'skill_development' else None,
                    "type": "Search" if section == 'improvement_resources' else None
                })

    return result
def _minimal_fallback(skill_category: str, level: str, tier: str) -> dict:
    """
    Minimal fallback that still uses the LLM's web knowledge concept —
    returns empty structure with guidance, not hardcoded URLs.
    """
    tier_label = "paid" if tier == 'paid' else "free"
    return {
        "skill_development": [
            {
                "title": f"Explore {skill_category} {level} resources",
                "description": f"Search for {tier_label} {level}-level courses on Google, Udemy, or Coursera for {skill_category}.",
                "url": f"https://www.google.com/search?q={skill_category.replace(' ', '+')}+{level}+{tier_label}+courses",
                "priority": "High",
                "buttonText": "Search Resources"
            }
        ],
        "improvement_resources": [
            {
                "title": f"{skill_category} Learning Path",
                "type": "Search",
                "priority": "High",
                "url": f"https://www.google.com/search?q=best+{tier_label}+{level}+{skill_category.replace(' ', '+')}+resources+2024",
                "description": f"Find current {tier_label} resources for {level} {skill_category} professionals."
            }
        ]
    }
    