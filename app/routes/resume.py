from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import re
import io
import httpx
import boto3
import os
from urllib.parse import urlparse
from app.bedrock_service import bedrock_extractor

router = APIRouter(prefix="/resume", tags=["Resume"])

# ── Comprehensive skills dictionary ───────────────────────────────────────────
SKILLS_DICT = [
    # Programming Languages
    "Python", "JavaScript", "TypeScript", "Java", "C", "C++", "C#", "Go", "Rust",
    "Ruby", "PHP", "Swift", "Kotlin", "Scala", "R", "MATLAB", "Perl", "Bash",
    "Shell", "PowerShell", "Dart", "Lua", "Julia",
    # Web Frontend
    "React", "Next.js", "Vue", "Angular", "Svelte", "HTML", "CSS", "Tailwind",
    "Bootstrap", "SASS", "SCSS", "jQuery", "Redux", "Zustand", "GraphQL",
    "REST", "WebSocket", "Webpack", "Vite", "Babel",
    # Web Backend
    "Node.js", "Express", "FastAPI", "Django", "Flask", "Spring Boot", "Laravel",
    "Rails", "ASP.NET", "Gin", "Fiber", "NestJS", "Hapi", "Koa",
    # Databases
    "PostgreSQL", "MySQL", "SQLite", "MongoDB", "Redis", "Cassandra", "DynamoDB",
    "Elasticsearch", "Neo4j", "InfluxDB", "Firestore", "Supabase", "Prisma",
    "SQLAlchemy", "Mongoose", "Sequelize",
    # Cloud & DevOps
    "AWS", "GCP", "Azure", "Docker", "Kubernetes", "Terraform", "Ansible",
    "Jenkins", "GitHub Actions", "CircleCI", "Helm", "Prometheus", "Grafana",
    "Nginx", "Apache", "Linux", "Git",
    # AWS Services
    "EKS", "EC2", "S3", "RDS", "Lambda", "CloudFormation", "CloudWatch",
    "CodeDeploy", "CodePipeline", "CodeBuild", "ECR", "ECS", "VPC", "IAM",
    "Route53", "CloudFront", "SQS", "SNS", "Bedrock", "Inspector",
    "AWS Bedrock", "AWS Lambda", "AWS EKS", "AWS EC2", "AWS S3",
    # Data & ML
    "Machine Learning", "Deep Learning", "NLP", "Computer Vision", "TensorFlow",
    "PyTorch", "Keras", "Scikit-learn", "Pandas", "NumPy", "Matplotlib",
    "Seaborn", "Jupyter", "Spark", "Hadoop", "Kafka", "Airflow", "dbt",
    "Power BI", "Tableau", "Excel", "SQL",
    # Mobile
    "Android", "iOS", "React Native", "Flutter", "Xamarin",
    # Testing
    "Jest", "Pytest", "Selenium", "Cypress", "Playwright", "JUnit",
    # Security & DevSecOps
    "DevSecOps", "SAST", "DAST", "OWASP", "Vault", "Trivy", "Snyk",
    "ISO 27001", "SOC 2", "NIST", "CVE", "Penetration Testing",
    # IaC & Config
    "Pulumi", "Chef", "Puppet", "SaltStack", "ArgoCD", "FluxCD",
    # Observability
    "Datadog", "New Relic", "Splunk", "ELK", "Loki", "Jaeger",
    # Other
    "Blockchain", "Solidity", "Web3", "Agile", "Scrum", "Jira", "Figma",
    "Photoshop", "Illustrator",
]

DEGREE_PATTERNS = [
    r"B\.?\s*Tech", r"M\.?\s*Tech", r"B\.?\s*E\.?", r"M\.?\s*E\.?",
    r"B\.?\s*Sc\.?", r"M\.?\s*Sc\.?", r"B\.?\s*Com\.?", r"M\.?\s*Com\.?",
    r"MBA", r"BBA", r"MCA", r"BCA", r"B\.?\s*A\.?", r"M\.?\s*A\.?",
    r"Ph\.?\s*D\.?", r"Bachelor", r"Master", r"Diploma",
    r"B\.?\s*S\.?", r"M\.?\s*S\.?",
]

SECTION_HEADERS = {
    "summary": ["summary", "objective", "about", "profile", "career objective", "professional summary"],
    "skills": ["skills", "technical skills", "key skills", "core competencies", "technologies", "tools", "tech stack"],
    "experience": ["experience", "work experience", "employment", "professional experience", "work history"],
    "education": ["education", "academic", "qualification", "educational background"],
    "projects": ["projects", "personal projects", "academic projects", "key projects"],
    "achievements": ["achievements", "awards", "accomplishments", "honors", "certifications"],
    "languages": ["languages", "language skills"],
}

