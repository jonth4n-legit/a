import os
import json
import time
import platform
import subprocess
import threading
import random
import string
import shutil
import requests
import pyperclip
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# Selenium imports
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

# GUI imports
import tkinter
from tkinter import simpledialog
import customtkinter

# Constants
LAB_URL = "https://www.cloudskillsboost.google/course_templates/976/labs/550875"
SIGN_IN_URL = "https://www.cloudskillsboost.google/users/sign_in"
USER_DATA_DIR = os.path.join(os.environ.get('USERPROFILE', ''), 'selenium-profile')
USER_DATA_DIR2 = "C:/Users/hp_5c/selenium-profile/Default/Extensions"
COOKIES_FILE = "cookies.json"
GCLOUD_COMMAND = "gcloud auth log-access-token"

# Buster Extension Path - Updated to use relative path
BUSTER_EXTENSION_PATH = os.path.join(os.getcwd(), "Extensions", "mpbjkejclgfgadiemmefgebjfooflfhl", "3.1.0_0")

# Firefox Relay API token (dari tes.py)
RELAY_API_TOKEN = "30eabdbb-b923-4f08-ae45-d5bf7eee562e"
RELAY_BASE_URL = "https://relay.firefox.com/api/v1"

# Global variables
driver = None
running = False
restart_now = False
loop_thread = None
gui_root = None
log_text = None
model_dropdown = None
polling_delay_entry = None


