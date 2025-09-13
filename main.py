#!/usr/bin/env python3
"""
SkillBoost API Key Automation Tool
Automated Google Cloud Skills Boost account creation and API key extraction

Based on analysis of skill.dll and skill_strings_ascii.txt
Refactored with enhanced error handling and stability improvements
"""

import os
import sys
import time
import random
import string
import threading
import logging
import re
import json
from datetime import datetime
from typing import Optional, Dict, Any, List

# GUI imports with fallback for headless operation
try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext, messagebox
    import customtkinter as ctk
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False
    print("GUI libraries not available. Running in CLI mode.")

# Core dependencies
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.common.exceptions import (
        TimeoutException, NoSuchElementException, WebDriverException,
        ElementClickInterceptedException, StaleElementReferenceException
    )
    from webdriver_manager.chrome import ChromeDriverManager
    import requests
    import pyperclip
except ImportError as e:
    print(f"Missing required dependency: {e}")
    print("Install dependencies with: pip install -r requirements.txt")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('automation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global variables (moved from local scope as per fixes)
def random_string(length: int = 8) -> str:
    """Generate a random string of specified length"""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

# Constants
FIREFOX_RELAY_URL = "https://relay.firefox.com/"
GOOGLE_CLOUD_SKILLS_BOOST_URL = "https://www.cloudskillsboost.google/"
EXTENSIONS_PATH = os.path.join(os.path.dirname(__file__), "Extensions")
BUSTER_EXTENSION_ID = "mpbjkejclgfgadiemmefgebjfooflfhl"
OUTPUT_FILE = "api.txt"

class AutomationError(Exception):
    """Custom exception for automation errors"""
    pass

class SkillBoostAutomation:
    """Main automation class for Google Cloud Skills Boost"""
    
    def __init__(self, headless: bool = False, log_callback=None):
        self.driver: Optional[webdriver.Chrome] = None
        self.headless = headless
        self.log_callback = log_callback
        self.running = False
        self.user_data = {}
        
    def log(self, message: str, level: str = "INFO"):
        """Log message with optional GUI callback"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] {level}: {message}"
        
        if level == "ERROR":
            logger.error(message)
        elif level == "WARNING":
            logger.warning(message)
        else:
            logger.info(message)
            
        if self.log_callback:
            self.log_callback(log_msg)
        
    def cleanup_chrome_processes(self):
        """Clean up Chrome processes to prevent conflicts"""
        try:
            if os.name == 'nt':  # Windows
                os.system('taskkill /f /im chrome.exe /t >nul 2>&1')
                os.system('taskkill /f /im chromedriver.exe /t >nul 2>&1')
            else:  # Linux/Mac
                os.system('pkill -f chrome >/dev/null 2>&1')
                os.system('pkill -f chromedriver >/dev/null 2>&1')
        except Exception as e:
            self.log(f"Error cleaning up processes: {e}", "WARNING")
    
    def create_chrome_driver(self) -> webdriver.Chrome:
        """Create and configure Chrome WebDriver with enhanced stability"""
        self.log("Setting up Chrome WebDriver...")
        
        # Clean up any existing processes
        self.cleanup_chrome_processes()
        time.sleep(2)
        
        options = Options()
        
        # Enhanced Chrome options for stability
        chrome_args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-extensions-except=" + os.path.join(EXTENSIONS_PATH, BUSTER_EXTENSION_ID),
            "--load-extension=" + os.path.join(EXTENSIONS_PATH, BUSTER_EXTENSION_ID),
            "--disable-blink-features=AutomationControlled",
            "--disable-web-security",
            "--disable-features=VizDisplayCompositor",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-infobars",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={os.path.join(os.getcwd(), 'chrome_profile_' + random_string())}",
        ]
        
        if self.headless:
            chrome_args.append("--headless")
        
        for arg in chrome_args:
            options.add_argument(arg)
        
        # Additional experimental options
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Retry logic for driver creation
        max_retries = 3
        for attempt in range(max_retries):
            try:
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=options)
                
                # Configure driver
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                driver.set_window_size(1920, 1080)
                
                self.log("Chrome WebDriver created successfully")
                return driver
                
            except Exception as e:
                self.log(f"Attempt {attempt + 1} failed: {e}", "WARNING")
                if attempt == max_retries - 1:
                    raise AutomationError(f"Failed to create Chrome driver after {max_retries} attempts: {e}")
                time.sleep(5)
    
    def open_signup_page(self) -> bool:
        """Open Google Cloud Skills Boost signup page"""
        try:
            self.log("Opening Google Cloud Skills Boost signup page...")
            self.driver.get(GOOGLE_CLOUD_SKILLS_BOOST_URL)
            
            # Wait for page to load and look for signup elements
            wait = WebDriverWait(self.driver, 30)
            
            # Try different selectors for signup/login
            signup_selectors = [
                "//a[contains(text(), 'Sign up')]",
                "//button[contains(text(), 'Sign up')]",
                "//a[contains(text(), 'Get started')]",
                "//button[contains(text(), 'Get started')]",
                ".signup-btn",
                ".get-started-btn"
            ]
            
            for selector in signup_selectors:
                try:
                    if selector.startswith("//"):
                        element = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    else:
                        element = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                    element.click()
                    self.log("Successfully clicked signup button")
                    return True
                except (TimeoutException, NoSuchElementException):
                    continue
            
            self.log("Could not find signup button, page might have loaded differently", "WARNING")
            return True  # Continue anyway, manual intervention might be needed
            
        except Exception as e:
            self.log(f"Error opening signup page: {e}", "ERROR")
            return False
    
    def generate_firefox_relay_email(self) -> Optional[str]:
        """Generate a new email using Firefox Relay with enhanced extraction"""
        try:
            self.log("Generating Firefox Relay email...")
            self.driver.get(FIREFOX_RELAY_URL)
            
            wait = WebDriverWait(self.driver, 30)
            
            # Wait for login or email generation interface
            time.sleep(5)
            
            # Try multiple selectors for email generation
            generate_selectors = [
                "//button[contains(text(), 'Generate new mask')]",
                "//button[contains(@class, 'generate')]",
                ".generate-button",
                ".btn-generate",
                "[data-testid='generate-new-alias']"
            ]
            
            for selector in generate_selectors:
                try:
                    if selector.startswith("//"):
                        generate_btn = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    else:
                        generate_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                    generate_btn.click()
                    break
                except (TimeoutException, NoSuchElementException):
                    continue
            else:
                self.log("Could not find email generation button", "WARNING")
                return None
            
            time.sleep(3)
            
            # Multiple fallback methods for email extraction
            email_selectors = [
                "button.MaskCard_copy-button__a7PXh samp",
                ".copy-button samp",
                ".email-address",
                ".alias-email",
                "[data-testid='alias-email']",
                ".mask-email"
            ]
            
            for selector in email_selectors:
                try:
                    email_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    email = email_element.text.strip()
                    if email and '@' in email:
                        self.log(f"Generated email: {email}")
                        return email
                except (TimeoutException, NoSuchElementException):
                    continue
            
            # Fallback: regex-based email extraction from page source
            page_source = self.driver.page_source
            email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
            emails = re.findall(email_pattern, page_source)
            
            for email in emails:
                if 'mozmail.com' in email or 'relay.firefox.com' in email:
                    self.log(f"Extracted email via regex: {email}")
                    return email
            
            # Final fallback: look for any element containing '@'
            elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), '@')]")
            for element in elements:
                text = element.text.strip()
                if '@' in text and '.' in text:
                    email_match = re.search(email_pattern, text)
                    if email_match:
                        email = email_match.group(0)
                        self.log(f"Found email in element: {email}")
                        return email
            
            self.log("Could not extract email address", "ERROR")
            return None
            
        except Exception as e:
            self.log(f"Error generating Firefox Relay email: {e}", "ERROR")
            return None
    
    def fill_signup_form(self, email: str) -> bool:
        """Fill the signup form with generated data"""
        try:
            self.log("Filling signup form...")
            
            # Generate user data
            first_name = random.choice(['John', 'Jane', 'Alex', 'Sam', 'Chris', 'Jordan'])
            last_name = random.choice(['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Davis'])
            company = random.choice(['TechCorp', 'InnovateCo', 'DataSoft', 'CloudTech', 'DevCorp'])
            password = f"SecurePass{random_string(4)}!"
            
            self.user_data = {
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'company': company,
                'password': password
            }
            
            wait = WebDriverWait(self.driver, 30)
            
            # Fill form fields
            form_fields = {
                'firstName': first_name,
                'first_name': first_name,
                'fname': first_name,
                'lastName': last_name,
                'last_name': last_name,
                'lname': last_name,
                'email': email,
                'emailAddress': email,
                'company': company,
                'organization': company,
                'password': password,
                'pwd': password,
                'confirmPassword': password,
                'confirm_password': password
            }
            
            for field_name, value in form_fields.items():
                try:
                    field = wait.until(EC.presence_of_element_located((By.NAME, field_name)))
                    field.clear()
                    field.send_keys(value)
                    self.log(f"Filled field: {field_name}")
                except (TimeoutException, NoSuchElementException):
                    # Try by ID
                    try:
                        field = self.driver.find_element(By.ID, field_name)
                        field.clear()
                        field.send_keys(value)
                        self.log(f"Filled field by ID: {field_name}")
                    except NoSuchElementException:
                        continue
            
            return True
            
        except Exception as e:
            self.log(f"Error filling signup form: {e}", "ERROR")
            return False
    
    def solve_captcha(self) -> bool:
        """Attempt to solve reCAPTCHA using Buster extension and fallback methods"""
        try:
            self.log("Attempting to solve reCAPTCHA...")
            
            wait = WebDriverWait(self.driver, 10)
            
            # Look for reCAPTCHA checkbox
            captcha_selectors = [
                ".recaptcha-checkbox-border",
                ".rc-anchor-checkbox",
                "iframe[src*='recaptcha']",
                "#recaptcha-checkbox"
            ]
            
            captcha_found = False
            for selector in captcha_selectors:
                try:
                    captcha_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    captcha_found = True
                    break
                except TimeoutException:
                    continue
            
            if not captcha_found:
                self.log("No reCAPTCHA found")
                return True
            
            # Click reCAPTCHA checkbox
            try:
                checkbox = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".recaptcha-checkbox-border")))
                checkbox.click()
                self.log("Clicked reCAPTCHA checkbox")
                time.sleep(3)
            except (TimeoutException, ElementClickInterceptedException):
                pass
            
            # Check if challenge appeared
            try:
                challenge = self.driver.find_element(By.CSS_SELECTOR, ".rc-imageselect-challenge")
                self.log("reCAPTCHA challenge detected, attempting to solve with Buster...")
                
                # Try to activate Buster extension
                buster_methods = [
                    "document.querySelector('.rc-button-audio').click();",
                    "document.querySelector('[aria-label=\"Get an audio challenge\"]').click();",
                    "window.postMessage({action: 'buster_solve'}, '*');"
                ]
                
                for method in buster_methods:
                    try:
                        self.driver.execute_script(method)
                        time.sleep(2)
                    except Exception:
                        continue
                
                # Wait for potential resolution
                time.sleep(10)
                
                # Check if still challenged
                try:
                    self.driver.find_element(By.CSS_SELECTOR, ".rc-imageselect-challenge")
                    self.log("reCAPTCHA still present, manual intervention may be required", "WARNING")
                    return False
                except NoSuchElementException:
                    self.log("reCAPTCHA solved successfully!")
                    return True
                    
            except NoSuchElementException:
                self.log("reCAPTCHA completed without challenge")
                return True
            
        except Exception as e:
            self.log(f"Error solving reCAPTCHA: {e}", "ERROR")
            return False
    
    def submit_form(self) -> bool:
        """Submit the registration form"""
        try:
            self.log("Submitting registration form...")
            
            wait = WebDriverWait(self.driver, 30)
            
            # Try different submit button selectors
            submit_selectors = [
                "//button[contains(text(), 'Sign up')]",
                "//button[contains(text(), 'Register')]",
                "//button[contains(text(), 'Create account')]",
                "//input[@type='submit']",
                ".submit-btn",
                ".signup-btn",
                "#submit-button"
            ]
            
            for selector in submit_selectors:
                try:
                    if selector.startswith("//"):
                        submit_btn = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    else:
                        submit_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                    submit_btn.click()
                    self.log("Clicked submit button")
                    time.sleep(5)
                    return True
                except (TimeoutException, NoSuchElementException, ElementClickInterceptedException):
                    continue
            
            # Fallback: press Enter on form
            try:
                form = self.driver.find_element(By.TAG_NAME, "form")
                form.send_keys(Keys.RETURN)
                self.log("Submitted form with Enter key")
                return True
            except NoSuchElementException:
                pass
            
            self.log("Could not find submit button", "ERROR")
            return False
            
        except Exception as e:
            self.log(f"Error submitting form: {e}", "ERROR")
            return False
    
    def extract_api_key(self) -> Optional[str]:
        """Extract API key from the account dashboard"""
        try:
            self.log("Attempting to extract API key...")
            
            wait = WebDriverWait(self.driver, 60)
            
            # Navigate to API/credentials section
            api_nav_selectors = [
                "//a[contains(text(), 'API')]",
                "//a[contains(text(), 'Credentials')]",
                "//a[contains(text(), 'Keys')]",
                ".api-link",
                ".credentials-link"
            ]
            
            for selector in api_nav_selectors:
                try:
                    if selector.startswith("//"):
                        api_link = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    else:
                        api_link = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                    api_link.click()
                    self.log("Navigated to API section")
                    break
                except (TimeoutException, NoSuchElementException):
                    continue
            
            time.sleep(5)
            
            # Look for API key on page
            api_key_patterns = [
                r'AIza[0-9A-Za-z-_]{35}',  # Google API key pattern
                r'[A-Za-z0-9-_]{32,}',    # Generic API key pattern
            ]
            
            page_source = self.driver.page_source
            for pattern in api_key_patterns:
                matches = re.findall(pattern, page_source)
                for match in matches:
                    if len(match) >= 32:  # Reasonable API key length
                        self.log(f"Found potential API key: {match[:10]}...")
                        return match
            
            # Look in specific elements
            api_key_selectors = [
                ".api-key",
                ".credential",
                "[data-testid='api-key']",
                ".token",
                "code"
            ]
            
            for selector in api_key_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        for pattern in api_key_patterns:
                            match = re.search(pattern, text)
                            if match:
                                api_key = match.group(0)
                                self.log(f"Extracted API key from element: {api_key[:10]}...")
                                return api_key
                except Exception:
                    continue
            
            self.log("Could not extract API key automatically", "WARNING")
            return None
            
        except Exception as e:
            self.log(f"Error extracting API key: {e}", "ERROR")
            return None
    
    def save_results(self, api_key: Optional[str] = None):
        """Save automation results to file"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
                f.write(f"\n[{timestamp}] Automation Results:\n")
                
                if self.user_data:
                    f.write(f"[{timestamp}] Username: {self.user_data.get('email', 'N/A')}\n")
                    f.write(f"[{timestamp}] Password: {self.user_data.get('password', 'N/A')}\n")
                    f.write(f"[{timestamp}] First Name: {self.user_data.get('first_name', 'N/A')}\n")
                    f.write(f"[{timestamp}] Last Name: {self.user_data.get('last_name', 'N/A')}\n")
                    f.write(f"[{timestamp}] Company: {self.user_data.get('company', 'N/A')}\n")
                
                if api_key:
                    f.write(f"[{timestamp}] API Key: {api_key}\n")
                else:
                    f.write(f"[{timestamp}] API Key: Not extracted\n")
                
                f.write(f"[{timestamp}] SSO URL: {self.driver.current_url}\n")
                f.write("-" * 50 + "\n")
            
            self.log(f"Results saved to {OUTPUT_FILE}")
            
        except Exception as e:
            self.log(f"Error saving results: {e}", "ERROR")
    
    def start_lab(self) -> bool:
        """Main automation workflow"""
        self.running = True
        success = False
        
        try:
            self.log("Starting SkillBoost automation...")
            
            # Step 1: Create Chrome driver
            self.driver = self.create_chrome_driver()
            
            # Step 2: Generate Firefox Relay email
            email = self.generate_firefox_relay_email()
            if not email:
                raise AutomationError("Failed to generate email")
            
            # Step 3: Open signup page
            if not self.open_signup_page():
                raise AutomationError("Failed to open signup page")
            
            # Step 4: Fill signup form
            if not self.fill_signup_form(email):
                raise AutomationError("Failed to fill signup form")
            
            # Step 5: Solve captcha
            if not self.solve_captcha():
                self.log("reCAPTCHA solving failed, continuing...", "WARNING")
            
            # Step 6: Submit form
            if not self.submit_form():
                raise AutomationError("Failed to submit form")
            
            # Step 7: Wait for account creation
            time.sleep(10)
            
            # Step 8: Extract API key
            api_key = self.extract_api_key()
            
            # Step 9: Save results
            self.save_results(api_key)
            
            self.log("Automation completed successfully!")
            success = True
            
        except AutomationError as e:
            self.log(f"Automation failed: {e}", "ERROR")
        except Exception as e:
            self.log(f"Unexpected error: {e}", "ERROR")
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass
            self.cleanup_chrome_processes()
            self.running = False
        
        return success

class SkillBoostGUI:
    """GUI interface for the automation tool"""
    
    def __init__(self):
        if not GUI_AVAILABLE:
            raise RuntimeError("GUI libraries not available")
        
        self.root = ctk.CTk()
        self.root.title("SkillBoost API Key Automation Tool")
        self.root.geometry("800x600")
        
        self.automation = None
        self.automation_thread = None
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the GUI interface"""
        # Main frame
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Title
        title_label = ctk.CTkLabel(
            main_frame, 
            text="SkillBoost API Key Automation Tool",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.pack(pady=10)
        
        # Control buttons frame
        button_frame = ctk.CTkFrame(main_frame)
        button_frame.pack(fill="x", padx=10, pady=5)
        
        # Start button
        self.start_btn = ctk.CTkButton(
            button_frame,
            text="Mulai Proses",
            command=self.start_automation,
            width=120
        )
        self.start_btn.pack(side="left", padx=5)
        
        # Stop button
        self.stop_btn = ctk.CTkButton(
            button_frame,
            text="Stop",
            command=self.stop_automation,
            width=120,
            state="disabled"
        )
        self.stop_btn.pack(side="left", padx=5)
        
        # Clear log button
        self.clear_btn = ctk.CTkButton(
            button_frame,
            text="Clear Log",
            command=self.clear_log,
            width=120
        )
        self.clear_btn.pack(side="left", padx=5)
        
        # Options frame
        options_frame = ctk.CTkFrame(main_frame)
        options_frame.pack(fill="x", padx=10, pady=5)
        
        # Headless mode checkbox
        self.headless_var = ctk.BooleanVar()
        self.headless_checkbox = ctk.CTkCheckBox(
            options_frame,
            text="Headless Mode",
            variable=self.headless_var
        )
        self.headless_checkbox.pack(side="left", padx=5)
        
        # Log output
        log_label = ctk.CTkLabel(main_frame, text="Log Output:")
        log_label.pack(anchor="w", padx=10, pady=(10, 0))
        
        self.log_text = ctk.CTkTextbox(main_frame)
        self.log_text.pack(fill="both", expand=True, padx=10, pady=5)
    
    def log_callback(self, message: str):
        """Callback function for logging to GUI"""
        self.root.after(0, self._update_log, message)
    
    def _update_log(self, message: str):
        """Update log text in GUI thread"""
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
    
    def clear_log(self):
        """Clear the log output"""
        self.log_text.delete("1.0", "end")
    
    def start_automation(self):
        """Start the automation process"""
        if self.automation and self.automation.running:
            messagebox.showwarning("Warning", "Proses sudah berjalan.")
            return
        
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        
        self.automation = SkillBoostAutomation(
            headless=self.headless_var.get(),
            log_callback=self.log_callback
        )
        
        self.automation_thread = threading.Thread(
            target=self.automation.start_lab,
            daemon=True
        )
        self.automation_thread.start()
        
        # Check completion
        self.root.after(1000, self.check_automation_status)
    
    def stop_automation(self):
        """Stop the automation process"""
        if self.automation:
            self.automation.running = False
            if self.automation.driver:
                try:
                    self.automation.driver.quit()
                except Exception:
                    pass
        
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.log_callback("Automation stopped by user")
    
    def check_automation_status(self):
        """Check if automation is still running"""
        if self.automation and not self.automation.running:
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
        else:
            self.root.after(1000, self.check_automation_status)
    
    def run(self):
        """Run the GUI application"""
        self.root.mainloop()

def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        
        if arg == "--cli":
            # CLI mode
            print("Starting SkillBoost Automation (CLI Mode)")
            automation = SkillBoostAutomation(headless=True)
            success = automation.start_lab()
            print(f"Automation {'succeeded' if success else 'failed'}")
            sys.exit(0 if success else 1)
            
        elif arg == "--test":
            # Test mode
            print("Running automation test...")
            automation = SkillBoostAutomation(headless=True)
            try:
                driver = automation.create_chrome_driver()
                print("✓ Chrome driver creation: SUCCESS")
                driver.quit()
                automation.cleanup_chrome_processes()
                print("✓ Driver cleanup: SUCCESS")
                print("All tests passed!")
            except Exception as e:
                print(f"✗ Test failed: {e}")
                sys.exit(1)
        
        elif arg in ["--help", "-h"]:
            print("""
SkillBoost API Key Automation Tool

Usage:
    python main.py              # Run with GUI (default)
    python main.py --cli         # Run in CLI mode
    python main.py --test        # Run tests
    python main.py --help        # Show this help

Features:
    - Automatic Firefox Relay email generation
    - Google Cloud Skills Boost account creation
    - reCAPTCHA solving with Buster extension
    - API key extraction and storage
    - Both GUI and CLI interfaces
            """)
            sys.exit(0)
    
    # Default: GUI mode
    if not GUI_AVAILABLE:
        print("GUI not available. Use --cli for command line mode.")
        sys.exit(1)
    
    try:
        app = SkillBoostGUI()
        app.run()
    except Exception as e:
        print(f"Failed to start GUI: {e}")
        print("Try running with --cli flag for command line mode")
        sys.exit(1)

if __name__ == "__main__":
    main()