# ── Known universities list (substring match, no regex) ───────────────────────
KNOWN_UNIVERSITIES = [
    # IITs
    "IIT Bombay", "IIT Delhi", "IIT Madras", "IIT Kanpur", "IIT Kharagpur",
    "IIT Roorkee", "IIT Guwahati", "IIT Hyderabad", "IIT Indore", "IIT Jodhpur",
    "IIT Patna", "IIT Ropar", "IIT Bhubaneswar", "IIT Gandhinagar", "IIT Tirupati",
    "IIT Mandi", "IIT Dharwad", "IIT Palakkad", "IIT Varanasi", "IIT BHU",
    # NITs
    "NIT Trichy", "NIT Warangal", "NIT Surathkal", "NIT Calicut", "NIT Rourkela",
    "NIT Allahabad", "NIT Bhopal", "NIT Durgapur", "NIT Kurukshetra", "NIT Nagpur",
    "NIT Jaipur", "NIT Surat", "NIT Silchar", "NIT Hamirpur", "NIT Jalandhar",
    # IIITs
    "IIIT Hyderabad", "IIIT Bangalore", "IIIT Allahabad", "IIIT Delhi", "IIIT Gwalior",
    # Deemed/Central Universities
    "BITS Pilani", "BITS Goa", "BITS Hyderabad", "VIT Vellore", "VIT Chennai",
    "SRM University", "SRM Institute", "Manipal University", "Manipal Institute",
    "Amity University", "Symbiosis International", "Thapar University",
    "Jadavpur University", "Osmania University", "Anna University",
    "University of Delhi", "Delhi University", "Mumbai University",
    "University of Mumbai", "University of Pune", "Pune University",
    "Bangalore University", "University of Hyderabad", "Hyderabad University",
    "Jawaharlal Nehru University", "JNU", "BHU", "Banaras Hindu University",
    "Aligarh Muslim University", "AMU", "Calcutta University",
    "University of Calcutta", "Madras University", "University of Madras",
    "Cochin University", "CUSAT", "Kerala University", "University of Kerala",
    "Andhra University", "Osmania University", "Nagpur University",
    "RTMNU", "Savitribai Phule Pune University", "SPPU",
    # Engineering Colleges
    "COEP", "College of Engineering Pune", "PSG College", "SSN College",
    "RV College", "PES University", "MSRIT", "MS Ramaiah",
    "Veermata Jijabai Technological Institute", "VJTI",
    "Netaji Subhas University", "NSUT", "DTU", "Delhi Technological University",
    "NSIT", "Netaji Subhas Institute",
    # IIMs
    "IIM Ahmedabad", "IIM Bangalore", "IIM Calcutta", "IIM Lucknow",
    "IIM Kozhikode", "IIM Indore", "IIM Udaipur",
    # Global
    "MIT", "Stanford University", "Harvard University", "Carnegie Mellon",
    "University of California", "UC Berkeley", "UCLA", "UCSD",
    "University of Michigan", "University of Texas", "Georgia Tech",
    "Columbia University", "Cornell University", "Princeton University",
    "Yale University", "University of Toronto", "University of Waterloo",
    "University of British Columbia", "National University of Singapore",
    "NUS", "Nanyang Technological University", "NTU",
    "Imperial College", "University College London", "UCL",
    "University of Edinburgh", "University of Oxford", "University of Cambridge",
    # Generic fallback tokens (short names people use)
    "MIT School", "Symbiosis", "Amrita", "Chandigarh University",
    "Lovely Professional University", "LPU", "Shiv Nadar University",
    "Ashoka University", "Plaksha University", "Krea University",
]

COMMON_LANGUAGES = [
    "English", "Hindi", "Tamil", "Telugu", "Kannada", "Malayalam",
    "Marathi", "Bengali", "Gujarati", "Punjabi", "Urdu", "French",
    "German", "Spanish", "Japanese", "Chinese", "Mandarin", "Arabic",
]


class ExtractRequest(BaseModel):
    resume_url: str


def extract_text_from_pdf(content: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(content))
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text


def extract_text_from_docx(content: bytes) -> str:
    import docx
    doc = docx.Document(io.BytesIO(content))
    return "\n".join([para.text for para in doc.paragraphs if para.text.strip()])