class RelayManager:
    """Manager untuk Firefox Relay masks"""
    def __init__(self):
        self.api_token = RELAY_API_TOKEN
        self.base_url = RELAY_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Token {self.api_token}',
            'Content-Type': 'application/json'
        })
    
    def get_masks(self) -> List[Dict]:
        """Mendapatkan semua masks"""
        try:
            response = self.session.get(f"{self.base_url}/relayaddresses/")
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and 'results' in data:
                return data['results']
            return []
        except Exception as e:
            log_text_message(f"Error mendapatkan masks: {e}")
            return []
    
    def delete_all_masks(self) -> int:
        """Hapus semua masks yang ada"""
        masks = self.get_masks()
        deleted_count = 0
        
        log_text_message(f"🗑️ Menemukan {len(masks)} mask untuk dihapus...")
        
        for mask in masks:
            mask_id = mask.get('id')
            address = mask.get('full_address', mask.get('address', 'N/A'))
            
            try:
                response = self.session.delete(f"{self.base_url}/relayaddresses/{mask_id}/")
                if response.status_code == 204:
                    deleted_count += 1
                    log_text_message(f"✅ Berhasil hapus mask: {address}")
                else:
                    log_text_message(f"❌ Gagal hapus mask: {address} (status: {response.status_code})")
                time.sleep(0.5)  # Delay untuk menghindari rate limit
            except Exception as e:
                log_text_message(f"❌ Error menghapus mask {address}: {e}")
        
        log_text_message(f"🧹 Total {deleted_count} mask berhasil dihapus")
        return deleted_count
    
    def create_mask(self, description: str = "") -> Optional[Dict]:
        """Membuat mask baru"""
        if not description:
            description = f"Mask dibuat pada {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        data = {
            "description": description,
            "enabled": True,
            "domain": 2
        }
        
        try:
            response = self.session.post(f"{self.base_url}/relayaddresses/", json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            log_text_message(f"Error membuat mask: {e}")
            return None


def log_text_message(message):
    """Log a message to the GUI text widget"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    formatted_message = f"{timestamp} - {message}"
    
    print(formatted_message)  # Console output
    
    if log_text:
        log_text.configure(state="normal")
        log_text.insert("end", formatted_message + "\n")
        log_text.see("end")
        log_text.configure(state="disabled")
        if gui_root:
            gui_root.update_idletasks()


def get_hwid():
    """Get hardware ID of the system"""
    system_info = platform.uname()
    return f"{system_info.node}-{system_info.machine}"


def detect_and_solve_captcha():
    """Detect and auto-solve reCAPTCHA using Buster extension with enhanced auto-clicking"""
    try:
        log_text_message("🔍 Checking for reCAPTCHA...")
        
        # Check if reCAPTCHA exists on page
        recaptcha_elements = driver.find_elements(By.CSS_SELECTOR, 
            "iframe[src*='recaptcha'], .g-recaptcha, [data-sitekey]")
        
        if not recaptcha_elements:
            return True  # No captcha found
            
        log_text_message("🤖 reCAPTCHA detected! Attempting auto-solve with Buster...")
        
        # First try to click the checkbox
        try:
            # Find and switch to reCAPTCHA iframe
            recaptcha_frame = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 
                    "iframe[src*='recaptcha/api2/anchor']"))
            )
            driver.switch_to.frame(recaptcha_frame)
            
            # Click the checkbox
            checkbox = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.ID, "recaptcha-anchor"))
            )
            checkbox.click()
            driver.switch_to.default_content()
            log_text_message("✅ Clicked reCAPTCHA checkbox")
            
            # Wait a bit to see if we need to solve challenge
            time.sleep(3)
            
            # Check if we got the challenge
            challenge_frame = driver.find_elements(By.CSS_SELECTOR, 
                "iframe[src*='recaptcha/api2/bframe']")
            
            if challenge_frame and challenge_frame[0].is_displayed():
                log_text_message("🎯 Challenge detected, attempting to auto-click Buster extension...")
                
                # Switch to challenge iframe
                driver.switch_to.frame(challenge_frame[0])
                
                # Try multiple methods to click Buster extension icon
                buster_clicked = False
                
                # Method 1: Try to find and click Buster solver button inside challenge frame
                try:
                    buster_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, 
                            "button#solver-button"))
                    )
                    buster_button.click()
                    log_text_message("✅ Clicked Buster solver button (Method 1)")
                    buster_clicked = True
                except:
                    pass
                
                # Method 2: Try to click help button that might have Buster attached
                if not buster_clicked:
                    try:
                        help_button = driver.find_element(By.CSS_SELECTOR, "button.rc-button.help-button-holder")
                        if help_button:
                            help_button.click()
                            time.sleep(1)
                            # Look for Buster in shadow DOM
                            shadow_buster = driver.execute_script("""
                                var helpBtn = document.querySelector('button.rc-button.help-button-holder');
                                if (helpBtn && helpBtn.shadowRoot) {
                                    var busterBtn = helpBtn.shadowRoot.querySelector('#solver-button');
                                    if (busterBtn) {
                                        busterBtn.click();
                                        return true;
                                    }
                                }
                                return false;
                            """)
                            if shadow_buster:
                                log_text_message("✅ Clicked Buster solver button (Method 2 - Shadow DOM)")
                                buster_clicked = True
                    except:
                        pass
                
                # Method 3: Try to trigger Buster via extension messaging
                if not buster_clicked:
                    try:
                        # Try to trigger Buster extension directly
                        driver.execute_script("""
                            // Try to trigger Buster extension
                            if (window.chrome && window.chrome.runtime) {
                                try {
                                    // Dispatch custom event that Buster might listen for
                                    window.dispatchEvent(new CustomEvent('buster-solve-captcha'));
                                    
                                    // Try to call Buster function if available
                                    if (window.buster && typeof window.buster.solve === 'function') {
                                        window.buster.solve();
                                    }
                                    
                                    // Try common Buster patterns
                                    if (window.Buster && typeof window.Buster.solve === 'function') {
                                        window.Buster.solve();
                                    }
                                } catch (e) {
                                    console.log('Buster trigger attempt failed:', e);
                                }
                            }
                        """)
                        log_text_message("✅ Attempted to trigger Buster via extension API (Method 3)")
                        buster_clicked = True
                        time.sleep(2)  # Give Buster time to work
                    except:
                        pass
                
                # Method 4: Fallback - look for any audio challenge and try to solve manually
                if not buster_clicked:
                    try:
                        # Try to click audio challenge button as fallback
                        audio_btn = driver.find_element(By.ID, "recaptcha-audio-button")
                        if audio_btn:
                            audio_btn.click()
                            log_text_message("🔊 Clicked audio challenge as fallback")
                            time.sleep(2)
                    except:
                        pass
                
                driver.switch_to.default_content()
                
                # Wait for Buster to solve or manual intervention
                time.sleep(5)  # Give Buster time to work
                
                # Check if solved
                if wait_for_captcha_solved(timeout=30):
                    log_text_message("✅ Captcha solved successfully!")
                    return True
                else:
                    log_text_message("⚠️ Buster auto-solve incomplete, may need manual intervention")
                    # Don't return False immediately, let the user try manual solve
                    log_text_message(">>> Silakan selesaikan captcha <<<")
                    log_text_message("➡️  Selesaikan reCAPTCHA di browser. Script lanjut otomatis setelah verified…")
                    
                    # Wait longer for manual solve
                    if wait_for_captcha_solved(timeout=60):
                        log_text_message("✅ Captcha solved manually!")
                        return True
                    else:
                        return False
            else:
                # No challenge, we're good
                log_text_message("✅ No challenge required!")
                return True
                
        except Exception as e:
            driver.switch_to.default_content()
            log_text_message(f"⚠️ Error during auto-solve: {e}")
            return False
            
    except Exception as e:
        log_text_message(f"❌ Failed to detect/solve captcha: {e}")
        return False


def wait_for_captcha_solved(timeout=60):
    """Wait for captcha to be solved"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            # Check if captcha is solved
            token = driver.execute_script("""
                try {
                    if (window.grecaptcha && grecaptcha.getResponse) {
                        var response = grecaptcha.getResponse();
                        if (response && response.length > 0) return response;
                    }
                    var ta = document.getElementById('g-recaptcha-response');
                    if (ta && ta.value && ta.value.length > 0) return ta.value;
                    return "";
                } catch (e) { return ""; }
            """)
            
            if token and len(token) > 0:
                return True
                
            # Also check if checkbox is checked
            try:
                driver.switch_to.default_content()
                recaptcha_frame = driver.find_element(By.CSS_SELECTOR, 
                    "iframe[src*='recaptcha/api2/anchor']")
                driver.switch_to.frame(recaptcha_frame)
                
                anchor = driver.find_element(By.ID, "recaptcha-anchor")
                if anchor.get_attribute("aria-checked") == "true":
                    driver.switch_to.default_content()
                    return True
                    
                driver.switch_to.default_content()
            except:
                driver.switch_to.default_content()
                
        except:
            pass
            
        time.sleep(1)
        
    return False


def wait_until_recaptcha_verified_any(timeout=300):
    """Wait for reCAPTCHA to be verified with auto-solve using Buster"""
    start_time = time.time()
    last_expired_seen = 0
    auto_solve_attempted = False
    
    log_text_message("🔍 Checking for reCAPTCHA...")
    
    while time.time() - start_time < timeout:
        try:
            # Try auto-solve first if not attempted
            if not auto_solve_attempted:
                auto_solve_attempted = True
                if detect_and_solve_captcha():
                    return True
                    
            # Check for reCAPTCHA token (manual solve fallback)
            token = driver.execute_script("""
                try {
                    if (window.grecaptcha && grecaptcha.getResponse) {
                        var t = grecaptcha.getResponse();
                        if (t && t.length > 0) return t;
                        if (grecaptcha.getResponse.length > 0) {
                            var count = (grecaptcha.rendered || grecaptcha.renderedCount || 10);
                        }
                        try {
                            var ids = (grecaptcha && grecaptcha.___grecaptcha_cfg && grecaptcha.___grecaptcha_cfg.count) || 10;
                            for (var i = 0; i < ids; i++) {
                                try {
                                    var tr = grecaptcha.getResponse(i);
                                    if (tr && tr.length > 0) return tr;
                                } catch(e) {}
                            }
                        } catch(e) {}
                    }
                    var ta = document.getElementById('g-recaptcha-response');
                    if (ta && ta.value && ta.value.length > 0) return ta.value;
                    var ta2 = document.querySelector("textarea[name='g-recaptcha-response']");
                    if (ta2 && ta2.value && ta2.value.length > 0) return ta2.value;
                    return "";
                } catch (e) { return ""; }
            """)
            
            if token and len(token) > 0:
                log_text_message("✅ reCAPTCHA verified!")
                return True
                
            # Check for checkbox verification
            iframes = driver.find_elements(By.CSS_SELECTOR, "iframe[title^='reCAPTCHA'], iframe[src*='recaptcha']")
            for iframe in iframes:
                try:
                    driver.switch_to.frame(iframe)
                    anchors = driver.find_elements(By.CSS_SELECTOR, "#recaptcha-anchor[aria-checked='true']")
                    if anchors:
                        driver.switch_to.default_content()
                        log_text_message("✅ reCAPTCHA verified via checkbox.")
                        return True
                    driver.switch_to.default_content()
                except:
                    driver.switch_to.default_content()
                    
            # Check for expired message
            err_boxes = driver.find_elements(By.CSS_SELECTOR, ".rc-anchor-error-msg-container")
            for box in err_boxes:
                if "display: none" not in box.get_attribute("style"):
                    if time.time() - last_expired_seen > 10:
                        log_text_message("⚠️ reCAPTCHA verification expired. Retrying...")
                        last_expired_seen = time.time()
                        auto_solve_attempted = False  # Retry auto-solve
                        
        except:
            pass
            
        time.sleep(1)
        
    raise TimeoutError("reCAPTCHA belum terverifikasi dalam batas waktu.")


def solve_captcha_then_click_create(captcha_timeout=300, click_timeout=60):
    """End-to-end function: auto-solve reCAPTCHA and click Create account"""
    log_text_message("🤖 Auto-solving captcha...")
    
    # Wait for captcha to be solved
    wait_until_recaptcha_verified_any(timeout=captcha_timeout)
    
    # Wait for create button to be enabled
    WebDriverWait(driver, 10).until(
        lambda d: not any(el.get_attribute("style") == "display: none" 
                         for el in d.find_elements(By.XPATH, "//button[contains(., 'Create account')]"))
    )
    
    # Click create account
    click_create_account_when_ready(timeout=click_timeout)
    log_text_message("🟦 Klik 'Create account' terkirim.")


# [Keep all other functions unchanged - only modified the captcha-related functions above]

def open_chrome_with_profile():
    """Open Chrome with custom profile for login"""
    chrome_candidates = [
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"
    ]
    
    chrome_path = None
    for path in chrome_candidates:
        if os.path.exists(path):
            chrome_path = path
            break
    
    if not chrome_path:
        log_text_message("chrome.exe tidak ditemukan. Pastikan Chrome terinstal.")
        return None
    
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    
    cmd = [
        chrome_path,
        f"--user-data-dir={USER_DATA_DIR}",
        "--new-window",
        "--no-first-run",
        "--no-default-browser-check",
        LAB_URL
    ]
    
    subprocess.Popen(cmd)
    log_text_message("Chrome dibuka dengan profil custom.")


def login_to_cloud():
    """Login to Cloud Skills Boost using Selenium"""
    global driver
    
    options = Options()
    options.add_argument(f"--user-data-dir={USER_DATA_DIR}")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--ignore-certificate-errors")
    
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    
    driver.get(SIGN_IN_URL)
    log_text_message("Halaman login dimuat.")
    
    # Get login credentials
    email, password = get_login()
    if email and password:
        log_text_message("Melakukan login menggunakan Selenium setelah form login")
        # Login logic here
        
    save_cookies()
    time.sleep(2)
    driver.quit()
    log_text_message("Browser ditutup setelah login berhasil.")


def test_api_key_veo(api_key):
    """Test if VEO API key is valid"""
    model = model_dropdown.get() if model_dropdown else "veo-3.0-generate-preview"
    log_text_message(f"model: {model}")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:predictLongRunning?key={api_key}"
    
    payload = {
        "instances": [{
            "prompt": "test"
        }],
        "parameters": {
            "aspectRatio": "16:9",
            "sampleCount": 1
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return "ok"
        elif response.status_code == 429:
            return "limited"
        elif response.status_code in [401, 403]:
            return "unauthorized"
        else:
            return "unknown_error"
    except requests.exceptions.RequestException:
        return "unknown_error"


def end_lab():
    """End the current lab"""
    global driver
    
    if not driver:
        return
        
    log_text_message("Mencoba End Lab...")
    
    try:
        # Wait for lab control panel
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "ql-lab-control-panel"))
        )
        
        # JavaScript to find and click End Lab button
        end_lab_js = """
        const host = document.querySelector('ql-lab-control-button');
        if (!host) return {ok:false, reason:'no_host'};
        const root = host.shadowRoot || (host.attachShadow ? host.attachShadow({mode:'open'}) : null);
        if (!root) return {ok:false, reason:'no_shadow'};
        
        function findEndButton(container) {
            const candidates = container.querySelectorAll('button, ql-button, a, [role="menuitem"], [data-testid], [aria-label]');
            for (const el of candidates) {
                const text = (el.innerText || el.textContent || '').trim().toLowerCase();
                const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                if (
                    text.includes('end lab') || text === 'end' || text.includes('end') ||
                    aria.includes('end lab') || aria === 'end'
                ) {
                    return el;
                }
            }
            return null;
        }
        
        let endBtn = findEndButton(root);
        if (endBtn) {
            endBtn.click();
            return {ok:true, stage:'direct', needOpen:false};
        }
        
        // Cari tombol utama untuk membuka menu
        const mainTriggers = root.querySelectorAll('button, ql-button, [aria-haspopup="menu"], [aria-expanded]');
        let trigger = null;
        for (const t of mainTriggers) {
            const aria = (t.getAttribute('aria-label') || '').toLowerCase();
            const txt  = (t.innerText || t.textContent || '').toLowerCase();
            if (t.getAttribute('aria-haspopup') === 'menu' || aria.includes('lab') || txt.includes('lab')) {
                trigger = t; 
                break;
            }
        }
        
        if (!trigger && mainTriggers.length) trigger = mainTriggers[0];
        
        if (trigger) {
            trigger.click();
            return {ok:true, stage:'opened', needOpen:true};
        }
        
        return {ok:false, reason:'no_trigger'};
        """
        
        result = driver.execute_script(end_lab_js)
        
        if result.get('ok'):
            if result.get('needOpen'):
                time.sleep(1)
                # Try clicking End Lab in opened menu
                find_after_open_js = """
                const host = document.querySelector('ql-lab-control-button');
                if (!host) return null;
                const root = host.shadowRoot;
                if (!root) return null;
                
                function findEndButton(container) {
                    const candidates = container.querySelectorAll('button, ql-button, a, [role="menuitem"], [data-testid], [aria-label]');
                    for (const el of candidates) {
                        const text = (el.innerText || el.textContent || '').trim().toLowerCase();
                        const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                        if (
                            text.includes('end lab') || text === 'end' || text.includes('end') ||
                            aria.includes('end lab') || aria === 'end'
                        ) {
                            return el;
                        }
                    }
                    return null;
                }
                
                const btn = findEndButton(root);
                if (btn) { 
                    btn.scrollIntoView({block:'center'}); 
                    btn.click(); 
                    return true; 
                }
                return false;
                """
                
                clicked = driver.execute_script(find_after_open_js)
                if clicked:
                    log_text_message("Klik 'End Lab' dari menu.")
                else:
                    log_text_message("Tidak menemukan tombol 'End Lab' setelah menu dibuka.")
            else:
                log_text_message("Klik 'End Lab' langsung.")
                
            # Handle confirmation dialog
            force_click_endlab_confirm()
        else:
            log_text_message(f"Gagal menemukan host/trigger End Lab: {result.get('reason')}")
            
    except TimeoutException:
        log_text_message("Timeout: End Lab tidak muncul.")
    except Exception as e:
        log_text_message(f"Gagal End Lab: {e}")


