from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timedelta
import json
import aiofiles
from enum import Enum
import asyncio
import requests

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Emergent LLM Key for hashtag generation
EMERGENT_LLM_KEY = "sk-emergent-5D6D5Fb306d7dD36b3"

# Create the main app without a prefix
app = FastAPI(title="TikTok Automation API")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Enums
class AccountStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BANNED = "banned"
    SUSPENDED = "suspended"

class VideoStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing" 
    PUBLISHED = "published"
    DELETED = "deleted"
    FAILED = "failed"

class CarouselStatus(str, Enum):
    IDLE = "idle"
    UPLOADING = "uploading"
    WAITING = "waiting"
    DELETING = "deleting"
    COMPLETED = "completed"
    PAUSED = "paused"

# Models
class TikTokAccount(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    display_name: str
    status: AccountStatus = AccountStatus.INACTIVE
    last_login: Optional[datetime] = None
    videos_uploaded_today: int = 0
    total_videos_uploaded: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None

class TikTokAccountCreate(BaseModel):
    username: str
    display_name: str
    notes: Optional[str] = None

class Video(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    original_name: str
    file_path: str
    file_size: int
    duration: Optional[float] = None
    description_template: Optional[str] = None
    hashtags: List[str] = []
    upload_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used: Optional[datetime] = None

class CarouselSession(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    account_id: str
    video_id: str
    status: CarouselStatus = CarouselStatus.IDLE
    videos_uploaded: int = 0
    target_uploads: int = 6
    wait_duration_minutes: int = 50  # 40-60 minutes
    start_time: Optional[datetime] = None
    completion_time: Optional[datetime] = None
    next_action_at: Optional[datetime] = None
    current_cycle: int = 0
    total_cycles: Optional[int] = None
    auto_restart: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    logs: List[str] = []

class HashtagTemplate(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    base_hashtags: List[str] = []
    generated_variations: List[List[str]] = []
    last_generated: Optional[datetime] = None
    usage_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)

# Create Models
class TikTokAccountResponse(TikTokAccount):
    pass

class VideoResponse(Video):
    pass

class CarouselSessionResponse(CarouselSession):
    account_username: Optional[str] = None
    video_filename: Optional[str] = None

class CarouselSessionCreate(BaseModel):
    account_id: str
    video_id: str
    target_uploads: int = 6
    wait_duration_minutes: int = 50
    total_cycles: Optional[int] = None
    auto_restart: bool = True

class HashtagGenerationRequest(BaseModel):
    theme: str = "dating"
    count: int = 20
    avoid_hashtags: List[str] = []

# Hashtag Generation Functions
async def generate_hashtags_with_ai(theme: str = "dating", count: int = 20) -> List[str]:
    """Generate hashtags using Emergent LLM"""
    try:
        prompt = f"""Generate {count} trending English hashtags for {theme} content on TikTok.
        
        Focus on:
        - Dating and romance themes
        - Popular English-speaking audience
        - Trending TikTok hashtags
        - Single lifestyle, relationships, love
        
        Requirements:
        - Only English hashtags
        - Include # symbol
        - No duplicates
        - Mix of popular and niche hashtags
        - Target dating/romance audience
        
        Return only hashtags separated by spaces, nothing else."""

        response = requests.post(
            "https://api.emergent.sh/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {EMERGENT_LLM_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.8
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            hashtags_text = result['choices'][0]['message']['content'].strip()
            hashtags = [tag.strip() for tag in hashtags_text.split() if tag.startswith('#')]
            return hashtags[:count]
        else:
            # Fallback hashtags if AI fails
            return get_fallback_hashtags()[:count]
    except Exception as e:
        logging.error(f"Failed to generate hashtags with AI: {e}")
        return get_fallback_hashtags()[:count]

def get_fallback_hashtags() -> List[str]:
    """Fallback hashtags for dating content"""
    return [
        "#dating", "#love", "#single", "#relationship", "#datenight", "#romance", "#flirt",
        "#crush", "#match", "#attraction", "#chemistry", "#lovequotes", "#heart",
        "#singlelife", "#lookingforlove", "#datinglife", "#romanticvibes", "#connection",
        "#soulmate", "#meetme", "#dateready", "#lovewins", "#relationshipgoals", "#datingtips",
        "#singles", "#meetup", "#loveisintheair", "#perfectmatch", "#datingapp", "#loveislove",
        "#romanticmood", "#datingadvice", "#lovethoughts", "#relationshipstatus", "#datingfun",
        "#lovelife", "#romanticdate", "#datingworld", "#lovematch", "#relationshipvibes"
    ]

async def create_hashtag_variation(base_hashtags: List[str], existing_variations: List[List[str]]) -> List[str]:
    """Create a new variation of hashtags avoiding duplicates with existing variations"""
    all_used = set()
    for variation in existing_variations:
        all_used.update(variation)
    
    # Generate fresh hashtags
    new_hashtags = await generate_hashtags_with_ai(count=30)
    fallback_hashtags = get_fallback_hashtags()
    
    all_available = list(set(new_hashtags + fallback_hashtags + base_hashtags))
    
    # Select hashtags not recently used
    selected = []
    for hashtag in all_available:
        if hashtag not in all_used and len(selected) < 20:
            selected.append(hashtag)
    
    # If we don't have enough, add from base_hashtags
    for hashtag in base_hashtags:
        if len(selected) < 20:
            selected.append(hashtag)
    
    return selected[:20]

# API Routes

# Accounts Management
@api_router.post("/accounts", response_model=TikTokAccountResponse)
async def create_account(account: TikTokAccountCreate):
    """Create a new TikTok account"""
    account_obj = TikTokAccount(**account.dict())
    await db.accounts.insert_one(account_obj.dict())
    return account_obj

@api_router.get("/accounts", response_model=List[TikTokAccountResponse])
async def get_accounts():
    """Get all TikTok accounts"""
    accounts = await db.accounts.find().to_list(1000)
    return [TikTokAccount(**account) for account in accounts]

@api_router.get("/accounts/{account_id}", response_model=TikTokAccountResponse)
async def get_account(account_id: str):
    """Get specific TikTok account"""
    account = await db.accounts.find_one({"id": account_id})
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return TikTokAccount(**account)

@api_router.put("/accounts/{account_id}/status")
async def update_account_status(account_id: str, status: AccountStatus):
    """Update account status"""
    result = await db.accounts.update_one(
        {"id": account_id}, 
        {"$set": {"status": status, "last_login": datetime.utcnow()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"message": "Status updated"}

# Video Management
@api_router.post("/videos/upload", response_model=VideoResponse)
async def upload_video(file: UploadFile = File(...), description_template: str = ""):
    """Upload a video file"""
    if not file.filename.lower().endswith(('.mp4', '.mov', '.avi')):
        raise HTTPException(status_code=400, detail="Invalid video format")
    
    # Create videos directory
    videos_dir = Path("/app/videos")
    videos_dir.mkdir(exist_ok=True)
    
    # Generate unique filename
    file_id = str(uuid.uuid4())
    file_extension = Path(file.filename).suffix
    filename = f"{file_id}{file_extension}"
    file_path = videos_dir / filename
    
    # Save file
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)
    
    # Create video object
    video_obj = Video(
        filename=filename,
        original_name=file.filename,
        file_path=str(file_path),
        file_size=len(content),
        description_template=description_template
    )
    
    await db.videos.insert_one(video_obj.dict())
    return video_obj

@api_router.get("/videos", response_model=List[VideoResponse])
async def get_videos():
    """Get all videos"""
    videos = await db.videos.find().to_list(1000)
    return [Video(**video) for video in videos]

@api_router.delete("/videos/{video_id}")
async def delete_video(video_id: str):
    """Delete a video"""
    video = await db.videos.find_one({"id": video_id})
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Delete file
    file_path = Path(video["file_path"])
    if file_path.exists():
        file_path.unlink()
    
    # Delete from database
    await db.videos.delete_one({"id": video_id})
    return {"message": "Video deleted"}

# Hashtag Management
@api_router.post("/hashtags/generate")
async def generate_hashtags(request: HashtagGenerationRequest):
    """Generate new hashtags for dating content"""
    hashtags = await generate_hashtags_with_ai(request.theme, request.count)
    
    # Filter out avoided hashtags
    if request.avoid_hashtags:
        hashtags = [tag for tag in hashtags if tag not in request.avoid_hashtags]
    
    return {"hashtags": hashtags, "count": len(hashtags)}

@api_router.post("/hashtag-templates", response_model=HashtagTemplate)
async def create_hashtag_template(name: str, base_hashtags: List[str]):
    """Create a hashtag template"""
    template = HashtagTemplate(
        name=name,
        base_hashtags=base_hashtags
    )
    await db.hashtag_templates.insert_one(template.dict())
    return template

@api_router.get("/hashtag-templates", response_model=List[HashtagTemplate])
async def get_hashtag_templates():
    """Get all hashtag templates"""
    templates = await db.hashtag_templates.find().to_list(1000)
    return [HashtagTemplate(**template) for template in templates]

@api_router.get("/hashtag-templates/{template_id}/variation")
async def get_hashtag_variation(template_id: str):
    """Get a new hashtag variation from template"""
    template = await db.hashtag_templates.find_one({"id": template_id})
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    template_obj = HashtagTemplate(**template)
    
    # Create new variation
    new_variation = await create_hashtag_variation(
        template_obj.base_hashtags, 
        template_obj.generated_variations
    )
    
    # Update template with new variation
    template_obj.generated_variations.append(new_variation)
    template_obj.usage_count += 1
    template_obj.last_generated = datetime.utcnow()
    
    await db.hashtag_templates.replace_one({"id": template_id}, template_obj.dict())
    
    return {"hashtags": new_variation, "description_with_hashtags": " ".join(new_variation)}

# Carousel Management
@api_router.post("/carousel-sessions", response_model=CarouselSessionResponse)
async def create_carousel_session(session: CarouselSessionCreate):
    """Create a new carousel session"""
    # Verify account and video exist
    account = await db.accounts.find_one({"id": session.account_id})
    video = await db.videos.find_one({"id": session.video_id})
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    carousel_obj = CarouselSession(**session.dict())
    carousel_obj.logs.append(f"Session created at {datetime.utcnow()}")
    
    await db.carousel_sessions.insert_one(carousel_obj.dict())
    return CarouselSessionResponse(**carousel_obj.dict(), 
                                   account_username=account["username"],
                                   video_filename=video["filename"])

@api_router.get("/carousel-sessions", response_model=List[CarouselSessionResponse])
async def get_carousel_sessions():
    """Get all carousel sessions"""
    sessions = await db.carousel_sessions.find().sort("created_at", -1).to_list(1000)
    
    # Enrich with account and video info
    enriched_sessions = []
    for session in sessions:
        account = await db.accounts.find_one({"id": session["account_id"]})
        video = await db.videos.find_one({"id": session["video_id"]})
        
        session_response = CarouselSessionResponse(
            **session,
            account_username=account["username"] if account else "Unknown",
            video_filename=video["filename"] if video else "Unknown"
        )
        enriched_sessions.append(session_response)
    
    return enriched_sessions

@api_router.put("/carousel-sessions/{session_id}/status")
async def update_carousel_status(session_id: str, status: CarouselStatus):
    """Update carousel session status"""
    update_data = {"status": status}
    
    if status == CarouselStatus.UPLOADING:
        update_data["start_time"] = datetime.utcnow()
    elif status == CarouselStatus.COMPLETED:
        update_data["completion_time"] = datetime.utcnow()
    
    result = await db.carousel_sessions.update_one(
        {"id": session_id}, 
        {"$set": update_data, "$push": {"logs": f"Status changed to {status} at {datetime.utcnow()}"}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Status updated"}

@api_router.get("/carousel-sessions/{session_id}/next-action")
async def get_next_carousel_action(session_id: str):
    """Get next action for carousel session"""
    session = await db.carousel_sessions.find_one({"id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_obj = CarouselSession(**session)
    now = datetime.utcnow()
    
    if session_obj.status == CarouselStatus.IDLE:
        return {"action": "start_uploading", "description": "Ready to start uploading videos"}
    elif session_obj.status == CarouselStatus.UPLOADING:
        if session_obj.videos_uploaded < session_obj.target_uploads:
            return {"action": "upload_video", "description": f"Upload video {session_obj.videos_uploaded + 1}/{session_obj.target_uploads}"}
        else:
            return {"action": "start_waiting", "description": "Start waiting period"}
    elif session_obj.status == CarouselStatus.WAITING:
        if session_obj.next_action_at and now >= session_obj.next_action_at:
            return {"action": "start_deleting", "description": "Ready to delete videos"}
        else:
            wait_time = session_obj.next_action_at - now if session_obj.next_action_at else timedelta(minutes=session_obj.wait_duration_minutes)
            return {"action": "wait", "description": f"Wait {wait_time} more"}
    elif session_obj.status == CarouselStatus.DELETING:
        return {"action": "delete_videos", "description": "Delete all uploaded videos"}
    elif session_obj.status == CarouselStatus.COMPLETED:
        if session_obj.auto_restart:
            return {"action": "restart_cycle", "description": "Start new cycle"}
        else:
            return {"action": "finished", "description": "Session completed"}
    
    return {"action": "unknown", "description": "Unknown status"}

# iOS Device Management
@api_router.post("/device/connect")
async def connect_device(device_udid: Optional[str] = None):
    """Connect to iOS device"""
    from automation_controller import get_automation_controller
    
    controller = await get_automation_controller()
    result = await controller.connect_to_device(device_udid)
    
    return result

@api_router.post("/device/disconnect")
async def disconnect_device():
    """Disconnect from iOS device"""
    from automation_controller import get_automation_controller
    
    controller = await get_automation_controller()
    result = await controller.disconnect_from_device()
    
    return result

@api_router.get("/device/status")
async def get_device_status():
    """Get device connection status"""
    from automation_controller import get_automation_controller
    
    controller = await get_automation_controller()
    result = await controller.get_device_status()
    
    return result

@api_router.post("/device/vpn/{action}")
async def manage_vpn(action: str):
    """Manage VPN connection (connect/disconnect)"""
    if action not in ["connect", "disconnect"]:
        raise HTTPException(status_code=400, detail="Invalid action. Use 'connect' or 'disconnect'")
    
    from automation_controller import get_automation_controller
    
    controller = await get_automation_controller()
    result = await controller.manage_vpn(action)
    
    return result

@api_router.post("/device/screenshot")
async def take_screenshot():
    """Take screenshot of device"""
    from automation_controller import get_automation_controller
    
    controller = await get_automation_controller()
    result = await controller.take_screenshot()
    
    return result

@api_router.post("/device/open-tiktok")
async def open_tiktok_app():
    """Open TikTok app on device"""
    from automation_controller import get_automation_controller
    
    controller = await get_automation_controller()
    
    if not controller.tiktok_automation or not controller.tiktok_automation.is_connected:
        return {"success": False, "message": "Device not connected"}
    
    try:
        success = await controller.tiktok_automation.open_tiktok_app()
        return {
            "success": success,
            "message": "TikTok app opened successfully" if success else "Failed to open TikTok app"
        }
    except Exception as e:
        return {"success": False, "message": f"Error opening TikTok: {str(e)}"}

# System Status
@api_router.get("/")
async def root():
    return {"message": "TikTok Automation API", "version": "1.0.0"}

@api_router.get("/status")
async def get_system_status():
    """Get system status"""
    accounts_count = await db.accounts.count_documents({})
    videos_count = await db.videos.count_documents({})
    active_sessions = await db.carousel_sessions.count_documents({"status": {"$in": ["uploading", "waiting", "deleting"]}})
    
    return {
        "accounts": accounts_count,
        "videos": videos_count,
        "active_carousel_sessions": active_sessions,
        "timestamp": datetime.utcnow()
    }

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()