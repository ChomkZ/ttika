"""
Automation Controller for TikTok Carousel Management
Handles background tasks and iOS device control
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from motor.motor_asyncio import AsyncIOMotorClient
import os
from ios_automation import TikTokAutomation, CarouselAutomation
from pathlib import Path
import json

logger = logging.getLogger(__name__)

class AutomationController:
    """Controls automation processes and carousel sessions"""
    
    def __init__(self, db_client):
        self.db = db_client
        self.tiktok_automation = None
        self.active_sessions = {}
        self.is_running = False
        
    async def initialize(self):
        """Initialize automation controller"""
        self.tiktok_automation = TikTokAutomation()
        logger.info("Automation controller initialized")
    
    async def start_automation_loop(self):
        """Start the main automation loop"""
        self.is_running = True
        logger.info("Starting automation loop")
        
        while self.is_running:
            try:
                await self.process_carousel_sessions()
                await asyncio.sleep(30)  # Check every 30 seconds
            except Exception as e:
                logger.error(f"Error in automation loop: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def stop_automation_loop(self):
        """Stop the automation loop"""
        self.is_running = False
        if self.tiktok_automation:
            await self.tiktok_automation.disconnect()
        logger.info("Automation loop stopped")
    
    async def process_carousel_sessions(self):
        """Process all active carousel sessions"""
        try:
            # Get all active sessions
            active_sessions = await self.db.carousel_sessions.find({
                "status": {"$in": ["uploading", "waiting", "deleting"]}
            }).to_list(100)
            
            for session in active_sessions:
                await self.process_single_session(session)
                
        except Exception as e:
            logger.error(f"Error processing carousel sessions: {e}")
    
    async def process_single_session(self, session_data: Dict):
        """Process a single carousel session based on its current status"""
        try:
            session_id = session_data["id"]
            current_status = session_data["status"]
            
            logger.info(f"Processing session {session_id} with status {current_status}")
            
            if current_status == "uploading":
                await self.handle_uploading_session(session_data)
            elif current_status == "waiting":
                await self.handle_waiting_session(session_data)
            elif current_status == "deleting":
                await self.handle_deleting_session(session_data)
                
        except Exception as e:
            logger.error(f"Error processing session {session_data['id']}: {e}")
            await self.update_session_status(session_data["id"], "paused", f"Error: {str(e)}")
    
    async def handle_uploading_session(self, session_data: Dict):
        """Handle session in uploading status"""
        session_id = session_data["id"]
        videos_uploaded = session_data["videos_uploaded"]
        target_uploads = session_data["target_uploads"]
        
        if videos_uploaded >= target_uploads:
            # All videos uploaded, start waiting period
            wait_until = datetime.utcnow() + timedelta(minutes=session_data["wait_duration_minutes"])
            
            await self.db.carousel_sessions.update_one(
                {"id": session_id},
                {
                    "$set": {
                        "status": "waiting",
                        "next_action_at": wait_until
                    },
                    "$push": {
                        "logs": f"Completed uploads, waiting until {wait_until}"
                    }
                }
            )
            logger.info(f"Session {session_id} moved to waiting status")
            return
        
        # Upload next video
        await self.upload_video_for_session(session_data)
    
    async def handle_waiting_session(self, session_data: Dict):
        """Handle session in waiting status"""
        session_id = session_data["id"]
        next_action_at = session_data.get("next_action_at")
        
        if not next_action_at:
            # No wait time set, move to deleting
            await self.update_session_status(session_id, "deleting", "Wait time completed")
            return
        
        # Convert string to datetime if needed
        if isinstance(next_action_at, str):
            next_action_at = datetime.fromisoformat(next_action_at.replace('Z', '+00:00'))
        
        if datetime.utcnow() >= next_action_at:
            # Wait time completed, start deleting
            await self.update_session_status(session_id, "deleting", "Wait time completed, starting deletion")
    
    async def handle_deleting_session(self, session_data: Dict):
        """Handle session in deleting status"""
        session_id = session_data["id"]
        
        # Delete videos
        success = await self.delete_videos_for_session(session_data)
        
        if success:
            # Check if should restart or complete
            auto_restart = session_data.get("auto_restart", True)
            total_cycles = session_data.get("total_cycles")
            current_cycle = session_data.get("current_cycle", 0)
            
            if auto_restart and (total_cycles is None or current_cycle < total_cycles):
                # Restart cycle
                await self.db.carousel_sessions.update_one(
                    {"id": session_id},
                    {
                        "$set": {
                            "status": "uploading",
                            "videos_uploaded": 0,
                            "current_cycle": current_cycle + 1,
                            "next_action_at": None
                        },
                        "$push": {
                            "logs": f"Starting cycle {current_cycle + 2}"
                        }
                    }
                )
                logger.info(f"Session {session_id} restarted for cycle {current_cycle + 2}")
            else:
                # Complete session
                await self.update_session_status(session_id, "completed", "All cycles completed")
        else:
            # Deletion failed, pause session
            await self.update_session_status(session_id, "paused", "Video deletion failed")
    
    async def upload_video_for_session(self, session_data: Dict):
        """Upload a video for the given session"""
        try:
            session_id = session_data["id"]
            account_id = session_data["account_id"]
            video_id = session_data["video_id"]
            
            # Get account and video info
            account = await self.db.accounts.find_one({"id": account_id})
            video = await self.db.videos.find_one({"id": video_id})
            
            if not account or not video:
                logger.error(f"Account or video not found for session {session_id}")
                return False
            
            # Generate hashtags for this upload
            hashtags = await self.generate_hashtags_for_upload()
            
            # Ensure device is connected
            if not self.tiktok_automation.is_connected:
                success = await self.tiktok_automation.connect_to_device()
                if not success:
                    logger.error("Failed to connect to iOS device")
                    return False
            
            # Switch to account if needed
            await self.tiktok_automation.switch_account(account["username"])
            
            # Upload video
            success = await self.tiktok_automation.upload_video(
                video_path=video["file_path"],
                description=video.get("description_template", ""),
                hashtags=hashtags
            )
            
            if success:
                # Update session
                await self.db.carousel_sessions.update_one(
                    {"id": session_id},
                    {
                        "$inc": {"videos_uploaded": 1},
                        "$push": {
                            "logs": f"Uploaded video {session_data['videos_uploaded'] + 1}/{session_data['target_uploads']}"
                        }
                    }
                )
                
                # Update account stats
                await self.db.accounts.update_one(
                    {"id": account_id},
                    {
                        "$inc": {
                            "videos_uploaded_today": 1,
                            "total_videos_uploaded": 1
                        }
                    }
                )
                
                # Update video stats
                await self.db.videos.update_one(
                    {"id": video_id},
                    {
                        "$inc": {"upload_count": 1},
                        "$set": {"last_used": datetime.utcnow()}
                    }
                )
                
                logger.info(f"Successfully uploaded video for session {session_id}")
                return True
            else:
                logger.error(f"Failed to upload video for session {session_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error uploading video for session {session_id}: {e}")
            return False
    
    async def delete_videos_for_session(self, session_data: Dict):
        """Delete videos for the given session"""
        try:
            session_id = session_data["id"]
            videos_to_delete = session_data["videos_uploaded"]
            
            if videos_to_delete == 0:
                return True
            
            # Ensure device is connected
            if not self.tiktok_automation.is_connected:
                success = await self.tiktok_automation.connect_to_device()
                if not success:
                    logger.error("Failed to connect to iOS device")
                    return False
            
            # Delete videos
            success = await self.tiktok_automation.delete_recent_videos(count=videos_to_delete)
            
            if success:
                await self.db.carousel_sessions.update_one(
                    {"id": session_id},
                    {
                        "$push": {
                            "logs": f"Deleted {videos_to_delete} videos"
                        }
                    }
                )
                logger.info(f"Successfully deleted {videos_to_delete} videos for session {session_id}")
                return True
            else:
                logger.error(f"Failed to delete videos for session {session_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting videos for session {session_id}: {e}")
            return False
    
    async def generate_hashtags_for_upload(self) -> list:
        """Generate hashtags for a single upload"""
        try:
            # Get a random template or create default
            templates = await self.db.hashtag_templates.find().to_list(10)
            
            if templates:
                # Use existing template
                template = templates[0]  # Use first template for simplicity
                
                # Generate variation
                from server import create_hashtag_variation
                hashtags = await create_hashtag_variation(
                    template["base_hashtags"],
                    template.get("generated_variations", [])
                )
            else:
                # Generate new hashtags
                from server import generate_hashtags_with_ai
                hashtags = await generate_hashtags_with_ai("dating", 20)
            
            return hashtags
            
        except Exception as e:
            logger.error(f"Error generating hashtags: {e}")
            # Return fallback hashtags
            return [
                "#dating", "#love", "#single", "#relationship", "#romance",
                "#flirt", "#crush", "#match", "#attraction", "#datenight"
            ]
    
    async def update_session_status(self, session_id: str, status: str, message: str = ""):
        """Update session status and add log entry"""
        try:
            update_data = {
                "status": status,
                "logs": f"{datetime.utcnow()}: {message}" if message else f"{datetime.utcnow()}: Status changed to {status}"
            }
            
            if status == "completed":
                update_data["completion_time"] = datetime.utcnow()
            
            await self.db.carousel_sessions.update_one(
                {"id": session_id},
                {
                    "$set": {"status": status},
                    "$push": {"logs": update_data["logs"]}
                }
            )
            
        except Exception as e:
            logger.error(f"Error updating session status: {e}")
    
    async def get_device_status(self) -> Dict:
        """Get current device connection status"""
        if not self.tiktok_automation:
            return {"connected": False, "error": "Automation not initialized"}
        
        try:
            device_info = await self.tiktok_automation.get_device_info()
            return {
                "connected": self.tiktok_automation.is_connected,
                "device_info": device_info
            }
        except Exception as e:
            return {"connected": False, "error": str(e)}
    
    async def connect_to_device(self, device_udid: str = None) -> Dict:
        """Connect to iOS device"""
        try:
            if not self.tiktok_automation:
                await self.initialize()
            
            success = await self.tiktok_automation.connect_to_device()
            
            if success:
                device_info = await self.tiktok_automation.get_device_info()
                return {
                    "success": True,
                    "message": "Connected successfully",
                    "device_info": device_info
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to connect to device"
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Connection error: {str(e)}"
            }
    
    async def disconnect_from_device(self) -> Dict:
        """Disconnect from iOS device"""
        try:
            if self.tiktok_automation:
                await self.tiktok_automation.disconnect()
            
            return {
                "success": True,
                "message": "Disconnected successfully"
            }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Disconnection error: {str(e)}"
            }
    
    async def manage_vpn(self, action: str) -> Dict:
        """Manage VPN connection"""
        try:
            if not self.tiktok_automation or not self.tiktok_automation.is_connected:
                return {
                    "success": False,
                    "message": "Device not connected"
                }
            
            success = await self.tiktok_automation.manage_ovpn_connection(action)
            
            return {
                "success": success,
                "message": f"VPN {action} {'successful' if success else 'failed'}"
            }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"VPN management error: {str(e)}"
            }
    
    async def take_screenshot(self) -> Dict:
        """Take screenshot of device"""
        try:
            if not self.tiktok_automation or not self.tiktok_automation.is_connected:
                return {
                    "success": False,
                    "message": "Device not connected"
                }
            
            screenshot_path = await self.tiktok_automation.take_screenshot()
            
            if screenshot_path:
                return {
                    "success": True,
                    "message": "Screenshot taken successfully",
                    "screenshot_path": screenshot_path
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to take screenshot"
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Screenshot error: {str(e)}"
            }


# Global automation controller instance
automation_controller = None

async def get_automation_controller():
    """Get or create automation controller instance"""
    global automation_controller
    
    if automation_controller is None:
        # Get database connection
        from server import db
        automation_controller = AutomationController(db)
        await automation_controller.initialize()
    
    return automation_controller

async def start_background_automation():
    """Start background automation processes"""
    controller = await get_automation_controller()
    await controller.start_automation_loop()

async def stop_background_automation():
    """Stop background automation processes"""
    global automation_controller
    if automation_controller:
        await automation_controller.stop_automation_loop()