def force_click_endlab_confirm():
    """Force click End Lab confirmation button"""
    try:
        # Wait for modal dialog
        WebDriverWait(driver, 5).until(
            lambda d: d.execute_script("""
                function hasDialog(root){
                    if (root.querySelector('[role="dialog"], md-dialog, div[aria-modal="true"]')) return true;
                    const all = root.querySelectorAll('*');
                    for (const el of all){ if (el.shadowRoot && hasDialog(el.shadowRoot)) return true; }
                    return false;
                }
                return hasDialog(document);
            """)
        )
        
        log_text_message("Paksa klik tombol 'End Lab' pada modal...")
        
        # Complex JavaScript to click End Lab confirmation
        click_result = driver.execute_script("""
            const LABEL = 'end lab';
            function isVisible(el){
                if (!el) return false;
                const rect = el.getBoundingClientRect();
                const style = getComputedStyle(el);
                return rect.width>1 && rect.height>1 &&
                       style.visibility!=='hidden' && style.display!=='none' &&
                       style.pointerEvents!=='none';
            }
            
            function deepFind(root){
                const hits=[];
                const stack=[root];
                while(stack.length){
                    const r=stack.pop();
                    const els=r.querySelectorAll('md-text-button, ql-button, button, [role="button"], [data-aria-label]');
                    for (const el of els){
                        const txt=(el.innerText||el.textContent||'').trim().toLowerCase();
                        const aria=(el.getAttribute('aria-label')||el.getAttribute('data-aria-label')||'').toLowerCase();
                        if ((txt && txt.includes(LABEL)) || (aria && aria.includes(LABEL))) hits.push(el);
                    }
                    r.querySelectorAll('*').forEach(n=>{ if (n.shadowRoot) stack.push(n.shadowRoot); });
                }
                return hits.filter(isVisible);
            }
            
            let candidates=deepFind(document);
            if (!candidates.length) return {ok:false, reason:'not_found'};
            
            let target=candidates[0];
            let clickable=target;
            if (target.shadowRoot){
                const inner=target.shadowRoot.querySelector('button,[role="button"]');
                if (inner) clickable=inner;
            }
            
            clickable.removeAttribute('disabled');
            clickable.setAttribute('aria-busy','false');
            clickable.scrollIntoView({block:'center', inline:'center'});
            
            function fire(el,t){ 
                el.dispatchEvent(new MouseEvent(t,{bubbles:true, composed:true, cancelable:true})); 
            }
            fire(clickable,'pointerdown'); 
            fire(clickable,'mousedown');
            fire(clickable,'pointerup');   
            fire(clickable,'mouseup'); 
            fire(clickable,'click');
            
            return {ok:true, tag:clickable.tagName};
        """)
        
        if click_result.get('ok'):
            log_text_message(f"Konfirmasi 'End Lab' ter-klik (node: {click_result.get('tag')})")
        else:
            log_text_message("Belum sukses via JS, coba fallback: TAB+ENTER.")
            actions = ActionChains(driver)
            for _ in range(5):
                actions.send_keys(Keys.TAB)
            actions.send_keys(Keys.ENTER)
            actions.perform()
            
    except TimeoutException:
        log_text_message("Modal konfirmasi belum muncul.")
    except Exception as e:
        log_text_message(f"Fallback TAB+ENTER gagal: {e}")


