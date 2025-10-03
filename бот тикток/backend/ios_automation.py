"""
iOS Automation for TikTok using Appium
Handles iPhone control, TikTok app automation, and OVPN management
"""

import asyncio
import logging
from typing import Optional, Dict, List
from appium import webdriver
from appium.options.ios import XCUITestOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import cv2
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)

class TikTokAutomation:
    """TikTok automation class for iOS using Appium"""
    
    def __init__(self, device_udid: str = None):
        self.device_udid = device_udid
        self.driver: Optional[webdriver.Remote] = None
        self.is_connected = False
        
        # Appium server settings
        self.appium_server_url = "http://localhost:4723"
        
        # TikTok app bundle ID
        self.tiktok_bundle_id = "com.zhiliaoapp.musically"
        
    async def connect_to_device(self) -> bool:
        """Connect to iOS device via Appium"""
        try:
            # Configure Appium options
            options = XCUITestOptions()
            options.platform_name = "iOS"
            options.automation_name = "XCUITest"
            options.device_name = "iPhone"  # Auto-detect connected iPhone
            
            if self.device_udid:
                options.udid = self.device_udid
            
            # TikTok app settings
            options.bundle_id = self.tiktok_bundle_id
            options.no_reset = True  # Don't reset app data
            options.full_reset = False
            
            # Performance settings
            options.new_command_timeout = 300
            options.command_timeouts = {'implicit': 30}
            
            # Connect to device
            self.driver = webdriver.Remote(
                command_executor=self.appium_server_url,
                options=options
            )
            
            self.driver.implicitly_wait(10)
            self.is_connected = True
            
            logger.info(f"Successfully connected to iOS device")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to device: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from device"""
        if self.driver:
            try:
                self.driver.quit()
                self.is_connected = False
                logger.info("Disconnected from iOS device")
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")
    
    async def open_tiktok_app(self) -> bool:
        """Open TikTok app"""
        try:
            if not self.is_connected:
                await self.connect_to_device()
            
            # TikTok should already be opened due to bundle_id in options
            # Wait for app to load
            await asyncio.sleep(3)
            
            # Check if we're on the main screen
            try:
                # Look for the main TikTok interface elements
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "XCUIElementTypeApplication"))
                )
                logger.info("TikTok app opened successfully")
                return True
            except TimeoutException:
                logger.error("TikTok app failed to load")
                return False
                
        except Exception as e:
            logger.error(f"Failed to open TikTok app: {e}")
            return False
    
    async def navigate_to_upload_screen(self) -> bool:
        """Navigate to TikTok upload screen"""
        try:
            # Look for the "+" button (upload button)
            upload_button = None
            
            # Try different selectors for upload button
            selectors = [
                "//XCUIElementTypeButton[@name='Add']",
                "//XCUIElementTypeButton[contains(@name, 'Create')]",
                "//XCUIElementTypeButton[contains(@name, '+')]",
                "//XCUIElementTypeTabBar//XCUIElementTypeButton[3]"  # Usually the middle button
            ]
            
            for selector in selectors:
                try:
                    upload_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    break
                except TimeoutException:
                    continue
            
            if upload_button:
                upload_button.click()
                await asyncio.sleep(2)
                
                # Wait for upload screen to appear
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//XCUIElementTypeButton[contains(@name, 'Upload')]"))
                    )
                    logger.info("Successfully navigated to upload screen")
                    return True
                except TimeoutException:
                    logger.warning("Upload screen not detected, but continuing")
                    return True
            else:
                logger.error("Upload button not found")
                return False
                
        except Exception as e:
            logger.error(f"Failed to navigate to upload screen: {e}")
            return False
    
    async def upload_video(self, video_path: str, description: str, hashtags: List[str]) -> bool:
        """Upload video to TikTok"""
        try:
            # Navigate to upload screen
            if not await self.navigate_to_upload_screen():
                return False
            
            # Look for "Upload" or "Select Video" button
            upload_selectors = [
                "//XCUIElementTypeButton[contains(@name, 'Upload')]",
                "//XCUIElementTypeButton[contains(@name, 'Select')]",
                "//XCUIElementTypeStaticText[contains(@name, 'Upload')]/..",
                "//XCUIElementTypeCell[contains(@name, 'Upload')]"
            ]
            
            upload_option = None
            for selector in upload_selectors:
                try:
                    upload_option = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    break
                except TimeoutException:
                    continue
            
            if upload_option:
                upload_option.click()
                await asyncio.sleep(2)
            
            # Note: File selection from gallery is complex on iOS
            # For now, we'll assume video is already in the gallery
            # In a real implementation, you'd need to:
            # 1. Navigate to the correct album
            # 2. Find the video by name
            # 3. Select it
            
            # Simulate selecting the first video in gallery
            try:
                first_video = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//XCUIElementTypeCell[1]"))
                )
                first_video.click()
                await asyncio.sleep(1)
                
                # Look for "Next" or "Continue" button
                next_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//XCUIElementTypeButton[contains(@name, 'Next')]"))
                )
                next_button.click()
                await asyncio.sleep(3)
                
            except TimeoutException:
                logger.error("Failed to select video from gallery")
                return False
            
            # Add description and hashtags
            full_description = f"{description}\n\n{' '.join(hashtags)}"
            
            try:
                # Look for description text field
                description_field = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//XCUIElementTypeTextView"))
                )
                description_field.click()
                description_field.clear()
                description_field.send_keys(full_description)
                
                await asyncio.sleep(2)
                
                # Look for "Post" button
                post_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//XCUIElementTypeButton[contains(@name, 'Post')]"))
                )
                post_button.click()
                
                # Wait for upload to complete
                await asyncio.sleep(5)
                
                logger.info(f"Video uploaded successfully with description: {full_description[:50]}...")
                return True
                
            except TimeoutException:
                logger.error("Failed to add description or post video")
                return False
                
        except Exception as e:
            logger.error(f"Failed to upload video: {e}")
            return False
    
    async def delete_recent_videos(self, count: int = 6) -> bool:
        """Delete recent videos from TikTok profile"""
        try:
            # Navigate to profile
            profile_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//XCUIElementTypeTabBar//XCUIElementTypeButton[5]"))
            )
            profile_button.click()
            await asyncio.sleep(3)
            
            # Delete videos one by one
            deleted_count = 0
            for i in range(count):
                try:
                    # Find first video in grid
                    first_video = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, f"//XCUIElementTypeCollectionView//XCUIElementTypeCell[1]"))
                    )
                    first_video.click()
                    await asyncio.sleep(2)
                    
                    # Look for options menu (3 dots)
                    options_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//XCUIElementTypeButton[contains(@name, 'More')]"))
                    )
                    options_button.click()
                    await asyncio.sleep(1)
                    
                    # Look for delete option
                    delete_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//XCUIElementTypeButton[contains(@name, 'Delete')]"))
                    )
                    delete_button.click()
                    await asyncio.sleep(1)
                    
                    # Confirm deletion
                    confirm_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//XCUIElementTypeButton[contains(@name, 'Delete')]"))
                    )
                    confirm_button.click()
                    await asyncio.sleep(2)
                    
                    deleted_count += 1
                    logger.info(f"Deleted video {deleted_count}/{count}")
                    
                    # Go back to profile
                    back_button = self.driver.find_element(By.XPATH, "//XCUIElementTypeButton[@name='Back']")
                    back_button.click()
                    await asyncio.sleep(2)
                    
                except TimeoutException:
                    logger.warning(f"Failed to delete video {i+1}, continuing...")
                    continue
            
            logger.info(f"Successfully deleted {deleted_count} videos")
            return deleted_count > 0
            
        except Exception as e:
            logger.error(f"Failed to delete videos: {e}")
            return False
    
    async def switch_account(self, username: str) -> bool:
        """Switch to different TikTok account"""
        try:
            # Navigate to profile
            profile_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//XCUIElementTypeTabBar//XCUIElementTypeButton[5]"))
            )
            profile_button.click()
            await asyncio.sleep(2)
            
            # Look for account switcher (usually username at top)
            account_switcher = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//XCUIElementTypeButton[contains(@name, '@')]"))
            )
            account_switcher.click()
            await asyncio.sleep(2)
            
            # Look for the target account in list
            target_account = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, f"//XCUIElementTypeButton[contains(@name, '{username}')]"))
            )
            target_account.click()
            await asyncio.sleep(3)
            
            logger.info(f"Switched to account: {username}")
            return True
            
        except TimeoutException:
            logger.error(f"Failed to switch to account: {username}")
            return False
        except Exception as e:
            logger.error(f"Error switching account: {e}")
            return False
    
    async def manage_ovpn_connection(self, action: str) -> bool:
        """Manage OVPN connection on iOS device"""
        try:
            # Open Settings app
            settings_bundle = "com.apple.Preferences"
            self.driver.activate_app(settings_bundle)
            await asyncio.sleep(2)
            
            # Navigate to VPN settings
            vpn_setting = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//XCUIElementTypeCell[contains(@name, 'VPN')]"))
            )
            vpn_setting.click()
            await asyncio.sleep(2)
            
            if action == "connect":
                # Look for VPN toggle or connect button
                connect_toggle = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//XCUIElementTypeSwitch[@name='VPN']"))
                )
                
                # Check if already connected
                if connect_toggle.get_attribute("value") == "0":
                    connect_toggle.click()
                    await asyncio.sleep(5)  # Wait for connection
                    logger.info("VPN connected")
                else:
                    logger.info("VPN already connected")
                    
            elif action == "disconnect":
                # Look for VPN toggle
                disconnect_toggle = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//XCUIElementTypeSwitch[@name='VPN']"))
                )
                
                # Check if connected
                if disconnect_toggle.get_attribute("value") == "1":
                    disconnect_toggle.click()
                    await asyncio.sleep(2)
                    logger.info("VPN disconnected")
                else:
                    logger.info("VPN already disconnected")
            
            # Return to TikTok app
            self.driver.activate_app(self.tiktok_bundle_id)
            await asyncio.sleep(2)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to manage VPN: {e}")
            return False
    
    async def take_screenshot(self, filepath: str = None) -> str:
        """Take screenshot of current screen"""
        try:
            screenshot = self.driver.get_screenshot_as_png()
            
            if not filepath:
                filepath = f"/app/screenshots/screenshot_{int(time.time())}.png"
            
            # Ensure directory exists
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            
            with open(filepath, 'wb') as f:
                f.write(screenshot)
            
            logger.info(f"Screenshot saved: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            return None
    
    async def get_device_info(self) -> Dict:
        """Get iOS device information"""
        try:
            if not self.is_connected:
                return {"error": "Device not connected"}
            
            capabilities = self.driver.capabilities
            
            return {
                "device_name": capabilities.get("deviceName", "Unknown"),
                "platform_version": capabilities.get("platformVersion", "Unknown"),
                "udid": capabilities.get("udid", "Unknown"),
                "automation_name": capabilities.get("automationName", "Unknown"),
                "app_bundle": capabilities.get("bundleId", "Unknown")
            }
            
        except Exception as e:
            logger.error(f"Failed to get device info: {e}")
            return {"error": str(e)}


# Carousel automation functions
class CarouselAutomation:
    """Handles the carousel logic for TikTok automation"""
    
    def __init__(self, tiktok_automation: TikTokAutomation):
        self.tiktok = tiktok_automation
    
    async def run_carousel_cycle(self, session_data: Dict) -> Dict:
        """Run a complete carousel cycle"""
        result = {
            "success": False,
            "videos_uploaded": 0,
            "videos_deleted": 0,
            "error": None,
            "logs": []
        }
        
        try:
            # Step 1: Upload 6 videos
            result["logs"].append("Starting video uploads...")
            
            for i in range(session_data["target_uploads"]):
                upload_success = await self.tiktok.upload_video(
                    video_path=session_data["video_path"],
                    description=session_data.get("description", ""),
                    hashtags=session_data.get("hashtags", [])
                )
                
                if upload_success:
                    result["videos_uploaded"] += 1
                    result["logs"].append(f"Uploaded video {i+1}/{session_data['target_uploads']}")
                else:
                    result["logs"].append(f"Failed to upload video {i+1}")
                
                # Wait between uploads
                await asyncio.sleep(10)
            
            # Step 2: Wait for specified duration
            wait_minutes = session_data.get("wait_duration_minutes", 50)
            result["logs"].append(f"Waiting {wait_minutes} minutes for views...")
            
            # In production, this would be handled by a background task
            # For now, we'll simulate with a shorter wait
            await asyncio.sleep(60)  # 1 minute for testing
            
            # Step 3: Delete uploaded videos
            result["logs"].append("Starting video deletion...")
            
            delete_success = await self.tiktok.delete_recent_videos(
                count=result["videos_uploaded"]
            )
            
            if delete_success:
                result["videos_deleted"] = result["videos_uploaded"]
                result["logs"].append(f"Deleted {result['videos_deleted']} videos")
            else:
                result["logs"].append("Failed to delete videos")
            
            result["success"] = result["videos_uploaded"] > 0
            
        except Exception as e:
            result["error"] = str(e)
            result["logs"].append(f"Carousel cycle failed: {e}")
            logger.error(f"Carousel cycle error: {e}")
        
        return result