def split_into_sections(text: str) -> Dict[str, str]:
    lines = text.split("\n")
    sections: Dict[str, List[str]] = {"header": []}
    current_section = "header"

    for line in lines:
        stripped = line.strip().lower()
        matched = False
        for section_key, keywords in SECTION_HEADERS.items():
            if any(
                stripped == kw or stripped.startswith(kw + ":") or stripped == kw.upper()
                for kw in keywords
            ):
                if len(stripped) < 50:
                    current_section = section_key
                    sections.setdefault(current_section, [])
                    matched = True
                    break
        if not matched:
            sections.setdefault(current_section, []).append(line)

    return {k: "\n".join(v) for k, v in sections.items()}


def extract_email(text: str) -> Optional[str]:
    match = re.search(r"[\w\.\+\-]+@[\w\-]+\.[\w\.]+", text)
    return match.group(0) if match else None


def extract_phone(text: str) -> Optional[str]:
    patterns = [
        r"(\+91[\s\-]?)?[6-9]\d{9}",
        r"\+?1?\s?[\(\-]?\d{3}[\)\-\s]?\s?\d{3}[\-\s]?\d{4}",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            phone = re.sub(r"[\s\-\(\)]", "", match.group(0))
            if len(phone) >= 10:
                return phone
    return None


def extract_linkedin(text: str) -> Optional[str]:
    match = re.search(r"(?:linkedin\.com/in/)([\w\-]+)", text, re.IGNORECASE)
    if match:
        return f"https://linkedin.com/in/{match.group(1)}"
    return None


def extract_github(text: str) -> Optional[str]:
    match = re.search(r"(?:github\.com/)([\w\-]+)", text, re.IGNORECASE)
    if match:
        return f"https://github.com/{match.group(1)}"
    return None


def extract_portfolio(text: str) -> Optional[str]:
    match = re.search(
        r"https?://(?!(?:linkedin|github|mail|gmail|yahoo)\.com)[\w\-]+\.[\w\-\.]+(?:/[\w\-\./?=&%#]*)?",
        text, re.IGNORECASE
    )
    return match.group(0) if match else None


def extract_name(text: str) -> Optional[str]:
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for line in lines[:6]:
        if (
            not re.search(r"@|http|www|\d{5,}|resume|curriculum|cv|phone|email|mobile", line, re.IGNORECASE)
            and 2 <= len(line.split()) <= 5
            and len(line) < 60
            and not re.search(r"[|•·,]", line)
        ):
            return line.title()
    return None


def extract_degree(text: str) -> Optional[str]:
    for pattern in DEGREE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            start = match.start()
            snippet = text[start:start + 80].split("\n")[0].strip()
            return snippet
    return None


def extract_university(text: str) -> Optional[str]:
    # Step 1: Direct lookup in known universities list (case-insensitive substring)
    text_lower = text.lower()
    for uni in KNOWN_UNIVERSITIES:
        if uni.lower() in text_lower:
            # Find original casing from text
            idx = text_lower.find(uni.lower())
            return text[idx: idx + len(uni)]

    # Step 2: Education section line-by-line fallback
    # Find where the education section starts
    edu_markers = ["education", "academic", "qualification"]
    edu_start = -1
    for line_num, line in enumerate(text.split("\n")):
        if line.strip().lower() in edu_markers or line.strip().lower().startswith(tuple(edu_markers)):
            if len(line.strip()) < 40:
                edu_start = line_num
                break

    if edu_start != -1:
        edu_lines = text.split("\n")[edu_start + 1 : edu_start + 15]
        degree_tokens = {"bachelor", "master", "b.tech", "m.tech", "b.e", "m.e",
                         "b.sc", "m.sc", "mba", "phd", "diploma", "bca", "mca",
                         "b.s", "m.s", "b.com", "m.com"}
        skip_tokens = {"cgpa", "gpa", "percentage", "grade", "%", "score",
                       "2019", "2020", "2021", "2022", "2023", "2024", "2025"}
        for line in edu_lines:
            stripped = line.strip()
            if not stripped or len(stripped) < 5:
                continue
            low = stripped.lower()
            # Skip lines that are just degree names or scores
            if any(tok in low for tok in degree_tokens | skip_tokens):
                continue
            # Must be at least 2 words and reasonably short
            words = stripped.split()
            if 2 <= len(words) <= 10 and len(stripped) < 80:
                return stripped.title()

    return None


def extract_location(text: str) -> Optional[str]:
    cities = [
        "Mumbai", "Delhi", "Bangalore", "Bengaluru", "Hyderabad", "Chennai",
        "Pune", "Kolkata", "Ahmedabad", "Jaipur", "Surat", "Lucknow",
        "Noida", "Gurgaon", "Gurugram", "Chandigarh", "Coimbatore", "Kochi",
        "Nagpur", "Indore", "Bhopal", "Patna", "Vadodara", "Ghaziabad",
        "Remote", "New York", "San Francisco", "London", "Singapore", "Dubai",
    ]
    for city in cities:
        if re.search(r"\b" + city + r"\b", text, re.IGNORECASE):
            return city
    match = re.search(r"(?:location|address|city)\s*[:\-]\s*([^\n,\.]+)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def extract_experience_years(text: str) -> Optional[str]:
    patterns = [
        r"(\d+\.?\d*)\+?\s*years?\s+(?:of\s+)?(?:experience|exp)",
        r"experience\s*[:\-]?\s*(\d+\.?\d*)\+?\s*years?",
        r"(\d+\.?\d*)\+?\s*yrs?\s+(?:of\s+)?(?:experience|exp)",
        r"(\d+\.?\d*)\+?\s*years?\s+(?:building|working|developing|designing|managing|leading)",
        r"with\s+(\d+\.?\d*)\+?\s*years?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return f"{match.group(1)}+ years"
    return None


def extract_skills(text: str) -> List[str]:
    found = []
    for skill in SKILLS_DICT:
        if re.search(r"\b" + re.escape(skill) + r"\b", text, re.IGNORECASE):
            found.append(skill)
    return found


def extract_summary(sections: Dict[str, str]) -> Optional[str]:
    text = sections.get("summary", "").strip()
    if text and len(text) > 30:
        return text[:800]
    return None


def extract_current_ctc(text: str) -> Optional[str]:
    patterns = [
        r"current\s*ctc\s*[:\-]?\s*([\d\.]+\s*(?:lpa|lakh|l|k|thousand)?)",
        r"(?:^|\s)ctc\s*[:\-]\s*([\d\.]+\s*(?:lpa|lakh|l|k)?)",
        r"current\s*salary\s*[:\-]?\s*([\d\.]+\s*(?:lpa|lakh|l|k|thousand)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def extract_expected_ctc(text: str) -> Optional[str]:
    patterns = [
        r"expected\s*ctc\s*[:\-]?\s*([\d\.]+\s*(?:lpa|lakh|l|k|thousand)?)",
        r"expected\s*salary\s*[:\-]?\s*([\d\.]+\s*(?:lpa|lakh|l|k|thousand)?)",
        r"desired\s*salary\s*[:\-]?\s*([\d\.]+\s*(?:lpa|lakh|l|k|thousand)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def extract_languages(text: str, sections: Dict[str, str]) -> List[str]:
    found = []
    search_text = sections.get("languages", "") or text
    for lang in COMMON_LANGUAGES:
        if re.search(r"\b" + lang + r"\b", search_text, re.IGNORECASE):
            found.append(lang)
    return found


def extract_employment(sections: Dict[str, str]) -> List[Dict]:
    text = sections.get("experience", "")
    if not text.strip():
        return []

    entries: List[Dict] = []
    # Split into job blocks by blank lines
    blocks = [b.strip() for b in re.split(r'\n\s*\n', text) if b.strip()]

    for block in blocks:
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        if len(lines) < 2:
            continue

        title, company, duration = None, None, None
        desc_lines: List[str] = []

        for line in lines:
            # Duration: line with month/year range
            if re.search(
                r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{4})\b.{0,30}(present|current|\d{4})',
                line, re.IGNORECASE
            ):
                if not duration:
                    duration = line
                continue
            # Description: bullet points or long sentences
            if line[:1] in ('•', '-', '*', '–', '→') or (len(line.split()) > 8):
                desc_lines.append(line.lstrip('•-*–→ '))
                continue
            # Short lines are title / company candidates
            if len(line.split()) <= 7:
                if title is None:
                    title = line
                elif company is None:
                    company = line

        if title or company:
            entries.append({
                "id": str(len(entries) + 1),
                "title": title or "",
                "company": company or "",
                "duration": duration or "",
                "description": " ".join(desc_lines[:4]),
            })

    return entries[:6]


def extract_projects(sections: Dict[str, str]) -> List[Dict]:
    text = sections.get("projects", "")
    if not text.strip():
        return []

    entries: List[Dict] = []
    blocks = [b.strip() for b in re.split(r'\n\s*\n', text) if b.strip()]

    for block in blocks:
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        if not lines:
            continue

        title = lines[0].lstrip('•-*–→ ').strip()
        duration = None
        desc_lines: List[str] = []

        for line in lines[1:]:
            if re.search(r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{4})\b', line, re.IGNORECASE):
                if not duration:
                    duration = line
            else:
                desc_lines.append(line.lstrip('•-*–→ '))

        if title and len(title.split()) <= 10:
            entries.append({
                "id": str(len(entries) + 1),
                "title": title,
                "duration": duration or "",
                "description": " ".join(desc_lines[:4]),
            })

    return entries[:8]


async def extract_text_from_url(resume_url: str) -> str:
    # Validate / normalize the incoming URL
    if not resume_url.lower().startswith(("http://", "https://")):
        # Assume HTTPS when scheme is omitted
        resume_url = f"https://{resume_url}"
        
    # 1. Download file from S3 securely using boto3, falling back to HTTP if not a standard S3 link
    content = b""
    content_type = ""
    try:
        if "s3.amazonaws.com" in resume_url or ".s3." in resume_url:
            parsed_url = urlparse(resume_url)
            netloc_parts = parsed_url.netloc.split('.')
            bucket_name = netloc_parts[0]
            file_key = parsed_url.path.lstrip('/')
            
            region = os.getenv("AWS_REGION", "ap-south-1")
            s3_client = boto3.client('s3', region_name=region)
            s3_response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
            content = s3_response['Body'].read()
            content_type = s3_response.get('ContentType', '')
        else:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(resume_url)
                response.raise_for_status()
                content = response.content
                content_type = response.headers.get("content-type", "")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to download resume: {str(e)}")

    # 2. Detect file type
    url_lower = resume_url.lower().split("?")[0]
    is_docx = url_lower.endswith(".docx") or "word" in content_type or "openxml" in content_type

    # 3. Extract raw text
    text = ""
    try:
        if is_docx:
            text = extract_text_from_docx(content)
        else:
            # Default to PDF (also handles unknown types)
            text = extract_text_from_pdf(content)
    except Exception:
        try:
            # Fallback: try the other parser
            text = extract_text_from_docx(content) if not is_docx else extract_text_from_pdf(content)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Could not parse resume file: {str(e)}")

    if not text or len(text.strip()) < 50:
        raise HTTPException(status_code=422, detail="Resume appears to be empty or unreadable.")
        
    return text


@router.post("/extract")
async def extract_resume(req: ExtractRequest):
    # Debug: log incoming payload
    print(f"[DEBUG] extract_resume payload: {req}")
    resume_url = req.resume_url
    if not resume_url:
        raise HTTPException(status_code=400, detail="Missing resume URL.")
        
    text = await extract_text_from_url(resume_url)

    # 4. Try Bedrock extraction first
    result = None
    extraction_method = "regex"
    
    if bedrock_extractor.is_available():
        try:
            result = await bedrock_extractor.extract_with_bedrock(text)
            if result:
                extraction_method = "bedrock"
        except Exception as e:
            print(f"Bedrock extraction failed, falling back to regex: {e}")
            result = None

    # 5. Fallback to regex extraction if Bedrock unavailable or failed
    if result is None:
        sections = split_into_sections(text)
        edu_text = sections.get("education", text)
        result = {
            "name": extract_name(text),
            "email": extract_email(text),
            "phone": extract_phone(text),
            "location": extract_location(text),
            "degree": extract_degree(edu_text),
            "university": extract_university(edu_text),
            "experience_years": extract_experience_years(text),
            "summary": extract_summary(sections),
            "skills": extract_skills(sections.get("skills", text)),
            "languages": extract_languages(text, sections),
            "current_ctc": extract_current_ctc(text),
            "expected_ctc": extract_expected_ctc(text),
            "linkedin": extract_linkedin(text),
            "github": extract_github(text),
            "portfolio": extract_portfolio(text),
            "employment": extract_employment(sections),
            "projects": extract_projects(sections),
        }

    # 6. Mark missing fields
    missing_fields = [
        k for k, v in result.items()
        if v is None or v == [] or v == ""
    ]

    return {
        "extracted": result,
        "missing_fields": missing_fields,
        "raw_text_length": len(text),
        "extraction_method": extraction_method,
    }


class TailorRequest(BaseModel):
    resume_url: Optional[str] = None
    resume_text: Optional[str] = None
    job_title: str
    company: Optional[str] = "Target Company"
    job_description: str


@router.post("/tailor")
async def tailor_resume(req: TailorRequest):
    import json
    
    # 1. Obtain raw resume text
    resume_text = req.resume_text
    if not resume_text:
        if not req.resume_url:
            raise HTTPException(status_code=400, detail="Either resume_text or resume_url must be provided.")
        try:
            resume_text = await extract_text_from_url(req.resume_url)
        except HTTPException as he:
            raise he
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to extract resume text: {str(e)}")

    # 2. Validate Bedrock availability
    if not bedrock_extractor.is_available():
        raise HTTPException(status_code=503, detail="AI tailoring service is currently unavailable.")

    # 3. Create prompt
    prompt = f"""You are an expert resume writer and career coach. Your task is to tailor a user's resume for a specific job description.
Align the user's skills, accomplishments, and professional experience to highlight matching capabilities for the target role while maintaining truthfulness.

Target Job Details:
Title: {req.job_title}
Company: {req.company}
Job Description:
{req.job_description}

Original Resume Content:
{resume_text}

Provide the tailored resume output in clean JSON format matching the following schema. Keep descriptions concise, using strong action verbs:
{{
  "contact": {{
    "name": "Full name of the candidate from the top of the original resume, if found. Otherwise, leave empty.",
    "email": "Email address from original resume, if found. Otherwise, leave empty.",
    "phone": "Phone number from original resume, if found. Otherwise, leave empty.",
    "location": "Location (city, country) from original resume, if found. Otherwise, leave empty.",
    "github": "GitHub profile URL from original resume, if found. Otherwise, leave empty.",
    "linkedin": "LinkedIn profile URL from original resume, if found. Otherwise, leave empty.",
    "portfolio": "Portfolio or personal website URL from original resume, if found. Otherwise, leave empty."
  }},
  "summary": "Tailored professional summary (max 3 sentences)",
  "skills": ["Matched Skill 1", "Matched Skill 2", "Matched Skill 3", "Matched Skill 4"],
  "employment": [
    {{
      "company": "Company Name",
      "title": "Tailored Title (if applicable/truthful)",
      "duration": "Duration",
      "description": [
         "Tailored bullet point 1 emphasizing matching responsibilities and metrics",
         "Tailored bullet point 2 emphasizing matching responsibilities and metrics"
      ]
    }}
  ],
  "projects": [
    {{
      "title": "Project Title",
      "description": [
         "Tailored bullet point 1 highlighting tech stack and achievements relevant to the job",
         "Tailored bullet point 2 highlighting tech stack and achievements relevant to the job"
      ]
    }}
  ],
  "education": [
    {{
      "institution": "University/School Name from original resume",
      "degree": "Degree name (e.g. B.Tech in Computer Science) from original resume",
      "details": "Graduation year or GPA from original resume (e.g., 2020 - 2024)"
    }}
  ],
  "accomplishments": [
    "Certification, award, or honor 1 from original resume",
    "Certification, award, or honor 2 from original resume"
  ],
  "languages": [
    "Language 1",
    "Language 2"
  ]
}}

Return ONLY the raw JSON object. No explanations, no markdown formatting (like ```json), no extra text."""

    # 4. Invoke AWS Bedrock API
    try:
        url = f"https://bedrock-runtime.ap-south-1.amazonaws.com/model/{bedrock_extractor.model_id}/invoke"
        headers = {
            "Authorization": f"Bearer {bedrock_extractor.bedrock_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"maxTokens": 2048, "temperature": 0.3, "topP": 0.9}
        }
        
        async with httpx.AsyncClient(timeout=120.0, verify=False) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail=f"Bedrock service error: {response.text}")
                
            response_data = response.json()
            output_text = ""
            if "output" in response_data:
                output_text = response_data["output"].get("message", {}).get("content", [{}])[0].get("text", "")
            elif "content" in response_data:
                output_text = response_data["content"][0].get("text", "")

            # Clean markdown codeblocks
            output_text = output_text.strip()
            if output_text.startswith("```json"):
                output_text = output_text[7:]
            elif output_text.startswith("```"):
                output_text = output_text[3:]
            if output_text.endswith("```"):
                output_text = output_text[:-3]
            output_text = output_text.strip()

            tailored_json = json.loads(output_text)
            return {"status": "success", "tailored": tailored_json}
            
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to parse Bedrock response as JSON.")
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during resume tailoring: {str(e)}")