def get_login():
    """Get login credentials via GUI dialog"""
    email = simpledialog.askstring("Login", "Masukkan Email:")
    password = simpledialog.askstring("Login", "Masukkan Password:", show='*')
    log_text_message("Membuat form login menggunakan Tkinter")
    return email, password


def save_cookies():
    """Save cookies to JSON file"""
    with open(COOKIES_FILE, 'w') as f:
        json.dump(driver.get_cookies(), f)
    log_text_message("Menyimpan cookies ke file JSON")


def load_cookies():
    """Load cookies from JSON file"""
    try:
        with open(COOKIES_FILE, 'r') as f:
            cookies = json.load(f)
            for cookie in cookies:
                driver.add_cookie(cookie)
        log_text_message("Cookies berhasil dimuat.")
        return True
    except:
        log_text_message("Gagal memuat cookies")
        return False


def click_cloud_shell_continue():
    """Click Continue button in Cloud Shell"""
    try:
        log_text_message("Mencoba klik tombol 'Continue' di Cloud Shell...")
        continue_button = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.XPATH, "//button[.//span[contains(text(), 'Continue')]]"))
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", continue_button)
        continue_button.click()
        log_text_message("Tombol 'Continue' Cloud Shell berhasil diklik.")
    except TimeoutException:
        log_text_message("Timeout: Tombol 'Continue' Cloud Shell tidak muncul.")
    except Exception as e:
        log_text_message(f"Gagal klik 'Continue' Cloud Shell: {e}")


def click_with_selenium():
    """Click Start Lab button using Selenium"""
    try:
        WebDriverWait(driver, 60).until(
            lambda d: d.execute_script("""
                const host = document.querySelector('ql-lab-control-panel');
                if (!host) return false;
                const root = host.shadowRoot;
                if (!root) return false;
                const buttonContainer = root.querySelector('ql-lab-control-button');
                if (!buttonContainer) return false;
                const buttonRoot = buttonContainer.shadowRoot;
                if (!buttonRoot) return false;
                const buttonElement = buttonRoot.querySelector('ql-button');
                if (!buttonElement) return false;
                const buttonShadow = buttonElement.shadowRoot;
                if (!buttonShadow) return false;
                const mdButton = buttonShadow.querySelector('md-filled-button');
                if (!mdButton) return false;
                const finalButton = mdButton.shadowRoot.querySelector('button');
                return finalButton !== null;
            """)
        )
        
        driver.execute_script("""
            const host = document.querySelector('ql-lab-control-panel');
            const root = host.shadowRoot;
            const buttonContainer = root.querySelector('ql-lab-control-button');
            const buttonRoot = buttonContainer.shadowRoot;
            const buttonElement = buttonRoot.querySelector('ql-button');
            const buttonShadow = buttonElement.shadowRoot;
            const mdButton = buttonShadow.querySelector('md-filled-button');
            const finalButton = mdButton.shadowRoot.querySelector('button');
            finalButton.click();
        """)
        
        return True
    except TimeoutException:
        log_text_message("Timeout: Tombol 'Start Lab' tidak muncul setelah menunggu.")
        return False
    except Exception as e:
        log_text_message(f"Gagal mengklik tombol: {e}")
        return False


def logout_from_cloudskillsboost():
    """Logout from Cloud Skills Boost"""
    try:
        driver.get("https://www.cloudskillsboost.google/")
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("""
                function deepFindLogout(root){
                    const stack=[root];
                    while(stack.length){
                        const r=stack.pop();
                        const btns=r.querySelectorAll('ql-button, md-text-button, button, [aria-label]');
                        for(const el of btns){
                            const aria=(el.getAttribute('aria-label')||'').toLowerCase();
                            const txt=(el.innerText||el.textContent||'').toLowerCase();
                            if(aria.includes('sign out') || txt.includes('sign out')) return el;
                        }
                        r.querySelectorAll('*').forEach(x=>{ if(x.shadowRoot) stack.push(x.shadowRoot); });
                    }
                    return null;
                }
                return !!deepFindLogout(document);
            """)
        )
        
        driver.execute_script("""
            function deepFindLogout(root){
                const stack=[root];
                while(stack.length){
                    const r=stack.pop();
                    const btns=r.querySelectorAll('ql-button, md-text-button, button, [aria-label]');
                    for(const el of btns){
                        const aria=(el.getAttribute('aria-label')||'').toLowerCase();
                        const txt=(el.innerText||el.textContent||'').toLowerCase();
                        if(aria.includes('sign out') || txt.includes('sign out')) return el;
                    }
                    r.querySelectorAll('*').forEach(x=>{ if(x.shadowRoot) stack.push(x.shadowRoot); });
                }
                return null;
            }
            let btn=deepFindLogout(document);
            if(btn){
                if(btn.shadowRoot){
                    let inner=btn.shadowRoot.querySelector('button,[role="button"]');
                    if(inner) btn=inner;
                }
                btn.click();
            }
        """)
        
        log_text_message("Logout berhasil")
    except Exception as e:
        log_text_message(f"Gagal logout: {e}")


def open_signup_page():
    """Open signup page"""
    max_retries = 5
    for attempt in range(max_retries):
        try:
            driver.get("https://www.cloudskillsboost.google/users/sign_up")
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "user_first_name"))
            )
            log_text_message("✅ Berhasil masuk ke halaman sign up")
            return True
        except:
            log_text_message(f"⚠️ Gagal masuk ke halaman sign up, percobaan {attempt + 1}/{max_retries}")
            logout_from_cloudskillsboost()
            time.sleep(2)
    return False


def click_create_account_when_ready(timeout=60):
    """Wait for Create Account button to be clickable and click it"""
    create_button = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, 
            "//button[normalize-space()='Create account' or .//span[normalize-space()='Create account']]"))
    )
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", create_button)
    create_button.click()


