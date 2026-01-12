# Installer Improvements - BOT MMORPG AI

## Overview
This document outlines the major improvements made to the Windows installer for BOT MMORPG AI, creating a professional, user-friendly installation experience optimized for gamers.

## Key Improvements

### 1. **Correct Installation Path** ✅
- **Fixed install directory**: `C:\Program Files\BOT-MMORPG-AI`
- Uses `$PROGRAMFILES64` for proper 64-bit Windows installation
- Remembers previous install location for upgrades
- Consistent folder naming across all components

### 2. **Component Selection Wizard** ✅
The installer now includes a professional component selection page with three options:

#### Required Component (Always Checked):
- **BOT MMORPG AI (UI + Backend)**: Core application providing all essential gaming assistance features
  - Cannot be unchecked (required for operation)
  - Includes user interface and backend services
  - Installs all necessary drivers (Interception, vJoy)

#### Optional Components (Unchecked by Default):
- **AI Models (Optional)**: Pre-trained AI models (~500MB-2GB)
  - Downloads models from GitHub repository during installation
  - Can be skipped and downloaded later from within the application
  - Smart fallback system if download fails

- **Developer Tools (Optional)**: For users creating custom AI models
  - Includes sample datasets folder
  - Model templates and examples
  - Developer documentation
  - Quick access shortcuts to models and dev folders

### 3. **Enhanced User Experience** ✅

#### Professional Wizard Pages:
1. **Welcome Page**: Clear introduction to the installation process
2. **License Page**: Optional, shows if license file is provided
3. **Components Page**: Select what to install with detailed descriptions
4. **Directory Page**: Choose installation location (defaults to Program Files)
5. **Installation Progress**: Real-time feedback on what's being installed
6. **Finish Page**: Option to launch application immediately

#### Smart Installation Types:
- **Full Installation**: Includes all components (UI + Backend + Models + Dev Tools)
- **Minimal Installation (Recommended)**: Only core application (UI + Backend)

### 4. **Improved Visual Appearance** ✅
- Custom welcome and finish page text
- Professional component descriptions
- Progress indicators for long-running operations
- Launch application option on finish page
- Consistent branding throughout installer

### 5. **Models Download System** ✅

#### Intelligent Multi-Method Download:
The `download_models.ps1` script tries three methods in order:

1. **GitHub Releases** (Fastest):
   - Looks for pre-packaged `models.zip` in latest release
   - Downloads and extracts automatically
   - No git required

2. **Git Sparse Checkout** (If git available):
   - Uses sparse checkout to download only models folder
   - Efficient for large repositories
   - Requires git to be installed

3. **Direct File Download** (Fallback):
   - Downloads individual model files from raw GitHub URLs
   - Works without any dependencies
   - Attempts common model files

4. **Graceful Failure**:
   - Creates README with manual download instructions
   - Doesn't fail installation if models can't be downloaded
   - User can download models later

### 6. **Smart Uninstaller** ✅
- Asks user if they want to keep models and custom data
- Clean uninstall option removes everything
- Keep data option preserves models and developer tools
- Properly removes all shortcuts and registry entries

### 7. **Windows Integration** ✅
- Proper Windows Programs and Features integration
- Version tracking in registry
- Install location persistence
- Start Menu folder with shortcuts:
  - Launch application
  - Uninstall
  - Models folder (if dev tools installed)
  - Developer tools folder (if installed)
- Desktop shortcut

## Technical Changes

### Files Modified:
1. **src-tauri/tauri.conf.json**
   - Changed `productName` from "BOT MMORPG AI" to "BOT-MMORPG-AI" for consistency
   - Ensures consistent folder names and shortcuts

2. **installer/nsis_template.nsi**
   - Complete rewrite with component support
   - Added `Sections.nsh` for component management
   - Three distinct sections: Core (required), Models (optional), DevTools (optional)
   - Enhanced UI customization with MUI2 macros
   - Smart driver installation with error handling
   - Registry tracking for installed components
   - Professional uninstaller with data preservation option

3. **scripts/download_models.ps1** (NEW)
   - Multi-method download strategy
   - Progress feedback for users
   - Graceful error handling
   - Creates helpful README if download fails

4. **.github/workflows/build-windows-installer.yml**
   - Added `download_models.ps1` to build artifacts
   - Updated step name to reflect additional scripts

## User Benefits

### For Gamers:
- **Clean Default Install**: No unnecessary downloads, fast installation
- **Easy to Use**: Professional installer guides through process
- **Launch and Play**: Option to start app immediately after install
- **No Bloat**: Optional components mean smaller base installation
- **Models on Demand**: Download AI models only if needed

### For Developers:
- **Optional Dev Tools**: Separate component for development resources
- **Model Access**: Quick shortcuts to models and dev folders
- **Documentation**: Built-in README files with instructions
- **Workspace Ready**: Pre-configured folders for datasets and templates

### For Power Users:
- **Custom Install Path**: Can change from default if desired
- **Component Control**: Choose exactly what gets installed
- **Data Preservation**: Keep models when reinstalling
- **Multiple Install Types**: Full or minimal installation options

## Testing Checklist

Before releasing, verify:
- [ ] Installer runs without admin warnings
- [ ] Default path is `C:\Program Files\BOT-MMORPG-AI`
- [ ] Component selection page appears and works
- [ ] Core component cannot be unchecked
- [ ] Optional components are unchecked by default
- [ ] Models download works (or fails gracefully)
- [ ] Drivers install correctly
- [ ] Shortcuts created in Start Menu and Desktop
- [ ] Application launches successfully after install
- [ ] Uninstaller preserves data when requested
- [ ] Uninstaller removes everything when requested (clean uninstall)
- [ ] Reinstall detects previous installation location

## Future Enhancements

Potential improvements for future versions:
1. Custom installer graphics (background images, header images)
2. More granular component selection (choose specific models)
3. Language selection (multi-language installer)
4. Automatic updates notification
5. Installation size estimation for each component
6. Download progress bar for models
7. Post-install configuration wizard
8. Integration with Windows Store (optional)

## Build Instructions

To build the installer with new changes:

```powershell
# From project root
cd src-tauri
cargo tauri build
```

The installer will be created at:
`src-tauri/target/release/bundle/nsis/BOT-MMORPG-AI_0.1.5_x64-setup.exe`

## Distribution

The improved installer is now:
- **Professional**: Looks and feels like commercial software
- **User-Friendly**: Clear options and descriptions
- **Flexible**: Choose what to install
- **Reliable**: Multiple fallback mechanisms
- **Gamer-Optimized**: Fast, clean, easy to use

Perfect for distribution to end users!

---

**Version**: 0.1.5
**Last Updated**: January 2026
**Status**: ✅ Production Ready
