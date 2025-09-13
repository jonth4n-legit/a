# SkillBoost API Key Automation Tool

This tool automates the process of creating Google Cloud Skills Boost accounts and extracting API keys using the Buster extension for automatic captcha solving.

## Features

- ✅ **Automatic reCAPTCHA solving** using Buster extension
- ✅ **Multiple solve methods** with fallback to manual solving
- ✅ **Session conflict resolution** with unique user profiles
- ✅ **Local API key storage** in `api.txt` file with timestamps
- ✅ **Enhanced error handling** and cleanup processes
- ✅ **Firefox Relay integration** for email generation

## Requirements

- Python 3.8+
- Chrome browser
- Buster Captcha Solver extension (included)

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Run the tool:
```bash
python main.py
```

## Usage

1. **Login Step**: Click "Login" to open Chrome with custom profile
2. **Manual Setup**: Login to Firefox Relay and Google Cloud Skills Boost manually
3. **Start Process**: Click "Mulai Proses" to begin automation
4. **Monitor**: Watch the logs for progress and any manual intervention needed

## Captcha Solving

The tool includes multiple methods for automatic captcha solving:

1. **Auto-click Buster extension icon** in challenge frames
2. **Shadow DOM detection** for hidden Buster buttons
3. **Extension API triggering** for direct activation
4. **Audio challenge fallback** when image challenges fail
5. **Manual solve support** with clear instructions

## Output

Results are saved to `api.txt` with timestamps:
```
[2024-01-01 12:00:00] API Key: AIza...
[2024-01-01 12:00:00] Username: student-001@qwiklabs.net
[2024-01-01 12:00:00] Password: SecurePass123
[2024-01-01 12:00:00] Project ID: qwiklabs-gcp-xxx
[2024-01-01 12:00:00] SSO URL: https://cloudskillsboost.google/...
```

## Troubleshooting

### Common Issues:
- **Session conflicts**: Tool now uses unique directories automatically
- **Captcha not solving**: Try manual solve when prompted
- **Extension not loading**: Check Extensions directory structure
- **Browser conflicts**: Tool cleans up temporary profiles automatically

### Manual Captcha Steps:
1. Click the reCAPTCHA checkbox
2. If challenge appears, click the Buster extension icon (🔧)
3. Wait for automatic solving or complete manually
4. Script continues automatically after verification

## File Structure

```
├── main.py                    # Main automation script
├── requirements.txt           # Python dependencies
├── Extensions/               # Buster extension files
│   └── mpbjkejclgfgadiemmefgebjfooflfhl/
├── api.txt                   # Output file (auto-generated)
└── .gitignore               # Git ignore rules
```

## Notes

- Tool creates unique browser profiles to avoid conflicts
- API keys are saved locally, no server upload
- Buster extension is included in the Extensions directory
- All temporary files are automatically cleaned up
- Firefox Relay integration requires manual login setup

## Safety

This tool is for educational purposes. Ensure compliance with Google's Terms of Service and use responsibly.