def process_api_key(driver_incognito):
    """Process API key creation/retrieval with passed driver"""
    try:
        driver_incognito.get("https://console.cloud.google.com/apis/credentials")
        time.sleep(5)
        
        # Check if API key already exists
        try:
            api_key_element = WebDriverWait(driver_incognito, 10).until(
                EC.presence_of_element_located((By.XPATH, "//mat-pseudo-checkbox[@aria-label='API key 1']"))
            )
            log_text_message("✅ API key 1 ditemukan.")
            
            # Get the API key value - click on the API key link first
            api_key_link = WebDriverWait(driver_incognito, 10).until(
                EC.element_to_be_clickable((By.LINK_TEXT, "API key 1"))
            )
            detail_url = api_key_link.get_attribute("href")
            driver_incognito.get(detail_url)
            time.sleep(5)
            
            # Click show key button
            show_key_button = WebDriverWait(driver_incognito, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[track-name='showApiKeyString']"))
            )
            show_key_button.click()
            time.sleep(2)
            
            # Get API key value
            api_key_input = driver_incognito.find_element(By.ID, "_0rif_mat-input-1")
            api_key = api_key_input.get_attribute("value")
            log_text_message(f"✅ API Key ditemukan: {api_key}")
            return api_key
            
        except:
            log_text_message("❌ API key belum ada, membuat baru...")
            
            # Close any popup
            try:
                close_popup = driver_incognito.find_element(By.CSS_SELECTOR, "button.cfc-callout-close-button")
                close_popup.click()
                log_text_message("✅ Popup callout berhasil ditutup.")
            except:
                log_text_message("ℹ️ Tidak ada popup callout yang muncul.")
                
            # Create new API key
            create_btn = WebDriverWait(driver_incognito, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[.//span[contains(text(), 'Create credentials')]]"))
            )
            create_btn.click()
            
            api_key_option = WebDriverWait(driver_incognito, 10).until(
                EC.element_to_be_clickable((By.XPATH, 
                    "//div[contains(@class,'cfc-menu-item-label') and normalize-space()='API key']"))
            )
            api_key_option.click()
            
            # Click Create in modal
            try:
                create_modal_btn = WebDriverWait(driver_incognito, 10).until(
                    EC.element_to_be_clickable((By.XPATH,
                        "//button[@type='submit' and contains(@class,'mat-mdc-unelevated-button')]"))
                )
                create_modal_btn.click()
                log_text_message("✅ Klik tombol Create di modal 'Create API key'.")
            except:
                log_text_message("ℹ️ Modal 'Create API key' tidak muncul, lanjut ke step berikutnya.")
                
            # Close success popup
            try:
                close_button = WebDriverWait(driver_incognito, 30).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[.//span[contains(text(), 'Close')]]"))
                )
                close_button.click()
                log_text_message("✅ Popup 'API Key Created' berhasil ditutup.")
            except:
                log_text_message("❌ Gagal menutup popup 'API Key Created'. Restart step.")
                return None
                
            # Navigate to the newly created API key
            time.sleep(3)
            api_key_link = WebDriverWait(driver_incognito, 10).until(
                EC.element_to_be_clickable((By.LINK_TEXT, "API key 1"))
            )
            detail_url = api_key_link.get_attribute("href")
            driver_incognito.get(detail_url)
            time.sleep(5)
            
            # Click show key button
            show_key_button = WebDriverWait(driver_incognito, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[track-name='showApiKeyString']"))
            )
            show_key_button.click()
            time.sleep(2)
            
            # Get API key value
            api_key_input = driver_incognito.find_element(By.ID, "_0rif_mat-input-1")
            api_key = api_key_input.get_attribute("value")
            log_text_message(f"✅ API Key berhasil dibuat: {api_key}")
            return api_key
                
    except Exception as e:
        log_text_message(f"Error processing API key: {e}")
        return None


def open_in_incognito(url):
    """Open URL in incognito mode WITHOUT user profile to avoid conflicts"""
    incognito_options = Options()
    # Don't use --user-data-dir for incognito to avoid conflicts
    incognito_options.add_argument("--incognito")
    incognito_options.add_argument("--disable-dev-shm-usage")
    incognito_options.add_argument("--no-sandbox")
    incognito_options.add_argument("--disable-gpu")
    incognito_options.add_argument("--ignore-certificate-errors")
    incognito_options.add_argument("--disable-blink-features=AutomationControlled")
    incognito_options.add_argument("--disable-web-security")
    incognito_options.add_argument("--allow-running-insecure-content")
    incognito_options.add_argument("--disable-features=VizDisplayCompositor")
    incognito_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    incognito_options.add_experimental_option('useAutomationExtension', False)
    incognito_options.add_experimental_option("detach", True)
    
    incognito_driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=incognito_options
    )
    incognito_driver.get(url)
    return incognito_driver


def wait_until_open_console(timeout=120):
    """Wait for Open Google Console button to appear"""
    return WebDriverWait(driver, timeout, poll_frequency=2).until(
        lambda d: d.execute_script("""
            const host=document.querySelector("ql-lab-control-panel");
            if(!host) return false;
            const root=host.shadowRoot; if(!root) return false;
            const button=root.querySelector("ql-button.open-console-button");
            return !!(button && button.getAttribute("href"));
        """)
    )


def get_open_console_url():
    """Get the URL from Open Google Console button"""
    try:
        host = driver.find_element(By.CSS_SELECTOR, "ql-lab-control-panel")
        root = driver.execute_script("return arguments[0].shadowRoot", host)
        button = root.find_element(By.CSS_SELECTOR, "ql-button.open-console-button")
        return button.get_attribute("href")
    except:
        return None


def get_lab_credentials() -> Tuple[str, str, str]:
    """Extract lab credentials (username, password, project_id) from the page"""
    try:
        # Wait for credentials to load
        WebDriverWait(driver, 30).until(
            lambda d: d.execute_script("""
                const panel = document.querySelector('ql-lab-control-panel');
                if (!panel) return false;
                return panel.textContent.includes('Username:') || panel.textContent.includes('Password:');
            """)
        )
        
        # JavaScript to extract credentials from the shadow DOM
        credentials = driver.execute_script("""
            const panel = document.querySelector('ql-lab-control-panel');
            if (!panel) return {};
            
            // Get text content from shadow DOM
            const shadowRoot = panel.shadowRoot;
            if (!shadowRoot) return {};
            
            const textContent = shadowRoot.textContent || '';
            const results = {};
            
            // Extract Username
            const userMatch = textContent.match(/Username[:\\s]+([\\w\\-\\.]+@[\\w\\-\\.]+)/i);
            if (userMatch) results.username = userMatch[1];
            
            // Extract Password  
            const passMatch = textContent.match(/Password[:\\s]+([\\w\\d]+)/);
            if (passMatch) results.password = passMatch[1];
            
            // Extract Project ID
            const projMatch = textContent.match(/Project\\s*ID[:\\s]+([\\w\\-]+)/i);
            if (projMatch) results.project_id = projMatch[1];
            
            // Alternative: Check copy buttons
            const copyButtons = shadowRoot.querySelectorAll('ql-copy-code-button');
            copyButtons.forEach(btn => {
                const label = btn.previousElementSibling?.textContent || '';
                const value = btn.textContent || '';
                
                if (label.includes('Username') && !results.username) {
                    results.username = value.trim();
                } else if (label.includes('Password') && !results.password) {
                    results.password = value.trim();
                } else if (label.includes('Project ID') && !results.project_id) {
                    results.project_id = value.trim();
                }
            });
            
            return results;
        """)
        
        username = credentials.get('username', '')
        password = credentials.get('password', '')
        project_id = credentials.get('project_id', '')
        
        if username and password and project_id:
            log_text_message(f"📋 Credentials extracted:")
            log_text_message(f"   Username: {username}")
            log_text_message(f"   Password: {password}")
            log_text_message(f"   Project ID: {project_id}")
            return username, password, project_id
        else:
            log_text_message("⚠️ Tidak semua credentials ditemukan")
            return username, password, project_id
            
    except Exception as e:
        log_text_message(f"❌ Error extracting credentials: {e}")
        return "", "", ""


def handle_google_login(driver_incognito, username, password):
    """Handle Google login if redirected"""
    try:
        if "accounts.google.com" in driver_incognito.current_url:
            log_text_message("📝 Terdeteksi halaman login Google, melakukan login otomatis...")
            
            # Enter email
            email_input = WebDriverWait(driver_incognito, 10).until(
                EC.presence_of_element_located((By.ID, "identifierId"))
            )
            email_input.clear()
            email_input.send_keys(username)
            
            # Click Next
            next_button = driver_incognito.find_element(By.ID, "identifierNext")
            next_button.click()
            
            time.sleep(2)
            
            # Enter password
            password_input = WebDriverWait(driver_incognito, 10).until(
                EC.presence_of_element_located((By.NAME, "password"))
            )
            password_input.clear()
            password_input.send_keys(password)
            
            # Click Next
            password_next = driver_incognito.find_element(By.ID, "passwordNext")
            password_next.click()
            
            log_text_message("✅ Login Google berhasil")
            time.sleep(5)
            
            return True
    except Exception as e:
        log_text_message(f"❌ Gagal login Google otomatis: {e}")
        return False


def check_firefox_relay_login(driver, max_retries=3):
    """Check if Firefox Relay is logged in with multiple verification methods"""
    for retry in range(max_retries):
        try:
            log_text_message(f"🔍 Memeriksa login Firefox Relay (percobaan {retry + 1}/{max_retries})...")
            
            # Navigate to Firefox Relay
            driver.get("https://relay.firefox.com/accounts/profile/")
            time.sleep(5)
            
            # Method 1: Look for Generate new mask button
            try:
                WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Generate new mask')]"))
                )
                log_text_message("✅ Firefox Relay terdeteksi sudah login (Generate button found)")
                return True
            except TimeoutException:
                pass
            
            # Method 2: Check for profile elements or dashboard
            try:
                profile_elements = [
                    "//div[contains(@class, 'profile')]",
                    "//div[contains(@class, 'dashboard')]", 
                    "//button[contains(@class, 'generate')]",
                    "//div[contains(@class, 'alias')]"
                ]
                
                for element_xpath in profile_elements:
                    try:
                        WebDriverWait(driver, 3).until(
                            EC.presence_of_element_located((By.XPATH, element_xpath))
                        )
                        log_text_message("✅ Firefox Relay terdeteksi sudah login (profile element found)")
                        return True
                    except TimeoutException:
                        continue
            except Exception:
                pass
            
            # Method 3: Check current URL for redirect patterns
            current_url = driver.current_url.lower()
            if "profile" in current_url or "dashboard" in current_url:
                log_text_message("✅ Firefox Relay terdeteksi sudah login (URL indicates logged in)")
                return True
            
            # Method 4: Check if we're redirected to login page
            if "accounts.firefox.com" in current_url or "login" in current_url:
                log_text_message("❌ Firefox Relay belum login (redirected to login page)")
                return False
            
            # If none of the above worked, try refreshing and retrying
            if retry < max_retries - 1:
                log_text_message("🔄 Status tidak jelas, refresh dan coba lagi...")
                driver.refresh()
                time.sleep(3)
                continue
            
            log_text_message("⚠️ Status login Firefox Relay tidak dapat dipastikan")
            return False
            
        except Exception as e:
            log_text_message(f"❌ Error checking Firefox Relay login (percobaan {retry + 1}): {e}")
            if retry < max_retries - 1:
                time.sleep(2)
                continue
            return False
    
    return False


def create_chrome_driver(use_existing_profile=True, max_retries=3):
    """Create Chrome driver with proper error handling and session reuse"""
    for retry in range(max_retries):
        try:
            options = Options()
            
            # Use existing profile by default, fallback to unique if needed
            if use_existing_profile and os.path.exists(USER_DATA_DIR):
                user_data_dir = USER_DATA_DIR
                log_text_message(f"🔄 Menggunakan profil yang sudah ada: {user_data_dir}")
            else:
                # Fallback to unique profile only if existing profile fails or doesn't exist
                def random_string(length=8):
                    return ''.join(random.choices(string.ascii_lowercase, k=length))
                unique_suffix = random_string(6)
                user_data_dir = f"{USER_DATA_DIR}_{unique_suffix}"
                log_text_message(f"🆕 Membuat profil baru: {user_data_dir}")
            
            # Clean up any conflicts with the selected directory
            try:
                if not use_existing_profile and os.path.exists(user_data_dir):
                    shutil.rmtree(user_data_dir, ignore_errors=True)
                    time.sleep(1)
            except:
                pass
            
            options.add_argument(f"--user-data-dir={user_data_dir}")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-gpu")
            options.add_argument("--ignore-certificate-errors")
            options.add_argument("--start-maximized")
            
            # Try to avoid port conflicts
            if retry > 0:
                # Use different port strategy on retry
                import random
                debug_port = random.randint(9222, 9999)
                options.add_argument(f"--remote-debugging-port={debug_port}")
                log_text_message(f"🔄 Retry {retry}: Menggunakan debug port {debug_port}")
            else:
                options.add_argument("--remote-debugging-port=0")  # Use random port
            
            options.add_argument("--disable-software-rasterizer")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-web-security")
            options.add_argument("--allow-running-insecure-content")
            options.add_argument("--disable-features=VizDisplayCompositor")
            options.add_argument("--disable-extensions-file-access-check")
            options.add_argument("--disable-extensions-http-throttling")
            
            # Additional stability options
            options.add_argument("--disable-background-timer-throttling")
            options.add_argument("--disable-renderer-backgrounding")
            options.add_argument("--disable-backgrounding-occluded-windows")
            
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # Load Buster extension
            if os.path.exists(BUSTER_EXTENSION_PATH):
                options.add_argument(f"--load-extension={BUSTER_EXTENSION_PATH}")
                log_text_message("✅ Buster Captcha Solver extension loaded")
            else:
                log_text_message("⚠️ Buster extension not found, captcha will need manual solving")
            
            # Load other extensions if exists
            extension_path = os.path.join(os.getcwd(), "0.4.2_0")
            if os.path.exists(extension_path):
                options.add_argument(f"--load-extension={extension_path}")
            
            # Create driver with timeout
            log_text_message(f"🚀 Memulai Chrome driver (percobaan {retry + 1}/{max_retries})...")
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=options
            )
            
            log_text_message("✅ Chrome driver berhasil dibuat")
            return driver, user_data_dir
            
        except Exception as e:
            log_text_message(f"❌ Error membuat Chrome driver (percobaan {retry + 1}): {e}")
            
            if "DevToolsActivePort" in str(e) or "session not created" in str(e):
                if retry < max_retries - 1:
                    log_text_message("🔄 DevToolsActivePort error detected, mencoba dengan profil baru...")
                    use_existing_profile = False  # Force new profile on retry
                    time.sleep(2)
                    continue
            
            if retry == max_retries - 1:
                raise Exception(f"Gagal membuat Chrome driver setelah {max_retries} percobaan: {e}")
    
    return None, None


def start_lab():
    """Main function to start lab and process"""
    global driver, restart_now
    
    try:
        log_text_message("🔁 Memulai proses lab...")
        
        # Try to create driver using existing profile first
        driver, user_data_dir = create_chrome_driver(use_existing_profile=True)
        
        # PENTING: Hapus semua masks Firefox Relay yang ada
        log_text_message("🧹 Membersihkan masks Firefox Relay yang ada...")
        relay_manager = RelayManager()
        relay_manager.delete_all_masks()
        
        # Check Firefox Relay login status
        log_text_message("🔍 Memeriksa status login Firefox Relay...")
        firefox_relay_logged_in = check_firefox_relay_login(driver)
        
        if not firefox_relay_logged_in:
            log_text_message("Firefox Relay belum login, silakan login manual terlebih dahulu.")
            log_text_message("Buka browser dan login ke Firefox Relay, lalu tekan Enter untuk melanjutkan...")
            input("Tekan Enter setelah login ke Firefox Relay...")
            
            # Verify login after manual intervention
            firefox_relay_logged_in = check_firefox_relay_login(driver)
            if not firefox_relay_logged_in:
                raise Exception("Firefox Relay login tidak berhasil, proses dihentikan.")
        
        log_text_message("✅ Firefox Relay sudah login, melanjutkan...")
        
        # Hapus masks yang mungkin muncul setelah page load (double check)
        try:
            delete_buttons = driver.find_elements(By.CSS_SELECTOR, 
                "button.AliasDeletionButtonPermanent_deletion-button__Cg_sD")
            for btn in delete_buttons:
                try:
                    btn.click()
                    time.sleep(1)
                    confirm_btn = driver.find_element(By.CSS_SELECTOR,
                        "button.AliasDeletionButtonPermanent_delete-btn__PUrm5")
                    confirm_btn.click()
                    time.sleep(2)
                    log_text_message("✅ Mask lama dihapus via browser")
                except:
                    pass
        except:
            pass
                
        # Generate new email
        generate_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Generate new mask')]"))
        )
        generate_btn.click()
        time.sleep(3)
        
        new_email_element = driver.find_element(By.CSS_SELECTOR, "button.MaskCard_copy-button__a7PXh samp")
        new_email = new_email_element.text
        log_text_message(f"📧 Email baru: {new_email}")
        
        # Open signup page
        if not open_signup_page():
            log_text_message("Tidak bisa membuka halaman sign up")
            return
            
        # Fill signup form
        first_name = random_string()
        last_name = random_string()
        company = random_string()
        password = "jalankaki"
        
        driver.find_element(By.ID, "user_first_name").send_keys(first_name)
        driver.find_element(By.ID, "user_last_name").send_keys(last_name)
        driver.find_element(By.ID, "user_email").send_keys(new_email)
        driver.find_element(By.ID, "user_company_name").send_keys(company)
        driver.find_element(By.ID, "user_password").send_keys(password)
        driver.find_element(By.ID, "user_password_confirmation").send_keys(password)
        
        # Set birthdate
        Select(driver.find_element(By.ID, "dob_month")).select_by_visible_text("January")
        driver.find_element(By.ID, "dob_day").send_keys("1")
        driver.find_element(By.ID, "dob_year").send_keys("1990")
        
        # Solve captcha and create account (now with auto-solve!)
        solve_captcha_then_click_create(captcha_timeout=300, click_timeout=60)
        
        log_text_message(f"✅ Akun dibuat dengan: {new_email}")
        time.sleep(5)
        
        # Confirm email
        driver.get("https://mail.google.com/mail/u/0/#inbox")
        time.sleep(10)
        
        email_row = WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "tr.zA"))
        )
        email_row.click()
        time.sleep(3)
        
        confirm_link_element = driver.find_element(By.XPATH, "//a[contains(text(),'Confirm email address')]")
        confirm_link = confirm_link_element.get_attribute("href")
        log_text_message(f"Confirm link: {confirm_link}")
        
        driver.execute_script("window.open(arguments[0]);", confirm_link)
        driver.switch_to.window(driver.window_handles[-1])
        time.sleep(5)
        
        # Login after confirmation
        try:
            password_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "user_password"))
            )
            password_field.send_keys(password)
            
            sign_in_btn = driver.find_element(By.XPATH, "//ql-button[@type='submit']")
            sign_in_btn.click()
            log_text_message("✅ Berhasil login setelah konfirmasi email")
        except:
            log_text_message(f"Tidak menemukan form login, kemungkinan sudah otomatis login: {driver.current_url}")
            
        # Navigate to lab
        driver.get(LAB_URL)
        time.sleep(5)
        log_text_message("🚀 Halaman lab dimuat, melanjutkan ke langkah berikutnya...")
        
        # Save cookies after successful login
        save_cookies()
        
        # Check if there's captcha before starting lab
        log_text_message("🔍 Checking for captcha before starting lab...")
        detect_and_solve_captcha()
        
        # Start lab
        if click_with_selenium():
            log_text_message("🚀 Lab berhasil dimulai! Proses selesai.")
            
            # Extract lab credentials
            username, password_lab, project_id = get_lab_credentials()
            
            # Wait for Open Google Console button
            try:
                wait_until_open_console(timeout=120)
                open_console_url = get_open_console_url()
                
                if open_console_url:
                    log_text_message(f"🔗 SSO URL: {open_console_url}")
                    
                    # Copy SSO URL to clipboard
                    try:
                        pyperclip.copy(open_console_url)
                        log_text_message("📋 SSO URL sudah dicopy ke clipboard!")
                    except:
                        pass
                    
                    driver_incognito = open_in_incognito(open_console_url)
                    log_text_message("🚀 Google Cloud Console dibuka di incognito!")
                    
                    # Handle Google login if needed
                    if "accounts.google.com" in driver_incognito.current_url and username and password_lab:
                        handle_google_login(driver_incognito, username, password_lab)
                else:
                    log_text_message("Gagal menemukan tombol 'Open Google Console' dalam batas waktu.")
                    restart_now = True
                    return
                    
            except TimeoutException:
                log_text_message("Gagal menemukan tombol 'Open Google Console' dalam batas waktu.")
                restart_now = True
                return
                
        # Open Gemini API page in incognito
        log_text_message("Mencoba membuka halaman Gemini API di incognito.")
        driver_incognito.get("https://console.cloud.google.com/marketplace/product/google/generativelanguage.googleapis.com")
        time.sleep(5)
        
        # Check if we need to login to Google
        if "accounts.google.com" in driver_incognito.current_url:
            if username and password_lab:
                handle_google_login(driver_incognito, username, password_lab)
            else:
                log_text_message("Perlu login ke Google, silakan login manual...")
                log_text_message("Buka browser dan login ke Google Console, lalu tekan Enter untuk melanjutkan...")
                input("Tekan Enter setelah login ke Google Console...")
                driver_incognito.refresh()
                time.sleep(3)
        
        log_text_message("✅ Halaman berhasil diakses.")
        
        # Handle agreement/terms
        try:
            # Click "I understand" button if present
            confirm_button = WebDriverWait(driver_incognito, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'I understand')]"))
            )
            confirm_button.click()
        except:
            log_text_message("Tidak ada tombol 'I understand' (diabaikan).")
            
        try:
            # Accept terms
            terms_checkbox = driver_incognito.find_element(By.ID, "mat-mdc-checkbox-0-input")
            if not terms_checkbox.is_selected():
                terms_checkbox.click()
                
            agree_button = WebDriverWait(driver_incognito, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Agree and continue')]"))
            )
            agree_button.click()
        except:
            log_text_message("Tidak ada terms agreement (diabaikan)")
            
        # Navigate to Gemini API page
        gemini_api_url = "https://console.cloud.google.com/marketplace/product/google/generativelanguage.googleapis.com"
        driver_incognito.get(gemini_api_url)
        time.sleep(5)
        
        # Enable API
        try:
            enable_button = WebDriverWait(driver_incognito, 20).until(
                EC.element_to_be_clickable((By.XPATH, 
                    "//button[@aria-label='enable this API' and .//span[contains(text(), 'Enable')]]"))
            )
            enable_button.click()
            log_text_message("🔄 Enabling API... (mohon tunggu)")
            time.sleep(10)  # Wait for API to be enabled
        except:
            log_text_message("API mungkin sudah enabled atau tombol tidak ditemukan")
            
        # Process API key
        max_retries = 3
        api_key = None
        
        for attempt in range(max_retries):
            log_text_message(f"🔁 Percobaan {attempt + 1} cek API Key...")
            api_key = process_api_key(driver_incognito)
            if api_key:
                break
            time.sleep(5)
            
        if not api_key:
            log_text_message("Gagal membuat/mengambil API Key setelah 3 percobaan.")
            return
            
        # Save API key to local file instead of server upload
        try:
            # Save to api.txt file (append mode to keep previous keys)
            with open("api.txt", "a", encoding="utf-8") as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{timestamp}] API Key: {api_key}\n")
                f.write(f"[{timestamp}] Username: {username}\n")
                f.write(f"[{timestamp}] Password: {password_lab}\n")
                f.write(f"[{timestamp}] Project ID: {project_id}\n")
                f.write(f"[{timestamp}] SSO URL: {open_console_url}\n")
                f.write("-" * 80 + "\n")
            
            log_text_message("✅ API key berhasil disimpan ke api.txt")
                
        except Exception as e:
            log_text_message(f"❌ Gagal menyimpan ke api.txt: {e}")
            
        # Display results
        log_text_message(f"{'=' * 60}")
        log_text_message(f"📋 HASIL EKSTRAKSI:")
        log_text_message(f"{'=' * 60}")
        log_text_message(f"🔑 API KEY: {api_key}")
        log_text_message(f"👤 Username: {username}")
        log_text_message(f"🔐 Password: {password_lab}")
        log_text_message(f"📁 Project ID: {project_id}")
        log_text_message(f"🔗 SSO URL: {open_console_url}")
        log_text_message(f"{'=' * 60}")
        
        # Test API key
        test_result = test_api_key_veo(api_key)
        log_text_message(f"🧪 Test API Key: {test_result}")
        
    except Exception as e:
        log_text_message(f"Error dalam start_lab: {e}")
        restart_now = True
    finally:
        # Close drivers properly
        try:
            if 'driver_incognito' in locals() and driver_incognito:
                driver_incognito.quit()
        except:
            pass
            
        try:
            if driver:
                # End lab before closing
                end_lab()
                time.sleep(5)
                driver.quit()
                driver = None
        except:
            pass
        
        # Clean up user data directory if it was a temporary one
        try:
            if 'user_data_dir' in locals() and user_data_dir != USER_DATA_DIR and os.path.exists(user_data_dir):
                time.sleep(2)  # Wait a bit before cleanup
                shutil.rmtree(user_data_dir, ignore_errors=True)
                log_text_message(f"🧹 Cleaned up temporary profile: {user_data_dir}")
        except Exception as e:
            log_text_message(f"⚠️ Could not clean up temp profile: {e}")


def loop_start_lab():
    """Loop function to continuously run start_lab"""
    global running, restart_now, polling_delay_entry
    
    while running:
        restart_now = False
        
        try:
            start_lab()
            
            if not running:
                break
                
            if restart_now:
                log_text_message("Pengulangan dihentikan.")
                continue
                
            # Get delay value
            try:
                delay_value = int(polling_delay_entry.get())
            except:
                log_text_message("Nilai delay tidak valid.")
                delay_value = 30
                
            # Wait with interruptible sleep
            log_text_message(f"⏱️ Menunggu pengulangan berikutnya... ({delay_value} detik)")
            
            for i in range(delay_value):
                if not running or restart_now:
                    break
                time.sleep(1)
                
        except Exception as e:
            log_text_message(f"Error dalam loop: {e}")
            time.sleep(5)


def run_in_thread():
    """Run start_lab in a separate thread"""
    global running, loop_thread
    
    if running:
        log_text_message("Proses sudah berjalan.")
        return
        
    running = True
    loop_thread = threading.Thread(target=loop_start_lab)
    loop_thread.start()
    
    clear_log()
    log_text_message("Memulai proses lab...")


def stop_thread():
    """Stop the running thread"""
    global running, driver
    
    if not running:
        log_text_message("Tidak ada proses yang sedang berjalan.")
        return
        
    running = False
    log_text_message("Proses akan dihentikan setelah iterasi saat ini selesai.")
    
    # Force close driver if exists
    try:
        if driver:
            driver.quit()
            driver = None
    except:
        pass


def clear_log():
    """Clear the log text widget"""
    if log_text:
        log_text.configure(state="normal")
        log_text.delete("1.0", "end")
        log_text.configure(state="disabled")


def copy_hwid():
    """Copy HWID to clipboard"""
    hwid = get_hwid()
    pyperclip.copy(hwid)
    log_text_message(f"HWID copied: {hwid}")


def setup_gui():
    """Setup the GUI interface"""
    global gui_root, log_text, model_dropdown, polling_delay_entry
    
    customtkinter.set_appearance_mode("dark")
    customtkinter.set_default_color_theme("blue")
    
    gui_root = customtkinter.CTk()
    gui_root.title("SkillBoost API Key Tool")
    gui_root.geometry("700x800")
    
    # Main frame
    main_frame = customtkinter.CTkFrame(gui_root)
    main_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Title
    title_label = customtkinter.CTkLabel(
        main_frame, 
        text="🚀 SkillBoost API Key Automation",
        font=("Arial", 20, "bold")
    )
    title_label.pack(pady=10)
    
    # Model selection
    model_label = customtkinter.CTkLabel(main_frame, text="Model:", font=("Arial", 12))
    model_label.pack(anchor="w", padx=20, pady=(10, 0))
    
    model_dropdown = customtkinter.CTkOptionMenu(
        main_frame,
        values=["veo-3.0-generate-preview", "veo-3.0-fast-generate-preview", "veo-2.0-generate-001"],
        font=("Arial", 12)
    )
    model_dropdown.set("veo-3.0-generate-preview")
    model_dropdown.pack(padx=20, pady=(0, 10), fill="x")
    
    # Polling delay
    polling_label = customtkinter.CTkLabel(main_frame, text="Delay (detik):", font=("Arial", 12))
    polling_label.pack(anchor="w", padx=20, pady=(10, 0))
    
    polling_delay_var = tkinter.StringVar(value="30")
    polling_delay_entry = customtkinter.CTkEntry(
        main_frame, 
        font=("Arial", 12),
        textvariable=polling_delay_var
    )
    polling_delay_entry.pack(padx=20, pady=(0, 10), fill="x")
    
    # Buttons
    button_frame = customtkinter.CTkFrame(main_frame)
    button_frame.pack(pady=10)
    
    login_btn = customtkinter.CTkButton(
        button_frame,
        text="Login",
        font=("Arial", 12),
        command=open_chrome_with_profile
    )
    login_btn.pack(side="left", padx=5)
    
    start_btn = customtkinter.CTkButton(
        button_frame,
        text="Mulai Proses",
        font=("Arial", 12),
        command=run_in_thread
    )
    start_btn.pack(side="left", padx=5)
    
    stop_btn = customtkinter.CTkButton(
        button_frame,
        text="Stop Proses",
        font=("Arial", 12),
        command=stop_thread
    )
    stop_btn.pack(side="left", padx=5)
    
    # HWID display
    hwid_frame = customtkinter.CTkFrame(main_frame)
    hwid_frame.pack(pady=10, fill="x", padx=20)
    
    hwid_label = customtkinter.CTkLabel(
        hwid_frame,
        text=f"HWID: {get_hwid()}",
        font=("Arial", 10)
    )
    hwid_label.pack(side="left", padx=5)
    
    copy_hwid_btn = customtkinter.CTkButton(
        hwid_frame,
        text="Copy",
        font=("Arial", 10),
        width=60,
        command=lambda: copy_hwid()
    )
    copy_hwid_btn.pack(side="right", padx=5)
    
    # Log text area
    log_text = customtkinter.CTkTextbox(
        main_frame,
        height=400,
        font=("Arial", 10)
    )
    log_text.pack(fill="both", expand=True, padx=20, pady=(10, 20))
    log_text.configure(state="disabled")
    
    # On close
    gui_root.protocol("WM_DELETE_WINDOW", lambda: (stop_thread(), gui_root.destroy()))
    
    gui_root.mainloop()


# Main execution
if __name__ == "__main__":
    setup_gui()